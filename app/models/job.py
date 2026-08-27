"""
app/models/job.py — Job table.

Stores scraped job listings.  The `url` column is the primary dedup key —
a UNIQUE constraint at the DB level ensures the cron job cannot insert
duplicates even under concurrent runs.
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Job(Base):
    __tablename__ = "jobs"

    # User-scoped unique constraint so each user has their own deduped listings
    __table_args__ = (
        UniqueConstraint("user_id", "url", name="uq_jobs_user_url"),
        Index("ix_jobs_user_id_id_desc", "user_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Owner of this discovered job listing
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, default=1, server_default="1"
    )

    # Where this job came from (currently always "apify")
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="apify")

    # The ID assigned by the scraping source (Apify run ID / actor result ID)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Primary dedup key (scoped per user via __table_args__)
    url: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Full job description text
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Recruiter contact obtained from Apify or Apollo enrichment
    recruiter_email: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # When the job was originally posted (from scrape data — not always reliable)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Full Apollo.io enrichment payload stored as JSONB on Postgres / JSON on SQLite
    apollo_enrichment: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Candidate requirement eligibility evaluation
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    match_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    filter_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="jobs")  # noqa: F821
    applications: Mapped[list["Application"]] = relationship(  # noqa: F821
        "Application", back_populates="job", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} company={self.company!r} title={self.title!r}>"
