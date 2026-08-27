"""
app/database.py — Async SQLAlchemy engine, session factory, and FastAPI dependency.

Rules:
- One engine per process (created at startup via lifespan).
- Never import the engine directly in route handlers — use the get_db dependency.
- AsyncSession is injected via FastAPI's Depends(get_db).
- PgBouncer / Supabase pooling compatibility: statement_cache_size=0, unique statement naming, and NullPool.
"""

import uuid
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config import settings

log = structlog.get_logger(__name__)


def _generate_unique_stmt_name() -> str:
    """Generate unique statement name for asyncpg to prevent PgBouncer statement conflicts."""
    return f"__asyncpg_{uuid.uuid4().hex}__"


# ── Engine ────────────────────────────────────────────────────────────────────
# Disable client-side pooling & prepared statement caching for Supabase / PgBouncer
database_url = settings.resolved_database_url
if database_url == settings.database_url and "db." in database_url and "supabase.co" in database_url:
    log.warning(
        "direct_supabase_host_detected",
        note="Set SUPABASE_POOLER_URL in Render to use the pooler host.",
    )
engine_kwargs = {"echo": False}
if "postgresql" in database_url or "asyncpg" in database_url:
    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "prepared_statement_name_func": _generate_unique_stmt_name,
            "server_settings": {
                "jit": "off",
            },
        },
    })
else:
    engine_kwargs.update({"pool_pre_ping": True})

engine = create_async_engine(
    database_url,
    **engine_kwargs,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep attributes accessible after commit
    autocommit=False,
    autoflush=False,
)


# ── Declarative base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """All ORM models inherit from this base."""
    pass


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an AsyncSession for a single request, then close it.
    Usage in route:
        async def my_route(db: AsyncSession = Depends(get_db)): ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
