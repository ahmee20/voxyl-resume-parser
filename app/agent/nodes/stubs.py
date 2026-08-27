"""
app/agent/nodes/stubs.py — Stub implementations for all 16 LangGraph nodes.

Every node here:
1. Logs its name + the application_id so traces are readable.
2. Records a row in the agent_runs table (latency included).
3. Returns the state unchanged (no real logic yet).

Replace each stub body with real logic in Phase 1 — the graph topology and
the observability wiring are correct from day one.

Node index (matches PROJECT_PLAN.md §5):
  1.  extract_resume
  2.  plan_search_queries
  3.  scrape_jobs
  4.  enrich_jobs
  5.  filter_relevant
  6.  persist_jobs
  7.  analyze_gaps
  8.  tailor_resume
  9.  render_pdf
  10. present_variants      (manual path)
  11. upload_manual         (manual path — terminal)
  12. draft_email           (auto path)
  13. agent_ats_reviewer    (auto path, review loop)
  14. agent_factual_reviewer(auto path, review loop)
  15. send_and_file         (auto path, approved — terminal)
  16. manual_fallback       (auto path, cap reached — terminal)
"""

import time
import structlog

from app.agent.state import GraphState

log = structlog.get_logger(__name__)


# ── Internal helper ───────────────────────────────────────────────────────────

def _log_node(name: str, state: GraphState) -> float:
    """Log entry into a node and return the start timestamp."""
    log.info(
        "node_enter",
        node=name,
        application_id=state.get("application_id"),
        user_id=state.get("user_id"),
    )
    return time.perf_counter()


def _log_node_exit(name: str, start: float, state: GraphState) -> None:
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    log.info(
        "node_exit",
        node=name,
        latency_ms=elapsed_ms,
        application_id=state.get("application_id"),
    )


# ── Node 1 ────────────────────────────────────────────────────────────────────
def extract_resume(state: GraphState) -> GraphState:
    """Parse uploaded resume PDF/DOCX into text + normalized HTML skeleton."""
    start = _log_node("extract_resume", state)
    # TODO (Phase 1): use pypdf / python-docx to extract text; call LLM to
    #   normalize into an HTML skeleton preserving the original layout sections.
    _log_node_exit("extract_resume", start, state)
    return {
        **state,
        "resume_text": state.get("resume_text", "[stub] resume text"),
        "resume_html": state.get("resume_html", "<html>[stub]</html>"),
    }


# ── Node 2 ────────────────────────────────────────────────────────────────────
def plan_search_queries(state: GraphState) -> GraphState:
    """LLM node: propose job-title/seniority search queries from the base resume."""
    start = _log_node("plan_search_queries", state)
    # TODO (Phase 1): invoke Claude via LangChain BaseChatModel with a prompt
    #   asking it to derive 3-5 job search queries from state["resume_text"].
    _log_node_exit("plan_search_queries", start, state)
    return {
        **state,
        "search_queries": state.get("search_queries", ["AI engineer", "software engineer"]),
    }


# ── Node 3 ────────────────────────────────────────────────────────────────────
def scrape_jobs(state: GraphState) -> GraphState:
    """Tool node: call Apify actor with the planned search queries."""
    start = _log_node("scrape_jobs", state)
    # TODO (Phase 1): apify_client.actor(settings.apify_actor_id).call(
    #   run_input={"queries": state["search_queries"], "maxResults": 50}
    # ) and map results to our schema.
    _log_node_exit("scrape_jobs", start, state)
    return {**state, "scraped_jobs": state.get("scraped_jobs", [])}


# ── Node 4 ────────────────────────────────────────────────────────────────────
def enrich_jobs(state: GraphState) -> GraphState:
    """Tool node: call Apollo.io to enrich company/recruiter data per job."""
    start = _log_node("enrich_jobs", state)
    # TODO (Phase 1): for each job in state["scraped_jobs"], POST to Apollo
    #   /v1/people/match or /v1/organizations/enrich and merge results.
    _log_node_exit("enrich_jobs", start, state)
    return {**state, "enriched_jobs": state.get("enriched_jobs", state.get("scraped_jobs", []))}


# ── Node 5 ────────────────────────────────────────────────────────────────────
def filter_relevant(state: GraphState) -> GraphState:
    """LLM or rule-based node: filter enriched jobs down to relevant/eligible ones."""
    start = _log_node("filter_relevant", state)
    # TODO (Phase 1): apply rule-based filters (seniority, location, etc.)
    #   then optionally run an LLM pass to score relevance against the resume.
    _log_node_exit("filter_relevant", start, state)
    return {**state, "relevant_jobs": state.get("relevant_jobs", state.get("enriched_jobs", []))}


# ── Node 6 ────────────────────────────────────────────────────────────────────
def persist_jobs(state: GraphState) -> GraphState:
    """Write filtered jobs to the jobs table, deduping on URL (unique constraint)."""
    start = _log_node("persist_jobs", state)
    # TODO (Phase 1): bulk-insert state["relevant_jobs"] using
    #   INSERT ... ON CONFLICT (url) DO NOTHING, return inserted DB ids.
    _log_node_exit("persist_jobs", start, state)
    return {**state, "persisted_job_ids": state.get("persisted_job_ids", [])}


# ── Node 7 ────────────────────────────────────────────────────────────────────
def analyze_gaps(state: GraphState) -> GraphState:
    """LLM node: job description + base resume → list of gap keywords/skills.

    Constraint (from §9 and §8): the LLM must only surface skills genuinely
    present in the candidate's real experience.  This is enforced in the prompt
    and verified by the faithfulness eval in LangSmith.
    """
    start = _log_node("analyze_gaps", state)
    # TODO (Phase 1): craft a system prompt that:
    #   1. Presents the job description and the base resume.
    #   2. Asks the LLM to list keywords/skills present in the JD but
    #      underemphasised in the resume, that the candidate actually has.
    #   3. Explicitly forbids the LLM from suggesting invented experience.
    _log_node_exit("analyze_gaps", start, state)
    return {**state, "gap_analysis": state.get("gap_analysis", "[stub] no gaps found")}


# ── Node 8 ────────────────────────────────────────────────────────────────────
def tailor_resume(state: GraphState) -> GraphState:
    """LLM node: fill identified gaps into resume_html, preserving layout."""
    start = _log_node("tailor_resume", state)
    # TODO (Phase 1): provide the LLM with state["resume_html"] and
    #   state["gap_analysis"]; instruct it to return valid HTML that fills
    #   the gaps while keeping all structure/section order identical.
    _log_node_exit("tailor_resume", start, state)
    return {
        **state,
        "tailored_resume_html": state.get("tailored_resume_html", state.get("resume_html", "")),
    }


# ── Node 9 ────────────────────────────────────────────────────────────────────
def render_pdf(state: GraphState) -> GraphState:
    """Tool node: POST tailored_resume_html to PDF.co and get a download URL."""
    start = _log_node("render_pdf", state)
    # TODO (Phase 1): POST to https://api.pdf.co/v1/pdf/convert/from/html
    #   with the API key from settings and state["tailored_resume_html"].
    _log_node_exit("render_pdf", start, state)
    return {**state, "pdf_url": state.get("pdf_url", "https://example.com/stub.pdf")}


# ── Node 10 (manual path) ─────────────────────────────────────────────────────
def present_variants(state: GraphState) -> GraphState:
    """Generate 2-3 resume/email variants; pause graph for user selection."""
    start = _log_node("present_variants", state)
    # TODO (Phase 1): invoke the LLM 2-3 times with temperature variation to
    #   produce distinct variants; persist them; signal the UI to render a
    #   picker. The graph will be resumed via a /applications/{id}/select
    #   endpoint that sets state["selected_variant"].
    _log_node_exit("present_variants", start, state)
    return {**state, "resume_variants": state.get("resume_variants", [])}


# ── Node 11 (manual path — terminal) ─────────────────────────────────────────
def upload_manual(state: GraphState) -> GraphState:
    """Upload chosen resume to Drive (root folder, no email sent). Terminal node."""
    start = _log_node("upload_manual", state)
    # TODO (Phase 1): use google-api-python-client to upload the PDF to Drive;
    #   store the returned file URL in state["drive_file_url"] and in the DB.
    _log_node_exit("upload_manual", start, state)
    return {**state, "drive_file_url": state.get("drive_file_url", "")}


# ── Node 12 (auto path) ───────────────────────────────────────────────────────
def draft_email(state: GraphState) -> GraphState:
    """LLM node: draft a recruiter outreach email for the current job."""
    start = _log_node("draft_email", state)
    # TODO (Phase 1): craft a prompt with the job description, company name,
    #   recruiter name (from Apollo enrichment), and the tailored resume summary.
    _log_node_exit("draft_email", start, state)
    return {**state, "email_draft": state.get("email_draft", "[stub] email draft")}


# ── Node 13 (auto path, review loop) ──────────────────────────────────────────
def agent_ats_reviewer(state: GraphState) -> GraphState:
    """LLM reviewer: score keyword/ATS match; flag any invented claims vs. source resume."""
    start = _log_node("agent_ats_reviewer", state)
    # TODO (Phase 1): compare state["tailored_resume_html"] to
    #   state["current_job"]["description"] for keyword coverage.
    #   Compare against state["resume_text"] to flag invented experience.
    #   Return a structured dict: {"score": 0-100, "pass": bool, "flags": [...]}
    _log_node_exit("agent_ats_reviewer", start, state)
    return {**state, "ats_review": state.get("ats_review", {"score": 100, "pass": True, "flags": []})}


# ── Node 14 (auto path, review loop) ──────────────────────────────────────────
def agent_factual_reviewer(state: GraphState) -> GraphState:
    """LLM reviewer: verify no hallucinated experience, credentials, or contact info."""
    start = _log_node("agent_factual_reviewer", state)
    # TODO (Phase 1): cross-reference every claim in state["tailored_resume_html"]
    #   and state["email_draft"] against state["resume_text"].
    #   Return {"pass": bool, "hallucinations": [...]}
    _log_node_exit("agent_factual_reviewer", start, state)
    return {
        **state,
        "factual_review": state.get("factual_review", {"pass": True, "hallucinations": []}),
    }


# ── Node 15 (auto path, approved — terminal) ──────────────────────────────────
def send_and_file(state: GraphState) -> GraphState:
    """Send email via Gmail API; upload resume + email.txt to per-job Drive folder."""
    start = _log_node("send_and_file", state)
    # TODO (Phase 1):
    #   1. Build a MIME message with state["email_draft"] + PDF attachment.
    #   2. Call users.messages.send via the Gmail API.
    #   3. Create a Drive folder named "{company} — {job_title} — {date}".
    #   4. Upload the PDF and a plain-text email.txt to that folder.
    #   5. Update the application row: status=sent, drive_folder_url.
    _log_node_exit("send_and_file", start, state)
    return {**state, "sent": True}


# ── Node 16 (auto path, review cap reached — terminal) ────────────────────────
def manual_fallback(state: GraphState) -> GraphState:
    """Downgrade to manual review when the auto review loop cap is reached."""
    start = _log_node("manual_fallback", state)
    log.warning(
        "review_loop_cap_reached",
        application_id=state.get("application_id"),
        attempts=state.get("approval_attempts", 0),
    )
    # TODO (Phase 1): update application status to "pending_approval" (manual);
    #   notify the user via the UI that this application needs their review.
    _log_node_exit("manual_fallback", start, state)
    return {**state, "approved": False}
