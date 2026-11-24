"""Offline-testable cross-process KIS quote/token gate. NEVER a scheduler.

Optional protection for the read-only KIS provider. Linux flock + protected
on-disk JSON keep shared state across process restarts. Tokens are stored as
plaintext inside owner-only 0700/0600 storage; protect home backups accordingly.

No implicit token issuance, retries, sleeps, API routes, or DB writes.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
import time
from typing import Callable, Mapping

from app.kis_readonly import (
    KR_DAILY_PATH, US_DAILY_PATH, KR_CURRENT_PATH, US_CURRENT_PATH,
    TOKEN_PATH, KisCredentials,
    KisReadOnlyError, Transport,
)

EXPECTED_TR = {
    KR_DAILY_PATH: "FHKST03010100",
    US_DAILY_PATH: "HHDFS76240000",
    KR_CURRENT_PATH: "FHKST01010100",
    US_CURRENT_PATH: "HHDFS00000300",
}
MAX_HTTP_REQUESTS_24H = 60
MIN_TOKEN_ISSUE_GAP = 24 * 3600
MIN_QUOTE_GAP = 1.25
MAX_STATE_BYTES = 16384
STATE_FILE = "kis-shared-state.json"
LOCK_FILE = "kis-shared-state.lock"
ISSUE_MARKER = "kis-ever-attempted-token.marker"


class KisSharedStateError(KisReadOnlyError):
    """Only fixed status codes; never raw upstream or stored state."""


def _valid_token(value: object) -> bool:
    return isinstance(value, str) and 10 <= len(value) <= 4096 and not any(
        character.isspace() for character in value
    )


def _number(value: object, *, optional: bool = False) -> bool:
    return (optional and value is None) or (
        type(value) in (int, float) and math.isfinite(value)
        and 0 <= value < 10**12
    )


class KisSharedState:
    """One owner/host/filesystem state. New token issue is default-DENIED.

    Cross-host, NFS and unrelated user accounts are NOT coordinated. Caller
    must explicitly choose live_enabled=True AND allow_new_token=True to
    authorize an issuance. No default state is initialized on deployment.
    """

    def __init__(self, directory: str | Path, *,
                 clock: Callable[[], float] = time.time):
        self._dir = Path(directory)
        if not self._dir.is_absolute():
            raise KisSharedStateError("KIS_SHARED_DIR_MUST_BE_ABSOLUTE")
        self._clock = clock

    def _secure_dir(self):
        try:
            info = self._dir.lstat()
        except OSError:
            raise KisSharedStateError("KIS_SHARED_DIR_UNAVAILABLE") from None
        if (not stat.S_ISDIR(info.st_mode)
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise KisSharedStateError("KIS_SHARED_DIR_UNSAFE")

    @contextmanager
    def _lock(self):
        self._secure_dir()
        try:
            fd = os.open(
                self._dir / LOCK_FILE,
                os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
                0o600,
            )
        except OSError:
            raise KisSharedStateError("KIS_SHARED_LOCK_UNAVAILABLE") from None
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() \
                    or stat.S_IMODE(info.st_mode) != 0o600:
                raise KisSharedStateError("KIS_SHARED_LOCK_UNSAFE")
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise KisSharedStateError("KIS_SHARED_LOCK_BUSY") from None
            yield
        finally:
            os.close(fd)

    def _mark_token_attempt_once(self):
        """Durable marker retained independently of replaceable token cache.

        If the state file disappears after a token attempt, the marker stops
        accidental 'first run' reissuance. Never automatically remove it.
        """
        path = self._dir / ISSUE_MARKER
        try:
            fd = os.open(
                path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
            )
        except FileExistsError:
            try:
                info = path.lstat()
            except OSError:
                raise KisSharedStateError("KIS_SHARED_ISSUE_MARKER_UNAVAILABLE") from None
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() \
                    or stat.S_IMODE(info.st_mode) != 0o600:
                raise KisSharedStateError("KIS_SHARED_ISSUE_MARKER_UNSAFE")
            return
        except OSError:
            raise KisSharedStateError("KIS_SHARED_ISSUE_MARKER_UNAVAILABLE") from None
        try:
            with os.fdopen(fd, "w", encoding="ascii") as stream:
                stream.write("TOKEN_ATTEMPT_RECORDED\\n")
                stream.flush()
                os.fsync(stream.fileno())
            dirfd = os.open(self._dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(dirfd)
            finally:
                os.close(dirfd)
        except Exception:
            raise KisSharedStateError("KIS_SHARED_ISSUE_MARKER_WRITE_FAILED") from None

    def _read(self, fingerprint: str) -> dict:
        path = self._dir / STATE_FILE
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            try:
                marker_info = (self._dir / ISSUE_MARKER).lstat()
            except FileNotFoundError:
                pass
            except OSError:
                raise KisSharedStateError("KIS_SHARED_ISSUE_MARKER_UNAVAILABLE") from None
            else:
                # An older issue attempt existed but state was lost/deleted;
                # never silently permit a fresh token with a blank timestamp.
                raise KisSharedStateError("KIS_SHARED_STATE_LOST_AFTER_ISSUE")
            return {
                "version": 1, "fingerprint": fingerprint, "token": None,
                "expires_at": None, "last_token_attempt": None,
                "last_quote_attempt": None, "last_clock": None,
                "requests": [],
            }
        except OSError:
            raise KisSharedStateError("KIS_SHARED_STATE_UNAVAILABLE") from None
        try:
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() \
                        or stat.S_IMODE(info.st_mode) != 0o600:
                    raise KisSharedStateError("KIS_SHARED_STATE_UNSAFE")
                if not 1 <= info.st_size <= MAX_STATE_BYTES:
                    raise KisSharedStateError("KIS_SHARED_STATE_INVALID")
                raw = stream.read(MAX_STATE_BYTES + 1)
            state = json.loads(raw)
        except KisSharedStateError:
            raise
        except (OSError, UnicodeError, ValueError, TypeError):
            raise KisSharedStateError("KIS_SHARED_STATE_INVALID") from None
        if not isinstance(state, dict) or set(state) != {
            "version", "fingerprint", "token", "expires_at",
            "last_token_attempt", "last_quote_attempt", "last_clock",
            "requests",
        } or type(state["version"]) is not int or state["version"] != 1:
            raise KisSharedStateError("KIS_SHARED_STATE_INVALID")
        if state["fingerprint"] != fingerprint:
            raise KisSharedStateError("KIS_SHARED_CREDENTIAL_MISMATCH")
        if (state["token"] is not None and not _valid_token(state["token"])) \
                or not all(_number(state[name], optional=True) for name in (
                    "expires_at", "last_token_attempt", "last_quote_attempt",
                    "last_clock",
                )):
            raise KisSharedStateError("KIS_SHARED_STATE_INVALID")
        if not isinstance(state["requests"], list) or len(state["requests"]) > MAX_HTTP_REQUESTS_24H \
                or not all(_number(value) for value in state["requests"]):
            raise KisSharedStateError("KIS_SHARED_STATE_INVALID")
        if (state["token"] is None) != (state["expires_at"] is None):
            raise KisSharedStateError("KIS_SHARED_STATE_INVALID")
        return state

    def _write(self, state: dict):
        temp = self._dir / (".kis-shared-" + secrets.token_hex(12))
        try:
            fd = os.open(temp, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as stream:
                    json.dump(state, stream, separators=(",", ":"), ensure_ascii=True)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, self._dir / STATE_FILE)
                dirfd = os.open(self._dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
                try:
                    os.fsync(dirfd)
                finally:
                    os.close(dirfd)
            except Exception:
                raise
        except Exception:
            raise KisSharedStateError("KIS_SHARED_STATE_WRITE_FAILED") from None
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def _now(self, state: dict) -> float:
        try:
            now = self._clock()
        except Exception:
            raise KisSharedStateError("KIS_SHARED_CLOCK_INVALID") from None
        if not _number(now) or now < 1600000000:
            raise KisSharedStateError("KIS_SHARED_CLOCK_INVALID")
        if state["last_clock"] is not None and now < state["last_clock"]:
            raise KisSharedStateError("KIS_SHARED_CLOCK_ROLLBACK")
        return float(now)

    def _reserve(self, state: dict, now: float):
        recent = [ts for ts in state["requests"] if ts > now - 86400]
        if len(recent) >= MAX_HTTP_REQUESTS_24H:
            raise KisSharedStateError("KIS_SHARED_DAILY_CAP")
        recent.append(now)
        state["requests"] = recent
        state["last_clock"] = now
        self._write(state)  # durable reservation BEFORE an outbound request

    def call_quote(
        self, credentials: KisCredentials, transport: Transport, *,
        path: str, tr_id: str, params: Mapping[str, str],
        live_enabled: bool = False, allow_new_token: bool = False,
    ) -> Mapping[str, object]:
        """At most token POST + quote GET; never automatic retry."""
        if not live_enabled:
            raise KisSharedStateError("KIS_LIVE_READ_DISABLED")
        if not isinstance(credentials, KisCredentials):
            raise KisSharedStateError("INVALID_KIS_CREDENTIALS")
        if path not in EXPECTED_TR or EXPECTED_TR[path] != tr_id \
                or not isinstance(params, Mapping) \
                or not all(isinstance(k, str) and isinstance(v, str)
                           for k, v in params.items()):
            raise KisSharedStateError("KIS_SHARED_QUOTE_NOT_ALLOWED")
        fingerprint = hashlib.sha256(credentials.appkey.encode("utf-8")).hexdigest()
        with self._lock():
            state = self._read(fingerprint)
            now = self._now(state)
            if state["last_quote_attempt"] is not None \
                    and now - state["last_quote_attempt"] < MIN_QUOTE_GAP:
                raise KisSharedStateError("KIS_SHARED_QUOTE_RATE_LIMIT")
            token = state["token"]
            if token is None or state["expires_at"] <= now + 60:
                if not allow_new_token:
                    raise KisSharedStateError("KIS_SHARED_TOKEN_MISSING_ISSUE_DENIED")
                if state["last_token_attempt"] is not None \
                        and now - state["last_token_attempt"] < MIN_TOKEN_ISSUE_GAP:
                    raise KisSharedStateError("KIS_SHARED_TOKEN_ISSUE_TOO_SOON")
                # An independent marker survives state-file loss. Place it
                # BEFORE quota reservation/transport and fail closed on I/O.
                self._mark_token_attempt_once()
                state["token"] = None
                state["expires_at"] = None
                state["last_token_attempt"] = now
                self._reserve(state, now)
                try:
                    result = transport(
                        "POST", TOKEN_PATH, {"content-type": "application/json"},
                        body={"grant_type": "client_credentials",
                              "appkey": credentials.appkey,
                              "appsecret": credentials.appsecret},
                    )
                    token, ttl = result.get("access_token"), result.get("expires_in")
                    if isinstance(ttl, str) and ttl.isdecimal():
                        ttl = int(ttl)
                    if not _valid_token(token) or type(ttl) is not int \
                            or not 120 <= ttl <= 86400:
                        raise KisSharedStateError("KIS_SHARED_TOKEN_REPLY_INVALID")
                except KisSharedStateError:
                    raise
                except Exception:
                    raise KisSharedStateError("KIS_SHARED_TOKEN_REQUEST_FAILED") from None
                state["token"] = token
                state["expires_at"] = now + ttl - 60
                self._write(state)
            now = self._now(state)
            # Debit quota and timestamp before GET, including failed attempts.
            state["last_quote_attempt"] = now
            self._reserve(state, now)
            try:
                result = transport(
                    "GET", path,
                    {"authorization": "Bearer " + token,
                     "appkey": credentials.appkey,
                     "appsecret": credentials.appsecret,
                     "content-type": "application/json",
                     "tr_id": tr_id},
                    params=params,
                )
            except Exception:
                raise KisSharedStateError("KIS_SHARED_QUOTE_REQUEST_FAILED") from None
            if not isinstance(result, Mapping):
                raise KisSharedStateError("KIS_SHARED_QUOTE_REPLY_INVALID")
            return result
