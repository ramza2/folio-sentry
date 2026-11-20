"""Synthetic, offline-only market data parser tests. No provider credentials/HTTP."""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.market_data import (
    DailyBarBatch, InstrumentIdentity, MarketDataContractError,
    normalize_kis_daily_response,
)

KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
FETCHED = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)

KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "70000", "stck_hgpr": "72000",
    "stck_lwpr": "69000", "stck_clpr": "71000", "acml_vol": "12345678",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}


def normalize(row, *, identity=KR, fetched=FETCHED, basis="RAW"):
    return normalize_kis_daily_response(
        {"rt_cd": "0", "output2": [row]}, identity=identity,
        price_basis=basis, fetched_at=fetched,
    )


def test_exchange_symbol_market_currency_strict_and_mapped():
    assert KR.kis_exchange_code == "J"
    assert US.kis_exchange_code == "NAS"
    assert InstrumentIdentity("KR", "XKOS", "035720", "KRW").kis_exchange_code == "J"
    assert InstrumentIdentity("US", "XNYS", "IBM", "USD").kis_exchange_code == "NYS"
    assert InstrumentIdentity("US", "XASE", "SPY", "USD").kis_exchange_code == "AMS"
    for args in [
        ("KR", "XNAS", "005930", "KRW"),
        ("KR", "XKRX", "005930", "USD"),
        ("US", "XNAS", "AAPL", "KRW"),
        ("KR", "XKRX", "5930", "KRW"),
        ("US", "XNYS", "aapl", "USD"),
        ("US", "XNYS", "AAPL/../../etc", "USD"),
        ("US", "NOPE", "AAPL", "USD"),
    ]:
        with pytest.raises(MarketDataContractError):
            InstrumentIdentity(*args)


@pytest.mark.parametrize("identity,row", [(KR, KR_ROW), (US, US_ROW)])
def test_kis_kr_and_us_daily_bars_parse_decimal_strings_without_finality(identity, row):
    batch = normalize(row, identity=identity)
    assert isinstance(batch, DailyBarBatch)
    assert batch.instrument == identity
    assert batch.provider == "KIS"
    assert batch.availability == "UNFINALIZED"
    assert len(batch.bars) == 1
    bar = batch.bars[0]
    assert isinstance(bar.close, Decimal)
    assert bar.close == Decimal(row["stck_clpr"] if identity.market == "KR" else row["clos"])
    assert isinstance(bar.volume, int)
    assert bar.price_basis == "RAW"
    assert bar.source == "KIS"
    assert bar.fetched_at == FETCHED
    assert bar.source_observed_at is None
    assert bar.is_final is False


def test_explicit_adjustment_basis_and_sorted_dates():
    first = {**KR_ROW, "stck_bsop_date": "20261118"}
    batch = normalize_kis_daily_response(
        {"rt_cd": "0", "output2": [KR_ROW, first]},
        identity=KR, price_basis="ADJUSTED", fetched_at=FETCHED,
    )
    assert [x.session_date.isoformat() for x in batch.bars] == [
        "2026-11-18", "2026-11-19",
    ]
    assert all(x.price_basis == "ADJUSTED" and not x.is_final for x in batch.bars)


def test_empty_batch_never_creates_synthetic_price():
    batch = normalize_kis_daily_response(
        {"rt_cd": "0", "output2": []}, identity=US,
        price_basis="RAW", fetched_at=FETCHED,
    )
    assert batch.availability == "UNAVAILABLE"
    assert batch.bars == ()


@pytest.mark.parametrize("changes", [
    {"stck_oprc": "0"}, {"stck_clpr": "-1"}, {"stck_oprc": "nan"},
    {"stck_oprc": 71000.0}, {"stck_oprc": "1e4"},
    {"stck_oprc": "1.123456789"}, {"stck_hgpr": "69000"},
    {"stck_lwpr": "72000"}, {"stck_bsop_date": "20260229"},
    {"stck_bsop_date": "20261121"}, {"stck_bsop_date": "2026-11-19"},
    {"acml_vol": -1}, {"acml_vol": "1.0"}, {"acml_vol": "null"},
    {"acml_vol": "99999999999999999999999999999"},
])
def test_invalid_kr_ohlcv_never_survives_normalization(changes):
    with pytest.raises(MarketDataContractError):
        normalize({**KR_ROW, **changes})


@pytest.mark.parametrize("changes", [
    {"clos": ""}, {"clos": "Infinity"}, {"clos": None},
    {"high": "250"}, {"low": "251.00"},
    {"xymd": "20261120"},  # US Nov 19 at FETCHED; respect NY timezone
    {"tvol": 123}, {"tvol": "00010"},
])
def test_invalid_us_ohlcv_fail_closed(changes):
    with pytest.raises(MarketDataContractError):
        normalize({**US_ROW, **changes}, identity=US)


def test_reject_failed_or_malformed_provider_responses():
    for payload in (
        {}, {"rt_cd": "1", "output2": [KR_ROW]},
        {"rt_cd": "0"}, {"rt_cd": "0", "output2": None},
        {"rt_cd": "0", "output2": [None]},
        {"rt_cd": "0", "output2": [KR_ROW, KR_ROW]},
        {"rt_cd": "0", "output2": [KR_ROW] * 201},
        {"rt_cd": "0", "output2": [{k: v for k, v in KR_ROW.items() if k != "stck_clpr"}]},
    ):
        with pytest.raises(MarketDataContractError):
            normalize_kis_daily_response(
                payload, identity=KR, price_basis="RAW", fetched_at=FETCHED,
            )


def test_reject_ambiguous_basis_and_naive_time():
    for basis in ("", "UNKNOWN", "DEMO", "raw"):
        with pytest.raises(MarketDataContractError):
            normalize(KR_ROW, basis=basis)
    with pytest.raises(MarketDataContractError):
        normalize(KR_ROW, fetched=datetime(2026, 11, 20))


def test_no_external_data_or_live_portfolio_wiring():
    # This isolated normalization contract contains no transport/DB import.
    import inspect
    import app.market_data as subject
    source = inspect.getsource(subject)
    assert "urlopen(" not in source
    assert "get_engine(" not in source
    assert "api/v1/demo" not in source
    assert "access_token" not in source
