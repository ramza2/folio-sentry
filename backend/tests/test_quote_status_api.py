"""MD-04C2 status-only GET, synthetic SQLite and single-owner auth only."""
from uuid import uuid4

import pytest
from fastapi.exceptions import ResponseValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app import portfolio_api
from app.main import app
from conftest import TEST_PASSWORD, TEST_USERNAME

client = TestClient(app)
BASE = "/api/v1/tracked"


def add_tracked(market, exchange, symbol, kind):
    csrf = client.get("/api/v1/auth/me").json()["csrf_token"]
    registered = client.post("/api/v1/instruments", json={
        "market": market, "exchange_mic": exchange, "symbol": symbol,
        "name": "Synthetic offline instrument", "asset_type": "STOCK",
    }, headers={"Origin": "http://testserver", "X-CSRF-Token": csrf})
    assert registered.status_code == 201, registered.text
    position = client.post(BASE, json={
        "instrument_id": registered.json()["id"], "kind": kind,
        **({"quantity": "2", "average_cost": "100"} if kind == "HOLDING" else {}),
    }, headers={"Origin": "http://testserver", "X-CSRF-Token": csrf})
    assert position.status_code == 201, position.text
    return position.json()


@pytest.mark.parametrize("market,exchange,symbol,kind", [
    ("KR", "XKRX", "005930", "HOLDING"),
    ("KR", "XKOS", "000001", "WATCH"),
    ("US", "XNAS", "AAPL", "HOLDING"),
    ("US", "XNYS", "IBM", "WATCH"),
    ("US", "XASE", "SPY", "WATCH"),
])
def test_authenticated_status_only_contract_is_price_free(market, exchange, symbol, kind):
    row = add_tracked(market, exchange, symbol, kind)
    response = client.get(f"{BASE}/{row['id']}/quote-status")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["vary"] == "Cookie"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.json() == {
        "tracked_id": row["id"],
        "quote": {
            "status": "UNAVAILABLE", "close": None,
            "change_pct": None, "as_of": None, "source": None,
        },
    }
    # This endpoint cannot expose holdings, synthetic price, position, OHLCV,
    # KIS provenance, or finality even for owner-authenticated requests.
    body = response.text
    assert all(value not in body for value in (
        "quantity", "average_cost", "market_value", "unrealized_pnl",
        "is_final", "price_basis", "fetched_at", "volume", "DEMO",
    ))


def test_no_unknown_tracked_id_and_malformed_path_is_not_found():
    assert client.get(f"{BASE}/{uuid4()}/quote-status").status_code == 404
    assert client.get(f"{BASE}/not-a-uuid/quote-status").status_code == 422


@pytest.mark.no_auto_login
def test_new_endpoint_inherits_mandatory_single_owner_auth():
    path = f"{BASE}/{uuid4()}/quote-status"
    first = client.get(path)
    assert first.status_code == 401
    assert first.json()["error"]["code"] == "AUTH_REQUIRED"
    login = client.post("/api/v1/auth/login", json={
        "username": TEST_USERNAME, "password": TEST_PASSWORD,
    }, headers={"Origin": "http://testserver"})
    assert login.status_code == 200
    assert client.get(path).status_code == 404
    csrf = login.json()["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    }).status_code == 200
    assert client.get(path).status_code == 401


def test_outage_never_falls_back_to_mock_or_available_price(monkeypatch):
    row = add_tracked("KR", "XKRX", "005930", "HOLDING")

    def synthetic_outage():
        raise SQLAlchemyError("synthetic storage failure")

    monkeypatch.setattr(portfolio_api, "get_engine", synthetic_outage)
    result = client.get(f"{BASE}/{row['id']}/quote-status")
    assert result.status_code == 503
    assert result.json()["error"]["code"] == "PORTFOLIO_DATABASE_UNAVAILABLE"
    assert "quote" not in result.json()
    assert "105" not in result.text


@pytest.mark.parametrize("malicious", [
    {"status": "UNFINALIZED", "close": None, "change_pct": None,
     "as_of": None, "source": None},
    {"status": "UNAVAILABLE", "close": "105", "change_pct": None,
     "as_of": None, "source": None},
    {"status": "UNAVAILABLE", "close": None, "change_pct": None,
     "as_of": None, "source": None, "is_final": True},
])
def test_response_model_fails_closed_if_unverified_adapter_changes(monkeypatch, malicious):
    row = add_tracked("KR", "XKRX", "005930", "WATCH")
    monkeypatch.setattr(portfolio_api, "masked_quote_from_finality", lambda _report: malicious)
    with pytest.raises(ResponseValidationError):
        client.get(f"{BASE}/{row['id']}/quote-status")


def test_route_openapi_schema_is_explicit_status_only():
    spec = get_openapi(title="MD04C2 isolated test", version="1", routes=app.routes)
    route = spec["paths"]["/api/v1/tracked/{tracked_id}/quote-status"]
    assert set(route) == {"get"}
    schema = spec["components"]["schemas"]["HiddenQuoteStatusDTO"]
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]) == {"status", "close", "change_pct", "as_of", "source"}
    assert schema["properties"]["status"]["const"] == "UNAVAILABLE"
