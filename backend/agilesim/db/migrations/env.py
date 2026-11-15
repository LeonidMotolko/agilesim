"""Alembic environment: online and offline (``--sql``) migrations."""

from alembic import context
from sqlalchemy import create_engine, pool

from agilesim.config import get_settings
from agilesim.db import models  # noqa: F401  (registers the tables on Base.metadata)
from agilesim.db.base import Base
from agilesim.db.session import normalize_url

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    url = config.get_main_option("sqlalchemy.url")
    if not url:
        settings = get_settings()
        url = settings.migration_database_url or settings.database_url
    if not url:
        msg = "Set AGILESIM_MIGRATION_DATABASE_URL (or AGILESIM_DATABASE_URL) to run migrations"
        raise RuntimeError(msg)
    return normalize_url(url)


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
