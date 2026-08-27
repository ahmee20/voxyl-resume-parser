"""
app/api/resumes.py — Resume upload and management endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.database import get_db
from app.models.resume import Resume
from app.models.user import User
from app.api.auth import get_current_user
from app.services.resume_parser import extract_text
from app.agent.nodes.extract_resume import generate_resume_html_skeleton
from app.services.resume_template import ResumeProfile, render_resume_html

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/resumes", tags=["resumes"])


class ResumeResponse(BaseModel):
    id: int
    user_id: int
    version: int
    filename: Optional[str] = None
    source_text: str
    source_html: Optional[str] = None
    is_base: bool

    model_config = ConfigDict(from_attributes=True)


@router.post("/upload", response_model=ResumeResponse, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    request: Request,
    user_id: Optional[int] = Query(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a resume in PDF or DOCX format.
    Extracts text, generates an HTML skeleton via LLM, and persists as the base resume.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename cannot be empty.",
        )

    # Validate file format before touching the database.
    lower_filename = file.filename.lower()
    if not (lower_filename.endswith(".pdf") or lower_filename.endswith(".docx")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf and .docx file formats are supported.",
        )

    # 1. Resolve active user_id from query, session, or database
    resolved_user_id = user_id or request.session.get("user_id")

    try:
        if not resolved_user_id:
            stmt = select(User).order_by(User.id.asc())
            res = await db.execute(stmt)
            first_user = res.scalars().first()

            if first_user:
                resolved_user_id = first_user.id
            else:
                new_user = User(
                    google_sub="local-default-sub",
                    email="user@autopilot.ai",
                    name="Autopilot Candidate",
                )
                db.add(new_user)
                await db.commit()
                await db.refresh(new_user)
                resolved_user_id = new_user.id

        stmt_user = select(User).where(User.id == resolved_user_id)
        res_user = await db.execute(stmt_user)
        active_user = res_user.scalar_one_or_none()

        if not active_user:
            request.session.clear()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your login session points to a user that no longer exists. Please sign in again.",
            )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        log.error("user_resolution_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database user session error: {str(exc)}",
        )

    # Read bytes
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Extract plain text
    try:
        raw_text = extract_text(content, file.filename)
    except Exception as exc:
        log.error("resume_text_extraction_error", filename=file.filename, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to parse resume text: {str(exc)}",
        )

    if not raw_text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any readable text from the uploaded document.",
        )

    # Generate a semantic, print-friendly HTML skeleton.
    try:
        html_skeleton = generate_resume_html_skeleton(
            raw_text,
            ResumeProfile(
                name=active_user.preferred_name or active_user.name,
                email=active_user.email,
                github_url=active_user.github_url,
                portfolio_url=active_user.portfolio_url,
                linkedin_url=active_user.linkedin_url,
            ),
        )
    except Exception as exc:
        log.warning("resume_skeleton_generation_fallback", error=str(exc))
        html_skeleton = render_resume_html(raw_text)

    # Save to database
    try:
        stmt = (
            select(Resume)
            .where(Resume.user_id == resolved_user_id)
            .order_by(Resume.version.desc())
        )
        result = await db.execute(stmt)
        latest_resume = result.scalars().first()
        next_version = (latest_resume.version + 1) if latest_resume else 1

        resume = Resume(
            user_id=resolved_user_id,
            version=next_version,
            filename=file.filename,
            source_text=raw_text,
            source_html=html_skeleton,
            is_base=True,
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)

        log.info(
            "resume_upload_success",
            resume_id=resume.id,
            user_id=resolved_user_id,
            version=resume.version,
            chars=len(raw_text),
        )
        return resume
    except Exception as exc:
        log.error("resume_db_save_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database save error: {str(exc)}",
        )


@router.get("/latest", response_model=Optional[ResumeResponse])
async def get_latest_resume(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the latest saved base resume for the logged-in user."""
    stmt = (
        select(Resume)
        .where(Resume.user_id == current_user.id, Resume.is_base == True)
        .order_by(Resume.created_at.desc(), Resume.version.desc())
    )
    result = await db.execute(stmt)
    resume = result.scalars().first()
    return resume


@router.get("/{resume_id}", response_model=ResumeResponse)
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific resume version by ID."""
    stmt = select(Resume).where(Resume.id == resume_id)
    result = await db.execute(stmt)
    resume = result.scalar_one_or_none()

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resume {resume_id} not found.",
        )

    return resume
