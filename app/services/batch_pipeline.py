"""
app/services/batch_pipeline.py — Batch-parallel job tailoring orchestrator.

Processes persisted jobs in parallel batches:
1. Takes a list of Job DB IDs + user's base resume.
2. Chunks jobs into batches of `settings.batch_parallel_workers` (default 10).
3. For each batch, dispatches all jobs to a ThreadPoolExecutor concurrently.
4. Each thread runs the full per-job pipeline:
   analyze_gaps → tailor_resume → render_pdf → draft_email → ATS review → factual review
5. Persists all results (Application record, tailored HTML, PDF, email, ATS score).
6. Waits for each batch to complete before starting the next.
"""

import asyncio
import concurrent.futures
import time
from typing import Any

import structlog
from sqlalchemy import select

import app.database
from app.agent.nodes.analyze_gaps import analyze_gaps_node
from app.agent.nodes.draft_email import draft_email_node
from app.agent.nodes.delivery import send_and_file_node
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


def _process_single_job(
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
    base_resume_id: int,
    base_resume_version: int,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    user_profile: dict | None = None,
) -> dict[str, Any]:
    """
    Run the full tailoring pipeline for a single job synchronously.
    Designed to run inside a ThreadPoolExecutor worker.

    Returns a summary dict with job_id, application_id, status, and ats_score.
    """
    start_time = time.perf_counter()
    log.info(
        "batch_job_start",
        job_id=job_id,
        application_id=application_id,
        job_title=job_title,
        company=company,
    )

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

    try:
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

        # Step D: Draft Outreach Email
        t0 = time.perf_counter()
        state = draft_email_node(state)
        lat = int((time.perf_counter() - t0) * 1000)
        email_draft_val = state.get("email_draft")
        timeline_entries.append(("draft_email", {"email_draft": (email_draft_val or "")[:300]}, lat))

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

        final_status = "success"

        if send_mode == "auto":
            try:
                t0 = time.perf_counter()
                state = send_and_file_node(state)
                lat = int((time.perf_counter() - t0) * 1000)
                timeline_entries.append(
                    ("send_and_file", {"sent": state.get("sent"), "drive_folder_url": state.get("drive_folder_url")}, lat)
                )
            except Exception as exc:
                log.warning("batch_auto_send_failed", job_id=job_id, application_id=application_id, error=str(exc))
                state = {**state, "sent": False}

    except Exception as exc:
        log.error("batch_job_pipeline_failed", job_id=job_id, application_id=application_id, error=str(exc))
        ats_data = {}
        email_draft_val = None
        final_status = "failed"

    elapsed_ms = int((time.perf_counter() - start_time) * 1000)
    log.info(
        "batch_job_complete",
        job_id=job_id,
        application_id=application_id,
        status=final_status,
        latency_ms=elapsed_ms,
    )

    return {
        "job_id": job_id,
        "application_id": application_id,
        "status": final_status,
        "ats_score": ats_data.get("score"),
        "state": state,
        "timeline_entries": timeline_entries,
        "ats_data": ats_data,
        "email_draft": email_draft_val if final_status == "success" else None,
        "sent": bool(state.get("sent")),
        "drive_folder_url": state.get("drive_folder_url"),
    }


async def _persist_single_job_result(
    result: dict[str, Any],
    user_id: int,
    base_resume_id: int,
    base_resume_version: int,
    base_resume_text: str,
    send_mode: str = "manual",
):
    """Persist the pipeline result for a single job to the database."""
    application_id = result["application_id"]
    state = result.get("state", {})
    timeline_entries = result.get("timeline_entries", [])
    ats_data = result.get("ats_data", {})
    email_draft_val = result.get("email_draft")

    async with app.database.AsyncSessionLocal() as db:
        try:
            # 1. Save tailored resume version
            tailored_html = state.get("tailored_resume_html")
            tailored_resume_id = None
            if tailored_html:
                try:
                    tailored_resume = Resume(
                        user_id=user_id,
                        version=base_resume_version + 1,
                        source_text=base_resume_text,
                        source_html=tailored_html,
                        is_base=False,
                    )
                    db.add(tailored_resume)
                    await db.commit()
                    await db.refresh(tailored_resume)
                    tailored_resume_id = tailored_resume.id
                except Exception as res_exc:
                    log.warning("batch_tailored_resume_save_skipped", error=str(res_exc), application_id=application_id)

            # 2. Update Application record
            stmt = select(Application).where(Application.id == application_id)
            res = await db.execute(stmt)
            application = res.scalar_one_or_none()

            if application:
                pdf_url = state.get("pdf_url")
                ats_score_val = ats_data.get("score", 85)
                sent = bool(result.get("sent"))

                if result["status"] != "success":
                    application.status = ApplicationStatus.failed
                elif send_mode == "auto" and sent:
                    application.status = ApplicationStatus.sent
                else:
                    application.status = ApplicationStatus.saved

                application.applied_status = AppliedStatus.yes if send_mode == "auto" and sent else AppliedStatus.manual
                application.mode = ApplicationMode.auto if send_mode == "auto" else ApplicationMode.manual
                application.resume_id = tailored_resume_id or base_resume_id
                application.tailored_html = tailored_html
                application.rendered_pdf_url = pdf_url
                application.drive_folder_url = result.get("drive_folder_url") or pdf_url
                application.email_draft = email_draft_val
                application.gap_analysis = state.get("gap_analysis")
                application.ats_score = ats_score_val
                application.approval_attempts = 1

                await db.commit()
                log.info("batch_persist_complete", application_id=application_id, ats_score=ats_score_val)

            # 3. Save timeline agent runs
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

        except Exception as exc:
            await db.rollback()
            log.error("batch_persist_failed", error=str(exc), application_id=application_id)

            try:
                stmt = select(Application).where(Application.id == application_id)
                res = await db.execute(stmt)
                application = res.scalar_one_or_none()
                if application:
                    application.status = ApplicationStatus.failed
                    await db.commit()
            except Exception:
                pass


async def _create_application_records(
    job_ids: list[int],
    user_id: int,
    base_resume_id: int,
    send_mode: str = "manual",
) -> list[dict[str, Any]]:
    """
    Create Application records for each job and return job metadata needed by workers.
    Returns list of dicts: {job_id, application_id, title, company, description, recruiter_name, recruiter_email}
    """
    job_entries = []
    async with app.database.AsyncSessionLocal() as db:
        for job_id in job_ids:
            # Fetch job details
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
    base_resume_version: int,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    batch_size: int | None = None,
    user_profile: dict | None = None,
) -> list[dict[str, Any]]:
    """
    Process all jobs in parallel batches.

    Chunks job_ids into batches of `settings.batch_parallel_workers` (default 10).
    Each batch runs concurrently via ThreadPoolExecutor.
    Batches are processed sequentially to control resource usage.

    Returns aggregated results across all batches.
    """
    batch_size = batch_size or settings.batch_parallel_workers
    all_results = []

    # 1. Create Application records and fetch job metadata
    job_entries = await _create_application_records(job_ids, user_id, base_resume_id, send_mode=send_mode)

    if not job_entries:
        log.warning("batch_pipeline_no_jobs", user_id=user_id)
        return []

    total_jobs = len(job_entries)
    total_batches = (total_jobs + batch_size - 1) // batch_size

    log.info(
        "batch_pipeline_start",
        total_jobs=total_jobs,
        batch_size=batch_size,
        total_batches=total_batches,
        user_id=user_id,
    )

    # 2. Process in batches
    for batch_idx in range(total_batches):
        batch_start = batch_idx * batch_size
        batch_end = min(batch_start + batch_size, total_jobs)
        batch = job_entries[batch_start:batch_end]

        log.info(
            "batch_start",
            batch_number=batch_idx + 1,
            total_batches=total_batches,
            jobs_in_batch=len(batch),
        )

        batch_t0 = time.perf_counter()
        loop = asyncio.get_event_loop()

        # Dispatch all jobs in this batch to the thread pool concurrently
        max_workers = min(len(batch), batch_size)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for entry in batch:
                future = loop.run_in_executor(
                    executor,
                    _process_single_job,
                    entry["job_id"],
                    entry["title"],
                    entry["company"],
                    entry["description"],
                    entry["recruiter_name"],
                    entry["recruiter_email"],
                    user_id,
                    entry["application_id"],
                    base_resume_text,
                    base_resume_html,
                    base_resume_id,
                    base_resume_version,
                    send_mode,
                    oauth_refresh_token,
                    user_profile,
                )
                futures.append(future)

            # Wait for all jobs in this batch to complete
            batch_results = await asyncio.gather(*futures, return_exceptions=True)

        # 3. Persist results for each job in this batch
        for result in batch_results:
            if isinstance(result, Exception):
                log.error("batch_job_exception", error=str(result))
                continue

            await _persist_single_job_result(
                result=result,
                user_id=user_id,
                base_resume_id=base_resume_id,
                base_resume_version=base_resume_version,
                base_resume_text=base_resume_text,
                send_mode=send_mode,
            )
            all_results.append({
                "job_id": result["job_id"],
                "application_id": result["application_id"],
                "status": result["status"],
                "ats_score": result.get("ats_score"),
                "sent": result.get("sent"),
                "drive_folder_url": result.get("drive_folder_url"),
            })

        batch_elapsed_ms = int((time.perf_counter() - batch_t0) * 1000)
        log.info(
            "batch_complete",
            batch_number=batch_idx + 1,
            total_batches=total_batches,
            latency_ms=batch_elapsed_ms,
            succeeded=sum(1 for r in all_results[batch_start:] if r["status"] == "success"),
        )

    log.info(
        "batch_pipeline_complete",
        total_jobs=total_jobs,
        total_succeeded=sum(1 for r in all_results if r["status"] == "success"),
        total_failed=sum(1 for r in all_results if r["status"] == "failed"),
    )

    return all_results


async def run_batch_pipeline_background(
    job_ids: list[int],
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    base_resume_version: int,
    send_mode: str = "manual",
    oauth_refresh_token: str | None = None,
    batch_size: int | None = None,
    user_profile: dict | None = None,
):
    """Thin async wrapper for BackgroundTasks.add_task()."""
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
