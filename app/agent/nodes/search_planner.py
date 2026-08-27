"""
app/agent/nodes/search_planner.py — LLM node for planning job search queries.
"""

import json
import time
import structlog
from langchain_core.messages import SystemMessage, HumanMessage

from app.agent.state import GraphState
from app.services.llm import get_llm

log = structlog.get_logger(__name__)

SEARCH_PLANNER_SYSTEM_PROMPT = """You are an expert technical recruiter and career strategist.
Analyze the candidate's resume and generate 3 to 5 highly targeted job search queries to discover relevant job openings.

RULES:
1. Extract the candidate's primary domain (e.g. AI Engineering, Backend, Fullstack, ML).
2. Match their seniority level (e.g. Senior, Lead, Staff, Mid-level).
3. Return a JSON list of search strings (e.g. ["Senior AI Engineer", "LLM Systems Engineer", "Lead Machine Learning Engineer"]).
4. OUTPUT FORMAT: Return ONLY valid JSON in the form: ["query 1", "query 2", "query 3"]
"""


def plan_search_queries_node(state: GraphState) -> GraphState:
    """LangGraph node: Proposes job search queries from base resume."""
    start_time = time.perf_counter()
    app_id = state.get("application_id")
    user_id = state.get("user_id")

    log.info("node_enter", node="plan_search_queries", application_id=app_id, user_id=user_id)

    resume_text = state.get("resume_text", "")
    queries = state.get("search_queries")

    if not queries:
        try:
            llm = get_llm(temperature=0.2)
            messages = [
                SystemMessage(content=SEARCH_PLANNER_SYSTEM_PROMPT),
                HumanMessage(content=f"Candidate resume content:\n\n{resume_text}\n\nPropose 3-5 search queries in JSON list format:"),
            ]
            resp = llm.invoke(messages)
            content = resp.content if isinstance(resp.content, str) else str(resp.content)
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            queries = json.loads(content.strip())
            if not isinstance(queries, list):
                queries = ["AI Engineer", "Software Engineer"]
        except Exception as exc:
            log.error("plan_search_queries_failed", error=str(exc), application_id=app_id)
            queries = ["AI Engineer", "Senior Software Engineer"]

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info("node_exit", node="plan_search_queries", latency_ms=elapsed_ms, queries=queries)

    return {
        **state,
        "search_queries": queries,
    }
