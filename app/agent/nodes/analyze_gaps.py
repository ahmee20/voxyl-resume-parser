"""
app/agent/nodes/analyze_gaps.py - LLM gap analysis node.

Analyzes the job description against the base resume to identify matching skills,
underemphasized qualifications, and key ATS keywords.

Guardrail: strictly forbidden from fabricating skills or experience.
"""

from __future__ import annotations

import json
import re
import time

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

GAP_ANALYSIS_SYSTEM_PROMPT = """You are an expert AI Career Coach and ATS Strategist.
Your goal is to compare a candidate's base resume against a specific target Job Description (JD) and perform a rigorous, evidence-grounded gap analysis.

CRITICAL GUARDRAIL & ETHICAL CONSTRAINT:
- You must NEVER invent, fabricate, or hallucinate credentials, degrees, employers, skills, or experience that the candidate does not have.
- A keyword may only be added if you can quote the EXACT phrase or sentence from the base resume that supports it. If you cannot point to specific text, the keyword does not belong in added_keywords, no exceptions.
- "Directly implied" does NOT mean "same general domain" or "adjacent skill." Working with LLMs is not evidence of model benchmarking. Building a RAG pipeline is not evidence of supervised fine-tuning. Do not infer a specific skill, tool, or methodology from a related-but-different one, even if they share the word "AI" or "LLM."
- If the JD requires a skill/tool/methodology that is absent from the resume, that gap is real. Do not paper over it by adding a nearby-sounding keyword. It is correct and expected for added_keywords to be short or empty when the candidate's real experience is a genuine mismatch for the role.
- When in doubt, leave it out and flag the uncertainty in notes instead.

Return STRICT JSON only with this schema:
{
  "added_keywords": [
    { "keyword": "keyword or phrase", "evidence": "exact short quote from the base resume that supports this" }
  ],
  "removed_keywords": ["keyword 1", "keyword 2"],
  "summary": "short explanation of how to tailor the resume safely, including if the candidate is a weak match for this JD",
  "notes": ["optional note, e.g. JD requirements the candidate does not meet"]
}

Rules:
1. `added_keywords` items must each include a real, verbatim (or near-verbatim) quote from the base resume as evidence. No quote, no entry.
2. `removed_keywords` should contain keywords or phrases currently in the resume that should be removed, downplayed, or not claimed because they are unsupported, too weak, or irrelevant for this job.
3. If a keyword is a strong fit for the JD but the resume does not clearly support it, do not add it, put it in `notes` instead as a flagged gap.
4. Keep the wording concise.
5. Do not invent any experience, tool, or qualification not already present in the base resume text.
6. If the candidate is missing important JD requirements, add a note such as: "If you have [missing skills or requirements], please update your resume or upload your latest resume."
"""


def _extract_json(text: str) -> dict | None:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    candidate = cleaned[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def run_gap_analysis(resume_text: str, job_description: str) -> str:
    """Invoke LLM to perform grounded gap analysis."""
    llm = get_llm(temperature=0.0)
    messages = [
        SystemMessage(content=GAP_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### TARGET JOB DESCRIPTION:\n{job_description}\n\n"
                f"### CANDIDATE BASE RESUME:\n{resume_text}\n\n"
                "Return the JSON payload now."
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, list):
        content = "".join([part if isinstance(part, str) else part.get("text", "") for part in content])

    raw = str(content).strip()
    parsed = _extract_json(raw)
    if parsed is not None:
        return json.dumps(parsed, ensure_ascii=False)
    return raw


def analyze_gaps_node(state: GraphState) -> GraphState:
    """LangGraph node for gap analysis."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="analyze_gaps", application_id=app_id, user_id=user_id)

    resume_text = state.get("resume_text", "")
    current_job = state.get("current_job", {})
    job_description = current_job.get("description", "")

    if not job_description:
        log.warning("analyze_gaps_empty_jd", application_id=app_id)
        gap_analysis = json.dumps(
            {
                "added_keywords": [],
                "removed_keywords": [],
                "summary": "No job description provided.",
                "notes": ["If you have missing job requirements, please update your resume or upload your latest resume."],
            }
        )
    else:
        try:
            gap_analysis = run_gap_analysis(resume_text, job_description)
        except Exception as exc:
            log.error("analyze_gaps_failed", error=str(exc), application_id=app_id)
            fallback = {
                "added_keywords": [],
                "removed_keywords": [],
                "summary": f"Align skills for {current_job.get('title', 'target role')}.",
                "notes": ["If you have missing job requirements, please update your resume or upload your latest resume."],
            }
            gap_analysis = json.dumps(fallback, ensure_ascii=False)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="analyze_gaps", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "gap_analysis": gap_analysis,
    }
