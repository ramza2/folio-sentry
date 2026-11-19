"""Auth tests run against isolated in-memory SQLite; never the user's database."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app import auth, portfolio_api, portfolio_models  # noqa: F401
from app.auth_models import AuthBase

TEST_USERNAME = "owner"
TEST_PASSWORD = "only-for-isolated-automated-tests-123!"


@pytest.fixture(autouse=True)
def isolated_auth(request, monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    AuthBase.metadata.create_all(engine)
    monkeypatch.setattr(auth, "get_engine", lambda: engine)
    monkeypatch.setattr(portfolio_api, "get_engine", lambda: engine)
    monkeypatch.setattr(auth, "get_settings", lambda: SimpleNamespace(
        auth_cookie_secure=False,
        auth_allowed_origins="http://testserver",
        allow_http_dev=True,
    ))
    auth.bootstrap_owner(TEST_USERNAME, TEST_PASSWORD)
    client = getattr(request.module, "client", None)
    if client is not None:
        client.cookies.clear()
        if not request.node.get_closest_marker("no_auto_login"):
            response = client.post(
                "/api/v1/auth/login",
                json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
                headers={"Origin": "http://testserver"},
            )
            assert response.status_code == 200, response.text
    yield
    if client is not None:
        client.cookies.clear()
    engine.dispose()
