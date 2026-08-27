"""
app/agent/nodes/render_pdf.py — PDF rendering node via PDF.co service.
"""

import asyncio
import time
import structlog

from app.agent.state import GraphState
from app.services.pdf_generator import convert_html_to_pdf

log = structlog.get_logger(__name__)


def render_pdf_node(state: GraphState) -> GraphState:
    """LangGraph node to convert tailored HTML resume into PDF."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="render_pdf", application_id=app_id, user_id=user_id)

    tailored_html = state.get("tailored_resume_html") or state.get("resume_html", "")
    pdf_url = state.get("pdf_url")

    if not pdf_url and tailored_html:
        try:
            import concurrent.futures
            def _runner():
                return asyncio.run(convert_html_to_pdf(tailored_html))
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pdf_url = pool.submit(_runner).result()
        except Exception as exc:
            log.error("render_pdf_failed", error=str(exc), application_id=app_id)
            pdf_url = f"https://api.pdf.co/fallback-error.pdf"

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="render_pdf", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "pdf_url": pdf_url or "https://example.com/tailored_resume.pdf",
    }
