"""Synthetic MD-04A KIS -> quality -> non-publishing contract tests.

No live KIS API, real credential, Docker, DB, or application startup changes.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.md04_intake import MD04IntakeError, inspect_unverified_intake
from app.portfolio_api import tracked_json
from app.price_quality import PriceBarQualityError

KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
FETCHED = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
NOW = FETCHED + timedelta(minutes=1)
SAMPLE = {
    "KR": {
        "stck_bsop_date": "20261119", "stck_oprc": "70000",
        "stck_hgpr": "72000", "stck_lwpr": "69000",
        "stck_clpr": "71000", "acml_vol": "12345678",
    },
    "US": {
        "xymd": "20261119", "open": "250.12", "high": "254.34",
        "low": "249.90", "clos": "252.44", "tvol": "234567",
    },
}


def make_batch(identity=KR, rows=None):
    return normalize_kis_daily_response(
        {"rt_cd": "0", "output2": [SAMPLE[identity.market]] if rows is None else rows},
        identity=identity, price_basis="RAW", fetched_at=FETCHED,
    )


@pytest.mark.parametrize("identity", (KR, US))
def test_both_markets_are_never_publishable_even_after_valid_session(identity):
    receipt = inspect_unverified_intake(identity, make_batch(identity), now=NOW)
    assert receipt.accepted_rows == 1
    assert receipt.availability == "UNFINALIZED"
    assert receipt.quality_status == "PARTIAL"
    assert receipt.is_final is False
    assert receipt.source_observed_at is None
    assert receipt.publication_allowed is False
    assert receipt.automatic_storage_allowed is False
    assert not hasattr(receipt, "close")
    assert "70000" not in repr(receipt)
    assert "250.12" not in repr(receipt)


def test_empty_successful_response_is_unavailable_not_ready():
    receipt = inspect_unverified_intake(KR, make_batch(rows=[]), now=NOW)
    assert receipt.accepted_rows == 0
    assert receipt.availability == "UNAVAILABLE"
    assert receipt.quality_status is None
    assert receipt.publication_allowed is False


def test_cross_symbol_and_exchange_assignment_is_denied_before_quality_check():
    batch = make_batch(KR)
    for wrong in (
        InstrumentIdentity("KR", "XKRX", "000660", "KRW"),
        InstrumentIdentity("KR", "XKOS", "005930", "KRW"),
        US,
    ):
        with pytest.raises(MD04IntakeError, match="MD04_INSTRUMENT_IDENTITY_MISMATCH"):
            inspect_unverified_intake(wrong, batch, now=NOW)


def test_wrong_type_and_relabelled_batch_are_rejected():
    with pytest.raises(MD04IntakeError, match="MD04_INPUT_INVALID"):
        inspect_unverified_intake(KR, object(), now=NOW)
    with pytest.raises(MD04IntakeError, match="MD04_INPUT_INVALID"):
        inspect_unverified_intake(None, make_batch(), now=NOW)
    with pytest.raises(PriceBarQualityError, match="PRICE_PROVIDER_NOT_ALLOWED"):
        inspect_unverified_intake(KR, replace(make_batch(), provider="OTHER"), now=NOW)


def test_forged_finality_and_unverified_calendar_block_intake():
    batch = make_batch()
    forged = replace(batch, bars=(replace(batch.bars[0], is_final=True),))
    with pytest.raises(PriceBarQualityError, match="PRICE_FINALITY_NOT_VERIFIED"):
        inspect_unverified_intake(KR, forged, now=NOW)
    invalid_day = replace(batch, bars=(replace(
        batch.bars[0], session_date=datetime(2026, 11, 20).date(),
    ),))
    with pytest.raises(PriceBarQualityError, match="PRICE_SESSION_CALENDAR_UNVERIFIED"):
        inspect_unverified_intake(KR, invalid_day, now=NOW)


def test_old_data_not_accepted_even_if_original_bar_shape_was_valid():
    with pytest.raises(PriceBarQualityError, match="PRICE_FETCH_TOO_OLD"):
        inspect_unverified_intake(KR, make_batch(), now=NOW + timedelta(days=2))


def test_portfolio_contract_never_receives_candidate_or_partial_price():
    inst = SimpleNamespace(
        id=uuid4(), market="KR", exchange_mic="XKRX", symbol="005930",
        name="Synthetic KR", currency="KRW", asset_type="STOCK",
    )
    tracked = SimpleNamespace(
        id=uuid4(), kind="HOLDING", quantity=Decimal("2"),
        average_cost=Decimal("70000"), alerts_enabled=True, memo=None,
    )
    receipt = inspect_unverified_intake(KR, make_batch(), now=NOW)
    assert receipt.availability == "UNFINALIZED"
    response = tracked_json(tracked, inst)
    assert response["quote"] == {
        "status": "UNAVAILABLE", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
    assert response["market_value"] is None
    assert response["unrealized_pnl"] is None
    assert response["unrealized_pnl_percent"] is None
    assert "71000" not in str(response)


def test_receipt_is_immutable_and_cannot_be_promoted_by_caller():
    receipt = inspect_unverified_intake(KR, make_batch(), now=NOW)
    with pytest.raises((AttributeError, TypeError)):
        receipt.publication_allowed = True
