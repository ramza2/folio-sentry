"""Typed configuration; secrets come only from environment variables."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIOSENTRY_", extra="ignore")

    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "folio"
    db_name: str = "folio"
    db_password: str = Field(default="", repr=False)
    db_password_file: str = ""

    auth_allowed_origins: str = ""
    auth_cookie_secure: bool = True
    allow_http_dev: bool = False

    @model_validator(mode="after")
    def secure_auth_configuration(self):
        if self.db_password_file:
            if self.db_password:
                raise ValueError("Use either DB_PASSWORD or DB_PASSWORD_FILE, not both")
            # Compose secret path is never returned to the frontend or logged.
            # Do not read it until an explicit settings object is constructed.
            try:
                self.db_password = Path(self.db_password_file).read_text(encoding="utf-8").strip()
            except OSError:
                # Do not expose a private filesystem path in validation errors.
                raise ValueError("PostgreSQL secret file unavailable") from None
            if not self.db_password:
                raise ValueError("DB password secret must not be empty")
        if not self.auth_cookie_secure:
            if not self.allow_http_dev:
                raise ValueError("HTTP authentication must be explicitly enabled for local development")
            origins = [s.strip() for s in self.auth_allowed_origins.split(",") if s.strip()]
            if not origins or any(
                not (origin.startswith("http://localhost:") or
                     origin.startswith("http://127.0.0.1:"))
                for origin in origins
            ):
                raise ValueError("Insecure cookie mode is only allowed for loopback browser origins")
        return self



@lru_cache
def get_settings() -> Settings:
    return Settings()
