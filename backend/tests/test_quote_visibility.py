"""MD-04C1 non-publishing envelope tests: synthetic only, no DB/KIS."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.md04_finality import review_daily_finality_gaps
from app.quote_visibility import HiddenQuoteContractError, masked_quote_from_finality

IDENTITY = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
FETCHED = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
NOW = FETCHED + timedelta(minutes=1)
ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "100",
    "stck_hgpr": "110", "stck_lwpr": "90",
    "stck_clpr": "105", "acml_vol": "123456",
}


def report(rows):
    batch = normalize_kis_daily_response(
        {"rt_cd": "0", "output2": rows},
        identity=IDENTITY, price_basis="RAW", fetched_at=FETCHED,
    )
    return review_daily_finality_gaps(
        IDENTITY, batch, requested_basis="RAW", now=NOW,
    )


def test_no_data_has_no_prices_or_fake_zero():
    assert masked_quote_from_finality(None) == {
        "status": "UNAVAILABLE", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
    assert masked_quote_from_finality(report([])) == masked_quote_from_finality(None)


def test_valid_synthetic_candidate_remains_hidden_unfinalized():
    output = masked_quote_from_finality(report([ROW]))
    assert output == {
        "status": "UNFINALIZED", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
    assert "105" not in str(output)
    assert all(x not in output for x in ("market_value", "pnl", "is_final", "price_basis"))


@pytest.mark.parametrize("field,value", [
    ("is_final", True),
    ("source_observed_at", FETCHED),
    ("promotion_allowed", True),
    ("publication_allowed", True),
    ("analysis_allowed", True),
    ("automatic_storage_allowed", True),
])
def test_promotion_forgery_is_rejected(field, value):
    with pytest.raises(HiddenQuoteContractError, match="QUOTE_PRICE_PUBLICATION_NOT_ALLOWED"):
        masked_quote_from_finality(replace(report([ROW]), **{field: value}))


@pytest.mark.parametrize("field,value", [
    ("availability", "CURRENT"),
    ("quality_status", "VALID"),
    ("reviewed_rows", 0),
    ("blockers", ()),
])
def test_inconsistent_partial_report_is_rejected(field, value):
    with pytest.raises(HiddenQuoteContractError, match="QUOTE_FINALITY_STATE_INVALID"):
        masked_quote_from_finality(replace(report([ROW]), **{field: value}))


def test_wrong_input_rejected_without_provider_or_db_fallback():
    with pytest.raises(HiddenQuoteContractError, match="QUOTE_FINALITY_REPORT_INVALID"):
        masked_quote_from_finality({"availability": "UNFINALIZED"})
