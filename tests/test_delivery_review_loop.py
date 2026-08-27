"""
tests/test_delivery_review_loop.py — Tests for draft_email, ATS/factual reviewer loop, and Gmail/Drive delivery.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from app.agent.graph import pipeline
from app.agent.nodes.draft_email import draft_email_node
from app.agent.nodes.reviewers import agent_ats_reviewer_node, agent_factual_reviewer_node
from app.agent.nodes.delivery import send_and_file_node, manual_fallback_node
from app.agent.state import GraphState


@pytest.mark.asyncio
async def test_draft_email_node_updates_state():
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Alex Hunter, Senior AI Engineer with Python expertise.",
        "current_job": {
            "title": "Lead Agentic AI Engineer",
            "company": "DeepMind",
            "description": "Building LangGraph multi-agent systems.",
        },
    }

    mock_email = "Subject: Application for Lead Agentic AI Engineer\n\nDear Team,\n\nI am excited to apply..."
    with patch("app.agent.nodes.draft_email.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_email)
        mock_get_llm.return_value = mock_chat

        updated = draft_email_node(state)
        assert updated["email_draft"] == mock_email


@pytest.mark.asyncio
async def test_agent_ats_reviewer_pass_and_fail():
    state: GraphState = {
        "application_id": 1,
        "tailored_resume_html": '<div class="resume">Python AI Specialist</div>',
        "current_job": {"description": "Seeking Python engineer."},
    }

    # 1. Passing response
    with patch("app.agent.nodes.reviewers.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content='{"score": 90, "pass": true, "flags": []}')
        mock_get_llm.return_value = mock_chat

        pass_state = agent_ats_reviewer_node(state)
        assert pass_state["ats_review"]["score"] == 90
        assert pass_state["ats_review"]["pass"] is True

    # 2. Failing response
    with patch("app.agent.nodes.reviewers.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content='{"score": 50, "pass": false, "flags": ["Missing Go"]}')
        mock_get_llm.return_value = mock_chat

        fail_state = agent_ats_reviewer_node(state)
        assert fail_state["ats_review"]["score"] == 50
        assert fail_state["ats_review"]["pass"] is False


@pytest.mark.asyncio
async def test_agent_factual_reviewer_and_attempt_incrementation():
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Genuine experience at TechCorp.",
        "tailored_resume_html": '<div class="resume">Experience at TechCorp</div>',
        "email_draft": "I worked at TechCorp.",
        "approval_attempts": 1,
        "ats_review": {"pass": True, "score": 85},
    }

    with patch("app.agent.nodes.reviewers.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content='{"pass": true, "hallucinations": []}')
        mock_get_llm.return_value = mock_chat

        updated = agent_factual_reviewer_node(state)
        assert updated["approval_attempts"] == 2
        assert updated["factual_review"]["pass"] is True
        assert updated["approved"] is True


@pytest.mark.asyncio
async def test_send_and_file_node_completes():
    state: GraphState = {
        "application_id": 1,
        "email_draft": "Subject: Hi\n\nBody",
        "current_job": {
            "title": "Staff Engineer",
            "company": "OpenAI",
            "recruiter_email": "recruiter@openai.com",
        },
        "oauth_refresh_token": "test-mock-token",
    }

    result = send_and_file_node(state)
    assert result["sent"] is True
    assert "drive_folder_url" in result
    assert result["drive_folder_url"].startswith("http")


@pytest.mark.asyncio
async def test_manual_fallback_node():
    state: GraphState = {
        "application_id": 1,
        "approval_attempts": 3,
    }
    result = manual_fallback_node(state)
    assert result["approved"] is False
    assert result["sent"] is False


@pytest.mark.asyncio
async def test_full_graph_auto_path_end_to_end():
    """Verify compiled graph auto path executes review loop and delivers."""
    initial_state: GraphState = {
        "user_id": 1,
        "application_id": 100,
        "send_mode": "auto",
        "resume_text": "Experienced Python Engineer.",
        "resume_html": '<div class="resume"><h1>Python Dev</h1></div>',
        "current_job": {
            "title": "AI Platform Engineer",
            "company": "Anthropic",
            "description": "Python, LLMs, Agents.",
            "recruiter_email": "recruiter@anthropic.com",
        },
        "oauth_refresh_token": "test-refresh-token",
    }

    # Mock all LLM calls in graph so it runs deterministically
    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gap, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_draft, \
         patch("app.agent.nodes.reviewers.get_llm") as mock_review:

        mock_gap.return_value.invoke.return_value = MagicMock(content="Gaps: Highlight agents.")
        mock_tailor.return_value.invoke.return_value = MagicMock(content='<div class="resume">Python AI Engineer</div>')
        mock_draft.return_value.invoke.return_value = MagicMock(content="Subject: Application\n\nDear Team...")
        # Reviewers return pass
        mock_review.return_value.invoke.return_value = MagicMock(content='{"score": 95, "pass": true, "hallucinations": []}')

        result = await asyncio.to_thread(pipeline.invoke, initial_state)

        assert result is not None
        assert result.get("sent") is True
        assert result.get("drive_folder_url") is not None
