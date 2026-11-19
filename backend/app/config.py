"""Typed configuration; secrets come only from environment variables."""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIOSENTRY_", extra="ignore")

    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "folio"
    db_name: str = "folio"
    db_password: str = ""

    auth_allowed_origins: str = ""
    auth_cookie_secure: bool = True
    allow_http_dev: bool = False

    @model_validator(mode="after")
    def secure_auth_configuration(self):
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
