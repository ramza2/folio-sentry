"""MD-03 quality tests: synthetic bars only, no provider, network or DB."""
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.price_quality import (
    PriceBarQualityError, analysis_eligible, validate_batch,
    validate_unverified_bar,
)

KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
FETCHED = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
NOW = FETCHED + timedelta(minutes=1)
KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "70000",
    "stck_hgpr": "72000", "stck_lwpr": "69000",
    "stck_clpr": "71000", "acml_vol": "12345678",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}


def batch(identity=KR, row=None, fetched=FETCHED):
    return normalize_kis_daily_response(
        {"rt_cd": "0", "output2": [row or (KR_ROW if identity.market == "KR" else US_ROW)]},
        identity=identity, price_basis="RAW", fetched_at=fetched,
    )


@pytest.mark.parametrize("identity", [KR, US])
def test_live_shape_remains_partial_and_no_final_price(identity):
    prepared = validate_batch(batch(identity), now=NOW)
    assert len(prepared) == 1
    bar = prepared[0]
    assert bar.quality_status == "PARTIAL" and bar.is_final is False
    assert bar.source_observed_at is None
    assert bar.timeframe == "1d" and bar.price_basis == "RAW"
    assert isinstance(bar.close, Decimal)
    assert not analysis_eligible(
        quality_status=bar.quality_status,
        is_final=bar.is_final,
        source_observed_at=bar.source_observed_at,
    )


def test_invalid_final_flag_and_false_observation_are_rejected():
    original = batch().bars[0]
    for changed in (
        replace(original, is_final=True),
        replace(original, source_observed_at=FETCHED),
        replace(original, source="OTHER"),
        replace(original, price_basis="UNKNOWN"),
    ):
        with pytest.raises(PriceBarQualityError):
            validate_unverified_bar(KR, changed, now=NOW)


def test_inconsistent_and_out_of_range_prices_rejected():
    original = batch().bars[0]
    for changed in (
        replace(original, high=Decimal("10")),
        replace(original, low=Decimal("72001")),
        replace(original, close=Decimal("0")),
        replace(original, close=Decimal("NaN")),
        replace(original, close=Decimal("1.123456789")),
        replace(original, close=Decimal("10000000000000000")),
        replace(original, volume=-1),
        replace(original, volume=10**28),
        replace(original, volume=True),
    ):
        with pytest.raises(PriceBarQualityError):
            validate_unverified_bar(KR, changed, now=NOW)


def test_weekends_rejected_even_when_source_has_bar():
    friday = batch(KR).bars[0]
    weekend = replace(friday, session_date=date(2026, 11, 21),
                      fetched_at=datetime(2026, 11, 22, 4, tzinfo=timezone.utc))
    with pytest.raises(PriceBarQualityError, match="PRICE_WEEKEND_SESSION_UNVERIFIED"):
        validate_unverified_bar(
            KR, weekend, now=datetime(2026, 11, 22, 4, 1, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("identity,cutoff", [
    (KR, datetime(2026, 11, 19, 6, 20, tzinfo=timezone.utc)),  # KST 15:20
    (US, datetime(2026, 11, 19, 20, 40, tzinfo=timezone.utc)),  # EST 15:40
])
def test_incomplete_regular_session_never_passes(identity, cutoff):
    original = batch(identity).bars[0]
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CLOSE_BUFFER_NOT_PASSED"):
        validate_unverified_bar(identity, replace(original, fetched_at=cutoff),
                                now=cutoff + timedelta(minutes=1))


def test_us_dst_cutoff_is_timezone_sensitive():
    original = batch(US).bars[0]
    march = date(2026, 3, 9)  # US daylight saving time
    # 19:00 UTC is 15:00 EDT; 23:00 UTC is 19:00 EDT.
    early = replace(original, session_date=march,
                    fetched_at=datetime(2026, 3, 9, 19, 0, tzinfo=timezone.utc))
    later = replace(original, session_date=march,
                    fetched_at=datetime(2026, 3, 9, 23, 0, tzinfo=timezone.utc))
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CLOSE_BUFFER_NOT_PASSED"):
        validate_unverified_bar(US, early, now=early.fetched_at)
    assert validate_unverified_bar(US, later, now=later.fetched_at).quality_status == "PARTIAL"


def test_clock_skew_fetch_age_and_future_day_fail_closed():
    original = batch().bars[0]
    with pytest.raises(PriceBarQualityError, match="PRICE_FETCHED_IN_FUTURE"):
        validate_unverified_bar(KR, original, now=FETCHED-timedelta(minutes=1))
    with pytest.raises(PriceBarQualityError, match="PRICE_FETCH_TOO_OLD"):
        validate_unverified_bar(KR, original, now=FETCHED+timedelta(hours=25))
    with pytest.raises(PriceBarQualityError, match="PRICE_TIMESTAMP_NOT_AWARE"):
        validate_unverified_bar(KR, original, now=datetime(2026, 11, 20))
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_IN_FUTURE"):
        validate_unverified_bar(KR, replace(original, session_date=date(2026, 11, 21)), now=NOW)


def test_duplicate_batch_fails_before_any_storage():
    first = batch()
    merged = replace(first, bars=first.bars + first.bars)
    with pytest.raises(PriceBarQualityError, match="PRICE_DUPLICATE_IN_BATCH"):
        validate_batch(merged, now=NOW)


def test_none_of_the_md03_data_is_eligible_for_real_signals():
    assert analysis_eligible(quality_status="PARTIAL", is_final=False, source_observed_at=None) is False
    # Even falsified caller arguments cannot override the MD-03 hard stop.
    assert analysis_eligible(quality_status="VALID", is_final=True, source_observed_at=FETCHED) is False


def test_2026_kr_csat_close_at_1630_not_regular_1530():
    from app.exchange_calendar import attested_session
    official = attested_session(KR, date(2026, 11, 19))
    assert (official.opens_at.hour, official.closes_at.hour, official.closes_at.minute) == (10, 16, 30)
    original = batch(KR).bars[0]
    # 18:00 KST is beyond ordinary 15:30+2h but NOT CSAT 16:30+2h.
    early = datetime(2026, 11, 19, 9, 0, tzinfo=timezone.utc)
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CLOSE_BUFFER_NOT_PASSED"):
        validate_unverified_bar(KR, replace(original, fetched_at=early),
                                now=early + timedelta(minutes=1))
    late = datetime(2026, 11, 19, 10, 31, tzinfo=timezone.utc)
    assert validate_unverified_bar(
        KR, replace(original, fetched_at=late),
        now=late + timedelta(minutes=1)
    ).quality_status == "PARTIAL"


def test_2026_us_thanksgiving_is_closed_and_nov27_early_close():
    from app.exchange_calendar import attested_session, ExchangeCalendarError
    from app.market_data import InstrumentIdentity
    for mic in ("XNAS", "XNYS", "XASE"):
        identity = InstrumentIdentity("US", mic, "AAPL", "USD")
        with pytest.raises(ExchangeCalendarError, match="PRICE_EXCHANGE_CLOSED"):
            attested_session(identity, date(2026, 11, 26))
        entry = attested_session(identity, date(2026, 11, 27))
        assert entry.closes_at.hour == 13
    original = batch(US).bars[0]
    # Nov27 US Eastern Standard Time: 15:10 local is after 13:00+2h.
    valid = datetime(2026, 11, 27, 20, 10, tzinfo=timezone.utc)
    assert validate_unverified_bar(
        US, replace(original, session_date=date(2026, 11, 27), fetched_at=valid),
        now=valid + timedelta(minutes=1)
    ).is_final is False
    too_soon = valid - timedelta(hours=1)
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CLOSE_BUFFER_NOT_PASSED"):
        validate_unverified_bar(
            US, replace(original, session_date=date(2026, 11, 27),
                        fetched_at=too_soon),
            now=too_soon + timedelta(minutes=1),
        )
    with pytest.raises(PriceBarQualityError, match="PRICE_EXCHANGE_CLOSED"):
        validate_unverified_bar(
            US, replace(original, session_date=date(2026, 11, 26),
                        fetched_at=valid),
            now=valid + timedelta(minutes=1),
        )


def test_unverified_weekday_and_full_holiday_not_guessed():
    from app.exchange_calendar import attested_session, ExchangeCalendarError
    unknown = date(2026, 11, 20)  # no attestation: fail closed even though Friday
    with pytest.raises(ExchangeCalendarError, match="PRICE_SESSION_CALENDAR_UNVERIFIED"):
        attested_session(KR, unknown)
    first = batch(KR).bars[0]
    observed = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CALENDAR_UNVERIFIED"):
        validate_unverified_bar(
            KR, replace(first, session_date=unknown, fetched_at=observed),
            now=observed + timedelta(minutes=1)
        )
