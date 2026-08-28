"""
app/agent/nodes/render_pdf.py - PDF rendering node via PDF.co service.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from app.agent.state import GraphState
from app.config import settings
from app.services.pdf_generator import convert_html_to_pdf
from app.services.pdfco_resume_payload import build_pdfco_resume_template_data
from app.services.resume_template import ResumeProfile, render_resume_html

log = structlog.get_logger(__name__)


def render_pdf_node(state: GraphState) -> GraphState:
    """LangGraph node to convert tailored resume content into PDF."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="render_pdf", application_id=app_id, user_id=user_id)

    tailored_html = state.get("tailored_resume_html") or state.get("resume_html", "")
    pdf_url = state.get("pdf_url")
    template_data = state.get("resume_template_data")
    profile_data = state.get("user_profile") or {}
    profile = ResumeProfile(
        name=profile_data.get("name"),
        email=profile_data.get("email"),
        github_url=profile_data.get("github_url"),
        portfolio_url=profile_data.get("portfolio_url"),
        linkedin_url=profile_data.get("linkedin_url"),
    )

    if "<div" not in tailored_html.lower() or "</div>" not in tailored_html.lower():
        tailored_html = render_resume_html(state.get("resume_text", ""), profile)

    if not template_data:
        template_data = build_pdfco_resume_template_data(
            tailored_resume_html=tailored_html,
            resume_text=state.get("resume_text", ""),
            profile=profile,
        )

    use_template = bool(template_data)

    if not pdf_url and tailored_html:
        try:
            import concurrent.futures

            def _runner():
                return asyncio.run(
                    convert_html_to_pdf(
                        tailored_html,
                        template_data=template_data if use_template else None,
                        template_id=settings.pdfco_resume_template_id if use_template else None,
                    )
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pdf_url = pool.submit(_runner).result()
        except Exception as exc:
            log.error("render_pdf_failed", error=str(exc), application_id=app_id)
            pdf_url = None

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="render_pdf", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "resume_template_data": template_data or state.get("resume_template_data"),
        "pdf_url": pdf_url,
    }
