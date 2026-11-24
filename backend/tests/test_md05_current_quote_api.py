"""MD05B synthetic current-quote HTTP tests, no real KIS or MiniPC network."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app import md05_current_quote as md05b, portfolio_api
from app.kis_current import CurrentQuoteCandidate
from app.main import app
from conftest import TEST_PASSWORD, TEST_USERNAME

client = TestClient(app)
FLAGS = (
    "FOLIOSENTRY_MD05_CURRENT_READ_ENABLED",
    "FOLIOSENTRY_MD05_CURRENT_DISPLAY_ENABLED",
)
PATH = "/api/v1/tracked"


@pytest.fixture(autouse=True)
def isolated_current(monkeypatch):
    monkeypatch.setattr(md05b, "get_engine", lambda: portfolio_api.get_engine())
    for flag in (*FLAGS, "FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED",
                 "FOLIOSENTRY_MD05_VALUATION_DISPLAY_ENABLED"):
        monkeypatch.delenv(flag, raising=False)
    for field in (
        "FOLIOSENTRY_KIS_APPKEY_FILE", "FOLIOSENTRY_KIS_APPSECRET_FILE",
        "FOLIOSENTRY_KIS_SHARED_STATE_DIR",
    ):
        monkeypatch.delenv(field, raising=False)


def enable(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "yes")


def create_tracked(market="KR", exchange="XKRX", symbol="005930"):
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}
    inst = client.post("/api/v1/instruments", headers=headers, json={
        "market": market, "exchange_mic": exchange, "symbol": symbol,
        "name": "MD05B synthetic-only", "asset_type": "STOCK",
    })
    assert inst.status_code == 201, inst.text
    position = client.post(PATH, headers=headers, json={
        "instrument_id": inst.json()["id"], "kind": "HOLDING",
        "quantity": "2", "average_cost": "100",
    })
    assert position.status_code == 201, position.text
    return position.json()["id"], csrf


def post(tracked_id, csrf, headers=None):
    if headers is None:
        headers = {"Origin": "http://testserver", "X-CSRF-Token": csrf}
    return client.post(f"{PATH}/{tracked_id}/current-quote", headers=headers)


class FakeCurrent:
    def __init__(self, *, price=Decimal("105.2500"), stale=False):
        self.calls = []
        self.price = price
        self.stale = stale

    def fetch_current(self, identity):
        self.calls.append(identity)
        return CurrentQuoteCandidate(
            instrument=identity, price=self.price,
            fetched_at=(
                None if self.price is None else
                datetime.now(timezone.utc) - timedelta(
                    minutes=3 if self.stale else 0
                )
            ),
        )


@pytest.mark.parametrize("flags", [
    (), (FLAGS[0],), (FLAGS[1],),
])
def test_default_disabled_never_accesses_db_secrets_or_kis(monkeypatch, flags):
    for flag in flags:
        monkeypatch.setenv(flag, "yes")
    def forbid():
        raise AssertionError("No KIS/DB while feature is disabled")
    monkeypatch.setattr(md05b, "_provider", forbid)
    monkeypatch.setattr(md05b, "get_engine", forbid)
    capability = client.get("/api/v1/market-data/current-capabilities")
    assert capability.status_code == 200
    assert capability.json() == {"manual_current_quote_enabled": False}
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    result = post(uuid4(), csrf)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "MD05B_MANUAL_CURRENT_DISABLED"
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.no_auto_login
def test_single_owner_auth_protects_capability_and_current_query(monkeypatch):
    enable(monkeypatch)
    def forbid():
        raise AssertionError("Unauthenticated request reached DB/provider")
    monkeypatch.setattr(md05b, "_provider", forbid)
    monkeypatch.setattr(md05b, "get_engine", forbid)
    assert client.get("/api/v1/market-data/current-capabilities").status_code == 401
    assert client.post(
        f"{PATH}/{uuid4()}/current-quote",
        headers={"Origin": "http://testserver"},
    ).status_code == 401


def test_missing_csrf_or_bad_origin_cannot_call_provider(monkeypatch):
    ident, csrf = create_tracked()
    enable(monkeypatch)
    monkeypatch.setattr(md05b, "_provider", lambda: (_ for _ in ()).throw(
        AssertionError("must not call provider")))
    assert post(ident, csrf, {"Origin": "http://testserver"}).status_code == 403
    assert post(ident, csrf, {
        "Origin": "https://evil.example", "X-CSRF-Token": csrf,
    }).status_code == 403
    assert client.get(f"{PATH}/{ident}/current-quote").status_code == 405


@pytest.mark.parametrize("market,exchange,symbol", [
    ("KR", "XKRX", "005930"),
    ("KR", "XKOS", "000001"),
    ("US", "XNAS", "AAPL"),
    ("US", "XNYS", "IBM"),
    ("US", "XASE", "SPY"),
])
def test_registered_current_quote_is_separate_and_never_claims_realtime(
    monkeypatch, market, exchange, symbol,
):
    tracked, csrf = create_tracked(market, exchange, symbol)
    enable(monkeypatch)
    provider = FakeCurrent()
    monkeypatch.setattr(md05b, "_provider", lambda: provider)
    cap = client.get("/api/v1/market-data/current-capabilities")
    assert cap.json() == {"manual_current_quote_enabled": True}
    result = post(tracked, csrf)
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["vary"] == "Cookie"
    assert result.headers["x-content-type-options"] == "nosniff"
    body = result.json()
    assert set(body) == {"tracked_id", "current_quote"}
    assert body["tracked_id"] == tracked
    q = body["current_quote"]
    assert set(q) == {
        "status", "price", "fetched_at", "currency", "source",
        "provider_time_status", "delay_status", "market_session",
        "realtime_verified", "is_final",
    }
    assert q["status"] == "RECEIVED"
    assert q["price"] == "105.2500"
    assert q["source"] == "KIS"
    assert q["currency"] == ("KRW" if market == "KR" else "USD")
    assert q["provider_time_status"] == "UNKNOWN"
    assert q["delay_status"] == "UNKNOWN"
    assert q["market_session"] == "UNKNOWN"
    assert q["realtime_verified"] is False
    assert q["is_final"] is False
    assert q["fetched_at"].endswith("Z") or q["fetched_at"].endswith("+00:00")
    assert len(provider.calls) == 1
    assert provider.calls[0].exchange_mic == exchange
    assert provider.calls[0].symbol == symbol
    assert all(x not in result.text for x in (
        "average_cost", "quantity", "market_value",
        "unrealized_pnl", "appkey", "appsecret", "DEMO",
    ))
    status = client.get(f"{PATH}/{tracked}/quote-status").json()["quote"]
    assert status["status"] == "UNAVAILABLE"
    assert status["close"] is None
    stored = client.get(f"{PATH}?limit=10").json()["items"][0]
    assert stored["quote"]["close"] is None
    assert stored["market_value"] is None
    assert stored["unrealized_pnl"] is None


def test_no_reported_current_price_does_not_forge_one(monkeypatch):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    monkeypatch.setattr(md05b, "_provider", lambda: FakeCurrent(price=None))
    res = post(tracked, csrf)
    assert res.status_code == 200
    quote = res.json()["current_quote"]
    assert quote["status"] == "UNAVAILABLE"
    assert quote["price"] is None
    assert quote["fetched_at"] is None
    assert quote["source"] is None
    assert quote["is_final"] is False


def test_unknown_tracked_is_404_without_provider(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(md05b, "_provider", lambda: (_ for _ in ()).throw(
        AssertionError("no external call for unknown registered id")))
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    assert post(uuid4(), csrf).status_code == 404


@pytest.mark.parametrize("change", [
    {"is_final": True},
    {"realtime_verified": True},
    {"provider_observed_at": datetime.now(timezone.utc)},
    {"source": "DEMO"},
    {"price": Decimal("-1")},
    {"price": Decimal("NaN")},
    {"price": Decimal("0")},
    {"fetched_at": datetime.now(timezone.utc) + timedelta(days=1)},
    {"fetched_at": datetime(2026, 11, 24, 1, 0)},
])
def test_forged_current_payload_never_exposes_price(monkeypatch, change):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    class Forged:
        def fetch_current(self, identity):
            return replace(FakeCurrent().fetch_current(identity), **change)
    monkeypatch.setattr(md05b, "_provider", lambda: Forged())
    result = post(tracked, csrf)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "MD05B_PROVIDER_UNAVAILABLE"
    assert "105.2500" not in result.text


def test_stale_receipt_does_not_forge_fresh_read(monkeypatch):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    monkeypatch.setattr(md05b, "_provider", lambda: FakeCurrent(stale=True))
    assert post(tracked, csrf).status_code == 503


def test_upstream_exception_body_and_token_are_never_rendered(monkeypatch):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    class Failed:
        def fetch_current(self, identity):
            raise RuntimeError("bearer-secret-0123456789 synthetic")
    monkeypatch.setattr(md05b, "_provider", lambda: Failed())
    response = post(tracked, csrf)
    assert response.status_code == 503
    assert "bearer-secret" not in response.text
    assert "synthetic" not in response.text


def test_new_token_issue_is_off_even_with_read_display_flags(monkeypatch):
    enable(monkeypatch)
    assert md05b._flag("FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED") is False
    for name, value in (
        ("FOLIOSENTRY_KIS_APPKEY_FILE", "/missing/md05b-key"),
        ("FOLIOSENTRY_KIS_APPSECRET_FILE", "/missing/md05b-secret"),
        ("FOLIOSENTRY_KIS_SHARED_STATE_DIR", "/missing/md05b-shared"),
    ):
        monkeypatch.setenv(name, value)
    with pytest.raises(Exception):
        md05b._provider()  # no real secret, no transport call


def test_md05a_daily_gate_remains_independent(monkeypatch):
    enable(monkeypatch)
    from app import md05_manual_reference
    assert md05_manual_reference._enabled() is False


@pytest.mark.parametrize("flags,expected", [
    ((), False),
    (FLAGS, False),
    (("FOLIOSENTRY_MD05_VALUATION_DISPLAY_ENABLED",), False),
    ((*FLAGS, "FOLIOSENTRY_MD05_VALUATION_DISPLAY_ENABLED"), True),
])
def test_valuation_capability_requires_all_flags_and_no_provider_access(monkeypatch, flags, expected):
    for flag in flags:
        monkeypatch.setenv(flag, "yes")
    def forbid():
        raise AssertionError("capability must not reach portfolio DB or KIS")
    monkeypatch.setattr(md05b, "_provider", forbid)
    monkeypatch.setattr(md05b, "get_engine", forbid)
    res = client.get("/api/v1/market-data/valuation-capabilities")
    assert res.status_code == 200
    assert res.json() == {"reference_valuation_enabled": expected}
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.no_auto_login
def test_valuation_capability_is_owner_only(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setenv("FOLIOSENTRY_MD05_VALUATION_DISPLAY_ENABLED", "yes")
    assert client.get("/api/v1/market-data/valuation-capabilities").status_code == 401
