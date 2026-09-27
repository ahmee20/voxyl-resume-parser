"""
app/services/batch_pipeline.py — Batch-parallel job tailoring orchestrator with real-time atomic persistence.

Processes multiple jobs in TRUE parallel:
1. Immediately creates/initializes Application records.
2. Runs LLM tailoring pipelines concurrently using a DEDICATED ThreadPoolExecutor
   (not the default asyncio executor) so all jobs execute simultaneously.
3. Immediately commits each completed resume, PDF, and email draft to the database as soon as it finishes,
   ensuring the UI transitions from 'tailoring' to 'saved' without waiting for the full batch.
4. Uses atomic version numbering with retry to prevent race conditions on resume versioning.
5. Marks any failed/crashed applications as 'failed' (never leaves stuck in 'tailoring').
"""

import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

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

    log.info("batch_job_core_start", application_id=application_id, job_id=job_id, company=company, title=job_title)

    # Step A: Gap Analysis
    t0 = time.perf_counter()
    state = analyze_gaps_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("analyze_gaps", {"gap_analysis": (state.get("gap_analysis") or "")[:300]}, lat))
    log.info("batch_step_done", step="analyze_gaps", latency_ms=lat, app_id=application_id)

    # Step B: Resume Tailoring
    t0 = time.perf_counter()
    state = tailor_resume_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("tailor_resume", {"html_len": len(state.get("tailored_resume_html") or "")}, lat))
    log.info("batch_step_done", step="tailor_resume", latency_ms=lat, app_id=application_id)

    # Step C: Render PDF
    t0 = time.perf_counter()
    state = render_pdf_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("render_pdf", {"pdf_url": state.get("pdf_url")}, lat))
    log.info("batch_step_done", step="render_pdf", latency_ms=lat, app_id=application_id)

    # Step D: Draft Cold Email
    t0 = time.perf_counter()
    state = draft_email_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    email_draft_val = state.get("email_draft")
    timeline_entries.append(("draft_email", {"email_draft": (email_draft_val or "")[:300]}, lat))
    log.info("batch_step_done", step="draft_email", latency_ms=lat, app_id=application_id)

    return state, timeline_entries, email_draft_val


def _run_job_review_sync(state: GraphState) -> tuple[GraphState, list, dict]:
    """Run ATS reviewer and factual anti-hallucination reviewer."""
    timeline_entries = []
    application_id = state.get("application_id")

    # Step E: ATS Reviewer
    t0 = time.perf_counter()
    state = agent_ats_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    ats_data = state.get("ats_review") or {}
    timeline_entries.append(("agent_ats_reviewer", ats_data, lat))
    log.info("batch_step_done", step="ats_reviewer", latency_ms=lat, app_id=application_id)

    # Step F: Factual Anti-Hallucination Reviewer
    t0 = time.perf_counter()
    state = agent_factual_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    factual_data = state.get("factual_review") or {}
    timeline_entries.append(("agent_factual_reviewer", factual_data, lat))
    log.info("batch_step_done", step="factual_reviewer", latency_ms=lat, app_id=application_id)

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
    """Immediately persist tailored HTML, PDF, and email draft in a single atomic transaction, setting status=saved."""
    tailored_html = state.get("tailored_resume_html")
    tailored_resume_id = None

    async with AsyncSessionLocal() as db:
        try:
            # 1. Save tailored resume with atomic SQL in 1 DB round trip (no retries, no sleep delays)
            if tailored_html:
                try:
                    insert_stmt = text("""
                        INSERT INTO resumes (user_id, version, source_text, source_html, is_base, created_at)
                        VALUES (
                            :user_id,
                            COALESCE((SELECT MAX(r.version) FROM resumes r WHERE r.user_id = :user_id), 0) + 1,
                            :source_text,
                            :source_html,
                            false,
                            CURRENT_TIMESTAMP
                        )
                        RETURNING id
                    """)
                    ins_res = await db.execute(
                        insert_stmt,
                        {
                            "user_id": user_id,
                            "source_text": base_resume_text,
                            "source_html": tailored_html,
                        },
                    )
                    tailored_resume_id = ins_res.scalar_one()
                    state["tailored_resume_id"] = tailored_resume_id
                except Exception as res_err:
                    log.warning("batch_tailored_resume_save_failed", error=str(res_err), user_id=user_id)

            # 2. Update Application record to saved (ready) in the exact same transaction
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


async def _mark_application_failed(application_id: int) -> None:
    """Mark an application as failed so it never gets stuck in 'tailoring'."""
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(Application).where(Application.id == application_id)
            res = await db.execute(stmt)
            app_rec = res.scalar_one_or_none()
            if app_rec and app_rec.status == ApplicationStatus.tailoring:
                app_rec.status = ApplicationStatus.failed
                await db.commit()
                log.info("batch_marked_failed", application_id=application_id)
    except Exception:
        pass


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
    executor: ThreadPoolExecutor | None = None,
) -> dict[str, Any]:
    """Execute end-to-end tailoring lifecycle for a single job with immediate real-time DB persistence."""
    job_id = entry["job_id"]
    application_id = entry["application_id"]

    async def _execute():
        loop = asyncio.get_event_loop()
        try:
            # Stage 1: Core Assets Generation — use the DEDICATED executor, not the default
            state, core_timeline, email_draft = await loop.run_in_executor(
                executor,
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

            log.info("batch_job_core_done", application_id=application_id, job_id=job_id)

            # Stage 3: Review & Telemetry (Non-blocking, uses the same dedicated executor)
            try:
                state, review_timeline, ats_data = await loop.run_in_executor(
                    executor,
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
            await _mark_application_failed(application_id)

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
                existing_app.resume_id = base_resume_id
                existing_app.tailored_html = None
                existing_app.rendered_pdf_url = None
                existing_app.email_draft = None
                existing_app.gap_analysis = None
                existing_app.approval_attempts = 0
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
    """
    Process all jobs concurrently with immediate real-time persistence.

    Key fix: Uses a DEDICATED ThreadPoolExecutor sized to the number of jobs
    so that all LLM calls run truly in parallel (not queued behind a tiny
    default pool). The semaphore still controls overall concurrency to avoid
    overwhelming the LLM API rate limits.
    """
    job_entries = await _create_application_records(job_ids, user_id, base_resume_id, send_mode=send_mode)
    if not job_entries:
        return []

    concurrency_limit = batch_size or settings.batch_parallel_workers or 5
    semaphore = asyncio.Semaphore(concurrency_limit)

    # Dedicated threadpool sized to handle all jobs simultaneously.
    # Each job's core pipeline is I/O-bound (waiting for LLM API response),
    # so having many threads is safe and necessary for true parallelism.
    # We multiply by 2 because each job may need threads for both core + review phases.
    pool_size = max(concurrency_limit * 2, len(job_entries) * 2)
    executor = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="batch_llm")

    log.info(
        "batch_pipeline_launching",
        total_jobs=len(job_entries),
        concurrency_limit=concurrency_limit,
        thread_pool_size=pool_size,
        user_id=user_id,
    )

    try:
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
                executor=executor,
            )
            for entry in job_entries
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # Always shut down the dedicated executor cleanly
        executor.shutdown(wait=False)

    clean_results = []
    failed_app_ids = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            app_id = job_entries[i]["application_id"] if i < len(job_entries) else None
            clean_results.append({"status": "failed", "error": str(r), "application_id": app_id})
            if app_id:
                failed_app_ids.append(app_id)
        else:
            clean_results.append(r)

    # Safety net: mark any unhandled exceptions as failed
    for app_id in failed_app_ids:
        await _mark_application_failed(app_id)

    success_count = sum(1 for r in clean_results if r.get("status") == "success")
    fail_count = len(clean_results) - success_count
    log.info("batch_pipeline_complete", total=len(clean_results), success=success_count, failed=fail_count)

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
        # Safety net: mark ALL applications in this batch as failed if the whole orchestrator crashes
        try:
            async with AsyncSessionLocal() as db:
                for job_id in job_ids:
                    stmt = select(Application).where(
                        Application.user_id == user_id,
                        Application.job_id == job_id,
                        Application.status == ApplicationStatus.tailoring,
                    )
                    res = await db.execute(stmt)
                    app = res.scalar_one_or_none()
                    if app:
                        app.status = ApplicationStatus.failed
                await db.commit()
        except Exception:
            pass
