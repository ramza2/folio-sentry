"""MD06 reference-only daily collector. One-shot CLI; no API/startup hook.

Requires explicit operator enablement, migrated PostgreSQL, and the SAME
private KIS state mount as manual MD05. No automatic retry, orders or signals.
"""
import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import fcntl
import os
from pathlib import Path
import stat
import time
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.database import get_engine
from app.kis_readonly import KisCredentials, KisReadOnlyDailyProvider
from app.kis_shared_state import KisSharedState
from app.market_data import DailyBarBatch, InstrumentIdentity
from app.portfolio_models import Instrument, TrackedInstrument
from app.price_models import PriceBar
from app.price_repository import insert_reference_daily_batch
from app.price_quality import validate_reference_batch

MAX_TARGETS = 15
AUTO_REQUEST_CAP = 40
LOOKBACK_DAYS = 89  # 90 calendar days inclusive; not guaranteed provider coverage
ZONES = {"KR": "Asia/Seoul", "US": "America/New_York"}
SCHEMA_REVISIONS = {"20261120_pricebar01", "20261123_quality01", "20261123_quality02"}


class CollectionError(RuntimeError):
    """Static failure code."""


@dataclass(frozen=True)
class Target:
    instrument_id: UUID
    identity: InstrumentIdentity


def collection_window(market: str, now: datetime):
    """Tue-Sat local 06:00-12:00: retrieve only PRIOR local session dates.

    Weekday window is a scheduling heuristic, NOT exchange-calendar evidence.
    Monday/Sunday skipped; holidays can return older or empty reference bars.
    """
    if market not in ZONES or not isinstance(now, datetime) or now.utcoffset() is None:
        raise CollectionError("MD06_INVALID_CLOCK_OR_MARKET")
    local = now.astimezone(ZoneInfo(ZONES[market]))
    if local.weekday() not in (1, 2, 3, 4, 5) or not 6 <= local.hour < 12:
        return None
    end = local.date() - timedelta(days=1)
    return local.date(), end - timedelta(days=LOOKBACK_DAYS), end


def _private(info, kind, mode):
    return kind(info.st_mode) and info.st_uid == os.geteuid() and stat.S_IMODE(info.st_mode) == mode


@contextmanager
def reserve_run(directory: Path, market: str, day):
    """Serialize collectors and persist one attempt per market/local date.

    Marker precedes network I/O, survives process failure; never removed or
    retried automatically. Different markets share a collector lock; KIS
    gate independently coordinates every HTTP request with manual MD05.
    """
    if not directory.is_absolute() or not _private(directory.lstat(), stat.S_ISDIR, 0o700):
        raise CollectionError("MD06_STATE_DIRECTORY_UNSAFE")
    if market not in ZONES:
        raise CollectionError("MD06_INVALID_MARKET")
    lock = os.open(directory / "md06-collector.lock",
                   os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        if not _private(os.fstat(lock), stat.S_ISREG, 0o600):
            raise CollectionError("MD06_LOCK_UNSAFE")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        marker = directory / f"md06-{market}-{day.isoformat()}.attempted"
        try:
            fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            if not _private(marker.lstat(), stat.S_ISREG, 0o600):
                raise CollectionError("MD06_MARKER_UNSAFE")
            yield False
            return
        with os.fdopen(fd, "wb") as stream:
            stream.write(b"ATTEMPT_RESERVED\n")
            stream.flush()
            os.fsync(stream.fileno())
        dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(dirfd)
        finally:
            os.close(dirfd)
        yield True
    finally:
        os.close(lock)


def load_targets(engine, market: str) -> tuple[Target, ...]:
    with Session(engine) as db:
        # Fail before credentials/network if the production schema is not ready.
        revisions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if len(revisions) != 1 or revisions[0] not in SCHEMA_REVISIONS:
            raise CollectionError("MD06_STORAGE_SCHEMA_NOT_READY")
        db.execute(select(PriceBar.id).limit(0))
        rows = db.scalars(select(Instrument)
            .join(TrackedInstrument, TrackedInstrument.instrument_id == Instrument.id)
            .where(Instrument.active.is_(True), Instrument.market == market)
            .order_by(Instrument.id).limit(MAX_TARGETS + 1)).all()
        if len(rows) > MAX_TARGETS:
            raise CollectionError("MD06_MARKET_TARGET_LIMIT")
        return tuple(Target(row.id, InstrumentIdentity(
            row.market, row.exchange_mic, row.normalized_symbol, row.currency,
        )) for row in rows)


def store_batch(engine, target: Target, batch: DailyBarBatch, now: datetime):
    # Network is finished before opening this short write transaction.
    with Session(engine) as db, db.begin():
        tracked = db.scalars(select(TrackedInstrument)
            .where(TrackedInstrument.instrument_id == target.instrument_id)
            .with_for_update()).one_or_none()
        if tracked is None:
            raise CollectionError("MD06_TARGET_REMOVED")
        row = db.scalars(select(Instrument).where(Instrument.id == target.instrument_id)
                         .with_for_update()).one_or_none()
        if row is None or not row.active:
            raise CollectionError("MD06_TARGET_INACTIVE")
        return insert_reference_daily_batch(db, target.instrument_id, batch,
                                            now=now, allow_write=True)


def run_collection(market, *, clock, list_targets, provider_factory, store,
                   state_dir, sleep=time.sleep):
    """Dependency-injected bounded runner. Failure stops remaining requests."""
    window = collection_window(market, clock())
    if window is None:
        return "OUTSIDE_WINDOW", 0, 0, 0, 0
    day, start, end = window
    targets = tuple(list_targets(market))
    if len(targets) > MAX_TARGETS or len({t.instrument_id for t in targets}) != len(targets):
        raise CollectionError("MD06_TARGET_LIMIT_OR_DUPLICATE")
    if any(t.identity.market != market for t in targets):
        raise CollectionError("MD06_TARGET_MARKET_MISMATCH")
    if not targets:
        return "NO_TARGETS", 0, 0, 0, 0
    with reserve_run(state_dir, market, day) as reserved:
        if not reserved:
            return "ALREADY_ATTEMPTED_OR_BUSY", 0, 0, 0, 0
        attempts = inserted = unchanged = empty = 0
        try:
            provider = provider_factory()
            for target in targets:
                if attempts:
                    sleep(2.0)
                if collection_window(market, clock()) != window:
                    raise CollectionError("MD06_WINDOW_CHANGED")
                attempts += 1
                batch = provider.fetch_daily(target.identity, start, end, "RAW")
                if not isinstance(batch, DailyBarBatch) or batch.instrument != target.identity:
                    raise CollectionError("MD06_BATCH_IDENTITY_MISMATCH")
                if any(not start <= bar.session_date <= end for bar in batch.bars):
                    raise CollectionError("MD06_BATCH_DATE_OUT_OF_WINDOW")
                now = clock()
                validate_reference_batch(batch, now=now)
                if not batch.bars:
                    empty += 1
                    continue
                result = store(target, batch, now)
                inserted += result.inserted
                unchanged += result.unchanged
        except Exception:
            # No exception payload, instrument, provider body or credentials.
            return "STOPPED_ON_ERROR", attempts, inserted, unchanged, empty
        return "COMPLETE", attempts, inserted, unchanged, empty


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", required=True, choices=tuple(ZONES))
    parser.add_argument("--confirm-reference-collection", action="store_true")
    args = parser.parse_args(argv)
    if not args.confirm_reference_collection or any(os.getenv(flag) != "yes" for flag in (
        "FOLIOSENTRY_MD06_AUTO_COLLECT_ENABLED", "FOLIOSENTRY_MD06_STORAGE_ENABLED",
    )):
        print("MD06_COLLECTION_DISABLED")
        return 2
    clock = lambda: datetime.now(timezone.utc)
    try:
        if collection_window(args.market, clock()) is None:
            print("MD06_STATUS=OUTSIDE_WINDOW")
            return 0
        engine = get_engine()
        state_dir = Path(os.getenv("FOLIOSENTRY_KIS_SHARED_STATE_DIR", ""))
        def provider_factory():
            creds = KisCredentials.from_private_files(
                os.getenv("FOLIOSENTRY_KIS_APPKEY_FILE", ""),
                os.getenv("FOLIOSENTRY_KIS_APPSECRET_FILE", ""),
            )
            return KisReadOnlyDailyProvider(
                creds, live_enabled=True,
                shared_state=KisSharedState(state_dir, request_cap=AUTO_REQUEST_CAP),
                allow_shared_token_issue=os.getenv("FOLIOSENTRY_MD06_NEW_TOKEN_ISSUE_ALLOWED") == "yes",
            )
        status, attempts, inserted, unchanged, empty = run_collection(
            args.market, clock=clock, list_targets=lambda market: load_targets(engine, market),
            provider_factory=provider_factory, store=lambda t,b,n: store_batch(engine,t,b,n),
            state_dir=state_dir,
        )
        print(f"MD06_STATUS={status} ATTEMPTS={attempts} INSERTED={inserted} UNCHANGED={unchanged} EMPTY={empty}")
        return 1 if status == "STOPPED_ON_ERROR" else 0
    except Exception:
        print("MD06_PREFLIGHT_OR_STATE_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
