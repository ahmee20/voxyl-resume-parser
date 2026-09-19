"""
app/services/batch_pipeline.py — Batch-parallel job tailoring orchestrator with real-time atomic persistence.

Processes multiple jobs in parallel:
1. Immediately creates/initializes Application records.
2. Runs LLM tailoring pipelines concurrently across worker threads with controlled concurrency.
3. Immediately commits each completed resume, PDF, and email draft to the database as soon as it finishes,
   ensuring the UI transitions from 'tailoring' to 'saved' without waiting for the full batch.
"""

import asyncio
import time
from typing import Any

import structlog
from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.agent.nodes.analyze_gaps import analyze_gaps_node
from app.agent.nodes.draft_email import draft_email_node
from app.agent.nodes.render_pdf import render_pdf_node
from app.agent.nodes.reviewers import agent_ats_reviewer_node, agent_factual_reviewer_node
from app.agent.nodes.tailor_resume import tailor_resume_node
from app.agent.state import GraphState
from app.config import settings
from app.models.agent_run import AgentRun
from app.models.application import Application, ApplicationMode, ApplicationStatus, AppliedStatus
from app.models.job import Job
from app.models.resume import Resume

log = structlog.get_logger(__name__)


def _run_job_core_sync(
    job_id: int,
    job_title: str,
    company: str,
    job_description: str,
    recruiter_name: str,
    recruiter_email: str | None,
    user_id: int,
    application_id: int,
    base_resume_text: str,
    base_resume_html: str,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    user_profile: dict | None = None,
) -> tuple[GraphState, list, str | None]:
    """Run Gap Analysis, Resume Tailoring, PDF Rendering, and Cold Email Draft."""
    state: GraphState = {
        "user_id": user_id,
        "application_id": application_id,
        "send_mode": send_mode,
        "user_profile": user_profile or {},
        "resume_text": base_resume_text,
        "resume_html": base_resume_html,
        "current_job_id": job_id,
        "current_job": {
            "title": job_title,
            "company": company,
            "description": job_description,
            "recruiter_name": recruiter_name,
            "recruiter_email": recruiter_email,
        },
    }
    if oauth_refresh_token:
        state["oauth_refresh_token"] = oauth_refresh_token

    timeline_entries = []

    # Step A: Gap Analysis
    t0 = time.perf_counter()
    state = analyze_gaps_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("analyze_gaps", {"gap_analysis": (state.get("gap_analysis") or "")[:300]}, lat))

    # Step B: Resume Tailoring
    t0 = time.perf_counter()
    state = tailor_resume_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("tailor_resume", {"html_len": len(state.get("tailored_resume_html") or "")}, lat))

    # Step C: Render PDF
    t0 = time.perf_counter()
    state = render_pdf_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("render_pdf", {"pdf_url": state.get("pdf_url")}, lat))

    # Step D: Draft Cold Email
    t0 = time.perf_counter()
    state = draft_email_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    email_draft_val = state.get("email_draft")
    timeline_entries.append(("draft_email", {"email_draft": (email_draft_val or "")[:300]}, lat))

    return state, timeline_entries, email_draft_val


def _run_job_review_sync(state: GraphState) -> tuple[GraphState, list, dict]:
    """Run ATS reviewer and factual anti-hallucination reviewer."""
    timeline_entries = []

    # Step E: ATS Reviewer
    t0 = time.perf_counter()
    state = agent_ats_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    ats_data = state.get("ats_review") or {}
    timeline_entries.append(("agent_ats_reviewer", ats_data, lat))

    # Step F: Factual Anti-Hallucination Reviewer
    t0 = time.perf_counter()
    state = agent_factual_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    factual_data = state.get("factual_review") or {}
    timeline_entries.append(("agent_factual_reviewer", factual_data, lat))

    return state, timeline_entries, ats_data


async def _persist_job_core_results(
    application_id: int,
    user_id: int,
    base_resume_id: int,
    base_resume_text: str,
    state: GraphState,
    timeline_entries: list,
    email_draft_val: str | None,
    send_mode: str = "manual",
) -> int | None:
    """Immediately persist tailored HTML, PDF, and email draft, setting status=saved."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Save tailored resume version with unique incremented version
            tailored_html = state.get("tailored_resume_html")
            tailored_resume_id = None

            if tailored_html:
                try:
                    ver_stmt = select(func.max(Resume.version)).where(Resume.user_id == user_id)
                    ver_res = await db.execute(ver_stmt)
                    current_max = ver_res.scalar() or 1
                    next_version = current_max + 1

                    tailored_resume = Resume(
                        user_id=user_id,
                        version=next_version,
                        source_text=base_resume_text,
                        source_html=tailored_html,
                        is_base=False,
                    )
                    db.add(tailored_resume)
                    await db.commit()
                    await db.refresh(tailored_resume)
                    tailored_resume_id = tailored_resume.id
                    state["tailored_resume_id"] = tailored_resume_id
                except Exception as res_exc:
                    log.warning("batch_tailored_resume_save_skipped", error=str(res_exc), application_id=application_id)

            # 2. Update Application record to saved (ready) immediately
            stmt = select(Application).where(Application.id == application_id)
            res = await db.execute(stmt)
            application = res.scalar_one_or_none()

            if application:
                pdf_url = state.get("pdf_url")
                application.status = ApplicationStatus.saved
                application.applied_status = AppliedStatus.manual
                application.mode = ApplicationMode.auto if send_mode == "auto" else ApplicationMode.manual
                application.resume_id = tailored_resume_id or base_resume_id
                if tailored_html:
                    application.tailored_html = tailored_html
                if pdf_url:
                    application.rendered_pdf_url = pdf_url
                    application.drive_folder_url = pdf_url
                if email_draft_val is not None:
                    application.email_draft = email_draft_val
                if state.get("gap_analysis"):
                    application.gap_analysis = state.get("gap_analysis")
                application.ats_score = application.ats_score or 85
                application.approval_attempts = max(application.approval_attempts or 0, 1)

                await db.commit()
                log.info("batch_core_assets_saved", application_id=application_id, job_id=application.job_id)
            else:
                log.error("batch_application_not_found_on_persist", application_id=application_id)

            # 3. Save initial timeline entries
            try:
                for node_name, output, latency_ms in timeline_entries:
                    db.add(AgentRun(
                        application_id=application_id,
                        node_name=node_name,
                        input={},
                        output=output,
                        latency_ms=latency_ms,
                    ))
                await db.commit()
            except Exception as run_exc:
                log.warning("batch_agent_runs_skipped", error=str(run_exc), application_id=application_id)

            return tailored_resume_id
        except Exception as exc:
            await db.rollback()
            log.error("batch_persist_core_failed", error=str(exc), application_id=application_id)
            return None


async def _persist_job_review_results(
    application_id: int,
    state: GraphState,
    timeline_entries: list,
    ats_data: dict,
):
    """Update ATS score and append review timeline entries."""
    async with AsyncSessionLocal() as db:
        try:
            stmt = select(Application).where(Application.id == application_id)
            res = await db.execute(stmt)
            application = res.scalar_one_or_none()

            if application and ats_data.get("score") is not None:
                application.ats_score = ats_data["score"]
                await db.commit()

            try:
                for node_name, output, latency_ms in timeline_entries:
                    db.add(AgentRun(
                        application_id=application_id,
                        node_name=node_name,
                        input={},
                        output=output,
                        latency_ms=latency_ms,
                    ))
                await db.commit()
            except Exception:
                pass
        except Exception as exc:
            log.warning("batch_persist_review_failed", error=str(exc), application_id=application_id)


async def _process_single_job_lifecycle(
    entry: dict[str, Any],
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    user_profile: dict | None = None,
    semaphore: asyncio.Semaphore | None = None,
) -> dict[str, Any]:
    """Execute end-to-end tailoring lifecycle for a single job with immediate real-time DB persistence."""
    job_id = entry["job_id"]
    application_id = entry["application_id"]

    async def _execute():
        loop = asyncio.get_event_loop()
        try:
            # Stage 1: Core Assets Generation
            state, core_timeline, email_draft = await loop.run_in_executor(
                None,
                _run_job_core_sync,
                job_id,
                entry["title"],
                entry["company"],
                entry["description"],
                entry["recruiter_name"],
                entry["recruiter_email"],
                user_id,
                application_id,
                base_resume_text,
                base_resume_html,
                send_mode,
                oauth_refresh_token,
                user_profile,
            )

            # Stage 2: Immediately persist to DB (Application transitions to saved / ready)
            await _persist_job_core_results(
                application_id=application_id,
                user_id=user_id,
                base_resume_id=base_resume_id,
                base_resume_text=base_resume_text,
                state=state,
                timeline_entries=core_timeline,
                email_draft_val=email_draft,
                send_mode=send_mode,
            )

            # Stage 3: Review & Telemetry (Non-blocking)
            try:
                state, review_timeline, ats_data = await loop.run_in_executor(
                    None,
                    _run_job_review_sync,
                    state,
                )
                await _persist_job_review_results(
                    application_id=application_id,
                    state=state,
                    timeline_entries=review_timeline,
                    ats_data=ats_data,
                )
            except Exception as rev_err:
                log.warning("batch_job_review_skipped", job_id=job_id, error=str(rev_err))

            return {
                "job_id": job_id,
                "application_id": application_id,
                "status": "success",
            }

        except Exception as exc:
            log.error("batch_single_job_failed", job_id=job_id, application_id=application_id, error=str(exc))
            # Immediately mark failed in DB so it doesn't get stuck in 'tailoring'
            try:
                async with AsyncSessionLocal() as db:
                    stmt = select(Application).where(Application.id == application_id)
                    res = await db.execute(stmt)
                    app_rec = res.scalar_one_or_none()
                    if app_rec:
                        app_rec.status = ApplicationStatus.failed
                        await db.commit()
            except Exception:
                pass

            return {
                "job_id": job_id,
                "application_id": application_id,
                "status": "failed",
                "error": str(exc),
            }

    if semaphore:
        async with semaphore:
            return await _execute()
    return await _execute()


async def _create_application_records(
    job_ids: list[int],
    user_id: int,
    base_resume_id: int,
    send_mode: str = "manual",
) -> list[dict[str, Any]]:
    """Create or reset Application records for each job and return job metadata."""
    job_entries = []
    async with AsyncSessionLocal() as db:
        for job_id in job_ids:
            stmt = select(Job).where(Job.id == job_id)
            res = await db.execute(stmt)
            job = res.scalar_one_or_none()
            if not job:
                log.warning("batch_job_not_found", job_id=job_id)
                continue

            job_title = job.title or "Software Engineer"
            company = job.company or "Technology Company"
            description = job.description or f"Job position for {job_title} at {company}."
            recruiter_email = job.recruiter_email
            recruiter_name = "Hiring Team"
            if job.apollo_enrichment:
                recruiter_name = job.apollo_enrichment.get("recruiter_name") or "Hiring Team"

            # Check for existing application
            stmt = select(Application).where(
                Application.user_id == user_id,
                Application.job_id == job.id,
            )
            res = await db.execute(stmt)
            existing_app = res.scalars().first()

            if existing_app:
                existing_app.status = ApplicationStatus.tailoring
                existing_app.mode = ApplicationMode.auto if send_mode == "auto" else ApplicationMode.manual
                await db.commit()
                app_id = existing_app.id
            else:
                new_app = Application(
                    user_id=user_id,
                    job_id=job.id,
                    resume_id=base_resume_id,
                    applied_status=AppliedStatus.manual,
                    mode=ApplicationMode.auto if send_mode == "auto" else ApplicationMode.manual,
                    status=ApplicationStatus.tailoring,
                )
                db.add(new_app)
                await db.commit()
                await db.refresh(new_app)
                app_id = new_app.id

            job_entries.append({
                "job_id": job.id,
                "application_id": app_id,
                "title": job_title,
                "company": company,
                "description": description,
                "recruiter_name": recruiter_name,
                "recruiter_email": recruiter_email,
            })

    return job_entries


async def run_batch_pipeline(
    job_ids: list[int],
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    base_resume_version: int = 1,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    batch_size: int | None = None,
    user_profile: dict | None = None,
) -> list[dict[str, Any]]:
    """Process all jobs concurrently with immediate real-time persistence."""
    job_entries = await _create_application_records(job_ids, user_id, base_resume_id, send_mode=send_mode)
    if not job_entries:
        return []

    concurrency_limit = batch_size or settings.batch_parallel_workers or 5
    semaphore = asyncio.Semaphore(concurrency_limit)

    tasks = [
        _process_single_job_lifecycle(
            entry=entry,
            user_id=user_id,
            base_resume_text=base_resume_text,
            base_resume_html=base_resume_html,
            base_resume_id=base_resume_id,
            send_mode=send_mode,
            oauth_refresh_token=oauth_refresh_token,
            user_profile=user_profile,
            semaphore=semaphore,
        )
        for entry in job_entries
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)
    clean_results = []
    for r in results:
        if isinstance(r, Exception):
            clean_results.append({"status": "failed", "error": str(r)})
        else:
            clean_results.append(r)
    return clean_results


async def run_batch_pipeline_background(
    job_ids: list[int],
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    base_resume_version: int = 1,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    batch_size: int | None = None,
    user_profile: dict | None = None,
):
    """Background entrypoint for batch tailoring."""
    try:
        await run_batch_pipeline(
            job_ids=job_ids,
            user_id=user_id,
            base_resume_text=base_resume_text,
            base_resume_html=base_resume_html,
            base_resume_id=base_resume_id,
            base_resume_version=base_resume_version,
            send_mode=send_mode,
            oauth_refresh_token=oauth_refresh_token,
            batch_size=batch_size,
            user_profile=user_profile,
        )
    except Exception as exc:
        log.error("batch_pipeline_background_crashed", error=str(exc), user_id=user_id)
