"""Unit tests for secret-file settings; never use a real MiniPC credential."""
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.config import Settings


def test_db_password_file_is_used_without_exposing_value(monkeypatch, tmp_path):
    secret = tmp_path / "pg_secret"
    secret.write_text("synthetic-ci-password\n", encoding="utf-8")
    monkeypatch.delenv("FOLIOSENTRY_DB_PASSWORD", raising=False)
    monkeypatch.setenv("FOLIOSENTRY_DB_PASSWORD_FILE", str(secret))
    s = Settings(_env_file=None)
    assert s.db_password == "synthetic-ci-password"
    assert "synthetic-ci-password" not in repr(s)


def test_secret_file_and_plain_env_cannot_be_combined(monkeypatch, tmp_path):
    secret = tmp_path / "pg_secret"
    secret.write_text("synthetic-ci-password\n", encoding="utf-8")
    monkeypatch.setenv("FOLIOSENTRY_DB_PASSWORD", "different-ci-password")
    monkeypatch.setenv("FOLIOSENTRY_DB_PASSWORD_FILE", str(secret))
    with pytest.raises(ValidationError, match="either DB_PASSWORD or DB_PASSWORD_FILE"):
        Settings(_env_file=None)


def test_secret_file_missing_rejects_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("FOLIOSENTRY_DB_PASSWORD", raising=False)
    monkeypatch.setenv("FOLIOSENTRY_DB_PASSWORD_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_secure_cookie_is_required_outside_explicit_loopback(monkeypatch):
    monkeypatch.delenv("FOLIOSENTRY_DB_PASSWORD_FILE", raising=False)
    monkeypatch.setenv("FOLIOSENTRY_AUTH_COOKIE_SECURE", "false")
    monkeypatch.setenv("FOLIOSENTRY_ALLOW_HTTP_DEV", "false")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
