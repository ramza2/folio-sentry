"""Typed configuration; secrets come only from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FOLIOSENTRY_", extra="ignore")

    db_host: str = "db"
    db_port: int = 5432
    db_user: str = "folio"
    db_name: str = "folio"
    db_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
