"""Database readiness only. Phase 1 will add migrations and repositories."""
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings


@lru_cache
def get_engine():
    settings = get_settings()
    url = URL.create(
        "postgresql+psycopg",
        username=settings.db_user,
        password=settings.db_password,
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
    )
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})


def check_database() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False
