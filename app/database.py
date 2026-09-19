"""
app/database.py — Async SQLAlchemy engine, session factory, and FastAPI dependency.

Rules:
- One engine per process (created at startup via lifespan).
- Never import the engine directly in route handlers — use the get_db dependency.
- AsyncSession is injected via FastAPI's Depends(get_db).
- PgBouncer / Supabase pooling compatibility: statement_cache_size=0, unique statement naming, and NullPool.
- Force IPv4 resolution to prevent [Errno 99] in IPv4-only serverless runtimes (e.g., Vercel / AWS Lambda).
"""

import socket
import uuid
from typing import AsyncGenerator
from urllib.parse import urlparse

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


def _resolve_ipv4_host(hostname: str, port: int) -> str:
    """Resolve hostname strictly to IPv4 to prevent [Errno 99] in IPv4-only serverless environments."""
    if not hostname or hostname in ("localhost", "127.0.0.1"):
        return hostname
    try:
        # Check if already an IP
        socket.inet_aton(hostname)
        return hostname
    except OSError:
        pass

    try:
        addr_info = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
        )
        if addr_info and addr_info[0][4]:
            ipv4 = addr_info[0][4][0]
            log.info("resolved_ipv4_host", hostname=hostname, ipv4=ipv4)
            return ipv4
    except Exception as exc:
        log.warning("ipv4_dns_resolution_failed", hostname=hostname, error=str(exc))
    return hostname


# ── Engine ────────────────────────────────────────────────────────────────────
database_url = settings.resolved_database_url
engine_kwargs = {"echo": False}

if "postgresql" in database_url or "asyncpg" in database_url:
    parsed = urlparse(database_url)
    orig_host = parsed.hostname or ""
    port = parsed.port or 5432
    ipv4_host = _resolve_ipv4_host(orig_host, port) if orig_host else ""

    connect_args: dict = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
        "prepared_statement_name_func": _generate_unique_stmt_name,
        "server_settings": {
            "jit": "off",
        },
    }

    if ipv4_host and ipv4_host != orig_host:
        connect_args["host"] = ipv4_host
        connect_args["server_hostname"] = orig_host

    engine_kwargs.update({
        "poolclass": NullPool,
        "connect_args": connect_args,
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
