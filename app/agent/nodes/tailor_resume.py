"""
app/agent/nodes/tailor_resume.py — LLM resume tailoring node.

Fills the gaps identified by analyze_gaps into the candidate's HTML resume template,
preserving the original structure, CSS classes, and layout.
"""

import html
import json
import re
import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

TAILOR_RESUME_SYSTEM_PROMPT = """You are an expert resume tailoring specialist.
Your task is to take a candidate's resume in HTML format and a detailed gap analysis, and produce an updated HTML resume tailored specifically for the target job.

CRITICAL RULES FOR CONTENT PRESERVATION & TAILORING:
1. PRESERVE ALL PROJECTS & EXPERIENCES:
   - Every single project entry must remain intact under its section with all its bullet points.
   - Every single work experience entry must remain intact with company name, dates, role, and all bullet points.
   - Every single education entry and certification must remain intact.
   - Do NOT drop, omit, summarize, or remove ANY projects or experience entries.

2. PRESERVE ALL SKILL CATEGORIES & ALL NON-REMOVED SKILLS:
   - The Technical Skills section contains multiple skill categories (e.g., "Agentic AI & LLMs", "AI Automation & Integration", "ML, CV & Data", "Frontend & Backend", "Tools & Practices").
   - You MUST keep EVERY skill category and EVERY skill within each category, EXCEPT ONLY the specific individual keywords listed in `removed_keywords` of the gap analysis.
   - NEVER drop an entire skill category.
   - NEVER replace the entire skills section with just the added keywords.
   - All skills that are NOT explicitly listed in `removed_keywords` MUST be preserved verbatim!

3. APPLY `removed_keywords`:
   - You MUST remove only the specific keywords/skills explicitly listed in `removed_keywords` of the gap analysis.
   - Do NOT remove any skill that is not in `removed_keywords`.

4. INTEGRATE `added_keywords`:
   - Add the keywords from `added_keywords` into the appropriate existing skill category in the Technical Skills section, and/or naturally weave them into relevant project or experience bullet points where supported.
   - Added keywords are ADDITIONS to the candidate's existing skill sets, NOT replacements for them.

5. PRESERVE HTML LAYOUT & TAGS:
   - Keep all HTML tags, hierarchy, section order, and CSS classes intact (<section class="resume-section">, <p class="skill-line">, <h2>, <ul>, <li>, etc.).
   - Do NOT wrap the output in markdown backticks or ```html wrappers. Return ONLY the raw HTML string starting with <div and ending with </div>.

6. NO FABRICATION:
   - Do NOT invent fabricated job titles, companies, dates, degrees, or tools. Only enhance genuine experience and skills.

FINAL CHECK BEFORE OUTPUTTING:
Count the number of skill categories, projects, and experience entries in your output. If ANY skill category, project, or experience entry from the base resume is missing, fix it before returning.
"""


def _gap_items(gap_analysis: str) -> tuple[list[str], list[str]]:
    """Extract added_keywords and removed_keywords from gap analysis."""
    try:
        parsed = json.loads(gap_analysis)
    except (TypeError, json.JSONDecodeError):
        return [], []
    if not isinstance(parsed, dict):
        return [], []

    added = parsed.get("added_keywords", [])
    added_keywords = [
        item.get("keyword", "").strip()
        for item in added
        if isinstance(item, dict) and isinstance(item.get("keyword"), str) and item.get("keyword", "").strip()
    ]
    removed = parsed.get("removed_keywords", [])
    removed_keywords = [item.strip() for item in removed if isinstance(item, str) and item.strip()]
    return added_keywords, removed_keywords


def _rewrite_text_nodes(resume_html: str, added_keywords: list[str], removed_keywords: list[str]) -> str:
    """Remove words marked in removed_keywords and ensure added_keywords are present."""
    parts = re.split(r"(<[^>]+>)", resume_html)
    text_indexes = range(0, len(parts), 2)
    for index in text_indexes:
        text = parts[index]
        for keyword in removed_keywords:
            text = re.sub(rf"(?<!\w){re.escape(keyword)}(?!\w)", "", text, flags=re.IGNORECASE)
        # Clean up punctuation artifacts from removals
        text = re.sub(r",\s*,+", ", ", text)
        text = re.sub(r":\s*,\s*", ": ", text)
        text = re.sub(r",\s*$", "", text.strip())
        parts[index] = text

    rewritten_html = "".join(parts)
    searchable_text = " ".join(parts[index] for index in text_indexes).casefold()
    missing = [keyword for keyword in added_keywords if not re.search(
        rf"(?<!\w){re.escape(keyword.casefold())}(?!\w)", searchable_text
    )]
    if not missing:
        return rewritten_html

    # Inject missing keywords into existing skill line or section rather than appending a duplicate section
    skill_line_match = re.search(r'(<p class="skill-line">.*?)(</p>)', rewritten_html, re.IGNORECASE | re.DOTALL)
    if skill_line_match:
        addition = ", " + ", ".join(html.escape(kw) for kw in missing)
        return rewritten_html[:skill_line_match.end(1)] + addition + rewritten_html[skill_line_match.start(2):]

    skills_sec_match = re.search(r'(<section\b[^>]*>.*?<h2>(?:Technical )?Skills</h2>.*?)(</section>)', rewritten_html, re.IGNORECASE | re.DOTALL)
    if skills_sec_match:
        addition = '<p class="skill-line"><strong>Additional:</strong> ' + ", ".join(html.escape(kw) for kw in missing) + '</p>'
        return rewritten_html[:skills_sec_match.start(2)] + addition + rewritten_html[skills_sec_match.start(2):]

    # Fallback if no skills section existed at all
    skills_markup = "<ul>" + "".join(f"<li>{html.escape(keyword)}</li>" for keyword in missing) + "</ul>"
    section = f'<section class="resume-section"><h2>Skills</h2>{skills_markup}</section>'
    closing_tag = re.search(r"</div>\s*$", rewritten_html, re.IGNORECASE)
    if closing_tag:
        return rewritten_html[:closing_tag.start()] + section + rewritten_html[closing_tag.start():]
    return rewritten_html + section


def _ensure_profile_links(resume_html: str, user_profile: dict | None) -> str:
    if not user_profile:
        return resume_html
    links = []
    for label, key in (("GitHub", "github_url"), ("LinkedIn", "linkedin_url"), ("Portfolio", "portfolio_url")):
        value = user_profile.get(key)
        if not isinstance(value, str) or not value.strip() or value.casefold() in resume_html.casefold():
            continue
        url = value.strip() if re.match(r"^https?://", value.strip(), re.IGNORECASE) else f"https://{value.strip()}"
        links.append(f'<a href="{html.escape(url, quote=True)}">{label}</a>')
    if not links:
        return resume_html
    contact_markup = '<p class="profile-links">' + " | ".join(links) + "</p>"
    header = re.search(r"<header\b[^>]*>", resume_html, re.IGNORECASE)
    if header:
        return resume_html[:header.end()] + contact_markup + resume_html[header.end():]
    return contact_markup + resume_html


def run_resume_tailoring(resume_html: str, gap_analysis: str, user_profile: dict | None = None) -> str:
    """Invoke LLM to update HTML resume based on gap analysis."""
    llm = get_llm(temperature=0.1)
    messages = [
        SystemMessage(content=TAILOR_RESUME_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                f"### GAP ANALYSIS & KEYWORD RECOMMENDATIONS:\n{gap_analysis}\n\n"
                f"### USER PROFILE LINKS (include these in the contact header):\n{json.dumps(user_profile or {}, ensure_ascii=False)}\n\n"
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
        candidate_html = fence_match.group(1).strip()
        added, removed = _gap_items(gap_analysis)
        return _ensure_profile_links(_rewrite_text_nodes(candidate_html, added, removed), user_profile)

    div_match = re.search(r"(<div.*?>.*?</div>)", cleaned, re.DOTALL | re.IGNORECASE)
    if div_match:
        candidate_html = div_match.group(1).strip()
        added, removed = _gap_items(gap_analysis)
        return _ensure_profile_links(_rewrite_text_nodes(candidate_html, added, removed), user_profile)

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

    added, removed = _gap_items(gap_analysis)
    return _ensure_profile_links(_rewrite_text_nodes(candidate_html, added, removed), user_profile)


def tailor_resume_node(state: GraphState) -> GraphState:
    """LangGraph node for resume tailoring."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="tailor_resume", application_id=app_id, user_id=user_id)

    resume_html = state.get("resume_html", "")
    gap_analysis = state.get("gap_analysis", "")
    user_profile = state.get("user_profile") or {}

    if not resume_html:
        log.warning("tailor_resume_missing_html", application_id=app_id)
        tailored_html = f'<div class="resume"><p>{state.get("resume_text", "")}</p></div>'
    else:
        try:
            tailored_html = run_resume_tailoring(resume_html, gap_analysis, user_profile)
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
