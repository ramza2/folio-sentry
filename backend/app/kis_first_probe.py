"""Explicit one-shot KIS KR/US daily quote smoke check, never used by the API.

Default 'check' only inspects local secret-file metadata. 'live' requires a
literal owner confirmation and creates a persistent once-only marker BEFORE
any token or quote request. It never prints prices, tokens, keys or raw errors.
"""
import argparse
from datetime import date, datetime, timezone
import os
from pathlib import Path
import re
import stat
import sys
import time

from app.kis_readonly import KisCredentials, KisReadOnlyDailyProvider, KisReadOnlyError
from app.market_data import InstrumentIdentity, MarketDataContractError

CONFIRM = "APPROVE_KIS_ONE_TIME_READONLY_QUOTES"
MARKER = "kis-first-readonly-probe.attempted"
KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")


class ProbeError(RuntimeError):
    """Static non-sensitive status code."""


def _inspect_secret_file(path: str) -> None:
    if not path or not os.path.isabs(path):
        raise ProbeError("SECRET_PATH_MUST_BE_ABSOLUTE")
    try:
        info = os.lstat(path)
    except OSError:
        raise ProbeError("SECRET_FILE_NOT_READY") from None
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() \
            or info.st_mode & 0o077 or not 1 <= info.st_size <= 257:
        raise ProbeError("SECRET_FILE_NOT_PRIVATE")


def _day(value: str, identity: InstrumentIdentity) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ProbeError("INVALID_PROBE_DATE")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ProbeError("INVALID_PROBE_DATE") from None
    local_today = datetime.now(timezone.utc).astimezone(identity.exchange_timezone).date()
    if parsed > local_today:
        raise ProbeError("FUTURE_PROBE_DATE")
    return parsed


def _reserve_once() -> None:
    """Reserve an irreversible one-shot attempt; never silently retry a token."""
    directory = Path.home() / ".local" / "state" / "folio-sentry"
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() \
                or (info.st_mode & 0o077):
            raise ProbeError("PROBE_STATE_DIRECTORY_UNSAFE")
        fd = os.open(
            directory / MARKER, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
    except FileExistsError:
        raise ProbeError("PROBE_ALREADY_ATTEMPTED") from None
    except OSError:
        raise ProbeError("PROBE_STATE_UNAVAILABLE") from None
    with os.fdopen(fd, "w", encoding="ascii") as stream:
        stream.write(datetime.now(timezone.utc).isoformat() + "\n")


def _live(appkey_file: str, appsecret_file: str, kr_day: date, us_day: date) -> int:
    # Credential contents are read only after the explicit live confirmation.
    creds = KisCredentials.from_private_files(appkey_file, appsecret_file)
    _reserve_once()
    reader = KisReadOnlyDailyProvider(creds, live_enabled=True)
    results = []
    for index, (identity, session_day) in enumerate(((KR, kr_day), (US, us_day))):
        if index:
            time.sleep(1.1)  # one quote per second, no retries
        batch = reader.fetch_daily(identity, session_day, session_day, "RAW")
        if any(bar.is_final or bar.source_observed_at is not None for bar in batch.bars):
            raise ProbeError("UNVERIFIED_FINALITY")
        results.append((identity.market, len(batch.bars)))
    for market, count in results:
        print(f"KIS_{market}_UNFINALIZED_BAR_COUNT={count}")
    if any(count == 0 for _, count in results):
        print("KIS_FIRST_CALL_STATUS=DATA_UNAVAILABLE_NOT_VERIFIED")
        return 3
    print("KIS_FIRST_CALL_STATUS=READONLY_QUOTE_SHAPE_PASS_NOT_PRODUCTION_APPROVAL")
    return 0


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="KIS private-file metadata preflight or gated one-shot KR/US read-only quotes"
    )
    parser.add_argument("action", choices=("check", "live"))
    parser.add_argument("--appkey-file", required=True)
    parser.add_argument("--appsecret-file", required=True)
    parser.add_argument("--kr-date")
    parser.add_argument("--us-date")
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    try:
        if os.path.abspath(args.appkey_file) == os.path.abspath(args.appsecret_file):
            raise ProbeError("SECRET_FILES_MUST_BE_DISTINCT")
        if args.action == "live" and args.confirm != CONFIRM:
            raise ProbeError("LIVE_CONFIRMATION_REQUIRED")
        _inspect_secret_file(args.appkey_file)
        _inspect_secret_file(args.appsecret_file)
        if args.action == "check":
            print("KIS_PRIVATE_FILES_METADATA_PASS_NO_SECRETS_READ_NO_NETWORK")
            return 0
        kr_day = _day(args.kr_date, KR)
        us_day = _day(args.us_date, US)
        return _live(args.appkey_file, args.appsecret_file, kr_day, us_day)
    except (ProbeError, KisReadOnlyError, MarketDataContractError) as exc:
        print(f"KIS_FIRST_CALL_STATUS={exc}", file=sys.stderr)
        return 2
    except Exception:
        # Never include exception details: upstream errors may carry credentials.
        print("KIS_FIRST_CALL_STATUS=UNEXPECTED_FAILURE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
