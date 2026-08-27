"""
app/agent/nodes/persist_jobs.py — DB persistence and URL deduplication node.
"""

import asyncio
import concurrent.futures
import time
import structlog
from sqlalchemy import select

import app.database
from app.agent.state import GraphState
from app.models.job import Job

log = structlog.get_logger(__name__)


async def _persist_jobs_async(jobs_data: list[dict], user_id: int) -> tuple[list[int], list[int]]:
    """Insert only new jobs for the user and update already-known rows in place."""
    new_job_ids: list[int] = []
    existing_job_ids: list[int] = []
    async with app.database.AsyncSessionLocal() as session:
        urls = [job_dict.get("url") for job_dict in jobs_data if job_dict.get("url")]
        existing_by_url: dict[str, Job] = {}
        if urls:
            stmt = select(Job).where(Job.user_id == user_id, Job.url.in_(urls))
            res = await session.execute(stmt)
            existing_by_url = {job.url: job for job in res.scalars().all()}

        new_jobs: list[Job] = []
        for job_dict in jobs_data:
            url = job_dict.get("url")
            if not url:
                continue

            existing = existing_by_url.get(url)

            if existing:
                # Update qualification meta if changed
                existing.is_qualified = job_dict.get("is_qualified", True)
                existing.match_score = job_dict.get("match_score")
                existing.filter_reason = job_dict.get("filter_reason")
                if job_dict.get("apollo_enrichment") or job_dict.get("location"):
                    existing_apollo = dict(existing.apollo_enrichment or {})
                    incoming_apollo = dict(job_dict.get("apollo_enrichment") or {})
                    location_val = job_dict.get("location")
                    if location_val:
                        incoming_apollo["location"] = location_val
                    existing.apollo_enrichment = {**existing_apollo, **incoming_apollo}
                if job_dict.get("recruiter_email"):
                    existing.recruiter_email = job_dict.get("recruiter_email")
                existing_job_ids.append(existing.id)
            else:
                apollo_enrichment = dict(job_dict.get("apollo_enrichment") or {})
                if job_dict.get("location"):
                    apollo_enrichment["location"] = job_dict.get("location")
                new_jobs.append(Job(
                    user_id=user_id,
                    source=job_dict.get("source", "apify"),
                    external_id=job_dict.get("external_id"),
                    url=url,
                    title=job_dict.get("title"),
                    company=job_dict.get("company"),
                    description=job_dict.get("description"),
                    recruiter_email=job_dict.get("recruiter_email"),
                    apollo_enrichment=apollo_enrichment or None,
                    is_qualified=job_dict.get("is_qualified", True),
                    match_score=job_dict.get("match_score"),
                    filter_reason=job_dict.get("filter_reason"),
                ))

        if new_jobs:
            session.add_all(new_jobs)
            await session.flush()
            new_job_ids.extend(job.id for job in new_jobs if job.id is not None)

        await session.commit()

    return new_job_ids, existing_job_ids


def persist_jobs_node(state: GraphState) -> GraphState:
    """LangGraph node: Persists qualified and filtered jobs to database with user-scoped URL deduplication."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id", 1) or 1

    log.info("node_enter", node="persist_jobs", application_id=app_id, user_id=user_id)

    relevant_jobs = state.get("relevant_jobs", [])
    filtered_jobs = state.get("filtered_jobs", [])
    all_to_persist = relevant_jobs + filtered_jobs

    persisted_job_ids = state.get("persisted_job_ids")
    duplicate_job_ids = state.get("duplicate_job_ids")

    if persisted_job_ids is None and all_to_persist:
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                persisted_job_ids, duplicate_job_ids = pool.submit(
                    asyncio.run, _persist_jobs_async(all_to_persist, user_id)
                ).result()
        except Exception as exc:
            log.error("persist_jobs_failed", error=str(exc), application_id=app_id)
            persisted_job_ids = []
            duplicate_job_ids = []

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info(
        "node_exit",
        node="persist_jobs",
        latency_ms=elapsed_ms,
        count=len(persisted_job_ids or []),
        duplicates=len(duplicate_job_ids or []),
    )

    return {
        **state,
        "persisted_job_ids": persisted_job_ids or [],
        "duplicate_job_ids": duplicate_job_ids or [],
    }
