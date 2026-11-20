"""Offline-only PR #24/25/26 integration guard: never use real KIS or DB."""
import inspect
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app import main, kis_first_probe, kis_readonly, kis_shared_state
from app import price_quality, price_repository, exchange_calendar
from app.kis_readonly import KisCredentials, KisReadOnlyDailyProvider, KisReadOnlyError
from app.kis_shared_state import KisSharedStateError
from app.market_data import InstrumentIdentity, normalize_kis_daily_response
from app.price_repository import PriceBarStorageError


def test_kis_real_network_and_storage_not_hooked_to_api():
    source = inspect.getsource(main)
    assert "kis_first_probe" not in source
    assert "kis_readonly" not in source
    assert "kis_shared_state" not in source
    assert "price_repository" not in source
    assert "price_quality" not in source
    assert "price_bar" not in source
    assert "/api/v1/demo/overview" in source


def test_md02_legacy_live_disabled_even_with_optional_shared_gate(tmp_path):
    path = tmp_path / "isolated"
    path.mkdir(mode=0o700)
    invoked = []

    def never_network(*args, **kwargs):
        invoked.append("called")
        raise AssertionError("network must be disabled")

    identity = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
    creds = KisCredentials("synthetic-appkey", "synthetic-appsecret")
    gate = kis_shared_state.KisSharedState(path)
    cli = KisReadOnlyDailyProvider(
        creds, live_enabled=False, transport=never_network,
        shared_state=gate, allow_shared_token_issue=True,
    )
    with pytest.raises(KisReadOnlyError, match="KIS_LIVE_READ_DISABLED"):
        cli.fetch_daily(
            identity, date(2026, 11, 19), date(2026, 11, 19), "RAW"
        )
    assert invoked == []
    assert not list(path.iterdir())


def test_live_enabled_but_token_issue_default_denied(tmp_path):
    path = tmp_path / "isolated"
    path.mkdir(mode=0o700)
    invoked = []
    def never_network(*args, **kwargs):
        invoked.append(1)
        raise AssertionError("default must deny token issuance")
    identity = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
    creds = KisCredentials("synthetic-appkey", "synthetic-appsecret")
    cli = KisReadOnlyDailyProvider(
        creds, live_enabled=True, transport=never_network,
        shared_state=kis_shared_state.KisSharedState(path),
        utcnow=lambda: datetime(2026, 11, 20, 2, tzinfo=timezone.utc),
    )
    with pytest.raises(KisSharedStateError, match="KIS_SHARED_TOKEN_MISSING_ISSUE_DENIED"):
        cli.fetch_daily(
            identity, date(2026, 11, 19), date(2026, 11, 19), "RAW"
        )
    assert invoked == []


def test_partial_bar_storage_default_rejected_offline():
    identity = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
    fetched = datetime(2026, 11, 20, 2, tzinfo=timezone.utc)
    batch = normalize_kis_daily_response(
        {"rt_cd": "0", "output2": [{
            "stck_bsop_date": "20261119", "stck_oprc": "100",
            "stck_hgpr": "110", "stck_lwpr": "90",
            "stck_clpr": "105", "acml_vol": "12345",
        }]},
        identity=identity, price_basis="RAW", fetched_at=fetched,
    )
    candidate = price_quality.validate_batch(batch, now=fetched)
    assert len(candidate) == 1 and candidate[0].is_final is False
    assert candidate[0].quality_status == "PARTIAL"
    assert price_quality.analysis_eligible(
        quality_status="VALID", is_final=True, source_observed_at=fetched
    ) is False
    with pytest.raises(PriceBarStorageError, match="PRICE_BAR_WRITE_DISABLED"):
        price_repository.insert_unverified_daily_batch(
            Session(), "not-a-real-uuid", batch, now=fetched,
        )
    assert kis_first_probe.MARKER == "kis-first-readonly-probe.attempted"


def test_csat_special_exchange_hours_are_present():
    kr = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
    session = exchange_calendar.attested_session(kr, date(2026, 11, 19))
    assert session.opens_at.hour == 10
    assert (session.closes_at.hour, session.closes_at.minute) == (16, 30)
