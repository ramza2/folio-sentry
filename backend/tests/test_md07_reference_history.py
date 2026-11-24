"""Synthetic, authenticated reference-history API tests; no provider I/O."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import portfolio_api, md07_reference_history as history
from app.main import app
from app.price_models import PriceBar

client = TestClient(app)


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setenv("FOLIOSENTRY_MD07_REFERENCE_HISTORY_DISPLAY_ENABLED", "yes")
    monkeypatch.setattr(history, "get_engine", portfolio_api.get_engine)


def tracked():
    headers = {"Origin": "http://testserver",
               "X-CSRF-Token": client.get("/api/v1/auth/me").json()["csrf_token"]}
    inst = client.post("/api/v1/instruments", headers=headers, json={
        "market": "KR", "exchange_mic": "XKRX", "symbol": "000001",
        "name": "Synthetic chart", "asset_type": "STOCK",
    })
    assert inst.status_code == 201
    row = client.post("/api/v1/tracked", headers=headers, json={
        "instrument_id": inst.json()["id"], "kind": "WATCH",
    })
    assert row.status_code == 201
    return UUID(inst.json()["id"]), row.json()["id"]


def path(id):
    return f"/api/v1/tracked/{id}/reference-history"


def test_disabled_does_not_open_storage(monkeypatch):
    monkeypatch.delenv("FOLIOSENTRY_MD07_REFERENCE_HISTORY_DISPLAY_ENABLED", raising=False)
    monkeypatch.setattr(history, "get_engine", lambda: pytest.fail("must not access history DB"))
    assert client.get("/api/v1/market-data/history-capabilities").json() == {
        "reference_history_enabled": False,
    }
    assert client.get(path(uuid4())).status_code == 503


@pytest.mark.no_auto_login
def test_anonymous_denied(enabled):
    assert client.get("/api/v1/market-data/history-capabilities").status_code == 401
    assert client.get(path(uuid4())).status_code == 401


def test_empty_range_missing(enabled):
    _, id = tracked()
    result = client.get(path(id) + "?days=30")
    assert result.status_code == 200
    assert result.headers["cache-control"] == "no-store"
    assert result.json()["bars"] == []
    assert result.json()["stored_rows"] == 0
    assert result.json()["status"] == "EMPTY"
    assert result.json()["latest_receipt"] is None
    assert client.get(path(id) + "?days=31").status_code == 422
    assert client.get(path(uuid4())).status_code == 404


def test_only_prior_raw_rows_in_range_sorted(enabled):
    inst, id = tracked()
    now = datetime.now(timezone.utc)
    local = now.astimezone(ZoneInfo("Asia/Seoul")).date()
    with Session(portfolio_api.get_engine()) as db, db.begin():
        for ago, basis in ((1, "RAW"), (3, "RAW"), (40, "RAW"), (2, "ADJUSTED"), (0, "RAW")):
            db.add(PriceBar(instrument_id=inst, timeframe="1d",
                session_date=local-timedelta(days=ago), price_basis=basis,
                open=Decimal("10"), high=Decimal("12"), low=Decimal("9"),
                close=Decimal("11"), volume=123, source="KIS",
                fetched_at=now, source_observed_at=None, is_final=False,
                quality_status="PARTIAL"))
    r = client.get(path(id) + "?days=30")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "STORED_REFERENCE"
    assert data["stored_rows"] == 2
    assert data["source"] == "KIS" and data["quality_status"] == "PARTIAL"
    assert data["price_basis"] == "RAW" and data["currency"] == "KRW"
    assert [b["session_date"] for b in data["bars"]] == [
        (local-timedelta(days=3)).isoformat(), (local-timedelta(days=1)).isoformat()]
    assert all(b["is_final"] is False for b in data["bars"])
    assert Decimal(data["bars"][0]["close"]) == Decimal("11")
    assert data["latest_session_date"] == data["bars"][-1]["session_date"]
    assert client.get(path(id) + "?days=90").json()["stored_rows"] == 3
