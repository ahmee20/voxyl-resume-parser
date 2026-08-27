"""Deterministic resume HTML renderer.

LLMs are useful for wording, but resume layout should not depend on model taste.
This module turns extracted resume text plus saved profile links into a clean,
print-friendly HTML document.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass


SECTION_ALIASES = {
    "professional summary": "Professional Summary",
    "summary": "Professional Summary",
    "profile": "Professional Summary",
    "overview": "Professional Summary",
    "technical skills": "Technical Skills",
    "skills": "Technical Skills",
    "core competencies": "Technical Skills",
    "competencies": "Technical Skills",
    "professional experience": "Professional Experience",
    "experience": "Professional Experience",
    "work experience": "Professional Experience",
    "industry experience": "Professional Experience",
    "job experience": "Professional Experience",
    "previous experience": "Professional Experience",
    "employment history": "Professional Experience",
    "career history": "Professional Experience",
    "key projects": "Key Projects",
    "projects": "Key Projects",
    "selected projects": "Key Projects",
    "relevant projects": "Key Projects",
    "education": "Education",
    "academic background": "Education",
    "certifications": "Certifications & Achievements",
    "certifications & achievements": "Certifications & Achievements",
    "achievements": "Certifications & Achievements",
    "honors": "Certifications & Achievements",
    "awards": "Certifications & Achievements",
}

SECTION_ORDER = [
    "Professional Summary",
    "Technical Skills",
    "Professional Experience",
    "Key Projects",
    "Education",
    "Certifications & Achievements",
]


@dataclass
class ResumeProfile:
    name: str | None = None
    email: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    linkedin_url: str | None = None


def _escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if re.match(r"^https?://", cleaned, re.IGNORECASE):
        return cleaned
    return f"https://{cleaned}"


def _is_section_heading(line: str) -> str | None:
    normalized = re.sub(r"[:\s]+$", "", line.strip()).lower()
    if normalized in SECTION_ALIASES:
        return SECTION_ALIASES[normalized]
    if line.strip().isupper() and 3 <= len(line.strip()) <= 50:
        return SECTION_ALIASES.get(normalized, line.strip().title())
    return None


def _split_resume_text(resume_text: str) -> tuple[list[str], dict[str, list[str]]]:
    lines = [line.strip() for line in resume_text.replace("\r\n", "\n").split("\n") if line.strip()]
    intro: list[str] = []
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in lines:
        heading = _is_section_heading(line)
        if heading:
            current_section = heading
            sections.setdefault(current_section, [])
            continue

        if current_section:
            sections.setdefault(current_section, []).append(line)
        else:
            intro.append(line)

    return intro, sections


def _render_contact_links(profile: ResumeProfile, intro: list[str]) -> str:
    links: list[tuple[str, str | None]] = []
    if profile.email:
        links.append(("Email", f"mailto:{profile.email}"))
    if profile.linkedin_url:
        links.append(("LinkedIn", _normalize_url(profile.linkedin_url)))
    if profile.github_url:
        links.append(("GitHub", _normalize_url(profile.github_url)))
    if profile.portfolio_url:
        links.append(("Portfolio", _normalize_url(profile.portfolio_url)))

    if links:
        return "\n".join(
            f'<a href="{_escape(url)}">{_escape(label)}</a>'
            for label, url in links
            if url
        )

    if len(intro) > 1:
        return _escape(intro[1])
    return ""


def _render_lines(lines: list[str], section_name: str) -> str:
    blocks: list[str] = []
    bullet_items: list[str] = []

    def flush_bullets() -> None:
        if bullet_items:
            blocks.append("<ul>" + "".join(bullet_items) + "</ul>")
            bullet_items.clear()

    for line in lines:
        stripped = line.lstrip("•-* ").strip()
        is_bullet = line.startswith(("•", "-", "*"))

        if is_bullet:
            bullet_items.append(f"<li>{_escape(stripped)}</li>")
            continue

        flush_bullets()

        if section_name in {"Professional Experience", "Key Projects", "Education"}:
            blocks.append(f'<p class="item-title">{_escape(line)}</p>')
        elif ":" in line and section_name == "Technical Skills":
            label, value = line.split(":", 1)
            blocks.append(
                f'<p class="skill-line"><strong>{_escape(label.strip())}:</strong> {_escape(value.strip())}</p>'
            )
        else:
            blocks.append(f"<p>{_escape(line)}</p>")

    flush_bullets()
    return "\n".join(blocks)


def render_resume_html(resume_text: str, profile: ResumeProfile | None = None) -> str:
    """Render resume text as polished, PDF-ready HTML."""
    # Never trust account profile data for resume identity fields. The uploaded
    # resume text is the source of truth, so the renderer only derives identity
    # from that text.
    profile = ResumeProfile()
    intro, sections = _split_resume_text(resume_text)
    fallback_name = intro[0] if intro else "Candidate"
    display_name = profile.name or fallback_name
    title = intro[1] if len(intro) > 1 and not profile.email else ""
    contact_html = _render_contact_links(profile, intro)

    ordered_sections = [name for name in SECTION_ORDER if sections.get(name)]
    ordered_sections.extend(name for name in sections if name not in ordered_sections)

    section_html = "\n".join(
        f"""
        <section class="resume-section">
          <h2>{_escape(section_name)}</h2>
          {_render_lines(sections[section_name], section_name)}
        </section>
        """
        for section_name in ordered_sections
    )

    return f"""<div class="resume-document">
  <style>
    .resume-document {{
      box-sizing: border-box;
      max-width: 8.5in;
      min-height: 11in;
      margin: 0 auto;
      padding: 0.42in 0.52in;
      color: #111827;
      background: #ffffff;
      font-family: "Aptos", "Calibri", "Segoe UI", sans-serif;
      font-size: 10.2px;
      line-height: 1.25;
    }}
    .resume-document * {{ box-sizing: border-box; }}
    .resume-header {{
      text-align: center;
      border-bottom: 1.5px solid #1f4e79;
      padding-bottom: 6px;
      margin-bottom: 7px;
    }}
    .resume-header h1 {{
      margin: 0;
      color: #000000;
      font-size: 18px;
      font-weight: 800;
      line-height: 1.05;
    }}
    .resume-title {{
      margin: 2px 0 3px;
      color: #1f2937;
      font-size: 10px;
      font-weight: 700;
    }}
    .resume-contact {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: center;
      gap: 5px 10px;
      color: #111827;
      font-size: 8.8px;
    }}
    .resume-contact a {{
      color: #111827;
      text-decoration: none;
      font-weight: 600;
    }}
    .resume-section {{
      margin: 5px 0 0;
      break-inside: avoid;
    }}
    .resume-section h2 {{
      margin: 0 0 3px;
      padding-bottom: 1px;
      border-bottom: 1px solid #1f4e79;
      color: #1f4e79;
      font-size: 10.6px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .resume-section p {{
      margin: 1.5px 0;
    }}
    .resume-section strong {{
      color: #000000;
      font-weight: 800;
    }}
    .item-title {{
      color: #111827;
      font-weight: 800;
    }}
    .skill-line {{
      margin: 1px 0;
    }}
    .resume-section ul {{
      margin: 1px 0 3px 13px;
      padding: 0;
    }}
    .resume-section li {{
      margin: 1px 0;
      padding-left: 1px;
    }}
    @page {{
      size: Letter;
      margin: 0.25in;
    }}
  </style>
  <header class="resume-header">
    <h1>{_escape(display_name)}</h1>
    {f'<p class="resume-title">{_escape(title)}</p>' if title else ''}
    <div class="resume-contact">{contact_html}</div>
  </header>
  {section_html}
</div>"""
