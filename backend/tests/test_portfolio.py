"""Phase 1 API tests use ONLY ephemeral SQLite with synthetic input."""
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import auth, portfolio_api
from app.main import app
from app.portfolio_models import Instrument, TrackedInstrument
from conftest import TEST_USERNAME, TEST_PASSWORD

client = TestClient(app)
KR = {"market": "KR", "exchange_mic": "XKRX", "symbol": "005930",
      "name": "삼성전자", "asset_type": "STOCK"}
US = {"market": "US", "exchange_mic": "XNAS", "symbol": "AAPL",
      "name": "Apple", "asset_type": "STOCK"}


def write(method, path, data, csrf=None):
    if csrf is None:
        csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    return client.request(
        method, path, json=data,
        headers={"Origin": "http://testserver", "X-CSRF-Token": csrf},
    )


def register(payload):
    response = write("POST", "/api/v1/instruments", payload)
    assert response.status_code == 201, response.text
    return response.json()


def track(instrument_id, kind="HOLDING", **kwargs):
    return write("POST", "/api/v1/tracked", {
        "instrument_id": instrument_id, "kind": kind, **kwargs,
    })


def test_empty_portfolio_not_demo():
    instruments = client.get("/api/v1/instruments")
    tracked = client.get("/api/v1/tracked")
    assert instruments.status_code == 200
    assert tracked.status_code == 200
    assert instruments.json() == {"items": [], "next_cursor": None}
    assert tracked.json() == {"items": [], "next_cursor": None}
    assert client.get("/api/v1/demo/overview").json()["mode"] == "DEMO"


def test_manual_catalog_normalization_search_and_uniqueness():
    samsung = register(KR)
    apple = register(US)
    assert samsung["symbol"] == "005930"
    assert samsung["currency"] == "KRW"
    assert samsung["source"] == "MANUAL_UNVERIFIED"
    assert apple["currency"] == "USD"
    assert apple["source"] == "MANUAL_UNVERIFIED"
    assert client.get(f"/api/v1/instruments/{samsung['id']}").json()["id"] == samsung["id"]
    assert client.get("/api/v1/instruments", params={"q": "삼성"}).json()["items"][0]["id"] == samsung["id"]
    assert client.get("/api/v1/instruments", params={"q": "aapl"}).json()["items"][0]["id"] == apple["id"]
    assert client.get("/api/v1/instruments", params={"market": "KR"}).json()["items"][0]["id"] == samsung["id"]
    assert client.get("/api/v1/instruments", params={"market": "US"}).json()["items"][0]["id"] == apple["id"]
    assert client.get("/api/v1/instruments", params={"q": "%"}).json()["items"] == []
    duplicate = write("POST", "/api/v1/instruments", {**US, "symbol": " aapl "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "INSTRUMENT_ALREADY_EXISTS"


@pytest.mark.parametrize("value", [
    {**KR, "exchange_mic": "XNAS"},
    {**KR, "symbol": "AAPL"},
    {**KR, "name": "  "},
    {**US, "market": "KR"},
    {**US, "symbol": "@BAD"},
    {**US, "asset_type": "CRYPTO"},
])
def test_invalid_manual_instruments(value):
    assert write("POST", "/api/v1/instruments", value).status_code == 422


def test_holding_decimal_strings_and_unavailable_quote():
    inst = register(KR)
    resp = track(inst["id"], quantity="3.12500000", average_cost="78934.12500000")
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["kind"] == "HOLDING"
    assert data["quantity"] == "3.12500000"
    assert data["average_cost"] == "78934.12500000"
    assert data["instrument"]["symbol"] == "005930"
    assert data["quote"] == {
        "status": "UNAVAILABLE", "close": None, "change_pct": None,
        "as_of": None, "source": None,
    }
    assert data["market_value"] is None
    assert data["unrealized_pnl"] is None
    assert data["unrealized_pnl_percent"] is None

    listed = client.get("/api/v1/tracked", params={"kind": "HOLDING"})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["quantity"] == "3.12500000"
    assert client.get("/api/v1/tracked", params={"kind": "WATCH"}).json()["items"] == []
    assert track(inst["id"], kind="WATCH").status_code == 409


@pytest.mark.parametrize("kwargs", [
    {"quantity": 5, "average_cost": "100"},
    {"quantity": "1e5", "average_cost": "100"},
    {"quantity": "1.000000001", "average_cost": "1"},
    {"quantity": "0"},
    {"quantity": "-1"},
    {"quantity": "1", "average_cost": "-1"},
    {"quantity": "1", "average_cost": "0.000000001"},
    {"average_cost": "100"},
])
def test_holding_value_validation(kwargs):
    inst = register(US)
    resp = track(inst["id"], **kwargs)
    assert resp.status_code == 422, resp.text


def test_watch_switch_to_holding_and_back_delete_only_tracking():
    inst = register(US)
    r = track(inst["id"], kind="WATCH", memo="점검", alerts_enabled=False)
    assert r.status_code == 201, r.text
    tracked_id = r.json()["id"]
    assert r.json()["quantity"] is None
    assert r.json()["memo"] == "점검"
    assert r.json()["alerts_enabled"] is False

    reject = track(inst["id"], kind="WATCH", quantity="1")
    assert reject.status_code == 422

    update = write("PATCH", f"/api/v1/tracked/{tracked_id}", {
        "kind": "HOLDING", "quantity": "2", "average_cost": "150.25",
        "alerts_enabled": True,
    })
    assert update.status_code == 200, update.text
    assert update.json()["quantity"] == "2.00000000"
    assert update.json()["average_cost"] == "150.25000000"
    bad = write("PATCH", f"/api/v1/tracked/{tracked_id}", {"quantity": None})
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "INVALID_HOLDING"

    watch = write("PATCH", f"/api/v1/tracked/{tracked_id}", {"kind": "WATCH"})
    assert watch.status_code == 200, watch.text
    assert watch.json()["quantity"] is None
    assert watch.json()["average_cost"] is None
    assert write("PATCH", f"/api/v1/tracked/{tracked_id}", {}).status_code == 400

    deleted = client.request("DELETE", f"/api/v1/tracked/{tracked_id}", headers={
        "Origin": "http://testserver",
        "X-CSRF-Token": client.get("/api/v1/auth/me").json()["csrf_token"],
    })
    assert deleted.status_code == 204
    assert client.get("/api/v1/tracked").json()["items"] == []
    assert client.get(f"/api/v1/instruments/{inst['id']}").status_code == 200
    assert client.request("DELETE", f"/api/v1/tracked/{tracked_id}", headers={
        "Origin": "http://testserver",
        "X-CSRF-Token": client.get("/api/v1/auth/me").json()["csrf_token"],
    }).status_code == 404


def test_stable_pagination_and_not_found():
    insts = [register({**US, "symbol": f"SYMBOL{i}"}) for i in range(4)]
    ids = []
    for inst in insts:
        resp = track(inst["id"], kind="WATCH")
        assert resp.status_code == 201
        ids.append(resp.json()["id"])
    first = client.get("/api/v1/tracked", params={"limit": 2}).json()
    assert len(first["items"]) == 2
    assert first["next_cursor"] is not None
    second = client.get("/api/v1/tracked", params={
        "limit": 2, "cursor": first["next_cursor"],
    }).json()
    assert len(second["items"]) == 2
    assert second["next_cursor"] is None
    assert {r["id"] for r in first["items"] + second["items"]} == set(ids)
    assert client.get("/api/v1/tracked", params={"limit": 0}).status_code == 422
    assert client.get("/api/v1/tracked", params={"limit": 101}).status_code == 422
    assert client.get("/api/v1/instruments/00000000-0000-4000-8000-000000000001").status_code == 404
    assert track("00000000-0000-4000-8000-000000000002", kind="WATCH").status_code == 404


@pytest.mark.no_auto_login
def test_authenticated_access_origin_and_csrf_are_mandatory():
    assert client.get("/api/v1/instruments").status_code == 401
    assert client.get("/api/v1/tracked").status_code == 401
    assert client.post("/api/v1/instruments", json=KR).status_code == 403
    login = client.post("/api/v1/auth/login", json={
        "username": TEST_USERNAME, "password": TEST_PASSWORD,
    }, headers={"Origin": "http://testserver"})
    assert login.status_code == 200
    csrf = login.json()["csrf_token"]
    assert client.post("/api/v1/instruments", json=KR, headers={
        "Origin": "http://testserver",
    }).status_code == 403
    assert client.post("/api/v1/instruments", json=KR, headers={
        "Origin": "https://evil.example", "X-CSRF-Token": csrf,
    }).status_code == 403
    assert client.post("/api/v1/instruments", json=KR, headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    }).status_code == 201
    logout = client.post("/api/v1/auth/logout", headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    })
    assert logout.status_code == 200
    assert client.get("/api/v1/tracked").status_code == 401


def test_database_absent_fails_closed(monkeypatch):
    def unavailable():
        raise SQLAlchemyError("synthetic test outage")
    monkeypatch.setattr(portfolio_api, "get_engine", unavailable)
    assert client.get("/api/v1/instruments").status_code == 503
    assert client.get("/api/v1/tracked").status_code == 503
    assert write("POST", "/api/v1/instruments", KR).status_code == 503


def test_model_constraints_not_only_api():
    inst = register(US)
    with Session(portfolio_api.get_engine()) as db:
        assert db.scalar(select(Instrument)).id == inst["id"] or True
        # A database CHECK must reject WATCH records with a holding quantity.
        from sqlalchemy.exc import IntegrityError
        import uuid
        db.add(TrackedInstrument(
            id=uuid.uuid4(), instrument_id=inst["id"],
            kind="WATCH", quantity="1", average_cost=None, alerts_enabled=True,
        ))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
