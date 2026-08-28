"""
tests/test_applications.py — Tests for the single-job tailoring pipeline and applications API.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

from app.agent.nodes.analyze_gaps import analyze_gaps_node
from app.agent.nodes.tailor_resume import tailor_resume_node
from app.agent.nodes.render_pdf import render_pdf_node
from app.agent.state import GraphState
from app.models.resume import Resume
from app.models.user import User
from app.services.resume_template import ResumeProfile, render_resume_html


@pytest.mark.asyncio
async def test_analyze_gaps_node_updates_state():
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Experienced Python Developer with FastAPI.",
        "current_job": {
            "title": "Senior AI Engineer",
            "company": "Tech Corp",
            "description": "Looking for Python, LangGraph, and Vector DB experience.",
        },
    }

    mock_analysis = "1. Keywords: LangGraph, Vector DB\n2. Emphasize: Python FastAPI production systems."
    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_analysis)
        mock_get_llm.return_value = mock_chat

        updated = analyze_gaps_node(state)
        assert updated["gap_analysis"] == mock_analysis


@pytest.mark.asyncio
async def test_analyze_gaps_node_expands_supported_keywords():
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Electrical engineer who designed embedded control systems and coordinated cross-functional projects.",
        "current_job": {
            "title": "Systems Engineer",
            "company": "Tech Corp",
            "description": "Looking for PLC programming, SCADA, stakeholder management, and process improvement experience.",
        },
    }

    mock_analysis = json.dumps(
        {
            "added_keywords": [],
            "removed_keywords": [],
            "summary": "Focus on the strongest transferable skills.",
            "notes": [],
        }
    )
    mock_expansion = json.dumps(
        {
            "added_keywords": [
                {"keyword": "PLC programming", "evidence": "designed embedded control systems"},
                {"keyword": "stakeholder management", "evidence": "coordinated cross-functional projects"},
            ]
        }
    )

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.side_effect = [MagicMock(content=mock_analysis), MagicMock(content=mock_expansion)]
        mock_get_llm.return_value = mock_chat

        updated = analyze_gaps_node(state)
        parsed = json.loads(updated["gap_analysis"])

        added_keywords = {item["keyword"] for item in parsed["added_keywords"]}
        assert "PLC programming" in added_keywords
        assert "stakeholder management" in added_keywords


@pytest.mark.asyncio
async def test_tailor_resume_node_updates_html():
    state: GraphState = {
        "application_id": 1,
        "resume_html": '<div class="resume"><h1>Jane Doe</h1><p>FastAPI Developer</p></div>',
        "gap_analysis": "Emphasize LangGraph and AI agents.",
    }

    mock_tailored_html = '<div class="resume"><h1>Jane Doe</h1><p>FastAPI & LangGraph AI Engineer</p></div>'
    with patch("app.agent.nodes.tailor_resume.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_tailored_html)
        mock_get_llm.return_value = mock_chat

        updated = tailor_resume_node(state)
        assert updated["tailored_resume_html"] == mock_tailored_html


def test_tailored_html_applies_keyword_changes_and_profile_links():
    base_html = '<div class="resume"><header><h1>Jane Doe</h1></header><p>Python LegacyTool</p></div>'
    gap_analysis = json.dumps(
        {
            "added_keywords": [{"keyword": "LangGraph", "evidence": "Python"}],
            "removed_keywords": ["LegacyTool"],
        }
    )

    with patch("app.agent.nodes.tailor_resume.get_llm") as mock_get_llm:
        mock_get_llm.return_value.invoke.return_value = MagicMock(content=base_html)
        result = tailor_resume_node(
            {
                "resume_html": base_html,
                "gap_analysis": gap_analysis,
                "user_profile": {"github_url": "github.com/jane"},
            }
        )

    tailored_html = result["tailored_resume_html"]
    assert "LegacyTool" not in tailored_html
    assert "LangGraph" in tailored_html
    assert "https://github.com/jane" in tailored_html


def test_render_resume_html_uses_profile_links_without_replacing_resume_identity():
    result = render_resume_html(
        "Jane Doe\nElectrical Engineer\n\nExperience\n- Designed control systems",
        ResumeProfile(name="Account Name", github_url="github.com/jane"),
    )

    assert "Jane Doe" in result
    assert "Account Name" not in result
    assert "https://github.com/jane" in result


@pytest.mark.asyncio
async def test_render_pdf_node_sets_url():
    state: GraphState = {
        "application_id": 1,
        "tailored_resume_html": '<div class="resume"><h1>Test</h1></div>',
    }
    updated = render_pdf_node(state)
    assert "pdf_url" in updated
    assert updated["pdf_url"].startswith("http")


@pytest.mark.asyncio
async def test_run_single_job_pipeline_no_resume_404(client: AsyncClient, db_session):
    user = User(google_sub="sub-no-resume-1", email="noresume@test.com", name="No Resume User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    payload = {
        "user_id": user.id,
        "job_title": "AI Engineer",
        "company": "DeepMind",
        "job_description": "LangGraph expert needed.",
    }
    response = await client.post("/applications/run-single", json=payload)
    assert response.status_code == 404
    assert "No base resume found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_run_single_job_pipeline_success(client: AsyncClient, db_session):
    # 1. Seed user & base resume
    user = User(google_sub="sub-pipeline-user-1", email="pilot@test.com", name="Pilot User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    base_resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Python software engineer with 5 years experience.",
        source_html='<div class="resume"><h1>Pilot User</h1><p>Python Engineer</p></div>',
        is_base=True,
    )
    db_session.add(base_resume)
    await db_session.commit()
    await db_session.refresh(base_resume)

    payload = {
        "user_id": user.id,
        "job_title": "Senior AI Engineer",
        "company": "Anthropic AI",
        "job_description": "We are seeking a Python and LangGraph specialist to build autonomous agents.",
    }

    mock_gap_analysis = "Emphasize Python, LangGraph and autonomous agents."
    mock_tailored_html = '<div class="resume"><h1>Pilot User</h1><p>Senior AI Engineer (LangGraph, Python)</p></div>'

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gap_llm, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor_llm, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_email_llm, \
         patch("app.agent.nodes.reviewers.get_llm") as mock_rev_llm:

        chat_gap = MagicMock()
        chat_gap.invoke.return_value = MagicMock(content=mock_gap_analysis)
        mock_gap_llm.return_value = chat_gap

        chat_tailor = MagicMock()
        chat_tailor.invoke.return_value = MagicMock(content=mock_tailored_html)
        mock_tailor_llm.return_value = chat_tailor

        chat_email = MagicMock()
        chat_email.invoke.return_value = MagicMock(content="Subject: Application for Senior AI Engineer\n\nDear Team...")
        mock_email_llm.return_value = chat_email

        chat_rev = MagicMock()
        chat_rev.invoke.return_value = MagicMock(content='{"score": 90, "pass": true, "flags": []}')
        mock_rev_llm.return_value = chat_rev

        response = await client.post("/applications/run-single", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "tailoring"
        assert "application_id" in data

        app_id = data["application_id"]

        # Test GET /applications/{id}
        detail_res = await client.get(f"/applications/{app_id}")
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["id"] == app_id
        assert detail["status"] == "saved"
        assert detail["mode"] == "manual"
        assert len(detail["timeline"]) >= 1


@pytest.mark.asyncio
async def test_run_batch_job_pipeline_no_jobs_400(client: AsyncClient):
    response = await client.post("/applications/run-batch", json={"job_ids": []})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_run_batch_job_pipeline_success(client: AsyncClient, db_session):
    from app.models.job import Job
    # 1. Seed user & resume
    user = User(google_sub="sub-batch-test-1", email="batch@test.com", name="Batch User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Senior Machine Learning & AI Engineer",
        source_html='<div class="resume"><h1>Batch User</h1></div>',
        is_base=True,
    )
    db_session.add(resume)

    # 2. Seed 2 jobs
    job1 = Job(user_id=user.id, title="AI Lead", company="OpenAI", url="https://job/1", source="apify")
    job2 = Job(user_id=user.id, title="ML Engineer", company="Anthropic", url="https://job/2", source="apify")
    db_session.add_all([job1, job2])
    await db_session.commit()
    await db_session.refresh(resume)
    await db_session.refresh(job1)
    await db_session.refresh(job2)

    with patch("app.api.applications.run_batch_pipeline_background") as mock_bg:
        response = await client.post(
            "/applications/run-batch",
            json={"user_id": user.id, "job_ids": [job1.id, job2.id], "resume_id": resume.id},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "tailoring"
        assert data["count"] == 2
        assert data["job_ids"] == [job1.id, job2.id]
