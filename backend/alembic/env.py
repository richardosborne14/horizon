"""
Alembic environment configuration.

Uses SQLAlchemy async engine with psycopg (sync) driver for migrations.
Reads DATABASE_URL from the application settings so we never have
credentials in version-controlled files.

Run migrations:
    # From backend/ directory:
    alembic upgrade head

    # Or via Docker:
    docker compose exec backend alembic upgrade head
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Import Base and ALL models so Alembic autogenerate sees every table
from app.core.database import Base  # noqa: F401
import app.models  # noqa: F401 — triggers all model registrations on Base.metadata

# Import settings to get DATABASE_URL
from app.core.config import settings

# Alembic Config object — provides access to values in alembic.ini
config = context.config

# Override sqlalchemy.url from alembic.ini with our actual settings
# This means we don't need real credentials in alembic.ini
# Use psycopg (sync) for migrations, not asyncpg
db_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg://"
)
config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support — Alembic compares this to the DB
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    Doesn't need a live DB connection — generates SQL scripts instead.
    Useful for reviewing what will be applied before running.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with a live DB connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using async engine (required for asyncpg-based setup)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode with a live DB connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
