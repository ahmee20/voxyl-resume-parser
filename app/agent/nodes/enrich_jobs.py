"""
app/agent/nodes/enrich_jobs.py — LangGraph tool node for Apollo enrichment.

Apollo is ONLY invoked for the latest qualified jobs returned from Apify
after passing the 70% requirement filter and experience tolerance check.
"""

import asyncio
import concurrent.futures
import time
import structlog
from app.agent.state import GraphState
from app.services.apollo_enricher import enrich_job_with_apollo

log = structlog.get_logger(__name__)


def _run_enrichment_sync(jobs: list[dict]) -> list[dict]:
    """Execute async enrichment across job list safely in isolated loop."""
    async def _async_batch():
        tasks = [enrich_job_with_apollo(j) for j in jobs]
        return await asyncio.gather(*tasks)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, _async_batch()).result()


def enrich_jobs_node(state: GraphState) -> GraphState:
    """
    LangGraph node: Enriches ONLY the qualified jobs (>= 70% match) from the latest Apify batch.
    Unqualified jobs (< 70%) are filtered out prior to this node to conserve Apollo credits.
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="enrich_jobs", application_id=app_id, user_id=user_id)

    # Scraped jobs here only contains qualified listings filtered by match_requirements_node
    scraped_jobs = state.get("scraped_jobs", [])
    enriched_jobs = state.get("enriched_jobs")

    if not enriched_jobs and scraped_jobs:
        log.info("enriching_scraped_jobs_with_apollo", count=len(scraped_jobs))
        try:
            enriched_jobs = _run_enrichment_sync(scraped_jobs)
        except Exception as exc:
            log.error("enrich_jobs_failed", error=str(exc), application_id=app_id)
            enriched_jobs = scraped_jobs
    elif not scraped_jobs:
        enriched_jobs = []

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="enrich_jobs", latency_ms=elapsed_ms, count=len(enriched_jobs or []))

    return {
        **state,
        "enriched_jobs": enriched_jobs or [],
    }
