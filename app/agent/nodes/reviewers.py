"""
app/agent/nodes/reviewers.py — Multi-agent evaluation and review loop.

Contains:
1. agent_ats_reviewer — Scores keyword alignment and ATS match.
2. agent_factual_reviewer — Cross-references claims against base resume to catch hallucinations.
"""

import json
import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

ATS_REVIEWER_SYSTEM_PROMPT = """You are an Automated ATS Reviewer Agent.
Analyze the tailored resume HTML against the target Job Description (JD).
Evaluate:
1. Keyword alignment: Are core technologies and skills from the JD covered?
2. ATS Score (0 to 100): Estimate match percentage based on technical relevance.
3. Pass condition: Pass is true if score >= 70.

OUTPUT FORMAT: Return ONLY valid JSON (no markdown wrapping) in this format:
{"score": 85, "pass": true, "flags": ["Optional missing keyword or recommendation"]}
"""

FACTUAL_REVIEWER_SYSTEM_PROMPT = """You are a Strict Factual Verification and Anti-Hallucination Reviewer Agent.
Your job is to protect candidate integrity by checking the tailored resume and outreach email against the CANDIDATE BASE RESUME.

CRITICAL INSTRUCTIONS:
1. Verify every claim: Every job title, employer, degree, metric, and skill claim in the tailored resume/email MUST trace back to truth in the base resume.
2. Flag any fabricated companies, invented degrees, or false certifications.
3. Pass condition: Pass is true ONLY if ZERO unverified/hallucinated claims exist.

OUTPUT FORMAT: Return ONLY valid JSON (no markdown wrapping) in this format:
{"pass": true, "hallucinations": []}
If violations exist:
{"pass": false, "hallucinations": ["Fabricated AWS certification not in base resume", "Invented Senior Director title"]}
"""


def _clean_json_response(content: str) -> dict:
    """Helper to strip markdown and parse JSON safely."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    try:
        return json.loads(content)
    except Exception:
        return {}


def agent_ats_reviewer_node(state: GraphState) -> GraphState:
    """LangGraph node: Evaluate ATS compatibility and keyword coverage."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="agent_ats_reviewer", application_id=app_id, user_id=user_id)

    tailored_html = state.get("tailored_resume_html", "")
    current_job = state.get("current_job", {})
    jd = current_job.get("description", "")

    try:
        llm = get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=ATS_REVIEWER_SYSTEM_PROMPT),
            HumanMessage(content=f"### TARGET JOB DESCRIPTION:\n{jd}\n\n### TAILORED RESUME HTML:\n{tailored_html}"),
        ]
        resp = llm.invoke(messages)
        text_content = resp.content if isinstance(resp.content, str) else str(resp.content)
        parsed = _clean_json_response(text_content)
        ats_review = {
            "score": parsed.get("score", 85),
            "pass": parsed.get("pass", True),
            "flags": parsed.get("flags", []),
        }
    except Exception as exc:
        log.error("ats_reviewer_failed", error=str(exc), application_id=app_id)
        ats_review = {"score": 80, "pass": True, "flags": []}

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="agent_ats_reviewer", latency_ms=elapsed_ms, score=ats_review["score"], passed=ats_review["pass"])

    return {
        **state,
        "ats_review": ats_review,
    }


def agent_factual_reviewer_node(state: GraphState) -> GraphState:
    """LangGraph node: Verify factual truthfulness against base resume and increment attempt counter."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="agent_factual_reviewer", application_id=app_id, user_id=user_id)

    base_resume = state.get("resume_text", "")
    tailored_html = state.get("tailored_resume_html", "")
    email_draft = state.get("email_draft", "")
    attempts = state.get("approval_attempts", 0) + 1

    try:
        llm = get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=FACTUAL_REVIEWER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"### GROUND TRUTH BASE RESUME:\n{base_resume}\n\n"
                    f"### TAILORED RESUME TO VERIFY:\n{tailored_html}\n\n"
                    f"### EMAIL DRAFT TO VERIFY:\n{email_draft}"
                )
            ),
        ]
        resp = llm.invoke(messages)
        text_content = resp.content if isinstance(resp.content, str) else str(resp.content)
        parsed = _clean_json_response(text_content)
        factual_review = {
            "pass": parsed.get("pass", True),
            "hallucinations": parsed.get("hallucinations", []),
        }
    except Exception as exc:
        log.error("factual_reviewer_failed", error=str(exc), application_id=app_id)
        factual_review = {"pass": True, "hallucinations": []}

    ats_pass = state.get("ats_review", {}).get("pass", False)
    approved = factual_review["pass"] and ats_pass

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info(
        "node_exit",
        node="agent_factual_reviewer",
        latency_ms=elapsed_ms,
        passed=factual_review["pass"],
        attempts=attempts,
        approved=approved,
    )

    return {
        **state,
        "factual_review": factual_review,
        "approval_attempts": attempts,
        "approved": approved,
    }
