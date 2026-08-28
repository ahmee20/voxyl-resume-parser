"""
tests/test_job_discovery.py — Tests for search planner, Apify scraper, Apollo enrichment, and jobs API.
"""

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient

from app.agent.nodes.search_planner import plan_search_queries_node
from app.agent.nodes.scrape_jobs import scrape_jobs_node
from app.agent.nodes.enrich_jobs import enrich_jobs_node
from app.agent.nodes.filter_jobs import filter_relevant_node
from app.agent.nodes.persist_jobs import persist_jobs_node
from app.agent.state import GraphState
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User


@pytest.mark.asyncio
async def test_plan_search_queries_node():
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Experienced Senior AI Engineer with Python, LangGraph, LLMs.",
    }

    mock_queries_json = '["Senior AI Engineer", "LLM Systems Engineer", "Agentic AI Developer"]'
    with patch("app.agent.nodes.search_planner.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_queries_json)
        mock_get_llm.return_value = mock_chat

        updated = plan_search_queries_node(state)
        assert len(updated["search_queries"]) == 3
        assert "Senior AI Engineer" in updated["search_queries"]


@pytest.mark.asyncio
async def test_scrape_jobs_node():
    state: GraphState = {
        "application_id": 1,
        "search_queries": ["AI Engineer", "Software Engineer"],
    }
    updated = scrape_jobs_node(state)
    assert "scraped_jobs" in updated
    assert len(updated["scraped_jobs"]) >= 1
    first_job = updated["scraped_jobs"][0]
    assert "title" in first_job
    assert "url" in first_job


@pytest.mark.asyncio
async def test_enrich_jobs_node():
    state: GraphState = {
        "application_id": 1,
        "scraped_jobs": [
            {
                "title": "Staff AI Engineer",
                "company": "DeepMind",
                "url": "https://deepmind.com/careers/123",
                "description": "Python agent systems.",
            }
        ],
    }
    updated = enrich_jobs_node(state)
    assert len(updated["enriched_jobs"]) == 1
    enriched = updated["enriched_jobs"][0]
    assert "apollo_enrichment" in enriched
    assert "recruiter_email" in enriched


@pytest.mark.asyncio
async def test_filter_relevant_node():
    state: GraphState = {
        "application_id": 1,
        "enriched_jobs": [
            {
                "title": "Senior AI Engineer",
                "company": "Tech Corp",
                "description": "Full-time position building production LLM systems with Python.",
            },
            {
                "title": "Unpaid Summer Internship",
                "company": "Startup X",
                "description": "Volunteer student project.",
            },
        ],
    }
    updated = filter_relevant_node(state)
    assert len(updated["relevant_jobs"]) == 1
    assert updated["relevant_jobs"][0]["title"] == "Senior AI Engineer"


@pytest.mark.asyncio
async def test_persist_jobs_node_and_deduplication(db_session):
    state: GraphState = {
        "application_id": 1,
        "relevant_jobs": [
            {
                "title": "AI Architect",
                "company": "OpenAI",
                "url": "https://openai.com/careers/ai-architect-1",
                "description": "Designing frontier models.",
                "recruiter_email": "recruiter@openai.com",
            }
        ],
    }

    # 1. First persistence
    updated = persist_jobs_node(state)
    assert len(updated["persisted_job_ids"]) == 1
    first_id = updated["persisted_job_ids"][0]

    # 2. Second persistence with identical URL should deduplicate
    state_repeat: GraphState = {
        "application_id": 1,
        "relevant_jobs": [
            {
                "title": "AI Architect",
                "company": "OpenAI",
                "url": "https://openai.com/careers/ai-architect-1",
                "description": "Designing frontier models.",
            }
        ],
    }
    updated_repeat = persist_jobs_node(state_repeat)
    assert updated_repeat["persisted_job_ids"] == []
    assert updated_repeat["duplicate_job_ids"] == [first_id]


@pytest.mark.asyncio
async def test_match_requirements_node():
    from app.agent.nodes.match_requirements import match_requirements_node
    state: GraphState = {
        "application_id": 1,
        "resume_text": "Experienced Python AI Engineer with 4 years building LLM agents.",
        "scraped_jobs": [
            {
                "title": "Senior AI Engineer (5+ years req)",
                "company": "TopAI",
                "url": "https://topai.com/job/1",
                "description": "Requires Python, LangChain, and 5 years experience.",
            },
            {
                "title": "Senior Staff Radiologist",
                "company": "General Hospital",
                "url": "https://hospital.com/job/2",
                "description": "Requires Board Certified MD in Diagnostic Radiology with 10+ years residency.",
            },
        ],
    }

    mock_llm_responses = [
        MagicMock(content='{"qualified": true, "match_percentage": 85, "match_reason": "Candidate has 4 years experience which satisfies 5-year requirement within 2-year tolerance and matches Python/LLM core stack."}'),
        MagicMock(content='{"qualified": false, "match_percentage": 10, "match_reason": "Candidate is an AI Engineer and lacks medical doctor certification."}'),
    ]

    with patch("app.agent.nodes.match_requirements.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.side_effect = mock_llm_responses
        mock_get_llm.return_value = mock_chat

        updated = match_requirements_node(state)
        assert len(updated["scraped_jobs"]) == 1
        assert updated["scraped_jobs"][0]["title"] == "Senior AI Engineer (5+ years req)"
        assert updated["scraped_jobs"][0]["match_score"] == 85
        assert len(updated["filtered_jobs"]) == 1
        assert updated["filtered_jobs"][0]["title"] == "Senior Staff Radiologist"
        assert updated["filtered_jobs"][0]["match_score"] == 10


@pytest.mark.asyncio
async def test_jobs_api_endpoints(client: AsyncClient, db_session):
    # 1. Seed user and resume
    user = User(google_sub="sub-jobs-api-1", email="jobsapi@test.com", name="Jobs User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Senior Machine Learning and AI Engineer.",
        source_html='<div class="resume">ML Engineer</div>',
        is_base=True,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    # 2. Test POST /jobs/discover
    mock_queries = '["AI Engineer", "ML Engineer"]'
    mock_eval = '{"qualified": true, "match_percentage": 85, "match_reason": "Meets 85% core requirements."}'
    with patch("app.agent.nodes.search_planner.get_llm") as mock_get_llm, \
         patch("app.agent.nodes.match_requirements.get_llm") as mock_match_llm, \
         patch("app.api.jobs.run_batch_pipeline_background") as mock_bg:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_queries)
        mock_get_llm.return_value = mock_chat

        mock_match_chat = MagicMock()
        mock_match_chat.invoke.return_value = MagicMock(content=mock_eval)
        mock_match_llm.return_value = mock_match_chat

        discover_res = await client.post("/jobs/discover", json={"user_id": user.id})
        assert discover_res.status_code == 200
        data = discover_res.json()
        assert data["status"] == "discovery_complete"
        assert len(data["persisted_job_ids"]) >= 1

        # 3. Test GET /jobs?qualified=true
        list_res = await client.get(f"/jobs?qualified=true&user_id={user.id}")
        assert list_res.status_code == 200
        jobs_list = list_res.json()
        assert len(jobs_list) >= 1
        assert all(j.get("is_qualified") is True for j in jobs_list)


@pytest.mark.asyncio
async def test_batch_pipeline_orchestrator(db_session):
    from app.services.batch_pipeline import run_batch_pipeline

    # 1. Seed user & resume
    user = User(google_sub="sub-batch-test-1", email="batch@test.com", name="Batch User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Senior Python AI Engineer with LLM systems experience.",
        source_html='<div class="resume"><h1>Batch User</h1></div>',
        is_base=True,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    # 2. Seed 3 jobs
    job_ids = []
    for i in range(3):
        job = Job(
            source="apify",
            url=f"https://example.com/batch-job-{i+1}",
            title=f"AI Engineer {i+1}",
            company=f"Batch AI Corp {i+1}",
            description="Build scalable AI agent systems in Python.",
        )
        db_session.add(job)
        await db_session.commit()
        await db_session.refresh(job)
        job_ids.append(job.id)

    # 3. Mock LLMs
    mock_gap = "Emphasize Python and AI agent architecture."
    mock_tailored = '<div class="resume"><h1>Batch User</h1><p>Tailored AI</p></div>'

    with patch("app.agent.nodes.analyze_gaps.get_llm") as mock_gap_llm, \
         patch("app.agent.nodes.tailor_resume.get_llm") as mock_tailor_llm, \
         patch("app.agent.nodes.draft_email.get_llm") as mock_email_llm, \
         patch("app.agent.nodes.reviewers.get_llm") as mock_rev_llm:

        chat_gap = MagicMock()
        chat_gap.invoke.return_value = MagicMock(content=mock_gap)
        mock_gap_llm.return_value = chat_gap

        chat_tailor = MagicMock()
        chat_tailor.invoke.return_value = MagicMock(content=mock_tailored)
        mock_tailor_llm.return_value = chat_tailor

        chat_email = MagicMock()
        chat_email.invoke.return_value = MagicMock(content="Subject: Application\n\nDear Team...")
        mock_email_llm.return_value = chat_email

        chat_rev = MagicMock()
        chat_rev.invoke.return_value = MagicMock(content='{"score": 90, "pass": true, "flags": []}')
        mock_rev_llm.return_value = chat_rev

        results = await run_batch_pipeline(
            job_ids=job_ids,
            user_id=user.id,
            base_resume_text=resume.source_text,
            base_resume_html=resume.source_html,
            base_resume_id=resume.id,
            base_resume_version=resume.version,
        )

        assert len(results) == 3
        assert all(r["status"] == "success" for r in results)
        assert all(r["ats_score"] == 90 for r in results)


@pytest.mark.asyncio
async def test_discover_and_apply_endpoint(client: AsyncClient, db_session):
    # 1. Seed user and resume
    user = User(google_sub="sub-disc-apply-1", email="discapply@test.com", name="DiscApply User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Senior Machine Learning and AI Engineer.",
        source_html='<div class="resume">ML Engineer</div>',
        is_base=True,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    mock_queries = '["AI Engineer", "ML Engineer"]'
    mock_eval = '{"qualified": true, "match_percentage": 85, "match_reason": "Meets 85% core requirements."}'

    with patch("app.agent.nodes.search_planner.get_llm") as mock_get_llm, \
         patch("app.agent.nodes.match_requirements.get_llm") as mock_match_llm, \
         patch("app.api.jobs.run_batch_pipeline_background") as mock_bg:

        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_queries)
        mock_get_llm.return_value = mock_chat

        mock_match_chat = MagicMock()
        mock_match_chat.invoke.return_value = MagicMock(content=mock_eval)
        mock_match_llm.return_value = mock_match_chat

        res = await client.post("/jobs/discover-and-apply", json={"user_id": user.id, "max_results": 5})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "discovery_and_tailoring_launched"
        assert len(data["persisted_job_ids"]) >= 1
        assert data["batch_size"] == 10
        assert data["total_batches"] >= 1


@pytest.mark.asyncio
async def test_user_isolated_jobs_and_latest_filtering(client: AsyncClient, db_session):
    # 1. Seed User A and User B
    user_a = User(google_sub="sub-user-a-iso", email="usera@test.com", name="User A")
    user_b = User(google_sub="sub-user-b-iso", email="userb@test.com", name="User B")
    db_session.add_all([user_a, user_b])
    await db_session.commit()
    await db_session.refresh(user_a)
    await db_session.refresh(user_b)

    # 2. Seed 3 jobs for User A
    for i in range(3):
        job = Job(
            user_id=user_a.id,
            source="apify",
            url=f"https://jobs.example.com/user-a-job-{i+1}",
            title=f"Role A{i+1}",
            company=f"Company A{i+1}",
            description="User A job listing description.",
            is_qualified=True,
        )
        db_session.add(job)

    # 3. Seed 2 jobs for User B
    for i in range(2):
        job = Job(
            user_id=user_b.id,
            source="apify",
            url=f"https://jobs.example.com/user-b-job-{i+1}",
            title=f"Role B{i+1}",
            company=f"Company B{i+1}",
            description="User B job listing description.",
            is_qualified=True,
        )
        db_session.add(job)

    await db_session.commit()

    # 4. User A query only returns User A's jobs
    res_a = await client.get(f"/jobs?user_id={user_a.id}")
    assert res_a.status_code == 200
    jobs_a = res_a.json()
    assert len(jobs_a) == 3
    assert all("Role A" in j["title"] for j in jobs_a)

    # 5. User B query only returns User B's jobs
    res_b = await client.get(f"/jobs?user_id={user_b.id}")
    assert res_b.status_code == 200
    jobs_b = res_b.json()
    assert len(jobs_b) == 2
    assert all("Role B" in j["title"] for j in jobs_b)

    # 6. Test latest=true filtering for User A
    res_latest = await client.get(f"/jobs?user_id={user_a.id}&latest=true&limit=2")
    assert res_latest.status_code == 200
    jobs_latest = res_latest.json()
    assert len(jobs_latest) == 2
    assert jobs_latest[0]["title"] == "Role A3"


@pytest.mark.asyncio
async def test_jobs_api_tailored_and_untailored_filters(client: AsyncClient, db_session):
    from app.models.application import Application, ApplicationMode, ApplicationStatus, AppliedStatus

    user = User(google_sub="sub-job-filters-1", email="filters@test.com", name="Filters User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Python engineer with strong product delivery experience.",
        source_html='<div class="resume">Filter User</div>',
        is_base=True,
    )
    db_session.add(resume)
    await db_session.commit()
    await db_session.refresh(resume)

    tailored_job = Job(
        user_id=user.id,
        source="apify",
        url="https://jobs.example.com/tailored-job",
        title="Tailored Role",
        company="Tailored Corp",
        description="Already tailored role.",
        is_qualified=True,
    )
    untailored_job = Job(
        user_id=user.id,
        source="apify",
        url="https://jobs.example.com/untailored-job",
        title="Untailored Role",
        company="Untailored Corp",
        description="Fresh untailored role.",
        is_qualified=True,
    )
    processing_job = Job(
        user_id=user.id,
        source="apify",
        url="https://jobs.example.com/processing-job",
        title="Processing Role",
        company="Processing Corp",
        description="In progress role.",
        is_qualified=True,
    )
    db_session.add_all([tailored_job, untailored_job, processing_job])
    await db_session.commit()
    await db_session.refresh(tailored_job)
    await db_session.refresh(untailored_job)
    await db_session.refresh(processing_job)

    tailored_app = Application(
        user_id=user.id,
        job_id=tailored_job.id,
        resume_id=resume.id,
        applied_status=AppliedStatus.manual,
        mode=ApplicationMode.manual,
        status=ApplicationStatus.saved,
        tailored_html='<div class="resume">Tailored</div>',
        rendered_pdf_url="https://example.com/tailored.pdf",
        email_draft="Subject: Ready",
    )
    processing_app = Application(
        user_id=user.id,
        job_id=processing_job.id,
        resume_id=resume.id,
        applied_status=AppliedStatus.manual,
        mode=ApplicationMode.manual,
        status=ApplicationStatus.tailoring,
    )
    db_session.add_all([tailored_app, processing_app])
    await db_session.commit()

    tailored_res = await client.get(f"/jobs?user_id={user.id}&tailored=true")
    assert tailored_res.status_code == 200
    tailored_jobs = tailored_res.json()
    assert [job["title"] for job in tailored_jobs] == ["Tailored Role"]

    untailored_res = await client.get(f"/jobs?user_id={user.id}&tailored=false")
    assert untailored_res.status_code == 200
    untailored_jobs = untailored_res.json()
    untailored_titles = {job["title"] for job in untailored_jobs}
    assert "Tailored Role" not in untailored_titles
    assert "Untailored Role" in untailored_titles
    assert "Processing Role" in untailored_titles
