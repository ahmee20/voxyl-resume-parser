"""
app/services/scheduler.py — APScheduler background job discovery loop.

Runs a recurring 3-hour autonomous cycle for users who opted into auto mode:
1. Generates search queries via LLM when needed
2. Scrapes jobs via Apify from the last 3 hours
3. Enriches, filters, and persists discovered jobs
4. Tailors and sends recruiter outreach in parallel batches
5. Sends the candidate a summary email when the run completes
"""

import asyncio
from datetime import datetime, timezone

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

import app.database as db_module
from app.agent.nodes.enrich_jobs import enrich_jobs_node
from app.agent.nodes.filter_jobs import filter_relevant_node
from app.agent.nodes.persist_jobs import persist_jobs_node
from app.agent.nodes.search_planner import plan_search_queries_node
from app.agent.state import GraphState
from app.config import settings
from app.models.resume import Resume
from app.models.user import SendMode, User
from app.services.apify_scraper import scrape_jobs_from_apify
from app.services.batch_pipeline import run_batch_pipeline
from app.services.google_delivery import send_gmail_email
from app.services.job_deduper import split_fresh_and_known_jobs
from app.services.resume_template import render_resume_html
from app.utils.security import decrypt_token

log = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler()


def _clean_string_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    cleaned: list[str] = []
    for value in values:
      item = value.strip()
      if item and item not in cleaned:
        cleaned.append(item)
    return cleaned[:3]


def _user_profile_payload(user: User | None) -> dict[str, str | None]:
    if not user:
        return {}
    return {
        "name": user.name,
        "preferred_name": user.preferred_name or user.name,
        "email": user.email,
        "github_url": user.github_url,
        "portfolio_url": user.portfolio_url,
        "linkedin_url": user.linkedin_url,
    }


async def _get_latest_base_resume(session, user_id: int) -> Resume | None:
    stmt = (
        select(Resume)
        .where(Resume.user_id == user_id, Resume.is_base == True)  # noqa: E712
        .order_by(Resume.version.desc(), Resume.created_at.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def _run_auto_cycle_for_user(user: User) -> None:
    refresh_token = None
    if user.oauth_refresh_token:
        try:
          refresh_token = decrypt_token(user.oauth_refresh_token)
        except Exception as exc:
          log.warning("scheduler_refresh_token_decrypt_failed", user_id=user.id, error=str(exc))
          refresh_token = None

    async with db_module.AsyncSessionLocal() as session:
        resume = await _get_latest_base_resume(session, user.id)
        if not resume or not resume.source_text:
            log.warning("scheduler_skip_user_no_resume", user_id=user.id)
            return

        preferred_roles = _clean_string_list(user.preferred_roles)[:1]
        preferred_countries = _clean_string_list(user.preferred_countries) or ["REMOTE", "US"]
        queries = preferred_roles

        if not queries:
            plan_state: GraphState = {
                "user_id": user.id,
                "application_id": 0,
                "resume_text": resume.source_text,
            }
            plan_state = await asyncio.to_thread(plan_search_queries_node, plan_state)
            queries = plan_state.get("search_queries") or []

        if not queries:
            log.warning("scheduler_skip_user_no_queries", user_id=user.id)
            return

        scraped_jobs = await asyncio.to_thread(
            scrape_jobs_from_apify,
            queries,
            preferred_countries,
            None,
            3,
        )

        state: GraphState = {
            "user_id": user.id,
            "application_id": 0,
            "resume_text": resume.source_text,
            "resume_html": resume.source_html or render_resume_html(resume.source_text),
            "search_queries": queries,
            "preferred_countries": preferred_countries,
            "scraped_jobs": scraped_jobs,
        }

        fresh_jobs, duplicate_jobs = await split_fresh_and_known_jobs(session, user.id, state.get("scraped_jobs", []))
        state["scraped_jobs"] = fresh_jobs
        state["duplicate_jobs"] = duplicate_jobs
        state["duplicate_job_ids"] = []

        state = await asyncio.to_thread(enrich_jobs_node, state)
        state = await asyncio.to_thread(filter_relevant_node, state)
        state = await asyncio.to_thread(persist_jobs_node, state)

        persisted_ids = state.get("persisted_job_ids", [])
        if not persisted_ids:
            log.info("scheduler_no_persisted_jobs", user_id=user.id)
            if refresh_token:
                try:
                    await send_gmail_email(
                        refresh_token=refresh_token,
                        to_email=user.email,
                        subject="Voxyl automated run complete",
                        body_text=(
                            "Your scheduled Voxyl run completed, but no new jobs were found in the last 3 hours.\n\n"
                            "You can open Voxyl anytime to adjust roles or countries."
                        ),
                    )
                except Exception as exc:
                    log.warning("scheduler_user_summary_email_failed", user_id=user.id, error=str(exc))
            return

        batch_size = 5
        results = await run_batch_pipeline(
            job_ids=persisted_ids,
            user_id=user.id,
            base_resume_text=resume.source_text,
            base_resume_html=resume.source_html or render_resume_html(resume.source_text),
            base_resume_id=resume.id,
            base_resume_version=resume.version,
            send_mode="auto",
            oauth_refresh_token=refresh_token,
            batch_size=batch_size,
            user_profile=_user_profile_payload(user),
        )

        tailored_count = sum(1 for item in results if item.get("status") == "success")
        sent_count = sum(1 for item in results if item.get("sent"))
        subject = f"Voxyl found {len(persisted_ids)} jobs ready for you"
        body = (
            f"Your scheduled Voxyl run finished at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.\n\n"
            f"Scraped jobs: {len(scraped_jobs)}\n"
            f"Tailored jobs: {tailored_count}\n"
            f"Sent to recruiters: {sent_count}\n\n"
            "Open Voxyl to review the latest batch and choose what to apply to next."
        )

        if refresh_token:
            try:
                await send_gmail_email(
                    refresh_token=refresh_token,
                    to_email=user.email,
                    subject=subject,
                    body_text=body,
                )
            except Exception as exc:
                log.warning("scheduler_user_summary_email_failed", user_id=user.id, error=str(exc))

        log.info(
            "scheduler_user_cycle_complete",
            user_id=user.id,
            scraped=len(scraped_jobs),
            persisted=len(persisted_ids),
            tailored=tailored_count,
            sent=sent_count,
        )


async def run_discovery_for_all_users() -> None:
    """Run the autonomous discovery/tailoring cycle for all opted-in users."""
    log.info("scheduler_discovery_started")
    processed = 0
    errors = 0

    try:
        async with db_module.AsyncSessionLocal() as session:
            stmt = select(User).where(
                User.send_mode == SendMode.auto,
                User.oauth_refresh_token.isnot(None),
            )
            result = await session.execute(stmt)
            users = result.scalars().all()

            if not users:
                log.info("scheduler_no_auto_users")
                return

            for user in users:
                try:
                    await _run_auto_cycle_for_user(user)
                    processed += 1
                except Exception as exc:
                    errors += 1
                    log.error("scheduler_discovery_user_error", user_id=user.id, error=str(exc))
    except Exception as exc:
        log.error("scheduler_discovery_fatal", error=str(exc))

    log.info("scheduler_discovery_finished", processed=processed, errors=errors)


def start_scheduler() -> None:
    """Add the discovery job and start the APScheduler event loop."""
    if scheduler.running:
        log.warning("scheduler_already_running")
        return

    interval = settings.scheduler_interval_hours
    scheduler.add_job(
        run_discovery_for_all_users,
        trigger=IntervalTrigger(hours=interval),
        id="job_discovery_loop",
        name="Discover and tailor jobs for auto users",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    log.info("scheduler_started", interval_hours=interval)


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
