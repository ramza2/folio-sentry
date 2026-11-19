"""Security gates. No real API keys, accounts, or home server are used."""
import hashlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.auth_models import AuthSession, Owner
from app.main import app
from conftest import TEST_PASSWORD, TEST_USERNAME

client = TestClient(app)
pytestmark = pytest.mark.no_auto_login


def login(username=TEST_USERNAME, password=TEST_PASSWORD):
    return client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
        headers={"Origin": "http://testserver"},
    )


def test_pre_auth_routes_are_protected_and_openapi_closed():
    assert client.get("/api/v1/demo/overview").status_code == 401
    assert client.get("/api/v1/demo/instruments").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/docs").status_code == 404
    assert client.get("/api/health/live").status_code == 200


def test_login_cookie_and_identity():
    response = login()
    assert response.status_code == 200
    csrf = response.json()["csrf_token"]
    assert isinstance(csrf, str) and len(csrf) >= 32
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/" in cookie_header
    assert "foliosentry_session_local=" in cookie_header
    assert "no-store" in response.headers["cache-control"]
    assert client.get("/api/v1/auth/me").json()["username"] == TEST_USERNAME
    assert client.get("/api/v1/demo/overview").status_code == 200

    raw_token = client.cookies.get(auth.cookie_name())
    with Session(auth.get_engine()) as db:
        sessions = db.scalars(select(AuthSession)).all()
        assert len(sessions) == 1
        assert sessions[0].id_hash == hashlib.sha256(raw_token.encode()).hexdigest()
        assert sessions[0].id_hash != raw_token
        owner = db.get(Owner, 1)
        assert owner.password_hash.startswith("$argon2id$")
        assert TEST_PASSWORD not in owner.password_hash


def test_wrong_credentials_lockout_and_origin():
    assert login(password="wrong-password").status_code == 401
    assert login(username="different", password=TEST_PASSWORD).status_code == 401
    assert login(password="wrong-password").status_code == 401
    assert login(password="wrong-password").status_code == 401
    assert login(password="wrong-password").status_code == 401
    assert login().status_code == 429

    assert client.post("/api/v1/auth/login", json={
        "username": TEST_USERNAME, "password": TEST_PASSWORD,
    }).status_code == 403
    assert client.post(
        "/api/v1/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    ).status_code == 403


def test_csrf_and_logout_invalidate_server_session():
    csrf = login().json()["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={
        "Origin": "http://testserver",
    }).status_code == 403
    assert client.post("/api/v1/auth/logout", headers={
        "Origin": "https://evil.example", "X-CSRF-Token": csrf,
    }).status_code == 403
    assert client.get("/api/v1/demo/instruments").status_code == 200
    assert client.post("/api/v1/auth/logout", headers={
        "Origin": "http://testserver", "X-CSRF-Token": csrf,
    }).status_code == 200
    assert client.get("/api/v1/demo/overview").status_code == 401
    with Session(auth.get_engine()) as db:
        assert db.scalars(select(AuthSession)).first() is None


def test_invalid_and_expired_sessions(monkeypatch):
    login()
    client.cookies.set(auth.cookie_name(), "not-a-session-token")
    assert client.get("/api/v1/auth/me").status_code == 401

    client.cookies.clear()
    login()
    future = auth._now() + auth.SESSION_SECONDS + 1
    monkeypatch.setattr(auth, "_now", lambda: future)
    assert client.get("/api/v1/demo/overview").status_code == 401


def test_owner_bootstrap_is_one_time_only():
    with pytest.raises(ValueError, match="이미"):
        auth.bootstrap_owner("another", "another-password-for-tests-123")


def test_missing_owner_or_auth_schema_fails_closed():
    with Session(auth.get_engine()) as db:
        db.query(Owner).delete()
        db.commit()
    assert login().status_code == 503
    assert client.get("/api/health/ready").status_code == 503

    # Migrated DB unavailable also must never provide portfolio data.
    auth.AuthSession.__table__.drop(auth.get_engine())
    client.cookies.set(auth.cookie_name(), "test-session")
    assert client.get("/api/v1/demo/overview").status_code == 503
