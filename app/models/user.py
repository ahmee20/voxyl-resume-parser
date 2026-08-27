"""
app/models/user.py — User table.

Stores the Google identity and OAuth credentials for each user.
The oauth_refresh_token column stores the Fernet-encrypted token — it is
NEVER stored or logged in plaintext anywhere in the application.
"""

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SendMode(str, enum.Enum):
    manual = "manual"
    auto = "auto"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Google OpenID Connect subject — globally unique per Google account
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    preferred_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    preferred_roles: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    preferred_countries: Mapped[list[str] | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    github_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    # Encrypted Fernet token — decrypted only when a Gmail/Drive API call is needed
    oauth_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Default to manual; auto is an explicit opt-in (guardrail §9)
    send_mode: Mapped[SendMode] = mapped_column(
        Enum(SendMode, name="send_mode_enum"),
        nullable=False,
        default=SendMode.manual,
        server_default="manual",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    resumes: Mapped[list["Resume"]] = relationship(  # noqa: F821
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job", back_populates="user", cascade="all, delete-orphan"
    )
    applications: Mapped[list["Application"]] = relationship(  # noqa: F821
        "Application", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"

    @property
    def has_google_token(self) -> bool:
        return bool(self.oauth_refresh_token)
