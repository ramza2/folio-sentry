from fastapi.testclient import TestClient

from app import main

client = TestClient(main.app)


def test_live() -> None:
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "folio-sentry"}


def test_demo_metadata_only() -> None:
    response = client.get("/api/v1/demo/instruments")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "demo"
    assert {item["market"] for item in data["instruments"]} == {"KR", "US"}
    assert all(item["is_demo"] is True for item in data["instruments"])
    assert all("price" not in item for item in data["instruments"])


def test_ready_database_up(monkeypatch) -> None:
    monkeypatch.setattr(main, "check_database", lambda: True)
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


def test_ready_database_down(monkeypatch) -> None:
    monkeypatch.setattr(main, "check_database", lambda: False)
    response = client.get("/api/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
