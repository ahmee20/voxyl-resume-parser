"""
app/services/job_deduper.py — helpers for skipping already discovered jobs.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.models.job import Job

log = structlog.get_logger(__name__)


def _normalize_url(value: Any) -> str:
    return str(value or "").strip()


async def split_fresh_and_known_jobs(
    session: AsyncSession,
    user_id: int,
    jobs_data: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Split scraped jobs into new records and already-known records for a user.

    Uses one indexed lookup on (user_id, url) and then filters in memory.
    Also removes duplicate URLs within the same scrape batch.
    """
    jobs_list = list(jobs_data)
    if not jobs_list:
        return [], []

    urls = [_normalize_url(job.get("url")) for job in jobs_list]
    urls = [url for url in urls if url]
    if not urls:
        return [], jobs_list

    stmt = select(Job.url).where(Job.user_id == user_id, Job.url.in_(urls))
    result = await session.execute(stmt)
    known_urls = set(result.scalars().all())

    fresh_jobs: list[dict[str, Any]] = []
    known_jobs: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for job in jobs_list:
        url = _normalize_url(job.get("url"))
        if not url:
            log.warning("job_dropped", reason="missing_url", title=job.get("title"), company=job.get("company"))
            continue
        if url in seen_urls or url in known_urls:
            known_jobs.append(job)
            log.info(
                "job_dropped",
                reason="duplicate_url_in_batch" if url in seen_urls else "already_known_for_user",
                url=url,
                title=job.get("title"),
                company=job.get("company"),
            )
            continue
        seen_urls.add(url)
        fresh_jobs.append(job)

    return fresh_jobs, known_jobs
