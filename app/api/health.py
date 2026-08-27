"""
app/api/health.py — Health check endpoint.

GET /health
  Returns 200 {"status": "ok", "db": "ok"} when the app and Postgres are reachable.
  Returns 503 {"status": "ok", "db": "error", "detail": "<msg>"} on DB failure.

This is the first endpoint a fresh reviewer hits after `docker-compose up`.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """Verify the app is running and the database is reachable."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
        http_status = status.HTTP_200_OK
    except Exception as exc:
        db_status = "error"
        http_status = status.HTTP_503_SERVICE_UNAVAILABLE
        return JSONResponse(
            status_code=http_status,
            content={"status": "ok", "db": db_status, "detail": str(exc)},
        )

    return JSONResponse(
        status_code=http_status,
        content={"status": "ok", "db": db_status},
    )
