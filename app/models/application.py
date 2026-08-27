"""
app/models/application.py — Application / User-Job record table.

Tracks each job found and applied for a user:
- applied_status: 'no' (found), 'yes' (auto-applied via Gmail), 'manual' (tailored for manual submission)
- Tailored resume HTML, rendered PDF URL, ATS score, and gap analysis
- Links user to job and tracks execution lifecycle.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AppliedStatus(str, enum.Enum):
    no = "no"          # Found / Discovered, not yet applied
    yes = "yes"        # Automatically applied & emailed via Gmail
    manual = "manual"  # Tailored resume & cold email generated for manual apply


class ApplicationMode(str, enum.Enum):
    auto = "auto"
    manual = "manual"


class ApplicationStatus(str, enum.Enum):
    discovered = "discovered"
    tailoring = "tailoring"
    pending_approval = "pending_approval"
    approved = "approved"
    sent = "sent"
    saved = "saved"
    failed = "failed"


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_user_id_id_desc", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # FK to the tailored resume used for this application
    resume_id: Mapped[int | None] = mapped_column(
        ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )

    # Applied status: 'no' | 'yes' | 'manual'
    applied_status: Mapped[AppliedStatus] = mapped_column(
        Enum(AppliedStatus, name="applied_status_enum"),
        nullable=False,
        default=AppliedStatus.no,
        server_default="no",
    )

    mode: Mapped[ApplicationMode] = mapped_column(
        Enum(ApplicationMode, name="application_mode_enum"),
        nullable=False,
        default=ApplicationMode.manual,
        server_default="manual",
    )
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, name="application_status_enum"),
        nullable=False,
        default=ApplicationStatus.discovered,
        server_default="discovered",
    )

    # Tailored assets directly associated with this user job
    tailored_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    ats_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gap_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Google Drive folder URL for the uploaded resume (+ email.txt in auto mode)
    drive_folder_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Drafted outreach email body
    email_draft: Mapped[str | None] = mapped_column(Text, nullable=True)

    # How many times the review loop has run for this application (capped at 3)
    approval_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="applications")  # noqa: F821
    job: Mapped["Job"] = relationship("Job", back_populates="applications")  # noqa: F821
    resume: Mapped["Resume"] = relationship("Resume", back_populates="applications")  # noqa: F821
    agent_runs: Mapped[list["AgentRun"]] = relationship(  # noqa: F821
        "AgentRun", back_populates="application", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Application id={self.id} user_id={self.user_id} "
            f"job_id={self.job_id} applied={self.applied_status.value!r}>"
        )
