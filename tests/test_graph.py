"""
tests/test_graph.py — End-to-end integration tests for the LangGraph pipeline.
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from app.agent.graph import pipeline
from app.agent.state import GraphState

MINIMAL_STATE: GraphState = {
    "user_id": 1,
    "application_id": 1,
    "resume_text": "Experienced AI engineer with Python and LangChain skills.",
    "resume_html": "<html><body><p>Test resume</p></body></html>",
    "oauth_refresh_token": "test-mock-token",
}


@pytest.mark.asyncio
async def test_graph_manual_path_completes():
    """Manual path: graph should run end-to-end without raising."""
    state: GraphState = {**MINIMAL_STATE, "send_mode": "manual"}

    with patch("app.services.llm.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content="Mock LLM response")
        mock_get_llm.return_value = mock_chat

        result = await asyncio.to_thread(pipeline.invoke, state)
        assert result is not None
        assert "drive_file_url" in result


@pytest.mark.asyncio
async def test_graph_auto_path_completes():
    """Auto path: graph should run review loop and reach send_and_file."""
    state: GraphState = {
        **MINIMAL_STATE,
        "send_mode": "auto",
        "current_job": {
            "title": "AI Engineer",
            "company": "Anthropic",
            "description": "Python, LangGraph",
            "recruiter_email": "recruiter@anthropic.com",
        },
    }

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gap, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_draft, \
         patch("app.agent.nodes.reviewers.get_llm") as mock_review:

        mock_gap.return_value.invoke.return_value = MagicMock(content="Gaps: LangGraph")
        mock_tailor.return_value.invoke.return_value = MagicMock(content='<div class="resume">Tailored HTML</div>')
        mock_draft.return_value.invoke.return_value = MagicMock(content="Subject: Application\n\nDear Team...")
        mock_review.return_value.invoke.return_value = MagicMock(content='{"score": 95, "pass": true, "hallucinations": []}')

        result = await asyncio.to_thread(pipeline.invoke, state)
        assert result is not None
        assert result.get("sent") is True


@pytest.mark.asyncio
async def test_graph_auto_path_fallback():
    """When reviewers fail and cap is hit, graph should fall back to manual."""
    state: GraphState = {
        **MINIMAL_STATE,
        "send_mode": "auto",
        "current_job": {
            "title": "AI Engineer",
            "company": "DeepMind",
            "description": "Python, LangGraph",
        },
    }

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gap, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_draft, \
         patch("app.agent.nodes.reviewers.get_llm") as mock_review:

        mock_gap.return_value.invoke.return_value = MagicMock(content="Gaps: LangGraph")
        mock_tailor.return_value.invoke.return_value = MagicMock(content='<div class="resume">Tailored HTML</div>')
        mock_draft.return_value.invoke.return_value = MagicMock(content="Subject: Application\n\nDear Team...")
        # Reviewers reject
        mock_review.return_value.invoke.return_value = MagicMock(content='{"score": 40, "pass": false, "hallucinations": ["Invented Degree"]}')

        result = await asyncio.to_thread(pipeline.invoke, state)
        assert result is not None
        # Should terminate at manual_fallback
        assert result.get("approved") is False
        assert result.get("sent") is False
