"""MD-02: fake-transport tests only; ZERO external requests or live keys."""
from datetime import date, datetime, timezone
import os

import pytest

from app.kis_readonly import (
    KR_DAILY_PATH, US_DAILY_PATH, KR_CURRENT_PATH, US_CURRENT_PATH,
    TOKEN_PATH, KisCredentials,
    KisHttpsTransport, KisReadOnlyDailyProvider, KisReadOnlyError,
)
from app.market_data import InstrumentIdentity, MarketDataContractError


KR = InstrumentIdentity("KR", "XKRX", "005930", "KRW")
US = InstrumentIdentity("US", "XNAS", "AAPL", "USD")
NOW = datetime(2026, 11, 20, 2, 0, tzinfo=timezone.utc)
KR_ROW = {
    "stck_bsop_date": "20261119", "stck_oprc": "70000", "stck_hgpr": "72000",
    "stck_lwpr": "69000", "stck_clpr": "71000", "acml_vol": "12345678",
}
US_ROW = {
    "xymd": "20261119", "open": "250.12", "high": "254.34",
    "low": "249.90", "clos": "252.44", "tvol": "234567",
}


class FakeClock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class StubKis:
    def __init__(self, rows=None, token_ttl=86400):
        self.calls = []
        self.rows = rows
        self.token_ttl = token_ttl

    def __call__(self, method, path, headers, params=None, body=None):
        self.calls.append((method, path, dict(headers), params, body))
        if path == TOKEN_PATH:
            return {"access_token": "synthetic-token-123456", "expires_in": self.token_ttl}
        if self.rows is None:
            rows = [KR_ROW if path == KR_DAILY_PATH else US_ROW]
        else:
            rows = self.rows
        return {"rt_cd": "0", "output2": rows}


def provider(*, enabled=True, clock=None, stub=None):
    return KisReadOnlyDailyProvider(
        KisCredentials("synthetic-appkey", "synthetic-appsecret"),
        live_enabled=enabled,
        monotonic=clock or FakeClock(),
        utcnow=lambda: NOW,
        transport=stub or StubKis(),
    )


def test_disabled_default_makes_zero_token_or_quote_calls():
    stub = StubKis()
    cli = KisReadOnlyDailyProvider(
        KisCredentials("synthetic-appkey", "synthetic-appsecret"),
        monotonic=FakeClock(), utcnow=lambda: NOW, transport=stub)
    with pytest.raises(KisReadOnlyError, match="KIS_LIVE_READ_DISABLED"):
        cli.fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert stub.calls == []


@pytest.mark.parametrize("identity,path,basis,price_bit", [
    (KR, KR_DAILY_PATH, "RAW", "1"),
    (KR, KR_DAILY_PATH, "ADJUSTED", "0"),
    (US, US_DAILY_PATH, "RAW", "0"),
    (US, US_DAILY_PATH, "ADJUSTED", "1"),
])
def test_query_is_quote_only_and_raw_adjusted_flags_explicit(identity, path, basis, price_bit):
    stub = StubKis()
    cli = provider(stub=stub)
    data = cli.fetch_daily(identity, date(2026, 11, 19), date(2026, 11, 19), basis)
    assert len(stub.calls) == 2
    method, token_path, _, _, token_body = stub.calls[0]
    assert (method, token_path) == ("POST", TOKEN_PATH)
    assert token_body["grant_type"] == "client_credentials"
    method, quote_path, headers, params, body = stub.calls[1]
    assert (method, quote_path, body) == ("GET", path, None)
    assert headers["authorization"] == "Bearer synthetic-token-123456"
    assert headers["tr_id"] == ("FHKST03010100" if identity.market == "KR" else "HHDFS76240000")
    if identity.market == "KR":
        assert params["FID_INPUT_ISCD"] == identity.symbol
        assert params["FID_INPUT_DATE_1"] == "20261119"
        assert params["FID_INPUT_DATE_2"] == "20261119"
        assert params["FID_ORG_ADJ_PRC"] == price_bit
        assert params["FID_PERIOD_DIV_CODE"] == "D"
        assert params["FID_COND_MRKT_DIV_CODE"] == "J"
    else:
        assert params["SYMB"] == "AAPL"
        assert params["EXCD"] == "NAS"
        assert params["GUBN"] == "0"
        assert params["BYMD"] == "20261119"
        assert params["MODP"] == price_bit
    assert data.instrument == identity and data.availability == "UNFINALIZED"
    assert data.bars[0].is_final is False
    assert data.bars[0].source_observed_at is None
    assert data.bars[0].price_basis == basis


def test_rate_limit_and_cache_prevent_unbounded_calls():
    clk = FakeClock()
    stub = StubKis()
    cli = provider(clock=clk, stub=stub)
    cli.fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    with pytest.raises(KisReadOnlyError, match="KIS_RATE_LIMIT"):
        cli.fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(stub.calls) == 2
    clk.advance(1.01)
    cli.fetch_daily(US, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(stub.calls) == 3
    assert [call[1] for call in stub.calls] == [TOKEN_PATH, KR_DAILY_PATH, US_DAILY_PATH]


def test_token_expiry_refuses_early_refresh_without_retry():
    clk = FakeClock()
    stub = StubKis(token_ttl=120)
    cli = provider(clock=clk, stub=stub)
    cli.fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    clk.advance(61)
    with pytest.raises(KisReadOnlyError, match="KIS_TOKEN_REFRESH_TOO_SOON"):
        cli.fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(stub.calls) == 2


@pytest.mark.parametrize("invalid", [
    (date(2026, 11, 20), date(2026, 11, 20)),  # US market still Nov19
    (date(2026, 11, 19), date(2026, 11, 18)),
    (date(2025, 1, 1), date(2026, 11, 19)),
])
def test_us_time_window_rejection_occurs_before_token(invalid):
    stub = StubKis()
    with pytest.raises(MarketDataContractError):
        provider(stub=stub).fetch_daily(US, invalid[0], invalid[1], "RAW")
    assert stub.calls == []


def test_us_older_rows_are_filtered_not_claimed_as_coverage():
    stub = StubKis(rows=[{**US_ROW, "xymd": "20261118"}, US_ROW])
    got = provider(stub=stub).fetch_daily(
        US, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(got.bars) == 1
    assert got.bars[0].session_date == date(2026, 11, 19)


@pytest.mark.parametrize("bad", [
    {"access_token": "short", "expires_in": "86400"},
    {"access_token": "synthetic-token-123456", "expires_in": 10},
    {"access_token": "synthetic-token-123456", "expires_in": "bad"},
    {"access_token": "synthetic-token-123456"},
    {"expires_in": 86400},
])
def test_bad_token_never_reaches_quote_request(bad):
    class BadToken(StubKis):
        def __call__(self, method, path, headers, params=None, body=None):
            if path == TOKEN_PATH:
                self.calls.append((method, path))
                return bad
            return super().__call__(method, path, headers, params=params, body=body)
    stub = BadToken()
    with pytest.raises(KisReadOnlyError, match="KIS_TOKEN_RESPONSE_INVALID"):
        provider(stub=stub).fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(stub.calls) == 1


def test_invalid_quote_is_fail_closed_never_synthesized():
    stub = StubKis(rows=[{**KR_ROW, "stck_clpr": "0"}])
    with pytest.raises(MarketDataContractError):
        provider(stub=stub).fetch_daily(KR, date(2026, 11, 19), date(2026, 11, 19), "RAW")
    assert len(stub.calls) == 2


def test_secret_files_permissions_and_symlink_rejected(tmp_path):
    key = tmp_path / "appkey"
    secret = tmp_path / "appsecret"
    key.write_text("dummy-appkey\n")
    secret.write_text("dummy-appsecret\n")
    key.chmod(0o600)
    secret.chmod(0o600)
    creds = KisCredentials.from_private_files(str(key), str(secret))
    assert creds.appkey == "dummy-appkey"
    assert "dummy-appkey" not in repr(creds) and "dummy-appsecret" not in repr(creds)
    key.chmod(0o644)
    with pytest.raises(KisReadOnlyError, match="SECRET_FILE_PERMISSIONS"):
        KisCredentials.from_private_files(str(key), str(secret))
    key.chmod(0o600)
    link = tmp_path / "symlink"
    link.symlink_to(key)
    with pytest.raises(KisReadOnlyError, match="SECRET_FILE_UNAVAILABLE"):
        KisCredentials.from_private_files(str(link), str(secret))


def test_transport_rejects_every_nonquote_or_order_path_before_network():
    transport = KisHttpsTransport(timeout=3)
    for method, path in [
        ("POST", "/uapi/domestic-stock/v1/trading/order-cash"),
        ("GET", "/uapi/domestic-stock/v1/trading/inquire-balance"),
        ("GET", "/uapi/overseas-stock/v1/trading/order"),
        ("GET", "https://evil.example/take-token"),
        ("DELETE", KR_DAILY_PATH),
        ("GET", "/oauth2/tokenP"),
    ]:
        with pytest.raises(KisReadOnlyError, match="KIS_PATH_NOT_ALLOWED"):
            transport(method, path, headers={})


def test_no_db_or_frontend_hook_and_only_explicit_daily_and_current_paths():
    import inspect
    import app.kis_readonly as subject
    source = inspect.getsource(subject)
    assert "from app.database" not in source
    assert "create_engine" not in source
    assert "include_router" not in source
    assert "/trading/" not in subject.KR_DAILY_PATH
    assert "/trading/" not in subject.US_DAILY_PATH
    assert subject.ALLOWED_CALLS == frozenset({
        ("POST", TOKEN_PATH),
        ("GET", KR_DAILY_PATH), ("GET", US_DAILY_PATH),
        ("GET", KR_CURRENT_PATH), ("GET", US_CURRENT_PATH),
    })
