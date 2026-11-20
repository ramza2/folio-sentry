"""MD-03 explicit, transaction-owned and idempotent storage for PARTIAL KIS bars.

Not imported from API, background tasks, or KIS reader. Caller supplies an
already-open SQLAlchemy Session and explicitly opts in. This helper never
opens a connection, commits a transaction, fetches prices, or marks final.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market_data import DailyBarBatch
from app.portfolio_models import Instrument
from app.price_models import PriceBar
from app.price_quality import UnverifiedPriceBar, validate_batch


class PriceBarStorageError(ValueError):
    """Fail closed, never output source data or private holdings."""


@dataclass(frozen=True)
class PriceBarWriteResult:
    inserted: int
    unchanged: int


def _same_values(persisted: PriceBar, incoming: UnverifiedPriceBar) -> bool:
    return (
        persisted.open == incoming.open
        and persisted.high == incoming.high
        and persisted.low == incoming.low
        and persisted.close == incoming.close
        and persisted.volume == incoming.volume
        and persisted.quality_status == "PARTIAL"
        and persisted.is_final is False
        and persisted.source_observed_at is None
    )


def insert_unverified_daily_batch(
    session: Session, instrument_id: UUID, batch: DailyBarBatch, *,
    now: datetime, allow_write: bool = False,
) -> PriceBarWriteResult:
    """Only approved callers use an isolated transaction and set allow_write.

    Same source/session/basis/value repeats are NOOP (first fetched_at retained).
    Changed OHLCV for the same key is rejected, never silently overwritten.
    """
    if not allow_write:
        raise PriceBarStorageError("PRICE_BAR_WRITE_DISABLED")
    if not isinstance(session, Session) or not isinstance(instrument_id, UUID):
        raise PriceBarStorageError("PRICE_BAR_STORAGE_INPUT_INVALID")
    bars = validate_batch(batch, now=now)  # all-or-nothing validation before DML
    if not bars:
        return PriceBarWriteResult(inserted=0, unchanged=0)

    identity = batch.instrument
    instrument = session.get(Instrument, instrument_id)
    if instrument is None:
        raise PriceBarStorageError("PRICE_BAR_INSTRUMENT_NOT_FOUND")
    if (
        instrument.market != identity.market
        or instrument.exchange_mic != identity.exchange_mic
        or instrument.normalized_symbol != identity.symbol
        or instrument.currency != identity.currency
        or not instrument.active
    ):
        raise PriceBarStorageError("PRICE_BAR_INSTRUMENT_IDENTITY_MISMATCH")

    added = 0
    unchanged = 0
    # Enforce batch atomicity even if a caller catches a later conflict and
    # commits its OUTER transaction. SQLAlchemy savepoint rollback removes all
    # preceding inserts within this batch; other caller DML remains untouched.
    with session.begin_nested():
        for bar in bars:
            key = (
                PriceBar.instrument_id == instrument_id,
                PriceBar.timeframe == "1d",
                PriceBar.session_date == bar.session_date,
                PriceBar.price_basis == bar.price_basis,
                PriceBar.source == "KIS",
            )
            statement = insert(PriceBar).values(
                instrument_id=instrument_id,
                timeframe="1d", session_date=bar.session_date,
                price_basis=bar.price_basis,
                open=bar.open, high=bar.high, low=bar.low, close=bar.close,
                volume=bar.volume, source="KIS",
                source_observed_at=None, fetched_at=bar.fetched_at,
                is_final=False, quality_status="PARTIAL",
            ).on_conflict_do_nothing(
                constraint="uq_price_bar_identity_session_source",
            ).returning(PriceBar.id)
            new_id = session.execute(statement).scalar_one_or_none()
            if new_id is not None:
                added += 1
            else:
                existing = session.scalars(select(PriceBar).where(*key)).one_or_none()
                if existing is None or not _same_values(existing, bar):
                    raise PriceBarStorageError("PRICE_BAR_CONFLICT_NEEDS_REVIEW")
                unchanged += 1
    # The caller owns commit/rollback; no side effects outside its transaction.
    return PriceBarWriteResult(inserted=added, unchanged=unchanged)
