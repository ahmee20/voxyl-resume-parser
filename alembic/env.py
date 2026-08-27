"""
alembic/env.py — Async-aware Alembic environment.

Key points:
- DATABASE_URL is pulled from app.config.settings — never hardcoded.
- All models are imported via app.models so autogenerate can see every table.
- Uses run_async_migrations() since SQLAlchemy 2.0 async engines require it.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

# Ensure project root is in sys.path when running alembic from CLI
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import the shared metadata and all model classes so Alembic autogenerate
# can detect every table.
from app.database import Base
import app.models  # noqa: F401 — side-effect import registers all mappers

from app.config import settings

# ── Alembic Config object ─────────────────────────────────────────────────────
config = context.config

# Set the DB URL from our Settings object so .ini never contains credentials.
config.set_main_option("sqlalchemy.url", settings.database_url)

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata for autogenerate support
target_metadata = Base.metadata


# ── Offline migrations (generates SQL without a live DB connection) ────────────
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online migrations (against a live async connection) ───────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connect_args = {}
    if "postgresql" in settings.database_url or "asyncpg" in settings.database_url:
        connect_args = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }

    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
