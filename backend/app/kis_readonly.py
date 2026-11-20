"""Opt-in, read-only KIS daily-price transport, not wired to API or scheduler.

No account information, balances, orders, order endpoints, DB connections,
background execution, or real quotes are exposed by this module. All network
activity requires live_enabled=True AND explicit owner-controlled credentials.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import json
import os
import stat
import time
from typing import Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.market_data import (
    DailyBarBatch, InstrumentIdentity, MarketDataContractError, PriceBasis,
    normalize_kis_daily_response,
)

KIS_BASE = "https://openapi.koreainvestment.com:9443"
TOKEN_PATH = "/oauth2/tokenP"
KR_DAILY_PATH = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
US_DAILY_PATH = "/uapi/overseas-price/v1/quotations/dailyprice"
ALLOWED_CALLS = frozenset({("POST", TOKEN_PATH), ("GET", KR_DAILY_PATH), ("GET", US_DAILY_PATH)})
MAX_RESPONSE_BYTES = 512 * 1024


class KisReadOnlyError(RuntimeError):
    """Non-sensitive error code only: no raw provider text or credentials."""


@dataclass(frozen=True, repr=False)
class KisCredentials:
    appkey: str = field(repr=False)
    appsecret: str = field(repr=False)

    def __post_init__(self):
        for value in (self.appkey, self.appsecret):
            if not isinstance(value, str) or not value or len(value) > 256 \
                    or value.strip() != value or any(ch.isspace() for ch in value):
                raise KisReadOnlyError("INVALID_KIS_CREDENTIALS")

    @classmethod
    def from_private_files(cls, appkey_path: str, appsecret_path: str):
        """Explicitly read 0600 same-owner regular files; reject symlinks."""
        def read_private(path: str):
            if not isinstance(path, str) or not path.startswith("/"):
                raise KisReadOnlyError("SECRET_PATH_MUST_BE_ABSOLUTE")
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                with os.fdopen(fd, "r", encoding="utf-8") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() \
                            or (info.st_mode & 0o077):
                        raise KisReadOnlyError("SECRET_FILE_PERMISSIONS")
                    value = stream.read(257)
            except (OSError, UnicodeError) as exc:
                raise KisReadOnlyError("SECRET_FILE_UNAVAILABLE") from None
            return value.strip("\r\n")
        return cls(read_private(appkey_path), read_private(appsecret_path))


class Transport(Protocol):
    def __call__(
        self, method: str, path: str, headers: Mapping[str, str],
        params: Mapping[str, str] | None = None,
        body: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]: ...


class SharedQuoteGate(Protocol):
    def call_quote(
        self, credentials: KisCredentials, transport: Transport, *,
        path: str, tr_id: str, params: Mapping[str, str],
        live_enabled: bool = False, allow_new_token: bool = False,
    ) -> Mapping[str, object]: ...


class _RejectRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise KisReadOnlyError("KIS_REDIRECT_REJECTED")


class KisHttpsTransport:
    """Fixed KIS production hostname, fixed allowlisted paths, HTTPS only."""

    def __init__(self, timeout: float = 6.0):
        if not 1.0 <= timeout <= 15.0:
            raise ValueError("INVALID_TIMEOUT")
        self._timeout = timeout
        self._opener = build_opener(_RejectRedirect)

    def __call__(self, method, path, headers, params=None, body=None):
        if (method, path) not in ALLOWED_CALLS:
            raise KisReadOnlyError("KIS_PATH_NOT_ALLOWED")
        if method == "GET" and body is not None:
            raise KisReadOnlyError("GET_BODY_NOT_ALLOWED")
        if method == "POST" and (params is not None or body is None):
            raise KisReadOnlyError("INVALID_TOKEN_REQUEST")
        if params is not None:
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in params.items()):
                raise KisReadOnlyError("INVALID_QUERY")
        if body is not None:
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in body.items()):
                raise KisReadOnlyError("INVALID_BODY")
        url = KIS_BASE + path + (("?" + urlencode(params)) if params else "")
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = Request(url, headers=dict(headers), data=data, method=method)
        try:
            with self._opener.open(req, timeout=self._timeout) as reply:
                if reply.status != 200:
                    raise KisReadOnlyError("KIS_HTTP_FAILURE")
                if not reply.headers.get("Content-Type", "").lower().startswith("application/json"):
                    raise KisReadOnlyError("KIS_NON_JSON_REPLY")
                raw = reply.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise KisReadOnlyError("KIS_REPLY_TOO_LARGE")
        except KisReadOnlyError:
            raise
        except (HTTPError, URLError, TimeoutError, OSError):
            # Deliberately no upstream body, URL, credentials or raw exception.
            raise KisReadOnlyError("KIS_NETWORK_UNAVAILABLE") from None
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeError):
            raise KisReadOnlyError("KIS_INVALID_JSON") from None
        if not isinstance(value, dict):
            raise KisReadOnlyError("KIS_INVALID_RESPONSE")
        return value


class KisReadOnlyDailyProvider:
    """Strict owner-invoked reader; not an automatic task or broker connector."""

    def __init__(
        self, credentials: KisCredentials, *,
        live_enabled: bool = False,
        transport: Transport | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        utcnow: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        shared_state: SharedQuoteGate | None = None,
        allow_shared_token_issue: bool = False,
    ):
        if not isinstance(credentials, KisCredentials):
            raise KisReadOnlyError("INVALID_KIS_CREDENTIALS")
        if allow_shared_token_issue and shared_state is None:
            raise KisReadOnlyError("KIS_SHARED_STATE_REQUIRED")
        self._shared_state = shared_state
        self._allow_shared_token_issue = allow_shared_token_issue
        self._credentials = credentials
        self._enabled = live_enabled
        self._transport = transport if transport is not None else KisHttpsTransport()
        self._clock = monotonic
        self._utcnow = utcnow
        self._access_token: str | None = None
        self._token_valid_until = float("-inf")
        self._last_token_issued = float("-inf")
        self._last_request = float("-inf")
        self._requests_made = 0

    def _guard_request(self, *, token: bool):
        if not self._enabled:
            raise KisReadOnlyError("KIS_LIVE_READ_DISABLED")
        now = self._clock()
        # Conservative per-instance limit; not a cross-process scheduler.
        if self._requests_made >= 60:
            raise KisReadOnlyError("KIS_PROCESS_REQUEST_CAP")
        # The OAuth token and first quote can be sent in succession;
        # enforce the quote-to-quote interval, not token-to-quote delay.
        if not token and now - self._last_request < 1.0:
            raise KisReadOnlyError("KIS_RATE_LIMIT")
        if token and now - self._last_token_issued < 6 * 3600:
            raise KisReadOnlyError("KIS_TOKEN_REFRESH_TOO_SOON")
        self._requests_made += 1
        if token:
            self._last_token_issued = now
        else:
            self._last_request = now

    def _authorize(self) -> str:
        if self._access_token and self._clock() < self._token_valid_until:
            return self._access_token
        self._guard_request(token=True)
        result = self._transport(
            "POST", TOKEN_PATH, {"content-type": "application/json"},
            body={"grant_type": "client_credentials",
                  "appkey": self._credentials.appkey, "appsecret": self._credentials.appsecret},
        )
        token, ttl = result.get("access_token"), result.get("expires_in")
        if isinstance(ttl, str) and ttl.isdecimal():
            ttl = int(ttl)
        if not isinstance(token, str) or not 10 <= len(token) <= 4096 \
                or any(ch.isspace() for ch in token) \
                or type(ttl) is not int or not 120 <= ttl <= 86400:
            raise KisReadOnlyError("KIS_TOKEN_RESPONSE_INVALID")
        self._access_token = token
        self._token_valid_until = self._clock() + ttl - 60
        return token

    def fetch_daily(
        self, identity: InstrumentIdentity, start: date, end: date,
        price_basis: PriceBasis,
    ) -> DailyBarBatch:
        if not isinstance(identity, InstrumentIdentity):
            raise MarketDataContractError("INVALID_INSTRUMENT")
        if price_basis not in ("RAW", "ADJUSTED"):
            raise MarketDataContractError("INVALID_PRICE_BASIS")
        now = self._utcnow()
        if now.tzinfo is None or now.utcoffset() is None:
            raise MarketDataContractError("INVALID_NOW")
        local_today = now.astimezone(identity.exchange_timezone).date()
        if not isinstance(start, date) or not isinstance(end, date) or \
                isinstance(start, datetime) or isinstance(end, datetime) or \
                start > end or end > local_today or (end - start).days > 99:
            raise MarketDataContractError("INVALID_DAILY_DATE_WINDOW")
        if not self._enabled:
            raise KisReadOnlyError("KIS_LIVE_READ_DISABLED")

        # Shared-state mode never falls through to the in-memory token logic.
        # It persists the issuance/quote attempt BEFORE each outbound call.
        headers = {"content-type": "application/json"}
        if identity.market == "KR":
            path = KR_DAILY_PATH
            headers["tr_id"] = "FHKST03010100"
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": identity.symbol,
                "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",
                "FID_ORG_ADJ_PRC": "1" if price_basis == "RAW" else "0",
            }
        else:
            path = US_DAILY_PATH
            headers["tr_id"] = "HHDFS76240000"
            params = {
                "AUTH": "", "EXCD": identity.kis_exchange_code,
                "SYMB": identity.symbol, "GUBN": "0",
                "BYMD": end.strftime("%Y%m%d"),
                "MODP": "0" if price_basis == "RAW" else "1",
            }
        if self._shared_state is not None:
            response = self._shared_state.call_quote(
                self._credentials, self._transport, path=path,
                tr_id=headers["tr_id"], params=params,
                live_enabled=self._enabled,
                allow_new_token=self._allow_shared_token_issue,
            )
        else:
            token = self._authorize()
            # Original single-process opt-in mode; NEVER attach a scheduler.
            self._guard_request(token=False)
            headers.update({
                "authorization": "Bearer " + token,
                "appkey": self._credentials.appkey,
                "appsecret": self._credentials.appsecret,
            })
            response = self._transport("GET", path, headers, params=params)
        batch = normalize_kis_daily_response(
            response, identity=identity, price_basis=price_basis, fetched_at=self._utcnow(),
        )
        # US BYMD returns rows older than requested start; do not claim
        # coverage and never persist anything without a separate gate.
        selected = tuple(bar for bar in batch.bars if start <= bar.session_date <= end)
        return DailyBarBatch(instrument=identity, bars=selected)
