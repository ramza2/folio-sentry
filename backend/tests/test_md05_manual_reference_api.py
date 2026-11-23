"""MD05A isolated owner-auth HTTP integration; NO real KIS transport/DB.

CI uses SQLite synthetic instruments and pure in-memory quote provider.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app import md05_manual_reference as md05, portfolio_api
from app.main import app
from app.market_data import DailyBarBatch, DailyBarCandidate
from conftest import TEST_USERNAME, TEST_PASSWORD

client = TestClient(app)
BASE = "/api/v1/tracked"
FLAGS = ("FOLIOSENTRY_MD05_MANUAL_READ_ENABLED",
         "FOLIOSENTRY_MD05_REFERENCE_DISPLAY_ENABLED")


@pytest.fixture(autouse=True)
def isolate_md05(monkeypatch):
    monkeypatch.setattr(md05, "get_engine", lambda: portfolio_api.get_engine())
    for flag in (*FLAGS, "FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED"):
        monkeypatch.delenv(flag, raising=False)
    monkeypatch.delenv("FOLIOSENTRY_KIS_APPKEY_FILE", raising=False)
    monkeypatch.delenv("FOLIOSENTRY_KIS_APPSECRET_FILE", raising=False)
    monkeypatch.delenv("FOLIOSENTRY_KIS_SHARED_STATE_DIR", raising=False)


def enable(monkeypatch):
    for flag in FLAGS:
        monkeypatch.setenv(flag, "yes")


def create_tracked(market="KR", exchange="XKRX", symbol="005930"):
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    inst = client.post("/api/v1/instruments", headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    }, json={
        "market": market, "exchange_mic": exchange, "symbol": symbol,
        "name": "MD05 synthetic instrument", "asset_type": "STOCK",
    })
    assert inst.status_code == 201
    item = client.post(BASE, headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    }, json={"instrument_id": inst.json()["id"], "kind": "HOLDING",
             "quantity": "2", "average_cost": "100"})
    assert item.status_code == 201
    return item.json()["id"], csrf


def request(tracked_id, csrf, headers=None):
    return client.post(f"{BASE}/{tracked_id}/daily-reference", headers=(
        headers if headers is not None else {
            "Origin": "http://testserver", "X-CSRF-Token": csrf,
        }
    ))


def fake_bar(identity, end, *, days_old=0, close=Decimal("105.25")):
    return DailyBarCandidate(
        session_date=end - timedelta(days=days_old),
        open=Decimal("100"), high=Decimal("111"),
        low=Decimal("90"), close=close, volume=12345,
        price_basis="RAW", source="KIS",
        fetched_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )


class FakeProvider:
    def __init__(self, result="REFERENCE"):
        self.calls = []
        self.result = result

    def fetch_daily(self, identity, start, end, basis):
        self.calls.append((identity, start, end, basis))
        rows = (
            () if self.result == "EMPTY" else
            (fake_bar(identity, end, days_old=9 if self.result == "STALE" else 1),)
        )
        return DailyBarBatch(instrument=identity, bars=rows)


@pytest.mark.parametrize("flags", [
    (), (FLAGS[0],), (FLAGS[1],),
])
def test_default_disabled_never_reads_secrets_or_db_or_provider(monkeypatch, flags):
    for flag in flags:
        monkeypatch.setenv(flag, "yes")
    def forbid():
        raise AssertionError("Never read KIS credentials or DB when disabled")
    monkeypatch.setattr(md05, "_provider", forbid)
    monkeypatch.setattr(md05, "get_engine", forbid)
    assert client.get("/api/v1/market-data/capabilities").json() == {
        "manual_daily_reference_enabled": False,
    }
    result = request(uuid4(), client.get("/api/v1/auth/me").json()["csrf_token"])
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "MD05_MANUAL_REFERENCE_DISABLED"
    assert result.headers["cache-control"] == "no-store"


@pytest.mark.no_auto_login
def test_auth_required_before_any_capability_or_provider(monkeypatch):
    enable(monkeypatch)
    def forbid():
        raise AssertionError("Unauthenticated request cannot access DB/secret")
    monkeypatch.setattr(md05, "_provider", forbid)
    monkeypatch.setattr(md05, "get_engine", forbid)
    assert client.get("/api/v1/market-data/capabilities").status_code == 401
    assert client.post(f"{BASE}/{uuid4()}/daily-reference").status_code == 401


def test_bad_csrf_and_origin_do_not_attempt_kis(monkeypatch):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    monkeypatch.setattr(md05, "_provider", lambda: (_ for _ in ()).throw(
        AssertionError("guard must stop request")))
    assert request(tracked, csrf, {"Origin": "http://testserver"}).status_code == 403
    assert request(tracked, csrf, {"Origin": "https://evil.example",
                                  "X-CSRF-Token": csrf}).status_code == 403
    assert client.get(f"{BASE}/{tracked}/daily-reference").status_code == 405


@pytest.mark.parametrize("market,exchange,symbol", [
    ("KR", "XKRX", "005930"),
    ("KR", "XKOS", "000001"),
    ("US", "XNAS", "AAPL"),
    ("US", "XNYS", "IBM"),
    ("US", "XASE", "SPY"),
])
def test_manual_reference_response_is_separate_from_holdings_and_nonfinal(
    monkeypatch, market, exchange, symbol,
):
    tracked, csrf = create_tracked(market, exchange, symbol)
    enable(monkeypatch)
    provider = FakeProvider()
    monkeypatch.setattr(md05, "_provider", lambda: provider)
    assert client.get("/api/v1/market-data/capabilities").json() == {
        "manual_daily_reference_enabled": True,
    }
    result = request(tracked, csrf)
    assert result.status_code == 200, result.text
    assert result.headers["cache-control"] == "no-store"
    assert result.headers["vary"] == "Cookie"
    assert result.headers["x-content-type-options"] == "nosniff"
    value = result.json()
    assert set(value) == {"tracked_id", "reference"}
    assert value["tracked_id"] == tracked
    ref = value["reference"]
    assert set(ref) == {
        "status", "close", "session_date", "fetched_at",
        "source", "price_basis", "currency", "is_final",
    }
    assert ref["status"] == "REFERENCE"
    assert ref["close"] == "105.25"
    assert ref["source"] == "KIS"
    assert ref["price_basis"] == "RAW"
    assert ref["currency"] == ("KRW" if market == "KR" else "USD")
    assert ref["is_final"] is False
    assert ref["fetched_at"].endswith("Z") or ref["fetched_at"].endswith("+00:00")
    assert len(provider.calls) == 1
    identity, start, end, basis = provider.calls[0]
    assert identity.exchange_mic == exchange
    assert identity.symbol == symbol
    assert basis == "RAW"
    assert (end - start).days == 14
    assert end == (datetime.now(timezone.utc)
                   .astimezone(identity.exchange_timezone).date()
                   - timedelta(days=1))
    assert all(word not in result.text for word in (
        "average_cost", "quantity", "market_value",
        "unrealized_pnl", "appkey", "appsecret", "DEMO",
    ))
    # Existing API remains a status-only GET, not retrofitted to hold prices.
    hidden = client.get(f"{BASE}/{tracked}/quote-status").json()["quote"]
    assert hidden["status"] == "UNAVAILABLE"
    assert hidden["close"] is None


@pytest.mark.parametrize("kind,expected", [
    ("EMPTY", "UNAVAILABLE"), ("STALE", "STALE"),
])
def test_missing_or_stale_close_never_displays_a_price(monkeypatch, kind, expected):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    monkeypatch.setattr(md05, "_provider", lambda: FakeProvider(kind))
    result = request(tracked, csrf)
    assert result.status_code == 200
    reference = result.json()["reference"]
    assert reference["status"] == expected
    assert reference["close"] is None
    assert reference["is_final"] is False


def test_unknown_instrument_does_not_call_provider(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setattr(md05, "_provider", lambda: (_ for _ in ()).throw(
        AssertionError("no provider when no tracked row")))
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    assert request(uuid4(), csrf).status_code == 404


@pytest.mark.parametrize("tamper", [
    {"is_final": True}, {"source_observed_at": datetime.now(timezone.utc)},
    {"price_basis": "ADJUSTED"}, {"source": "DEMO"},
    {"close": Decimal("-1")}, {"close": Decimal("NaN")},
])
def test_forged_daily_bar_is_denied_without_price_leak(monkeypatch, tamper):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    class Forged:
        def fetch_daily(self, identity, start, end, basis):
            return DailyBarBatch(
                instrument=identity,
                bars=(replace(fake_bar(identity, end), **tamper),),
            )
    monkeypatch.setattr(md05, "_provider", lambda: Forged())
    result = request(tracked, csrf)
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "MD05_PROVIDER_UNAVAILABLE"
    assert "105.25" not in result.text


def test_unexpected_upstream_error_redacted(monkeypatch):
    tracked, csrf = create_tracked()
    enable(monkeypatch)
    class Crash:
        def fetch_daily(self, *args):
            raise RuntimeError("synthetic TOKEN=do-not-echo")
    monkeypatch.setattr(md05, "_provider", lambda: Crash())
    result = request(tracked, csrf)
    assert result.status_code == 503
    assert "do-not-echo" not in result.text
    assert "TOKEN" not in result.text


def test_real_provider_defaults_to_denied_token_issuance(monkeypatch):
    enable(monkeypatch)
    for name, value in (
        ("FOLIOSENTRY_KIS_APPKEY_FILE", "/missing/md05-key"),
        ("FOLIOSENTRY_KIS_APPSECRET_FILE", "/missing/md05-secret"),
        ("FOLIOSENTRY_KIS_SHARED_STATE_DIR", "/missing/md05-shared"),
    ):
        monkeypatch.setenv(name, value)
    with pytest.raises(Exception):
        md05._provider()  # missing files, never issues token or HTTP
    assert md05._flag("FOLIOSENTRY_MD05_NEW_TOKEN_ISSUE_ALLOWED") is False
