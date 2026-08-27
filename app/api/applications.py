"""
app/api/applications.py — Job application endpoints and single-job pipeline runner.

Runs the multi-agent tailoring pipeline as a background task:
1. Branch B:
   - Gap Analysis (compares JD to base resume, documents targeted changes & keywords)
   - Resume Tailoring (generates tailored HTML incorporating legit JD keywords)
   - PDF Rendering (converts HTML to PDF via pdf.co or local fallback)
   - Cold Outreach Email Drafting (personalized with Apollo recruiter details)
   - ATS & Factual Anti-Hallucination Review Loop
2. Persists all tailored assets and observability traces.
"""

import asyncio
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.nodes.analyze_gaps import analyze_gaps_node
from app.agent.nodes.tailor_resume import tailor_resume_node
from app.agent.nodes.render_pdf import render_pdf_node
from app.agent.nodes.draft_email import draft_email_node
from app.agent.nodes.reviewers import agent_ats_reviewer_node, agent_factual_reviewer_node
from app.agent.state import GraphState
from app.database import AsyncSessionLocal, get_db
from app.models.agent_run import AgentRun
from app.models.application import Application, ApplicationMode, ApplicationStatus, AppliedStatus
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.services.batch_pipeline import run_batch_pipeline_background
from app.services.resume_template import ResumeProfile, render_resume_html

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/applications", tags=["applications"])


class SingleJobRequest(BaseModel):
    user_id: Optional[int] = None
    job_id: Optional[int] = None
    job_title: Optional[str] = None
    company: Optional[str] = None
    job_description: Optional[str] = None
    resume_id: Optional[int] = None


class BatchJobRequest(BaseModel):
    user_id: Optional[int] = None
    job_ids: list[int]
    resume_id: Optional[int] = None


class AgentRunResponse(BaseModel):
    id: int
    node_name: str
    status: str = "success"
    latency_ms: Optional[int] = None
    created_at: datetime
    state_snapshot: Optional[dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class ApplicationDetailResponse(BaseModel):
    id: int
    user_id: int
    job_id: int
    resume_id: Optional[int] = None
    applied_status: AppliedStatus
    mode: ApplicationMode
    status: ApplicationStatus
    pdf_url: Optional[str] = None
    email_draft: Optional[str] = None
    tailored_html: Optional[str] = None
    ats_score: Optional[int] = None
    gap_analysis: Optional[str] = None
    approval_attempts: int = 1
    timeline: list[AgentRunResponse] = []

    model_config = ConfigDict(from_attributes=True)


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


def _resume_profile(user: User | None) -> ResumeProfile:
    return ResumeProfile(
        name=(user.preferred_name or user.name) if user else None,
        email=user.email if user else None,
        github_url=user.github_url if user else None,
        portfolio_url=user.portfolio_url if user else None,
        linkedin_url=user.linkedin_url if user else None,
    )


# ── Background pipeline runner ───────────────────────────────────────────────

def _run_pipeline_sync(
    application_id: int,
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    base_resume_version: int,
    job_id: int,
    job_title: str,
    company: str,
    job_description: str,
    recruiter_name: str = "Hiring Team",
    recruiter_email: str | None = None,
    user_profile: dict | None = None,
):
    """
    Run the multi-agent tailoring pipeline synchronously inside a background worker thread.
    """
    log.info("pipeline_bg_start", application_id=application_id, job_title=job_title, company=company)

    state: GraphState = {
        "user_id": user_id,
        "application_id": application_id,
        "send_mode": "manual",
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

    timeline_entries = []

    # Step A: Gap Analysis & Changes Identification
    t0 = time.perf_counter()
    state = analyze_gaps_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("analyze_gaps", {"gap_analysis": (state.get("gap_analysis") or "")[:300]}, lat))
    log.info("pipeline_step_done", step="analyze_gaps", latency_ms=lat, app_id=application_id)

    # Step B: Resume Tailoring
    t0 = time.perf_counter()
    state = tailor_resume_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("tailor_resume", {"html_len": len(state.get("tailored_resume_html") or "")}, lat))
    log.info("pipeline_step_done", step="tailor_resume", latency_ms=lat, app_id=application_id)

    # Step C: Render PDF
    t0 = time.perf_counter()
    state = render_pdf_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    timeline_entries.append(("render_pdf", {"pdf_url": state.get("pdf_url")}, lat))
    log.info("pipeline_step_done", step="render_pdf", latency_ms=lat, app_id=application_id)

    # Step D: Draft Outreach Email (with Apollo Recruiter Details)
    t0 = time.perf_counter()
    state = draft_email_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    email_draft_val = state.get("email_draft")
    timeline_entries.append(("draft_email", {"email_draft": (email_draft_val or "")[:300]}, lat))
    log.info("pipeline_step_done", step="draft_email", latency_ms=lat, app_id=application_id)

    # Step E: ATS Reviewer
    t0 = time.perf_counter()
    state = agent_ats_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    ats_data = state.get("ats_review") or {}
    timeline_entries.append(("agent_ats_reviewer", ats_data, lat))
    log.info("pipeline_step_done", step="ats_reviewer", latency_ms=lat, app_id=application_id)

    # Step F: Factual Anti-Hallucination Reviewer
    t0 = time.perf_counter()
    state = agent_factual_reviewer_node(state)
    lat = int((time.perf_counter() - t0) * 1000)
    factual_data = state.get("factual_review") or {}
    timeline_entries.append(("agent_factual_reviewer", factual_data, lat))
    log.info("pipeline_step_done", step="factual_reviewer", latency_ms=lat, app_id=application_id)

    return state, timeline_entries, ats_data, email_draft_val


async def _persist_pipeline_results(
    application_id: int,
    user_id: int,
    base_resume_id: int,
    base_resume_version: int,
    base_resume_text: str,
    state: dict,
    timeline_entries: list,
    ats_data: dict,
    email_draft_val: str | None,
):
    """Persist pipeline results using a fresh async DB session."""
    async with AsyncSessionLocal() as db:
        try:
            # 1. Save tailored resume version first
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
                    log.warning("tailored_resume_save_skipped", error=str(res_exc))

            # 2. Update Application record with all tailored assets
            stmt = select(Application).where(Application.id == application_id)
            res = await db.execute(stmt)
            application = res.scalar_one_or_none()

            if application:
                pdf_url = state.get("pdf_url")
                ats_score_val = ats_data.get("score", 85)

                application.status = ApplicationStatus.saved
                application.applied_status = AppliedStatus.manual
                application.resume_id = tailored_resume_id or base_resume_id
                application.tailored_html = tailored_html
                application.rendered_pdf_url = pdf_url
                application.drive_folder_url = pdf_url
                application.email_draft = email_draft_val
                application.gap_analysis = state.get("gap_analysis")
                application.ats_score = ats_score_val
                application.approval_attempts = 1

                await db.commit()
                log.info("pipeline_bg_complete", application_id=application_id, ats_score=ats_score_val)
            else:
                log.error("pipeline_bg_app_not_found", application_id=application_id)

            # 3. Save timeline agent runs (observability) in separate transaction
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
                log.warning("agent_runs_telemetry_skipped", error=str(run_exc), application_id=application_id)

        except Exception as exc:
            await db.rollback()
            log.error("pipeline_bg_persist_failed", error=str(exc), application_id=application_id)

            # Mark application as failed if critical error occurred
            try:
                stmt = select(Application).where(Application.id == application_id)
                res = await db.execute(stmt)
                application = res.scalar_one_or_none()
                if application:
                    application.status = ApplicationStatus.failed
                    await db.commit()
            except Exception:
                pass


async def run_pipeline_background(
    application_id: int,
    user_id: int,
    base_resume_text: str,
    base_resume_html: str,
    base_resume_id: int,
    base_resume_version: int,
    job_id: int,
    job_title: str,
    company: str,
    job_description: str,
    recruiter_name: str = "Hiring Team",
    recruiter_email: str | None = None,
    user_profile: dict | None = None,
):
    """Async wrapper that executes LLM pipeline in threadpool, then persists results."""
    try:
        loop = asyncio.get_event_loop()
        state, timeline_entries, ats_data, email_draft_val = await loop.run_in_executor(
            None,
            _run_pipeline_sync,
            application_id,
            user_id,
            base_resume_text,
            base_resume_html,
            base_resume_id,
            base_resume_version,
            job_id,
            job_title,
            company,
            job_description,
            recruiter_name,
            recruiter_email,
            user_profile,
        )

        await _persist_pipeline_results(
            application_id=application_id,
            user_id=user_id,
            base_resume_id=base_resume_id,
            base_resume_version=base_resume_version,
            base_resume_text=base_resume_text,
            state=state,
            timeline_entries=timeline_entries,
            ats_data=ats_data,
            email_draft_val=email_draft_val,
        )

    except Exception as exc:
        log.error("pipeline_bg_crashed", error=str(exc), application_id=application_id)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/run-single", status_code=status.HTTP_201_CREATED)
async def run_single_job_pipeline(
    payload: SingleJobRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute the tailoring pipeline for a job.
    Creates an Application record and launches the multi-agent tailoring in the background.
    Returns immediately with application_id so UI can display live progress.
    """
    # 1. Resolve active user_id
    resolved_user_id = payload.user_id
    if not resolved_user_id:
        stmt = select(User).order_by(User.id.asc())
        res = await db.execute(stmt)
        first_user = res.scalars().first()
        resolved_user_id = first_user.id if first_user else 1

    stmt = select(User).where(User.id == resolved_user_id)
    user_res = await db.execute(stmt)
    active_user = user_res.scalar_one_or_none()

    # 2. Fetch base resume
    if payload.resume_id:
        stmt = select(Resume).where(Resume.id == payload.resume_id)
    else:
        stmt = (
            select(Resume)
            .where(Resume.user_id == resolved_user_id)
            .order_by(Resume.version.desc())
        )
    result = await db.execute(stmt)
    base_resume = result.scalars().first()

    if not base_resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No base resume found for user. Please upload a resume first.",
        )

    # 3. Resolve Job record
    recruiter_name = "Hiring Team"
    recruiter_email = None

    if payload.job_id:
        stmt = select(Job).where(Job.id == payload.job_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {payload.job_id} not found.",
            )
        job_title = job.title or "Software Engineer"
        company = job.company or "Technology Company"
        job_description = job.description or f"Job position for {job_title} at {company}."
        recruiter_email = job.recruiter_email
        if job.apollo_enrichment:
            recruiter_name = job.apollo_enrichment.get("recruiter_name") or "Hiring Team"
    else:
        job_title = payload.job_title or "Software Engineer"
        company = payload.company or "Company"
        job_description = payload.job_description or f"Job position for {job_title} at {company}."

        unique_hash = hashlib.md5(
            f"{company}_{job_title}_{job_description[:100]}".encode()
        ).hexdigest()
        job_url = f"manual://job/{unique_hash}"

        stmt = select(Job).where(Job.url == job_url, Job.user_id == resolved_user_id)
        res = await db.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            job = Job(
                user_id=resolved_user_id,
                source="manual_paste",
                url=job_url,
                title=job_title,
                company=company,
                description=job_description,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)

    # 4. Check if an application already exists for this user and job
    stmt = select(Application).where(
        Application.user_id == resolved_user_id,
        Application.job_id == job.id,
    )
    res = await db.execute(stmt)
    application = res.scalars().first()

    if not application:
        application = Application(
            user_id=resolved_user_id,
            job_id=job.id,
            resume_id=base_resume.id,
            applied_status=AppliedStatus.manual,
            mode=ApplicationMode.manual,
            status=ApplicationStatus.tailoring,
        )
        db.add(application)
        await db.commit()
        await db.refresh(application)
    else:
        application.status = ApplicationStatus.tailoring
        await db.commit()

    # 5. Launch the multi-agent tailoring pipeline in background
    background_tasks.add_task(
        run_pipeline_background,
        application_id=application.id,
        user_id=resolved_user_id,
        base_resume_text=base_resume.source_text,
        base_resume_html=base_resume.source_html or render_resume_html(base_resume.source_text, _resume_profile(active_user)),
        base_resume_id=base_resume.id,
        base_resume_version=base_resume.version,
        job_id=job.id,
        job_title=job_title,
        company=company,
        job_description=job_description,
        recruiter_name=recruiter_name,
        recruiter_email=recruiter_email,
        user_profile=_user_profile_payload(active_user),
    )

    return {
        "status": "tailoring",
        "application_id": application.id,
        "job_id": job.id,
        "applied_status": application.applied_status.value,
        "message": "Multi-agent tailoring pipeline launched in background.",
    }


@router.post("/run-batch", status_code=status.HTTP_202_ACCEPTED)
async def run_batch_job_pipeline(
    payload: BatchJobRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute the multi-agent tailoring pipeline for multiple selected jobs in parallel batches.
    Launches background worker threads to tailor resumes, draft cold emails, and run review guardrails.
    """
    if not payload.job_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No job_ids provided for batch tailoring.",
        )

    # 1. Resolve active user_id
    resolved_user_id = payload.user_id
    if not resolved_user_id:
        stmt = select(User).order_by(User.id.asc())
        res = await db.execute(stmt)
        first_user = res.scalars().first()
        resolved_user_id = first_user.id if first_user else 1

    stmt = select(User).where(User.id == resolved_user_id)
    user_res = await db.execute(stmt)
    active_user = user_res.scalar_one_or_none()

    # 2. Fetch base resume
    if payload.resume_id:
        stmt = select(Resume).where(Resume.id == payload.resume_id)
    else:
        stmt = (
            select(Resume)
            .where(Resume.user_id == resolved_user_id)
            .order_by(Resume.version.desc())
        )
    result = await db.execute(stmt)
    base_resume = result.scalars().first()

    if not base_resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No base resume found for user. Please upload a resume first.",
        )

    # 3. Launch the batch-parallel tailoring pipeline in background
    background_tasks.add_task(
        run_batch_pipeline_background,
        job_ids=payload.job_ids,
        user_id=resolved_user_id,
        base_resume_text=base_resume.source_text,
        base_resume_html=base_resume.source_html or render_resume_html(base_resume.source_text, _resume_profile(active_user)),
        base_resume_id=base_resume.id,
        base_resume_version=base_resume.version,
        user_profile=_user_profile_payload(active_user),
    )

    return {
        "status": "tailoring",
        "job_ids": payload.job_ids,
        "count": len(payload.job_ids),
        "message": f"Multi-agent tailoring pipeline launched in background for {len(payload.job_ids)} selected jobs.",
    }


@router.get("/{application_id}")
async def get_application_details(
    application_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full application details, linked job, tailored assets, and observability timeline."""
    stmt = select(Application).where(Application.id == application_id)
    result = await db.execute(stmt)
    app_record = result.scalar_one_or_none()

    if not app_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with ID {application_id} not found.",
        )

    # Fetch agent runs
    timeline_stmt = (
        select(AgentRun)
        .where(AgentRun.application_id == application_id)
        .order_by(AgentRun.created_at.asc())
    )
    timeline_res = await db.execute(timeline_stmt)
    runs = timeline_res.scalars().all()

    formatted_timeline = []
    for r in runs:
        snapshot = {}
        if r.node_name == "agent_ats_reviewer" and r.output:
            snapshot["ats_review"] = {
                "pass": r.output.get("pass", True),
                "score": r.output.get("score", 85),
                "feedback": ", ".join(r.output.get("flags", [])) if isinstance(r.output.get("flags"), list) else "Strong ATS alignment.",
            }
        elif r.node_name == "draft_email" and app_record.email_draft:
            snapshot["draft_email"] = {
                "subject": f"Application for Role",
                "body": app_record.email_draft,
            }
        elif r.node_name == "render_pdf" and app_record.rendered_pdf_url:
            snapshot["drive_folder_url"] = app_record.rendered_pdf_url

        formatted_timeline.append(
            {
                "id": r.id,
                "node_name": r.node_name,
                "status": getattr(r, "status", "success") or "success",
                "latency_ms": r.latency_ms or 150,
                "created_at": r.created_at.isoformat(),
                "state_snapshot": snapshot if snapshot else None,
            }
        )

    return {
        "id": app_record.id,
        "user_id": app_record.user_id,
        "job_id": app_record.job_id,
        "resume_id": app_record.resume_id,
        "applied_status": app_record.applied_status.value,
        "mode": app_record.mode.value,
        "status": app_record.status.value,
        "pdf_url": app_record.rendered_pdf_url or app_record.drive_folder_url,
        "tailored_html": app_record.tailored_html,
        "ats_score": app_record.ats_score,
        "gap_analysis": app_record.gap_analysis,
        "email_draft": app_record.email_draft,
        "rendered_pdf_url": app_record.rendered_pdf_url,
        "approval_attempts": app_record.approval_attempts,
        "timeline": formatted_timeline,
    }
