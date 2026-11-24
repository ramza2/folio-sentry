"""Strict quality gate for KIS daily candidates; no DB, network or calendar API.

Regular close + 2h is only a *minimum observation delay*, NOT finality proof.
Only a small set of explicitly attested sessions can pass the offline gate;
all other days are denied. Provider finality still cannot be inferred.
Consequently every accepted bar remains
PARTIAL, source_observed_at=None and is_final=False.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from app.exchange_calendar import attested_session, ExchangeCalendarError

from app.market_data import (
    DailyBarBatch, DailyBarCandidate, InstrumentIdentity, MarketDataContractError,
)

SOURCE = "KIS"
MAX_FETCH_AGE = timedelta(hours=24)
MAX_CLOCK_SKEW = timedelta(seconds=5)
CLOSE_BUFFER = timedelta(hours=2)
DECIMAL_LIMIT = Decimal("10000000000000000")  # NUMERIC(24,8) maximum boundary
VOLUME_LIMIT = 10**28


class PriceBarQualityError(ValueError):
    """Static error code only; no provider bodies or personal positions."""


@dataclass(frozen=True)
class UnverifiedPriceBar:
    session_date: date
    price_basis: Literal["RAW", "ADJUSTED"]
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    fetched_at: datetime
    source: Literal["KIS"] = "KIS"
    source_observed_at: None = None
    is_final: Literal[False] = False
    quality_status: Literal["PARTIAL"] = "PARTIAL"
    timeframe: Literal["1d"] = "1d"


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise PriceBarQualityError("PRICE_TIMESTAMP_NOT_AWARE")
    return value.astimezone(timezone.utc)


def _check_prices(bar: DailyBarCandidate) -> None:
    values = (bar.open, bar.high, bar.low, bar.close)
    if any(type(p) is not Decimal or not p.is_finite() or p <= 0 or p >= DECIMAL_LIMIT
           or p.as_tuple().exponent < -8 for p in values):
        raise PriceBarQualityError("PRICE_VALUE_OUT_OF_RANGE")
    if bar.low > min(bar.open, bar.close) or bar.high < max(bar.open, bar.close):
        raise PriceBarQualityError("PRICE_OHLC_INCONSISTENT")
    if type(bar.volume) is not int or not 0 <= bar.volume < VOLUME_LIMIT:
        raise PriceBarQualityError("PRICE_VOLUME_OUT_OF_RANGE")


def validate_unverified_bar(
    identity: InstrumentIdentity, bar: DailyBarCandidate, *, now: datetime,
) -> UnverifiedPriceBar:
    if not isinstance(identity, InstrumentIdentity) or not isinstance(bar, DailyBarCandidate):
        raise PriceBarQualityError("PRICE_IDENTITY_OR_BAR_INVALID")
    if bar.source != SOURCE or bar.price_basis not in ("RAW", "ADJUSTED") \
            or bar.is_final is not False or bar.source_observed_at is not None:
        raise PriceBarQualityError("PRICE_FINALITY_NOT_VERIFIED")
    if not isinstance(bar.session_date, date) or isinstance(bar.session_date, datetime):
        raise PriceBarQualityError("PRICE_SESSION_DATE_INVALID")
    _check_prices(bar)
    fetched_at = _utc(bar.fetched_at)
    current = _utc(now)
    if fetched_at > current + MAX_CLOCK_SKEW:
        raise PriceBarQualityError("PRICE_FETCHED_IN_FUTURE")
    if current - fetched_at > MAX_FETCH_AGE:
        raise PriceBarQualityError("PRICE_FETCH_TOO_OLD")
    if bar.session_date > fetched_at.astimezone(identity.exchange_timezone).date():
        raise PriceBarQualityError("PRICE_SESSION_IN_FUTURE")
    # Weekdays are NOT sufficient evidence of an open trading session. Do not
    # promote prices to final even when this coarse condition passes.
    if bar.session_date.weekday() >= 5:
        raise PriceBarQualityError("PRICE_WEEKEND_SESSION_UNVERIFIED")
    try:
        session = attested_session(identity, bar.session_date)
    except ExchangeCalendarError as exc:
        raise PriceBarQualityError(str(exc)) from None
    earliest = (
        datetime.combine(bar.session_date, session.closes_at,
                         tzinfo=identity.exchange_timezone) + CLOSE_BUFFER
    ).astimezone(timezone.utc)
    if fetched_at < earliest:
        raise PriceBarQualityError("PRICE_SESSION_CLOSE_BUFFER_NOT_PASSED")
    return UnverifiedPriceBar(
        session_date=bar.session_date, price_basis=bar.price_basis,
        open=bar.open, high=bar.high, low=bar.low, close=bar.close,
        volume=bar.volume, fetched_at=fetched_at,
    )


def validate_batch(
    batch: DailyBarBatch, *, now: datetime,
) -> tuple[UnverifiedPriceBar, ...]:
    if not isinstance(batch, DailyBarBatch):
        raise PriceBarQualityError("PRICE_BATCH_INVALID")
    _utc(now)
    if batch.provider != SOURCE:
        raise PriceBarQualityError("PRICE_PROVIDER_NOT_ALLOWED")
    seen: set[tuple[date, str]] = set()
    result = []
    for bar in batch.bars:
        item = validate_unverified_bar(batch.instrument, bar, now=now)
        key = item.session_date, item.price_basis
        if key in seen:
            raise PriceBarQualityError("PRICE_DUPLICATE_IN_BATCH")
        seen.add(key)
        result.append(item)
    return tuple(result)



def validate_reference_batch(
    batch: DailyBarBatch, *, now: datetime,
) -> tuple[UnverifiedPriceBar, ...]:
    """MD06: prior local dates, RAW reference history only.

    No calendar attestation or finality assertion. This is a separate policy
    from validate_batch, intended for non-final chart history, never evidence
    of exchange hours, settlement or analysis eligibility.
    """
    current = _utc(now)
    if not isinstance(batch, DailyBarBatch) or batch.provider != SOURCE \
            or not isinstance(batch.instrument, InstrumentIdentity):
        raise PriceBarQualityError("PRICE_REFERENCE_BATCH_INVALID")
    seen = set()
    result = []
    for bar in batch.bars:
        if not isinstance(bar, DailyBarCandidate) or bar.source != SOURCE \
                or bar.price_basis != "RAW" or bar.is_final is not False \
                or bar.source_observed_at is not None:
            raise PriceBarQualityError("PRICE_REFERENCE_BAR_INVALID")
        if not isinstance(bar.session_date, date) or isinstance(bar.session_date, datetime):
            raise PriceBarQualityError("PRICE_SESSION_DATE_INVALID")
        _check_prices(bar)
        fetched = _utc(bar.fetched_at)
        if fetched > current + MAX_CLOCK_SKEW or current - fetched > MAX_FETCH_AGE:
            raise PriceBarQualityError("PRICE_REFERENCE_FETCH_TIME_INVALID")
        if bar.session_date >= fetched.astimezone(batch.instrument.exchange_timezone).date() \
                or bar.session_date >= current.astimezone(batch.instrument.exchange_timezone).date() \
                or bar.session_date.weekday() >= 5:
            raise PriceBarQualityError("PRICE_REFERENCE_SESSION_INVALID")
        if bar.session_date in seen:
            raise PriceBarQualityError("PRICE_DUPLICATE_IN_BATCH")
        seen.add(bar.session_date)
        result.append(UnverifiedPriceBar(
            session_date=bar.session_date, price_basis="RAW", open=bar.open,
            high=bar.high, low=bar.low, close=bar.close, volume=bar.volume,
            fetched_at=fetched,
        ))
    return tuple(result)

def analysis_eligible(*, quality_status: str, is_final: bool,
                      source_observed_at: datetime | None) -> bool:
    """MD-03 hard stop; validation policy and finality promotion not yet built."""
    return False
