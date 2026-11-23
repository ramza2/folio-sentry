"""MD-04B evidence-gap policy: synthetic only, no network/DB/credentials."""
from dataclasses import FrozenInstanceError, replace
from datetime import date, datetime, timedelta, timezone

import pytest

from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.md04_finality import (
    FinalityPolicyError, NO_DATA, UNVERIFIED_REASONS,
    review_daily_finality_gaps,
)
from app.price_quality import PriceBarQualityError, analysis_eligible

FETCHED = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
NOW = FETCHED + timedelta(minutes=1)
KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "100",
    "stck_hgpr": "110", "stck_lwpr": "90",
    "stck_clpr": "105", "acml_vol": "123456",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}
IDENTITIES = (
    InstrumentIdentity("KR", "XKRX", "005930", "KRW"),
    InstrumentIdentity("KR", "XKOS", "000001", "KRW"),
    InstrumentIdentity("US", "XNAS", "AAPL", "USD"),
    InstrumentIdentity("US", "XNYS", "IBM", "USD"),
    InstrumentIdentity("US", "XASE", "SPY", "USD"),
)


def candidate(identity=IDENTITIES[0], *, basis="RAW", rows=None, fetched=FETCHED):
    return normalize_kis_daily_response(
        {"rt_cd": "0", "output2": (
            [KR_ROW if identity.market == "KR" else US_ROW] if rows is None else rows
        )},
        identity=identity, price_basis=basis, fetched_at=fetched,
    )


@pytest.mark.parametrize("identity", IDENTITIES)
@pytest.mark.parametrize("basis", ("RAW", "ADJUSTED"))
def test_all_supported_exchanges_and_bases_remain_unfinalized(identity, basis):
    batch = candidate(identity, basis=basis)
    result = review_daily_finality_gaps(
        identity, batch, requested_basis=basis, now=NOW,
    )
    assert result.availability == "UNFINALIZED"
    assert result.reviewed_rows == 1
    assert result.blockers == UNVERIFIED_REASONS
    assert result.quality_status == "PARTIAL"
    assert result.is_final is False
    assert result.source_observed_at is None
    assert result.promotion_allowed is False
    assert result.publication_allowed is False
    assert result.analysis_allowed is False
    assert result.automatic_storage_allowed is False
    assert not analysis_eligible(
        quality_status=result.quality_status,
        is_final=result.is_final, source_observed_at=result.source_observed_at,
    )
    assert "250.12" not in repr(result) and "105" not in repr(result)
    assert not hasattr(result, "close")


def test_empty_batch_never_becomes_an_implicitly_final_zero():
    identity = IDENTITIES[0]
    result = review_daily_finality_gaps(
        identity, candidate(identity, rows=[]), requested_basis="RAW", now=NOW,
    )
    assert result.availability == "UNAVAILABLE"
    assert result.reviewed_rows == 0
    assert result.blockers == (NO_DATA,)
    assert result.quality_status is None
    assert result.publication_allowed is False


@pytest.mark.parametrize("basis", ("ADJUSTED", "invalid", "", None, 1))
def test_requested_price_basis_is_not_inferred_or_autocorrected(basis):
    identity = IDENTITIES[0]
    with pytest.raises(FinalityPolicyError):
        review_daily_finality_gaps(
            identity, candidate(identity, basis="RAW"),
            requested_basis=basis, now=NOW,
        )


def test_mixed_raw_and_adjusted_rows_are_not_silently_merged():
    identity = IDENTITIES[0]
    raw = candidate(identity)
    mixed = replace(raw, bars=(
        raw.bars[0], replace(raw.bars[0], price_basis="ADJUSTED"),
    ))
    with pytest.raises(FinalityPolicyError, match="MD04B_REQUESTED_BASIS_MISMATCH"):
        review_daily_finality_gaps(
            identity, mixed, requested_basis="RAW", now=NOW,
        )


def test_wrong_instrument_or_exchange_is_still_rejected_by_md04a():
    with pytest.raises(ValueError, match="MD04_INSTRUMENT_IDENTITY_MISMATCH"):
        review_daily_finality_gaps(
            IDENTITIES[1], candidate(IDENTITIES[0]),
            requested_basis="RAW", now=NOW,
        )


def test_forged_final_and_fake_observation_are_not_admitted():
    identity = IDENTITIES[0]
    batch = candidate(identity)
    modified = (
        replace(batch.bars[0], is_final=True),
        replace(batch.bars[0], source_observed_at=FETCHED),
    )
    for row in modified:
        with pytest.raises(PriceBarQualityError, match="PRICE_FINALITY_NOT_VERIFIED"):
            review_daily_finality_gaps(
                identity, replace(batch, bars=(row,)),
                requested_basis="RAW", now=NOW,
            )


def test_unknown_session_and_stale_fetch_remain_denied():
    identity = IDENTITIES[0]
    batch = candidate(identity)
    future_session = replace(batch, bars=(
        replace(batch.bars[0], session_date=date(2026, 11, 20)),
    ))
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CALENDAR_UNVERIFIED"):
        review_daily_finality_gaps(
            identity, future_session, requested_basis="RAW", now=NOW,
        )
    with pytest.raises(PriceBarQualityError, match="PRICE_FETCH_TOO_OLD"):
        review_daily_finality_gaps(
            identity, batch, requested_basis="RAW",
            now=NOW + timedelta(days=3),
        )


def test_diagnostic_report_is_immutable_no_magic_promotion():
    identity = IDENTITIES[0]
    result = review_daily_finality_gaps(
        identity, candidate(identity), requested_basis="RAW", now=NOW,
    )
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.promotion_allowed = True
    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.is_final = True
    assert result.blockers[-1] == "MD04B_FINALITY_PROMOTION_NOT_IMPLEMENTED"
