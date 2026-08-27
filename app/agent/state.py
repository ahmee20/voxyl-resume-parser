"""
app/agent/state.py — Shared graph state for the LangGraph pipeline.

GraphState is the single TypedDict that every node reads from and writes to.
LangGraph merges node outputs into this state between node executions.

Design notes:
- All fields are Optional so stub nodes can run without all data present.
- Fields are grouped by pipeline stage for readability.
- The `application_id` and `user_id` fields are required; they must be set
  by the caller before invoking the graph.
"""

from typing import Any, Optional
from typing_extensions import TypedDict


class GraphState(TypedDict, total=False):
    # ── Identity (required before graph entry) ────────────────────────────────
    user_id: int
    application_id: int
    user_profile: dict[str, Any]

    # ── User send-mode preference (read from DB at graph entry) ───────────────
    # "manual" | "auto"
    send_mode: str

    # ── Resume extraction (extract_resume node) ───────────────────────────────
    resume_text: str          # plain-text content of the uploaded resume
    resume_html: str          # normalized HTML skeleton capturing the layout

    # ── Search query planning (plan_search_queries node) ─────────────────────
    search_queries: list[str]  # e.g. ["AI engineer", "senior software engineer"]
    preferred_countries: list[str]  # e.g. ["US", "CA", "GB"]

    # ── Job discovery (scrape_jobs node) ──────────────────────────────────────
    scraped_jobs: list[dict[str, Any]]   # raw Apify result records
    posted_within_hours: int             # discovery window for Apify scraping

    # ── Enrichment (enrich_jobs node) ─────────────────────────────────────────
    enriched_jobs: list[dict[str, Any]]  # scraped_jobs + Apollo data merged

    # ── Filtering + persistence (filter_relevant, persist_jobs nodes) ─────────
    relevant_jobs: list[dict[str, Any]]  # filtered subset
    filtered_jobs: list[dict[str, Any]]  # unqualified jobs (< 70% match)
    persisted_job_ids: list[int]         # DB IDs of jobs written to the jobs table

    # ── Current job being processed (one iteration of the pipeline) ───────────
    current_job: dict[str, Any]
    current_job_id: int                  # DB id of the job being tailored

    # ── Gap analysis (analyze_gaps node) ──────────────────────────────────────
    gap_analysis: str         # LLM output: list of keywords/skills to highlight

    # ── Resume tailoring (tailor_resume node) ─────────────────────────────────
    tailored_resume_html: str  # gap-filled HTML ready for PDF rendering
    resume_template_data: dict[str, Any]  # structured JSON for the PDF.co resume template
    tailored_resume_id: int    # DB id of the saved tailored Resume row

    # ── PDF rendering (render_pdf node) ───────────────────────────────────────
    pdf_url: str              # temporary download URL returned by PDF.co

    # ── Manual path ───────────────────────────────────────────────────────────
    resume_variants: list[str]   # 2-3 HTML variants shown to the user
    selected_variant: str        # the variant the user chose in the UI
    drive_file_url: str          # Drive URL of the uploaded resume (manual)

    # ── Auto path ─────────────────────────────────────────────────────────────
    email_draft: str             # drafted outreach email body
    ats_review: dict[str, Any]   # ATS reviewer output (score + flags)
    factual_review: dict[str, Any]  # factual reviewer output (flags)
    approval_attempts: int       # how many review loops have run (max 3)
    approved: bool               # True when both reviewers pass
    sent: bool                   # True after Gmail send succeeds
    drive_folder_url: str        # Drive folder URL (auto path — per-job folder)

    # ── Error / fallback ──────────────────────────────────────────────────────
    error: Optional[str]          # set by any node on unrecoverable failure
