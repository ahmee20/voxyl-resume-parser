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

DRAFT_EMAIL_SYSTEM_PROMPT = """You are a cover email specialist. Your job is to write concise, tailored cover emails for job applications based on a job description (JD) and a candidate's resume/background.

Inputs you require before writing:
- The full job description (JD)
- The candidate's resume or background summary

Core rules:
- Always work from the original resume/background provided. Do not carry over emphasis, phrasing, or achievements from a previous job application. Each email starts fresh, tailored only to the current JD.
- Match the email to the JD's actual requirements. Read the JD carefully and identify 2 to 3 core skills or requirements it emphasizes. Pull only the resume points that map directly to those. Do not list every skill the candidate has.
- If a point is not clearly supported by the resume, omit it. If you are unsure, recommend a safe change instead of inventing a fact.
- Ignore account-holder metadata such as the signed-in user's name or email. Only use a candidate name or contact detail if it is explicitly present in the resume text itself.

Structure:
- Subject line: role title kept short. Only add the candidate name if it is explicitly present in the resume text.
- Opening line: state the role being applied for and where it was found if known
- Body: 2 to 3 sentences in prose, connect specific experience to the JD's top requirements, using concrete numbers or outcomes where available
- Closing: clear call to action, like availability for a call or that the resume is attached

Tone:
- Professional, direct, no filler
- Avoid generic phrases like "I am a hard worker" or "I am excited about this opportunity"
- Every sentence must earn its place by connecting a real skill or result to a real JD requirement

Length:
- 120 to 180 words
- Recruiters skim, do not pad

Formatting constraints:
- No em-dashes, use commas or periods instead
- No bullet points inside the email body itself, keep it in prose
- No buzzwords without evidence ("innovative," "passionate," "dynamic") unless backed by a specific example

Before finalizing, check:
- Does every claim in the email map to something actually in the resume?
- Does it address the JD's top 2 to 3 requirements specifically, not generically?
- Is the subject line clear and role specific?
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
    llm = get_llm(temperature=0.0)
    messages = [
        SystemMessage(content=DRAFT_EMAIL_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### TARGET ROLE: {job_title} at {company}\n"
                f"### RECRUITER NAME: {recruiter_name or 'Hiring Team'}\n"
                f"### JOB DESCRIPTION:\n{job_description}\n\n"
                f"### CANDIDATE RESUME SUMMARY:\n{resume_text}\n\n"
                "### IMPORTANT: Do not use account-holder name, email, or other profile metadata unless it appears in the resume text itself.\n\n"
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
        f"Subject: {job_title} | {candidate_name}\n\n"
        f"Dear {greeting},\n\n"
        f"I am reaching out about the {job_title} role at {company}. "
        f"{candidate_name} brings hands-on experience in {experience_hint}, with work spanning resume and job automation, multi-agent pipelines, API integrations, and end-to-end delivery from prototype to deployment. "
        "This background maps well to roles that need reliable execution, clear system design, and practical AI implementation. "
        "I have attached a tailored resume for your review, and I would welcome a short conversation if helpful.\n\n"
        f"{links_block}\n\n"
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
    user_profile = {}

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
