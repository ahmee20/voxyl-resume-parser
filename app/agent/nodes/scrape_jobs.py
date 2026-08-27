"""
app/agent/nodes/scrape_jobs.py — LangGraph tool node for job scraping.
"""

import time
import structlog
from app.agent.state import GraphState
from app.services.apify_scraper import scrape_jobs_from_apify

log = structlog.get_logger(__name__)


def scrape_jobs_node(state: GraphState) -> GraphState:
    """LangGraph node: Executes Apify scraper using planned queries and user preferred countries."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="scrape_jobs", application_id=app_id, user_id=user_id)

    queries = state.get("search_queries", ["AI Engineer"])
    countries = state.get("preferred_countries", ["US"])
    scraped_jobs = state.get("scraped_jobs")

    max_results = state.get("max_results", 5)
    posted_within_hours = state.get("posted_within_hours")
    if not scraped_jobs:
        scraped_jobs = scrape_jobs_from_apify(
            queries=queries,
            countries=countries,
            max_results=max_results,
            posted_within_hours=posted_within_hours,
        )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="scrape_jobs", latency_ms=elapsed_ms, count=len(scraped_jobs))

    return {
        **state,
        "scraped_jobs": scraped_jobs,
    }
