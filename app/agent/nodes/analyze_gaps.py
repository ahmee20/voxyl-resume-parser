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
- `added_keywords` should contain JD-relevant keywords that can be safely and credibly introduced into the resume because the resume shows supporting evidence for the underlying capability.
- The added keyword itself may be a newer or adjacent term, as long as the resume gives clear support for the domain.
- Example: if the resume mentions a "deep learning project", it is valid to recommend `PyTorch` or `TensorFlow` when the JD asks for those frameworks.
- Example: if the resume mentions `LangSmith`, it is valid to recommend `evaluation`, `tracing`, and `observability` when those terms help align with the JD.
- Do not invent a capability that the resume does not support at all. If the JD requires something completely absent, put it in notes.
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


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _has_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _find_evidence(resume_text: str, phrases: list[str], fallback: str) -> str:
    for phrase in phrases:
        match = re.search(phrase, resume_text, flags=re.IGNORECASE)
        if match:
            return match.group(0)
    return fallback


def _normalize_added_keywords(items: object) -> tuple[list[dict[str, str]], set[str]]:
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()

    if not isinstance(items, list):
        return normalized, seen

    for item in items:
        keyword = ""
        evidence = ""
        if isinstance(item, str):
            keyword = item.strip()
        elif isinstance(item, dict):
            keyword = str(item.get("keyword", "")).strip()
            evidence = str(item.get("evidence", "")).strip()
        if not keyword:
            continue
        key = keyword.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "keyword": keyword,
                "evidence": evidence or keyword,
            }
        )

    return normalized, seen


def _add_keyword(
    items: list[dict[str, str]],
    seen: set[str],
    keyword: str,
    evidence: str,
) -> None:
    key = keyword.strip().lower()
    if not key or key in seen:
        return
    items.append({"keyword": keyword.strip(), "evidence": evidence.strip() or keyword.strip()})
    seen.add(key)


def _augment_keywords(parsed: dict, resume_text: str, job_description: str) -> dict:
    added_keywords, seen = _normalize_added_keywords(parsed.get("added_keywords"))
    resume_norm = _norm_text(resume_text)
    jd_norm = _norm_text(job_description)

    if _has_any(resume_norm, [r"\bdeep learning\b", r"\bneural network\b", r"\bcomputer vision\b"]) and _has_any(
        jd_norm, [r"\bpytorch\b", r"\btensorflow\b", r"\bdeep learning\b", r"\bneural network\b", r"\bml\b", r"\bmachine learning\b"]
    ):
        evidence = _find_evidence(resume_text, [r"deep learning", r"neural network", r"computer vision"], "deep learning")
        _add_keyword(added_keywords, seen, "PyTorch", evidence)
        _add_keyword(added_keywords, seen, "TensorFlow", evidence)

    if _has_any(resume_norm, [r"\blangsmith\b"]):
        evidence = _find_evidence(resume_text, [r"LangSmith"], "LangSmith")
        _add_keyword(added_keywords, seen, "evaluation", evidence)
        _add_keyword(added_keywords, seen, "tracing", evidence)
        _add_keyword(added_keywords, seen, "observability", evidence)

    if _has_any(resume_norm, [r"\blangchain\b", r"\bllm\b", r"\brag\b", r"\bagentic\b", r"\bai agent\b"]) and _has_any(
        jd_norm, [r"\bevaluation\b", r"\btracing\b", r"\bobservability\b", r"\bllmops\b", r"\bprompt engineering\b"]
    ):
        evidence = _find_evidence(resume_text, [r"LangChain", r"LLM", r"RAG", r"agentic", r"AI agent"], "LLM systems work")
        _add_keyword(added_keywords, seen, "evaluation", evidence)
        _add_keyword(added_keywords, seen, "tracing", evidence)

    parsed["added_keywords"] = added_keywords
    return parsed


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
        parsed = _augment_keywords(parsed, resume_text, job_description)
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
