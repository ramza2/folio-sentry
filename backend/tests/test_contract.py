"""Contract tests are offline and never contact broker/news providers."""
from copy import deepcopy
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.contract import QuoteDTO, TrackedInstrumentDTO
from app.main import app

client = TestClient(app)


def test_overview_demo_contract() -> None:
    res = client.get("/api/v1/demo/overview")
    assert res.status_code == 200
    payload = res.json()
    assert payload["mode"] == "DEMO"
    assert "실제 시세" in payload["disclaimer"]
    assert payload["summary"]["registered_count"] == 3
    assert payload["summary"]["holding_count"] == 2
    assert payload["summary"]["watch_count"] == 1
    assert {x["instrument"]["market"] for x in payload["tracked"]} == {"KR", "US"}
    assert {x["instrument"]["asset_type"] for x in payload["tracked"]} == {"STOCK", "ETF"}
    assert all(x["quote"]["status"] in ("DEMO", "UNAVAILABLE") for x in payload["tracked"])
    assert all(n["publisher"] and n["url"] and n["published_at"] for n in payload["news"])
    assert all(s["state"] == "DEMO" for s in payload["signals"])
    assert all(s["strategy_version"] and s["reason"] for s in payload["signals"])
    assert all(x["quantity"] is None for x in payload["tracked"] if x["kind"] == "WATCH")


def test_decimal_values_are_strings() -> None:
    payload = client.get("/api/v1/demo/overview").json()
    assert payload["tracked"][0]["quantity"] == "10"
    assert payload["tracked"][0]["market_value"] == "720000"
    assert payload["tracked"][1]["quote"]["close"] == "120.50"
    assert payload["summary"]["valuation_by_currency"] == {"KRW": "720000", "USD": "361.50"}


def test_unavailable_quote_does_not_fake_zero() -> None:
    payload = client.get("/api/v1/demo/overview").json()
    watch = next(x for x in payload["tracked"] if x["kind"] == "WATCH")
    assert watch["quote"]["close"] is None
    assert watch["quote"]["as_of"] is None
    assert watch["market_value"] is None
    assert watch["unrealized_pnl"] is None


def test_unavailable_quote_rejects_prices() -> None:
    with pytest.raises(ValidationError):
        QuoteDTO(status="UNAVAILABLE", close=Decimal("1"), change_pct=None, as_of=None, source=None)


def test_contract_openapi_is_exposed() -> None:
    openapi = client.get("/openapi.json").json()
    assert "/api/v1/demo/overview" in openapi["paths"]
    assert "DemoOverviewDTO" in openapi["components"]["schemas"]


def test_holding_invariants() -> None:
    payload = client.get("/api/v1/demo/overview").json()
    demo = deepcopy(payload["tracked"][0])
    demo["kind"] = "WATCH"
    with pytest.raises(ValidationError):
        TrackedInstrumentDTO.model_validate(demo)

    holding = deepcopy(payload["tracked"][0])
    holding["average_cost"] = "-1"
    with pytest.raises(ValidationError):
        TrackedInstrumentDTO.model_validate(holding)
