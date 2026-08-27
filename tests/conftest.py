"""
tests/conftest.py — Shared pytest fixtures.

Uses a file-based SQLite database for unit tests so no Postgres is required.
File-based DB is needed because persist_jobs_node runs async code in a
separate thread, which cannot share an in-memory SQLite connection.
"""

import os
import pytest

# ── Set env vars before any app import so pydantic-settings sees them ─────────
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("LANGCHAIN_API_KEY", "test-langsmith-key")
os.environ.setdefault("LANGCHAIN_PROJECT", "job-application-autopilot-test")
# Disable LangSmith tracing in tests — dummy key is rejected by the real API
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ.setdefault("APIFY_API_TOKEN", "test-apify-token")
os.environ.setdefault("APOLLO_API_KEY", "test-apollo-key")
os.environ.setdefault("PDFCO_API_KEY", "test-pdfco-key")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret-key-32chars!!")
os.environ.setdefault("TOKEN_ENCRYPTION_KEY", "dGVzdC1mZXJuZXQta2V5LTMyLWJ5dGVzLWhlcmUhISE=")
os.environ["SCHEDULER_ENABLED"] = "false"
# Use SQLite for unit tests — avoids a live Postgres requirement
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_autopilot.db")


from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession  # noqa: E402

# Import database module BEFORE importing the FastAPI app so we can patch it
import app.database as db_module  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


# ── File-based test DB ────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_autopilot.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Patch the database module so nodes that import app.database use the test DB
db_module.AsyncSessionLocal = TestSessionLocal
db_module.engine = test_engine


@pytest.fixture(autouse=True)
async def setup_db_tables():
    """Create all tables before each test and clean up after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, checkfirst=True))


@pytest.fixture
async def db_session():
    """Yield a test AsyncSession, rolling back after each test."""
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session: AsyncSession):
    """Yield an AsyncClient with the test DB injected via dependency override."""

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()
