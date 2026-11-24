"""MD05B synthetic KIS current quote contract and read-only transport tests."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.kis_current import (
    CurrentQuoteCandidate, KisReadOnlyCurrentProvider,
    parse_current_quote,
)
from app.kis_readonly import (
    ALLOWED_CALLS, KR_CURRENT_PATH, US_CURRENT_PATH,
    KisCredentials, KisHttpsTransport, KisReadOnlyError,
)
from app.kis_shared_state import EXPECTED_TR
from app.market_data import InstrumentIdentity, MarketDataContractError

NOW = datetime(2026, 11, 24, 1, 0, tzinfo=timezone.utc)
KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")


@pytest.mark.parametrize("identity,body,expected", [
    (KR, {"stck_prpr": "70800", "stck_shrn_iscd": "005930"}, Decimal("70800")),
    (US, {"last": "251.2300", "rsym": "DNASAAPL"}, Decimal("251.2300")),
])
def test_valid_current_prices_have_only_local_receipt_not_provider_time(
    identity, body, expected,
):
    result = parse_current_quote(
        {"rt_cd": "0", "output": body},
        identity=identity, fetched_at=NOW,
    )
    assert result.instrument == identity
    assert result.price == expected
    assert result.fetched_at == NOW
    assert result.source == "KIS"
    assert result.provider_observed_at is None
    assert result.realtime_verified is False
    assert result.is_final is False


@pytest.mark.parametrize("identity,field", [(KR, "stck_prpr"), (US, "last")])
def test_empty_price_is_explicitly_unavailable(identity, field):
    for value in (None, ""):
        result = parse_current_quote(
            {"rt_cd": "0", "output": {field: value}},
            identity=identity, fetched_at=NOW,
        )
        assert result.price is None
        assert result.fetched_at is None
        assert result.realtime_verified is False


@pytest.mark.parametrize("bad", [
    False, 0, -10, "0", "0.000", "-1", "NaN", "Infinity",
    "1e3", "+20", " 20", "00100", "5.123456789", "1" * 17,
    "100,000", "100\nX", "25.4USD", True,
])
def test_bad_kis_current_price_is_never_converted_via_float(bad):
    with pytest.raises(MarketDataContractError, match="MD05B_KIS_PRICE_INVALID"):
        parse_current_quote(
            {"rt_cd": "0", "output": {"stck_prpr": bad}},
            identity=KR, fetched_at=NOW,
        )


@pytest.mark.parametrize("payload", [
    {}, {"rt_cd": "1", "output": {"stck_prpr": "100"}},
    {"rt_cd": "0", "output": []},
    {"rt_cd": "0", "output": "100"},
    {"rt_cd": "0", "output": None},
    None, [],
])
def test_invalid_kis_envelope_fails_closed(payload):
    with pytest.raises(MarketDataContractError):
        parse_current_quote(payload, identity=KR, fetched_at=NOW)


@pytest.mark.parametrize("payload,identity", [
    ({"rt_cd": "0", "output": {"stck_prpr": "100", "stck_shrn_iscd": "000000"}}, KR),
    ({"rt_cd": "0", "output": {"last": "200", "rsym": "NYSIBM"}}, US),
    ({"rt_cd": "0", "output": {"last": "200", "rsym": 0}}, US),
])
def test_response_identity_mismatch_fails_closed(payload, identity):
    with pytest.raises(MarketDataContractError, match="MD05B_KIS_INSTRUMENT_MISMATCH"):
        parse_current_quote(payload, identity=identity, fetched_at=NOW)


def test_naive_receipt_timestamp_rejected():
    with pytest.raises(MarketDataContractError, match="MD05B_QUOTE_CONTEXT_INVALID"):
        parse_current_quote(
            {"rt_cd": "0", "output": {"stck_prpr": "100"}},
            identity=KR, fetched_at=datetime(2026, 11, 24, 1),
        )


class Gate:
    def __init__(self):
        self.calls = []

    def call_quote(self, credentials, transport, **kwargs):
        self.calls.append(kwargs)
        path = kwargs["path"]
        if path == KR_CURRENT_PATH:
            return {"rt_cd": "0", "output": {"stck_prpr": "70800"}}
        return {"rt_cd": "0", "output": {"last": "251.2300"}}


@pytest.mark.parametrize("identity,expected_path,expected_tr,params", [
    (KR, KR_CURRENT_PATH, "FHKST01010100", {
        "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "005930",
    }),
    (US, US_CURRENT_PATH, "HHDFS00000300", {
        "AUTH": "", "EXCD": "NAS", "SYMB": "AAPL",
    }),
    (InstrumentIdentity("KR", "XKOS", "000001", "KRW"),
     KR_CURRENT_PATH, "FHKST01010100", {
         "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": "000001",
     }),
    (InstrumentIdentity("US", "XNYS", "IBM", "USD"),
     US_CURRENT_PATH, "HHDFS00000300", {
         "AUTH": "", "EXCD": "NYS", "SYMB": "IBM",
     }),
    (InstrumentIdentity("US", "XASE", "SPY", "USD"),
     US_CURRENT_PATH, "HHDFS00000300", {
         "AUTH": "", "EXCD": "AMS", "SYMB": "SPY",
     }),
])
def test_only_exact_kis_current_tr_with_shared_gate(
    identity, expected_path, expected_tr, params,
):
    gate = Gate()
    credentials = KisCredentials("synthetic-appkey-123", "synthetic-secret-456")
    reader = KisReadOnlyCurrentProvider(
        credentials, gate, live_enabled=True,
        transport=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Shared gate mock must not call transport")),
        utcnow=lambda: NOW,
    )
    result = reader.fetch_current(identity)
    assert result.instrument == identity
    assert len(gate.calls) == 1
    call = gate.calls[0]
    assert call["path"] == expected_path
    assert call["tr_id"] == expected_tr
    assert call["params"] == params
    assert call["live_enabled"] is True
    assert call["allow_new_token"] is False
    assert EXPECTED_TR[expected_path] == expected_tr
    assert ("GET", expected_path) in ALLOWED_CALLS
    assert result.provider_observed_at is None
    assert result.realtime_verified is False


def test_disabled_reader_never_calls_gate():
    gate = Gate()
    reader = KisReadOnlyCurrentProvider(
        KisCredentials("synthetic-key-123", "synthetic-secret-123"),
        gate, live_enabled=False, utcnow=lambda: NOW,
    )
    with pytest.raises(KisReadOnlyError, match="KIS_LIVE_READ_DISABLED"):
        reader.fetch_current(KR)
    assert gate.calls == []


def test_shared_gate_is_required_even_when_disabled():
    with pytest.raises(KisReadOnlyError, match="KIS_SHARED_STATE_REQUIRED"):
        KisReadOnlyCurrentProvider(
            KisCredentials("synthetic-key-123", "synthetic-secret-123"),
            None,
        )


def test_transport_rejects_non_allowlisted_order_and_untrusted_read_paths():
    transport = KisHttpsTransport()
    for method, path in (
        ("POST", KR_CURRENT_PATH), ("POST", US_CURRENT_PATH),
        ("GET", "/uapi/domestic-stock/v1/trading/order-cash"),
        ("GET", "/uapi/overseas-stock/v1/trading/inquire-balance"),
    ):
        with pytest.raises(KisReadOnlyError, match="KIS_PATH_NOT_ALLOWED"):
            transport(method, path, {}, params={})


def test_no_implicit_token_issuance_and_live_contract_frozen():
    gate = Gate()
    reader = KisReadOnlyCurrentProvider(
        KisCredentials("synthetic-key-123", "synthetic-secret-123"),
        gate, live_enabled=True, utcnow=lambda: NOW,
        allow_new_token=False,
    )
    row = reader.fetch_current(US)
    assert row.price == Decimal("251.2300")
    assert gate.calls[0]["allow_new_token"] is False
    with pytest.raises((AttributeError, TypeError)):
        row.price = Decimal("99999")
