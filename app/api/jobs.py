"""
app/api/jobs.py — Job discovery and listing endpoints.
"""

from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.agent.nodes.enrich_jobs import enrich_jobs_node
from app.agent.nodes.filter_jobs import filter_relevant_node
from app.agent.nodes.persist_jobs import persist_jobs_node
from app.agent.nodes.scrape_jobs import scrape_jobs_node
from app.agent.nodes.search_planner import plan_search_queries_node
from app.agent.state import GraphState
from app.config import settings
from app.database import get_db
from app.models.application import Application
from app.models.job import Job
from app.models.resume import Resume
from app.models.user import User
from app.services.job_deduper import split_fresh_and_known_jobs
from app.services.batch_pipeline import run_batch_pipeline_background
from app.services.resume_template import ResumeProfile, render_resume_html

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _effective_application_status(application: Application) -> str:
    raw_status = application.status.value if hasattr(application.status, "value") else str(application.status)
    has_assets = bool(application.tailored_html or application.rendered_pdf_url or application.email_draft)
    if raw_status == "tailoring" and has_assets:
        return "saved"
    return raw_status


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


class JobApplicationSummary(BaseModel):
    id: int
    status: str
    applied_status: str
    pdf_url: Optional[str] = None
    email_draft: Optional[str] = None
    tailored_html: Optional[str] = None
    ats_score: Optional[int] = None
    gap_analysis: Optional[str] = None
    approval_attempts: int = 1

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: int
    title: Optional[str] = None
    company: Optional[str] = None
    url: str
    description: Optional[str] = None
    recruiter_email: Optional[str] = None
    source: str
    is_qualified: bool = True
    match_score: Optional[int] = None
    filter_reason: Optional[str] = None
    apollo_enrichment: Optional[dict[str, Any]] = None
    application: Optional[JobApplicationSummary] = None

    model_config = ConfigDict(from_attributes=True)


class DiscoveryRequest(BaseModel):
    user_id: int
    resume_id: Optional[int] = None
    target_role: Optional[str] = None
    preferred_roles: Optional[list[str]] = None
    countries: Optional[list[str]] = None
    max_results: Optional[int] = None


def _job_to_response(job: Job, latest_app: Application | None = None) -> JobResponse:
    app = latest_app
    latest_app_summary = None
    if app:
        latest_app_summary = JobApplicationSummary(
            id=app.id,
            status=_effective_application_status(app),
            applied_status=app.applied_status.value if hasattr(app.applied_status, "value") else str(app.applied_status),
            pdf_url=app.rendered_pdf_url or app.drive_folder_url,
            email_draft=app.email_draft,
            tailored_html=app.tailored_html,
            ats_score=app.ats_score,
            gap_analysis=app.gap_analysis,
            approval_attempts=app.approval_attempts or 1,
        )

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        url=job.url,
        description=job.description,
        recruiter_email=job.recruiter_email,
        source=job.source,
        is_qualified=job.is_qualified if job.is_qualified is not None else True,
        match_score=job.match_score,
        filter_reason=job.filter_reason,
        apollo_enrichment=job.apollo_enrichment,
        application=latest_app_summary,
    )


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    request: Request,
    user_id: Optional[int] = Query(default=None),
    latest: bool = Query(default=False),
    qualified: Optional[bool] = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List jobs discovered for the specific user with associated application state.
    - user_id: filters specifically to the target user (from query param or session)
    - latest=true: returns only the most recent Apify discovery run batch for the dashboard
    - latest=false: returns all discovered jobs till date with offset/limit pagination
    - qualified=true/false: optionally filters by match status
    """
    # 1. Resolve active user_id (query param -> session cookie)
    resolved_user_id = user_id
    if not resolved_user_id and request:
        resolved_user_id = request.session.get("user_id")

    if not resolved_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please log in with Google.",
        )

    # 2. Build user-scoped query
    latest_app_subquery = (
        select(Application.job_id, func.max(Application.id).label("max_application_id"))
        .group_by(Application.job_id)
        .subquery()
    )
    latest_app_alias = aliased(Application)
    stmt = (
        select(Job, latest_app_alias)
        .outerjoin(latest_app_subquery, Job.id == latest_app_subquery.c.job_id)
        .outerjoin(latest_app_alias, latest_app_alias.id == latest_app_subquery.c.max_application_id)
        .where(Job.user_id == resolved_user_id)
    )

    if qualified is not None:
        stmt = stmt.where(Job.is_qualified == qualified)

    stmt = stmt.order_by(Job.id.desc())

    if latest:
        stmt = stmt.limit(limit)
    else:
        stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    rows = result.all()

    response_items = []
    for job, latest_app in rows:
        response_items.append(_job_to_response(job, latest_app))

    return response_items


@router.post("/discover", status_code=status.HTTP_200_OK)
async def discover_jobs_for_user(
    payload: DiscoveryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the fast job discovery and multi-agent enrichment pipeline:
    1. Extract search queries / role from user parameters or resume
    2. Scrape latest matching jobs via Apify (all jobs retained, no 70% cutoff)
    3. Apollo Branch: Enrich company profiles & search recruiter contacts for all scraped jobs
    4. Persist all discovered jobs with Apollo metadata to the database
    5. Return immediately so discovered jobs are visible instantly.
    """
    # 1. Fetch user base resume
    if payload.resume_id:
        stmt = select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == payload.user_id)
    else:
        stmt = (
            select(Resume)
            .where(Resume.user_id == payload.user_id, Resume.is_base == True)
            .order_by(Resume.version.desc())
        )
    res = await db.execute(stmt)
    resume = res.scalars().first()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No base resume found for user. Please upload a resume first.",
        )

    # 2. Prepare discovery parameters
    explicit_role = payload.target_role.strip() if payload.target_role and payload.target_role.strip() else None
    preferred_roles = [role.strip() for role in (payload.preferred_roles or []) if role and role.strip()]
    preferred_roles = preferred_roles[:3]
    queries = preferred_roles or ([explicit_role] if explicit_role else None)
    countries = payload.countries if (payload.countries and len(payload.countries) > 0) else ["US"]

    state: GraphState = {
        "user_id": payload.user_id,
        "application_id": 0,
        "resume_text": resume.source_text,
        "search_queries": queries,
        "preferred_countries": countries,
        "max_results": None,
        "posted_within_hours": 24,
    }

    # Only invoke the planner if the user did not provide preferred roles.
    if not queries:
        state = plan_search_queries_node(state)

    # Pipeline execution:
    # 1. Scrape jobs
    state = scrape_jobs_node(state)

    # 2. Drop jobs already discovered for this user before we spend more time on them
    fresh_jobs, duplicate_jobs = await split_fresh_and_known_jobs(db, payload.user_id, state.get("scraped_jobs", []))
    state["scraped_jobs"] = fresh_jobs
    state["duplicate_jobs"] = duplicate_jobs
    state["duplicate_job_ids"] = []

    # 3. Apollo enrichment branch across only fresh jobs
    state = enrich_jobs_node(state)

    # 4. Clean and filter basic formatting
    state = filter_relevant_node(state)

    # 5. Persist all discovered jobs with deduplication
    state = persist_jobs_node(state)

    persisted_ids = state.get("persisted_job_ids", [])
    fresh_count = len(fresh_jobs)
    relevant_count = len(state.get("relevant_jobs", []))
    fresh_jobs: list[JobResponse] = []
    if persisted_ids:
        stmt_jobs = (
            select(Job)
            .where(Job.user_id == payload.user_id, Job.id.in_(persisted_ids))
            .order_by(Job.id.desc())
        )
        jobs_res = await db.execute(stmt_jobs)
        fresh_jobs = [_job_to_response(job) for job in jobs_res.scalars().all()]

    return {
        "status": "discovery_complete",
        "search_queries": state.get("search_queries"),
        "preferred_roles": queries,
        "preferred_countries": countries,
        "scraped_count": fresh_count,
        "relevant_count": relevant_count,
        "persisted_job_ids": persisted_ids,
        "duplicate_count": len(duplicate_jobs),
        "jobs": fresh_jobs,
    }


@router.post("/discover-and-apply", status_code=status.HTTP_200_OK)
async def discover_and_apply_for_user(
    payload: DiscoveryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger the end-to-end autonomous discovery and tailoring pipeline:
    1. Extract search queries / role from user parameters or resume
    2. Scrape matching jobs via Apify from the last 3 hours with no item cap
    3. Apollo enrichment branch across all scraped jobs
    4. Clean, filter, and persist all discovered jobs
    5. Launch batch-parallel tailoring pipeline in background:
       Processes all persisted jobs in parallel batches of up to 10
       (analyze_gaps -> tailor_resume -> render_pdf -> draft_email -> ATS/factual reviews -> persist)
    6. Return immediately with status and summary counts
    """
    # 1. Fetch user base resume
    if payload.resume_id:
        stmt = select(Resume).where(Resume.id == payload.resume_id, Resume.user_id == payload.user_id)
    else:
        stmt = (
            select(Resume)
            .where(Resume.user_id == payload.user_id, Resume.is_base == True)
            .order_by(Resume.version.desc())
        )
    res = await db.execute(stmt)
    resume = res.scalars().first()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No base resume found for user. Please upload a resume first.",
        )

    stmt_user = select(User).where(User.id == payload.user_id)
    user_res = await db.execute(stmt_user)
    active_user = user_res.scalar_one_or_none()

    # 2. Prepare discovery parameters
    explicit_role = payload.target_role.strip() if payload.target_role and payload.target_role.strip() else None
    preferred_roles = [role.strip() for role in (payload.preferred_roles or []) if role and role.strip()]
    preferred_roles = preferred_roles[:3]
    queries = preferred_roles or ([explicit_role] if explicit_role else None)
    countries = payload.countries if (payload.countries and len(payload.countries) > 0) else ["US"]

    state: GraphState = {
        "user_id": payload.user_id,
        "application_id": 0,
        "resume_text": resume.source_text,
        "search_queries": queries,
        "preferred_countries": countries,
        "max_results": None,
        "posted_within_hours": 3,
    }

    # Only invoke the planner if the user did not provide preferred roles.
    if not queries:
        state = plan_search_queries_node(state)

    # Pipeline execution:
    # 1. Scrape jobs
    state = scrape_jobs_node(state)

    # 2. Drop jobs already discovered for this user before we spend more time on them
    fresh_jobs, duplicate_jobs = await split_fresh_and_known_jobs(db, payload.user_id, state.get("scraped_jobs", []))
    state["scraped_jobs"] = fresh_jobs
    state["duplicate_jobs"] = duplicate_jobs
    state["duplicate_job_ids"] = []

    # 3. Apollo enrichment branch across only fresh jobs
    state = enrich_jobs_node(state)

    # 4. Clean and filter basic formatting
    state = filter_relevant_node(state)

    # 5. Persist all discovered jobs with deduplication
    state = persist_jobs_node(state)

    persisted_ids = state.get("persisted_job_ids", [])
    fresh_count = len(fresh_jobs)
    relevant_count = len(state.get("relevant_jobs", []))

    # 5. Launch batch-parallel tailoring for all discovered jobs in background
    if persisted_ids:
        background_tasks.add_task(
            run_batch_pipeline_background,
            job_ids=persisted_ids,
            user_id=payload.user_id,
            base_resume_text=resume.source_text,
            base_resume_html=resume.source_html or render_resume_html(resume.source_text, _resume_profile(active_user)),
            base_resume_id=resume.id,
            base_resume_version=resume.version,
            user_profile=_user_profile_payload(active_user),
        )

    batch_size = settings.batch_parallel_workers
    total_batches = (len(persisted_ids) + batch_size - 1) // batch_size if persisted_ids else 0

    return {
        "status": "discovery_and_tailoring_launched",
        "search_queries": state.get("search_queries"),
        "preferred_roles": queries,
        "preferred_countries": countries,
        "scraped_count": fresh_count,
        "persisted_job_ids": persisted_ids,
        "duplicate_count": len(duplicate_jobs),
        "batch_size": batch_size,
        "total_batches": total_batches,
        "message": f"Tailoring pipeline launched for {len(persisted_ids)} jobs in {total_batches} parallel batch(es) of up to {batch_size}.",
    }
