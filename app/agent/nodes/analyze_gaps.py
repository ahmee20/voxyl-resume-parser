"""
app/agent/nodes/analyze_gaps.py — LLM gap analysis node.

Analyzes the job description against the base resume to identify matching skills,
underemphasized qualifications, and key ATS keywords.

Guardrail (§9 & §8): Strictly forbidden from fabricating skills or experience.
"""

import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

GAP_ANALYSIS_SYSTEM_PROMPT = """You are an expert AI Career Coach and ATS Strategist.
Your goal is to compare a candidate's base resume against a specific target Job Description (JD) and perform a rigorous gap analysis.

CRITICAL GUARDRAIL & ETHICAL CONSTRAINT:
- You must NEVER invent, fabricate, or hallucinate credentials, degrees, employers, or experience that the candidate does not have.
- Only highlight genuine skills, tools, methodologies, and achievements that are already present or directly implied in the candidate's base resume.

Your output should be structured as follows:
1. Target Keywords & Phrases: List the top keywords from the JD that match the candidate's existing experience.
2. Emphasize & Reframe: Identify which bullet points in the resume should be reframed to better showcase impact relevant to the JD.
3. Relevant Skills: Specific tools/frameworks from the candidate's background that should be prominently featured in the skills section.
"""


def run_gap_analysis(resume_text: str, job_description: str) -> str:
    """Invoke LLM to perform grounded gap analysis."""
    llm = get_llm(temperature=0.0)
    messages = [
        SystemMessage(content=GAP_ANALYSIS_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### TARGET JOB DESCRIPTION:\n{job_description}\n\n"
                f"### CANDIDATE BASE RESUME:\n{resume_text}\n\n"
                "Perform the gap analysis according to the instructions:"
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, list):
        content = "".join([part if isinstance(part, str) else part.get("text", "") for part in content])
    return content.strip()


def analyze_gaps_node(state: GraphState) -> GraphState:
    """LangGraph node for gap analysis."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="analyze_gaps", application_id=app_id, user_id=user_id)

    resume_text = state.get("resume_text", "")
    current_job = state.get("current_job", {})
    job_description = current_job.get("description", "") or state.get("gap_analysis", "")

    if not job_description:
        log.warning("analyze_gaps_empty_jd", application_id=app_id)
        gap_analysis = "No job description provided."
    else:
        try:
            gap_analysis = run_gap_analysis(resume_text, job_description)
        except Exception as exc:
            log.error("analyze_gaps_failed", error=str(exc), application_id=app_id)
            gap_analysis = f"Automated gap analysis fallback: align skills for {current_job.get('title', 'target role')}."

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="analyze_gaps", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "gap_analysis": gap_analysis,
    }
