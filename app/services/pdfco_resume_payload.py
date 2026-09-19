"""
app/services/pdfco_resume_payload.py — build structured JSON for PDF.co resume templates.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.json import parse_partial_json

from app.config import settings
from app.services.llm import get_llm
from app.services.resume_template import ResumeProfile

log = structlog.get_logger(__name__)

RESUME_TEMPLATE_PROMPT = """You convert a tailored resume into structured JSON for the PDF.co HTML template with template id 37621.

Return JSON only. Do not add markdown, commentary, or code fences.

Source-of-truth precedence:
1. TAILORED RESUME HTML is the primary source of truth for all content.
2. BASE RESUME TEXT is a fallback to restore any sections, categories, or details omitted in the tailored HTML.
3. GAP ANALYSIS documents the keyword additions and specific keyword removals applied during tailoring.

CRITICAL RULES — SKILLS EXTRACTION & PRESERVATION:
- The `skills` array MUST contain EVERY skill category and ALL remaining skill items from the tailored resume HTML (or base resume text).
- Each skill category (e.g. "Agentic AI & LLMs", "AI Automation & Integration", "ML, CV & Data", "Frontend & Backend", "Tools & Practices") must be its own object in the `skills` array with `category` and `items` keys.
- The `items` value must be a comma-separated string of ALL the skills listed under that category.
- Only the specific individual keywords listed in `removed_keywords` should be excluded. ALL OTHER skills, tools, and technologies from the candidate's resume MUST be included in full!
- NEVER collapse multiple skill categories into one single "Core" or generic category.
- NEVER replace the full skills list with just the gap analysis added keywords. Added keywords are additions to existing skills, NOT a replacement for all other skills.
- If the tailored resume HTML is missing any skill category that existed in the base resume text, extract that category from the base resume text (omitting only the specific removed_keywords).

Rules:
1. Extract ALL content from the tailored resume HTML faithfully. Do not summarize, abbreviate, or omit anything.
2. If a field or section or skill category is missing from the tailored resume, fall back to the base resume text to restore it (omitting only the specific removed_keywords).
3. PRESERVE ALL PROJECTS: You MUST include every single project present in the resume under `projects` with ALL their bullet points. Do NOT remove, drop, omit, or merge any projects.
4. PRESERVE ALL EXPERIENCES: Every work experience entry must appear under `experience` with ALL bullet points. Do NOT remove, drop, or omit any job entry.
5. PRESERVE ALL SKILLS: Every skill category must appear under `skills` with ALL its items (omitting only the specific individual words in `removed_keywords`). Do NOT collapse categories or drop untouched skills.
6. PRESERVE ALL EDUCATION: Every degree, institution, date range, and coursework must appear under `education`.
7. PRESERVE ALL CERTIFICATIONS: Every certification, achievement, award, or honor must appear under `certifications`.
8. Do not invent titles, dates, employers, degrees, skills, or certifications.
9. If the profile block conflicts with the tailored resume or base text, the resume text wins.
10. Recognize these section aliases and map them to the canonical key instead of skipping them:
   - summary: professional summary, summary, profile, overview
   - skills: technical skills, skills, core competencies, competencies
   - experience: professional experience, work experience, industry experience, job experience, previous experience, employment history, career history
   - projects: projects, key projects, selected projects, relevant projects, personal projects, academic projects
   - education: education, academic background, academics
   - certifications: certifications, certifications & achievements, achievements, honors, awards
11. Use only these top-level keys: full_name, headline, phone, email, linkedin_url, github_url, summary, skills, experience, projects, education, certifications.
12. Do not emit empty strings, empty arrays, or extra keys.

VERIFICATION BEFORE RETURNING:
- Check `projects`: Are ALL projects from the candidate's resume present? None may be missing.
- Check `experience`: Are ALL work experiences and all bullets present? None may be missing.
- Check `skills`: Are ALL skill categories (e.g. Agentic AI & LLMs, AI Automation & Integration, ML, CV & Data, Frontend & Backend, Tools & Practices) present with all their items? Only specific `removed_keywords` should be excluded.
- Check `education` and `certifications`: Are all entries included?
If any item was omitted in the tailored HTML, you MUST restore it from the base resume text before returning!

Schema:
{
  "full_name": string,
  "headline": string,
  "phone": string,
  "email": string,
  "linkedin_url": string,
  "github_url": string,
  "summary": string,
  "skills": [{"category": string, "items": string}],
  "experience": [
    {
      "company": string,
      "role": string,
      "location": string,
      "date_start": string,
      "date_end": string,
      "bullets": [string]
    }
  ],
  "projects": [
    {
      "name": string,
      "tech": string,
      "date": string,
      "bullets": [string]
    }
  ],
  "education": [
    {
      "school": string,
      "degree": string,
      "location": string,
      "date_start": string,
      "date_end": string,
      "coursework": string
    }
  ],
  "certifications": [string]
}
"""

ALLOWED_TOP_LEVEL_KEYS = {
    "full_name",
    "headline",
    "phone",
    "email",
    "linkedin_url",
    "github_url",
    "summary",
    "skills",
    "experience",
    "projects",
    "education",
    "certifications",
}

ALLOWED_SKILL_KEYS = {"category", "items"}
ALLOWED_EXPERIENCE_KEYS = {"company", "role", "location", "date_start", "date_end", "bullets"}
ALLOWED_PROJECT_KEYS = {"name", "tech", "date", "bullets"}
ALLOWED_EDUCATION_KEYS = {"school", "degree", "location", "date_start", "date_end", "coursework"}


def _profile_block(profile: ResumeProfile | None) -> str:
    if not profile:
        return "{}"
    return json.dumps(
        {
            "linkedin_url": profile.linkedin_url,
            "github_url": profile.github_url,
            "portfolio_url": profile.portfolio_url,
        },
        ensure_ascii=False,
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    payload = cleaned[start : end + 1]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        try:
            data = parse_partial_json(payload)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
    return data if isinstance(data, dict) else None


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            pruned = _prune_empty(item)
            if pruned in (None, "", [], {}):
                continue
            cleaned[key] = pruned
        return cleaned
    if isinstance(value, list):
        cleaned_list = []
        for item in value:
            pruned = _prune_empty(item)
            if pruned in (None, "", [], {}):
                continue
            cleaned_list.append(pruned)
        return cleaned_list
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


def _normalize_section_items(items: Any, allowed_keys: set[str]) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        candidate = {key: item.get(key) for key in allowed_keys if key in item}
        cleaned = _prune_empty(candidate)
        if isinstance(cleaned, dict) and cleaned:
            normalized.append(cleaned)
    return normalized


def _normalize_resume_payload(data: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in ALLOWED_TOP_LEVEL_KEYS:
        if key in data:
            normalized[key] = data[key]

    normalized = _prune_empty(normalized) if isinstance(normalized, dict) else {}
    if not isinstance(normalized, dict):
        return {}

    if "skills" in normalized:
        normalized["skills"] = _normalize_section_items(normalized["skills"], ALLOWED_SKILL_KEYS)
    if "experience" in normalized:
        normalized["experience"] = _normalize_section_items(normalized["experience"], ALLOWED_EXPERIENCE_KEYS)
    if "projects" in normalized:
        normalized["projects"] = _normalize_section_items(normalized["projects"], ALLOWED_PROJECT_KEYS)
    if "education" in normalized:
        normalized["education"] = _normalize_section_items(normalized["education"], ALLOWED_EDUCATION_KEYS)
    if "certifications" in normalized and isinstance(normalized["certifications"], list):
        normalized["certifications"] = [item.strip() for item in normalized["certifications"] if isinstance(item, str) and item.strip()]

    return _prune_empty(normalized) if isinstance(normalized, dict) else {}


def build_pdfco_resume_template_data(
    tailored_resume_html: str,
    resume_text: str,
    profile: ResumeProfile | None = None,
    gap_analysis: str | None = None,
) -> dict[str, Any] | None:
    """
    Convert a tailored resume into the structured JSON object expected by the PDF.co template.
    Missing fields are omitted. If parsing fails, the caller can still send an empty
    payload to the template rather than falling back to plain HTML rendering.
    """
    if not (tailored_resume_html.strip() or resume_text.strip()):
        return None

    llm = get_llm(temperature=0.0, max_tokens=settings.llm_max_output_tokens)
    gap_analysis_block = gap_analysis.strip() if isinstance(gap_analysis, str) else "{}"
    messages = [
        SystemMessage(content=RESUME_TEMPLATE_PROMPT),
        HumanMessage(
            content=(
                f"### CANDIDATE PROFILE\n{_profile_block(profile)}\n\n"
                f"### TAILORED RESUME HTML\n{tailored_resume_html}\n\n"
                f"### GAP ANALYSIS (keyword additions and specific keyword removals)\n{gap_analysis_block}\n\n"
                f"### BASE RESUME TEXT (use to restore any categories or sections omitted in tailored HTML)\n{resume_text}\n\n"
                "Return the JSON payload for the PDF.co template now."
            )
        ),
    ]

    try:
        response = llm.invoke(messages)
        content = response.content
        if isinstance(content, list):
            content = "".join([part if isinstance(part, str) else part.get("text", "") for part in content])
        data = _extract_json(str(content))
        if not data:
            return None
        cleaned = _normalize_resume_payload(data)
        return cleaned if isinstance(cleaned, dict) and cleaned else None
    except Exception as exc:
        log.warning("pdfco_resume_template_data_failed", error=str(exc))
        return None
