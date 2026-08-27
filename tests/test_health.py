"""
tests/test_health.py — Health check endpoint tests.

Tests:
1. GET /health returns 200 when DB is reachable (mocked in-memory SQLite).
2. Response body has the expected keys.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_body_schema(client: AsyncClient):
    response = await client.get("/health")
    body = response.json()
    assert "status" in body
    assert "db" in body
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_health_db_ok(client: AsyncClient):
    """With the in-memory SQLite fixture, DB should report 'ok'."""
    response = await client.get("/health")
    assert response.json()["db"] == "ok"
