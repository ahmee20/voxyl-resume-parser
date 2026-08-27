"""
app/agent/nodes/match_requirements.py — Pre-enrichment candidate requirement & eligibility matcher.

Evaluates scraped job listings against the candidate's resume BEFORE invoking Apollo.io:
1. Tolerance Rule: A difference of ±2 years of experience does NOT disqualify the candidate.
2. 70% Match Rule: Candidate must meet at least 70% of core requirements (or legitimate transferable skills).
3. Jobs meeting >= 70% match proceed to Apollo enrichment.
4. Jobs < 70% are marked as filtered with reasons and match score.
"""

import concurrent.futures
import json
import re
import time
from typing import Any
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from app.agent.state import GraphState
from app.config import settings
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """You are an expert technical talent evaluation system.
Your job is to strictly and objectively assess if a candidate's resume qualifies for a job description.

EVALUATION RULES:
1. EXPERIENCE TOLERANCE: A difference of ±2 years of experience does NOT disqualify the candidate (e.g. if the job asks for 5 years and the candidate has 3-4 years, count it as qualified).
2. 70% MATCH THRESHOLD: The candidate must meet at least 70% of the core requirements, technologies, or have legitimate transferable skills that align with the role.
3. KEYWORD EXPANSION: Consider if the candidate's authentic experience can reasonably cover the role's expectations without fabrication.

OUTPUT FORMAT:
Respond with ONLY valid JSON (no markdown formatting, no code blocks):
{
  "qualified": true,
  "match_percentage": 85,
  "match_reason": "Candidate has strong matching background in required technologies and falls within experience tolerance.",
  "missing_skills": ["Kubernetes"]
}
"""


def _extract_json_from_llm(content: str) -> dict:
    """Extract JSON object from LLM response safely, handling extra text, markdown, or think tags."""
    if not content:
        return {}

    # 1. Remove <think>...</think> if present
    cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 2. Try direct json load
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # 3. Find first outer {...} block
    match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except Exception:
            pass

    # 4. Handle escaped code blocks
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if code_match:
        try:
            return json.loads(code_match.group(1).strip())
        except Exception:
            pass

    # 5. Fallback: extract key values via regex
    qual_match = re.search(r'"qualified"\s*:\s*(true|false)', cleaned, re.IGNORECASE)
    pct_match = re.search(r'"match_percentage"\s*:\s*(\d+)', cleaned)
    reason_match = re.search(r'"match_reason"\s*:\s*"([^"]+)"', cleaned)

    if pct_match:
        score = int(pct_match.group(1))
        is_q = qual_match.group(1).lower() == "true" if qual_match else (score >= 70)
        return {
            "qualified": is_q,
            "match_percentage": score,
            "match_reason": reason_match.group(1) if reason_match else "Evaluated by LLM.",
            "missing_skills": [],
        }

    return {}


def evaluate_job_eligibility(resume_text: str, job: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one job against the resume using LLM with fallback heuristics."""
    title = job.get("title", "Position")
    company = job.get("company", "Company")
    description = job.get("description", "")

    # Fast heuristic check if description is very brief
    if len(description) < 30:
        return {
            "qualified": True,
            "match_percentage": 75,
            "match_reason": "Listing had concise description; matches target title role.",
            "missing_skills": [],
        }

    try:
        llm = get_llm(temperature=0.0)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"CANDIDATE RESUME:\n{resume_text[:2500]}\n\n"
                    f"JOB POSITION: {title} at {company}\n"
                    f"JOB DESCRIPTION:\n{description[:3000]}\n\n"
                    f"Evaluate eligibility (remember ±2 years experience tolerance & 70% match threshold):"
                )
            ),
        ]
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = "".join([p if isinstance(p, str) else p.get("text", "") for p in content])

        parsed = _extract_json_from_llm(str(content))
        if parsed and "match_percentage" in parsed:
            match_score = int(parsed.get("match_percentage", 75))
            qualified = bool(parsed.get("qualified", match_score >= 70))
            return {
                "qualified": qualified and (match_score >= 70),
                "match_percentage": match_score,
                "match_reason": parsed.get("match_reason", "Meets 70%+ core requirements."),
                "missing_skills": parsed.get("missing_skills", []),
            }
        else:
            raise ValueError(f"Could not parse valid JSON from response: {content[:100]}")

    except Exception as exc:
        log.warning("llm_eligibility_eval_fallback", error=str(exc), title=title)
        # Fallback heuristic: keyword matching
        resume_lower = resume_text.lower()
        desc_lower = description.lower()
        common_words = set(re.findall(r"\w{4,}", desc_lower))
        matched = sum(1 for w in common_words if w in resume_lower)
        score = min(90, max(60, int((matched / max(len(common_words), 1)) * 200)))
        return {
            "qualified": score >= 70,
            "match_percentage": score,
            "match_reason": f"Heuristic evaluation estimated {score}% background alignment.",
            "missing_skills": [],
        }


def match_requirements_node(state: GraphState) -> GraphState:
    """
    LangGraph node: Evaluates all scraped jobs against candidate resume before Apollo enrichment.
    Segregates jobs into qualified (>= 70%) and filtered (< 70%).
    """
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="match_requirements", application_id=app_id, user_id=user_id)

    resume_text = state.get("resume_text", "")
    scraped_jobs = state.get("scraped_jobs", [])

    qualified_jobs = []
    filtered_jobs = []

    if scraped_jobs:
        max_workers = min(len(scraped_jobs), settings.batch_parallel_workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            eval_results = list(executor.map(lambda j: evaluate_job_eligibility(resume_text, j), scraped_jobs))

        for job, eval_result in zip(scraped_jobs, eval_results):
            match_score = eval_result["match_percentage"]
            is_qual = eval_result["qualified"]
            reason = eval_result["match_reason"]

            enriched_meta = {
                **job,
                "is_qualified": is_qual,
                "match_score": match_score,
                "filter_reason": reason,
            }

            if is_qual:
                qualified_jobs.append(enriched_meta)
            else:
                filtered_jobs.append(enriched_meta)

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info(
        "node_exit",
        node="match_requirements",
        latency_ms=elapsed_ms,
        qualified_count=len(qualified_jobs),
        filtered_count=len(filtered_jobs),
    )

    return {
        **state,
        "scraped_jobs": qualified_jobs,  # Qualified jobs go to Apollo enrichment
        "filtered_jobs": filtered_jobs,   # Preserved for filtered board
    }
