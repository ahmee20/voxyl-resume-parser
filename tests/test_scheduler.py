"""
tests/test_scheduler.py — Tests for the APScheduler background discovery loop.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.scheduler import run_discovery_for_all_users
from app.models.user import User
from app.models.resume import Resume


@pytest.mark.asyncio
async def test_run_discovery_no_users(db_session):
    """When no users have resumes, the discovery loop should complete silently."""
    await run_discovery_for_all_users()
    # No errors, no crash — just a clean return


@pytest.mark.asyncio
async def test_run_discovery_with_user_and_resume(db_session):
    """Discovery loop should process a user with a base resume."""
    # Seed a user + base resume
    user = User(google_sub="sub-sched-1", email="sched@test.com", name="Scheduler User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    resume = Resume(
        user_id=user.id,
        version=1,
        source_text="Senior AI Engineer with Python and LangGraph experience.",
        source_html="<div>AI Engineer</div>",
        is_base=True,
    )
    db_session.add(resume)
    await db_session.commit()

    mock_queries = '["AI Engineer", "ML Engineer"]'
    with patch("app.agent.nodes.search_planner.get_llm") as mock_get_llm:
        mock_chat = MagicMock()
        mock_chat.invoke.return_value = MagicMock(content=mock_queries)
        mock_get_llm.return_value = mock_chat

        await run_discovery_for_all_users()
    # Should complete without error — jobs persisted via mock Apify


@pytest.mark.asyncio
async def test_start_scheduler_adds_job():
    """start_scheduler should add the discovery job to the scheduler."""
    with patch("app.services.scheduler.scheduler") as mock_sched:
        mock_sched.running = False
        from app.services.scheduler import start_scheduler
        start_scheduler()
        mock_sched.add_job.assert_called_once()
        mock_sched.start.assert_called_once()


@pytest.mark.asyncio
async def test_stop_scheduler_shuts_down():
    """stop_scheduler should call shutdown when scheduler is running."""
    with patch("app.services.scheduler.scheduler") as mock_sched:
        mock_sched.running = True
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
        mock_sched.shutdown.assert_called_once_with(wait=False)


@pytest.mark.asyncio
async def test_start_scheduler_skips_if_already_running():
    """start_scheduler should skip if scheduler is already running."""
    with patch("app.services.scheduler.scheduler") as mock_sched:
        mock_sched.running = True
        from app.services.scheduler import start_scheduler
        start_scheduler()
        mock_sched.start.assert_not_called()
