"""
app/agent/nodes/extract_resume.py — Extract text and generate semantic HTML skeleton.
"""

import time
import structlog

from app.agent.state import GraphState
from app.services.resume_template import ResumeProfile, render_resume_html

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are an expert resume parsing and layout assistant.
Your task is to take plain text from an uploaded resume and convert it into clean, semantic HTML.

Rules:
1. Preserve all the candidate's original text, sections, dates, and bullet points verbatim. Do NOT summarize or invent anything.
2. Structure the resume with semantic HTML elements (e.g. <header>, <section>, <h2>, <h3>, <p>, <ul>, <li>).
3. Use simple CSS classes like 'header', 'section', 'experience-item', 'education-item', 'skills-list'.
4. Do NOT include markdown formatting or ```html tags in the output. Return ONLY the raw HTML string (from <div class="resume"> to </div>).
"""


def generate_resume_html_skeleton(resume_text: str, profile: ResumeProfile | None = None) -> str:
    """Generate a polished, predictable HTML resume skeleton from raw text."""
    return render_resume_html(resume_text, profile)


def extract_resume_node(state: GraphState) -> GraphState:
    """LangGraph node: Generates normalized HTML skeleton if not already present."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")
    
    log.info("node_enter", node="extract_resume", application_id=app_id, user_id=user_id)
    
    resume_text = state.get("resume_text", "")
    resume_html = state.get("resume_html")
    
    if not resume_html and resume_text:
        try:
            resume_html = generate_resume_html_skeleton(resume_text)
        except Exception as exc:
            log.error("extract_resume_failed", error=str(exc), application_id=app_id)
            resume_html = render_resume_html(resume_text)
            
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="extract_resume", latency_ms=elapsed_ms, application_id=app_id)
    
    return {
        **state,
        "resume_text": resume_text,
        "resume_html": resume_html,
    }
