"""
app/agent/nodes/tailor_resume.py — LLM resume tailoring node.

Fills the gaps identified by analyze_gaps into the candidate's HTML resume template,
preserving the original structure, CSS classes, and layout.
"""

import re
import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

TAILOR_RESUME_SYSTEM_PROMPT = """You are an expert resume tailoring specialist.
Your task is to take a candidate's resume in HTML format and a detailed gap analysis, and produce an updated HTML resume tailored specifically for the target job.

RULES:
1. PRESERVE LAYOUT: Keep all HTML tags, hierarchy, section order, and CSS classes intact.
2. TAILOR CONTENT: Refine bullet points, summary, and skills list to naturally incorporate the target keywords identified in the gap analysis. Keep the edits minimal and grounded in the existing resume.
3. SECTION ALIASES: Do not drop a section just because the heading is phrased differently. Treat headings like professional experience, work experience, industry experience, job experience, and previous experience as the same section when preserving content.
4. NO HALLUCINATION: Do NOT add fabricated job titles, companies, dates, degrees, or tools. Only enhance descriptions of existing genuine experience.
5. NO OLD CRITERIA: Use the provided gap analysis as the only tailoring signal. Do not reuse prior runs or job-description language that is not supported by the resume.
6. UNCERTAINTY: If a change feels speculative, leave the original wording mostly intact and keep the edit conservative rather than forcing a new claim.
7. OUTPUT FORMAT: Return ONLY the tailored raw HTML string (from <div class="resume"> to </div>). Do not include any markdown backticks or ```html wrappers.
"""


def run_resume_tailoring(resume_html: str, gap_analysis: str) -> str:
    """Invoke LLM to update HTML resume based on gap analysis."""
    llm = get_llm(temperature=0.1)
    messages = [
        SystemMessage(content=TAILOR_RESUME_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### GAP ANALYSIS & KEYWORD RECOMMENDATIONS:\n{gap_analysis}\n\n"
                f"### BASE RESUME HTML:\n{resume_html}\n\n"
                "Produce the tailored HTML resume:"
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, list):
        content = "".join([part if isinstance(part, str) else part.get("text", "") for part in content])

    raw = str(content)
    # 1. Remove reasoning / think tags
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

    # 2. Extract HTML div block
    fence_match = re.search(r"```(?:html)?\s*(<div.*?>.*?</div>)\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    div_match = re.search(r"(<div.*?>.*?</div>)", cleaned, re.DOTALL | re.IGNORECASE)
    if div_match:
        return div_match.group(1).strip()

    # 3. Code fence stripping fallback
    if cleaned.startswith("```html"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]

    candidate_html = cleaned.strip()
    if not candidate_html:
        return resume_html

    # Guard against thin or malformed generations that collapse the resume into
    # just a header/name fragment. If the model output is too small to plausibly
    # be a full resume, fall back to the original base HTML.
    plain_text = re.sub(r"<[^>]+>", " ", candidate_html)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    if len(plain_text.split()) < 40 or len(candidate_html) < 500:
        log.warning(
            "tailor_resume_output_rejected",
            reason="output_too_short",
            output_chars=len(candidate_html),
            output_words=len(plain_text.split()),
        )
        return resume_html

    return candidate_html


def tailor_resume_node(state: GraphState) -> GraphState:
    """LangGraph node for resume tailoring."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="tailor_resume", application_id=app_id, user_id=user_id)

    resume_html = state.get("resume_html", "")
    gap_analysis = state.get("gap_analysis", "")

    if not resume_html:
        log.warning("tailor_resume_missing_html", application_id=app_id)
        tailored_html = f'<div class="resume"><p>{state.get("resume_text", "")}</p></div>'
    else:
        try:
            tailored_html = run_resume_tailoring(resume_html, gap_analysis)
        except Exception as exc:
            log.error("tailor_resume_failed", error=str(exc), application_id=app_id)
            # Fallback to base HTML if tailoring fails
            tailored_html = resume_html

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="tailor_resume", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "tailored_resume_html": tailored_html,
    }
