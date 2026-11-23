"""Alembic configuration; connection credentials never appear in alembic.ini."""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import URL

from app.auth_models import AuthBase
from app import portfolio_models  # noqa: F401 — register Phase 1 tables in metadata
from app import price_models  # noqa: F401 — MD-03 model metadata only
from app import quality_evidence_models  # noqa: F401 — MD-04C3 price-free quality snapshots
from app import evidence_reference_models  # noqa: F401 — MD-04C4 unverified reference history
from app.config import get_settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = AuthBase.metadata


def database_url() -> str:
    s = get_settings()
    return URL.create(
        "postgresql+psycopg",
        username=s.db_user, password=s.db_password,
        host=s.db_host, port=s.db_port, database=s.db_name,
    ).render_as_string(hide_password=False)


def run_migrations_offline():
    context.configure(
        url=database_url(), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = engine_from_config(
        {"sqlalchemy.url": database_url()},
        prefix="sqlalchemy.", poolclass=pool.NullPool,
    )
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
