"""
app/agent/nodes/draft_email.py — LLM node for drafting recruiter outreach emails.
"""

import re
import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

DRAFT_EMAIL_SYSTEM_PROMPT = """You are a professional executive career agent.
Your task is to draft a concise, persuasive, and professional cold outreach email to a hiring manager or recruiter.

RULES:
1. Grounding: Reference only genuine achievements and skills from the candidate's tailored resume. Never invent facts.
2. Structure:
   - Subject: Specific and value-oriented, not "Application for ..."
   - Greeting: Use the recruiter name if present, otherwise "Hiring Team".
   - Opening: Name the role and explain the candidate's fit in one concrete sentence.
   - Value Proposition: 2-3 bullets with evidence from the resume, tied to how the company benefits.
   - Links: Include portfolio, GitHub, and LinkedIn only if provided.
   - Call to Action: Ask for a short conversation or next step.
   - Attachment notice: Mention that the tailored resume is attached as a PDF.
3. Tone: Human, confident, concise, and respectful of the recruiter's time (150-230 words).
4. Avoid generic filler such as "enthusiastic interest" unless followed by real evidence.
"""


def run_email_drafting(
    resume_text: str,
    job_title: str,
    company: str,
    job_description: str,
    recruiter_name: str | None = None,
    user_profile: dict | None = None,
) -> str:
    """Invoke LLM to draft outreach email."""
    llm = get_llm(temperature=0.2)
    messages = [
        SystemMessage(content=DRAFT_EMAIL_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### TARGET ROLE: {job_title} at {company}\n"
                f"### RECRUITER NAME: {recruiter_name or 'Hiring Team'}\n"
                f"### CANDIDATE PROFILE LINKS:\n{user_profile or {}}\n\n"
                f"### JOB DESCRIPTION:\n{job_description}\n\n"
                f"### CANDIDATE RESUME SUMMARY:\n{resume_text}\n\n"
                "Draft the outreach email:"
            )
        ),
    ]
    response = llm.invoke(messages)
    content = response.content
    if isinstance(content, list):
        content = "".join([part if isinstance(part, str) else part.get("text", "") for part in content])

    raw = str(content)
    # Remove reasoning / think tags
    cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return cleaned.strip()


def _candidate_name_from_profile(user_profile: dict | None) -> str:
    if not user_profile:
        return "the candidate"
    return user_profile.get("preferred_name") or user_profile.get("name") or "the candidate"


def _profile_links_text(user_profile: dict | None) -> str:
    if not user_profile:
        return ""
    links = []
    if user_profile.get("portfolio_url"):
        links.append(f"Portfolio: {user_profile['portfolio_url']}")
    if user_profile.get("github_url"):
        links.append(f"GitHub: {user_profile['github_url']}")
    if user_profile.get("linkedin_url"):
        links.append(f"LinkedIn: {user_profile['linkedin_url']}")
    return "\n".join(links)


def build_fallback_email(
    resume_text: str,
    job_title: str,
    company: str,
    recruiter_name: str | None = None,
    user_profile: dict | None = None,
) -> str:
    """Deterministic fallback that is still usable if the LLM fails."""
    candidate_name = _candidate_name_from_profile(user_profile)
    greeting = recruiter_name or "Hiring Team"
    links = _profile_links_text(user_profile)
    experience_hint = "agentic AI systems, LLM integration, workflow automation, and production Python/FastAPI systems"
    if "LangGraph" in resume_text or "LangChain" in resume_text:
        experience_hint = "agentic AI workflows with LangGraph/LangChain, LLM integration, and production automation"

    links_block = f"\n\n{links}" if links else ""

    return (
        f"Subject: {job_title} | AI automation and agentic systems experience\n\n"
        f"Dear {greeting},\n\n"
        f"I am reaching out about the {job_title} role at {company}. "
        f"{candidate_name} brings hands-on experience in {experience_hint}, with work spanning resume/job automation, "
        "multi-agent pipelines, API integrations, and end-to-end delivery from prototype to deployment.\n\n"
        "A few areas where this background could be useful to your team:\n"
        "- Building reliable AI workflows that connect LLM reasoning with real business operations.\n"
        "- Integrating third-party APIs, databases, and automation tools into production-ready systems.\n"
        "- Translating ambiguous product requirements into working software with observability and review loops.\n"
        f"{links_block}\n\n"
        "I have attached a tailored resume for your review. "
        "Would you be open to a short conversation about how this experience maps to your current AI engineering priorities?\n\n"
        "Best regards"
    )


def draft_email_node(state: GraphState) -> GraphState:
    """LangGraph node for drafting recruiter outreach email."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="draft_email", application_id=app_id, user_id=user_id)

    resume_text = state.get("resume_text", "")
    current_job = state.get("current_job", {})
    job_title = current_job.get("title", "Position")
    company = current_job.get("company", "Company")
    job_description = current_job.get("description", "")
    recruiter_name = current_job.get("recruiter_name")
    user_profile = state.get("user_profile")

    try:
        email_draft = run_email_drafting(
            resume_text=resume_text,
            job_title=job_title,
            company=company,
            job_description=job_description,
            recruiter_name=recruiter_name,
            user_profile=user_profile,
        )
    except Exception as exc:
        log.error("draft_email_failed", error=str(exc), application_id=app_id)
        email_draft = build_fallback_email(
            resume_text=resume_text,
            job_title=job_title,
            company=company,
            recruiter_name=recruiter_name,
            user_profile=user_profile,
        )

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="draft_email", latency_ms=elapsed_ms, application_id=app_id)

    return {
        **state,
        "email_draft": email_draft,
    }
