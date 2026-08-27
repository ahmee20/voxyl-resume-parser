"""
app/agent/nodes/filter_jobs.py — Relevance filtering node for enriched job listings.
"""

import time
import structlog
from app.agent.state import GraphState

log = structlog.get_logger(__name__)


def filter_relevant_node(state: GraphState) -> GraphState:
    """
    Filter scraped/enriched jobs down to relevant, high-quality matches.
    Checks that the job contains meaningful descriptions and required title domains.
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="filter_relevant", application_id=app_id, user_id=user_id)

    enriched_jobs = state.get("enriched_jobs", [])
    relevant_jobs = state.get("relevant_jobs")

    if relevant_jobs is None or len(relevant_jobs) == 0:
        filtered = []
        for job in enriched_jobs:
            title = str(job.get("title") or "").lower()
            description = str(job.get("description") or "").lower()
            if len(description) >= 10 and not any(kw in title for kw in ["volunteer", "unpaid"]):
                filtered.append(job)
        relevant_jobs = filtered if filtered else enriched_jobs

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="filter_relevant", latency_ms=elapsed_ms, count=len(relevant_jobs))

    return {
        **state,
        "relevant_jobs": relevant_jobs,
    }
