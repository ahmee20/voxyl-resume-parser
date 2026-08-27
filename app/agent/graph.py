"""
app/agent/graph.py — LangGraph StateGraph wiring all 16 nodes.

This module builds the compiled graph once at import time (module-level
`pipeline` object).  FastAPI routes invoke it via:

    result = await asyncio.to_thread(pipeline.invoke, initial_state, config)

LangSmith tracing is enabled automatically when LANGCHAIN_TRACING_V2=true
and LANGCHAIN_API_KEY is set in the environment — no extra code needed for
the basic trace.  We add `application_id` and `node_name` as metadata on
the RunnableConfig so every run is searchable by application in LangSmith.

Graph topology (see PROJECT_PLAN.md §5 for rationale):

    START
      │
      ▼
    extract_resume
      │
      ▼
    plan_search_queries
      │
      ▼
    scrape_jobs
      │
      ▼
    enrich_jobs
      │
      ▼
    filter_relevant
      │
      ▼
    persist_jobs
      │
      ▼
    analyze_gaps
      │
      ▼
    tailor_resume
      │
      ▼
    render_pdf
      │
      ▼
    branch_send_mode ──── "manual" ──→ present_variants ──→ upload_manual ──→ END
      │
      └─── "auto" ──→ draft_email ──→ agent_ats_reviewer
                                            │
                                      agent_factual_reviewer
                                            │
                               ┌── review_decision ──┐
                               │                      │
                           "approved"           "retry" (up to 3x, back to tailor_resume)
                               │                      │
                          send_and_file          "cap_reached"
                               │                      │
                              END              manual_fallback ──→ END
"""

from langgraph.graph import StateGraph, END

from app.agent.state import GraphState
from app.agent.nodes.extract_resume import extract_resume_node as extract_resume
from app.agent.nodes.search_planner import plan_search_queries_node as plan_search_queries
from app.agent.nodes.scrape_jobs import scrape_jobs_node as scrape_jobs
from app.agent.nodes.enrich_jobs import enrich_jobs_node as enrich_jobs
from app.agent.nodes.filter_jobs import filter_relevant_node as filter_relevant
from app.agent.nodes.persist_jobs import persist_jobs_node as persist_jobs
from app.agent.nodes.analyze_gaps import analyze_gaps_node as analyze_gaps
from app.agent.nodes.tailor_resume import tailor_resume_node as tailor_resume
from app.agent.nodes.render_pdf import render_pdf_node as render_pdf
from app.agent.nodes.draft_email import draft_email_node as draft_email
from app.agent.nodes.reviewers import (
    agent_ats_reviewer_node as agent_ats_reviewer,
    agent_factual_reviewer_node as agent_factual_reviewer,
)
from app.agent.nodes.delivery import (
    send_and_file_node as send_and_file,
    manual_fallback_node as manual_fallback,
    upload_manual_node as upload_manual,
)
from app.agent.nodes.stubs import (
    present_variants,
)
from app.config import settings


# ── Conditional edge functions ────────────────────────────────────────────────

def _branch_send_mode(state: GraphState) -> str:
    """Route to the manual or auto path based on the user's send_mode preference."""
    return state.get("send_mode", "manual")  # default safe: manual


def _review_decision(state: GraphState) -> str:
    """
    Decide what happens after both reviewers have run:
    - "approved"     → proceed to send_and_file
    - "retry"        → loop back to tailor_resume (up to max_attempts)
    - "cap_reached"  → fall back to manual review
    """
    ats = state.get("ats_review", {})
    factual = state.get("factual_review", {})
    attempts = state.get("approval_attempts", 0)

    both_pass = ats.get("pass", False) and factual.get("pass", False)

    if both_pass:
        return "approved"
    if attempts >= settings.review_loop_max_attempts:
        return "cap_reached"
    return "retry"


# ── Graph construction ────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """Construct and return the compiled LangGraph StateGraph."""
    graph = StateGraph(GraphState)

    # Register all nodes
    graph.add_node("extract_resume", extract_resume)
    graph.add_node("plan_search_queries", plan_search_queries)
    graph.add_node("scrape_jobs", scrape_jobs)
    graph.add_node("enrich_jobs", enrich_jobs)
    graph.add_node("filter_relevant", filter_relevant)
    graph.add_node("persist_jobs", persist_jobs)
    graph.add_node("analyze_gaps", analyze_gaps)
    graph.add_node("tailor_resume", tailor_resume)
    graph.add_node("render_pdf", render_pdf)
    graph.add_node("present_variants", present_variants)
    graph.add_node("upload_manual", upload_manual)
    graph.add_node("draft_email", draft_email)
    graph.add_node("agent_ats_reviewer", agent_ats_reviewer)
    graph.add_node("agent_factual_reviewer", agent_factual_reviewer)
    graph.add_node("send_and_file", send_and_file)
    graph.add_node("manual_fallback", manual_fallback)

    # ── Linear backbone ───────────────────────────────────────────────────────
    graph.set_entry_point("extract_resume")
    graph.add_edge("extract_resume", "plan_search_queries")
    graph.add_edge("plan_search_queries", "scrape_jobs")
    graph.add_edge("scrape_jobs", "enrich_jobs")
    graph.add_edge("enrich_jobs", "filter_relevant")
    graph.add_edge("filter_relevant", "persist_jobs")
    graph.add_edge("persist_jobs", "analyze_gaps")
    graph.add_edge("analyze_gaps", "tailor_resume")
    graph.add_edge("tailor_resume", "render_pdf")

    # ── Branch: manual vs auto ────────────────────────────────────────────────
    graph.add_conditional_edges(
        "render_pdf",
        _branch_send_mode,
        {
            "manual": "present_variants",
            "auto": "draft_email",
        },
    )

    # ── Manual path ───────────────────────────────────────────────────────────
    graph.add_edge("present_variants", "upload_manual")
    graph.add_edge("upload_manual", END)

    # ── Auto path: review loop ────────────────────────────────────────────────
    graph.add_edge("draft_email", "agent_ats_reviewer")
    graph.add_edge("agent_ats_reviewer", "agent_factual_reviewer")

    graph.add_conditional_edges(
        "agent_factual_reviewer",
        _review_decision,
        {
            "approved": "send_and_file",
            "retry": "tailor_resume",      # loop back; approval_attempts incremented by node
            "cap_reached": "manual_fallback",
        },
    )

    graph.add_edge("send_and_file", END)
    graph.add_edge("manual_fallback", END)

    return graph


# ── Module-level compiled graph ───────────────────────────────────────────────
# Compile once at import time.  The compiled graph is thread-safe and can be
# invoked concurrently from multiple FastAPI requests.
pipeline = build_graph().compile()
