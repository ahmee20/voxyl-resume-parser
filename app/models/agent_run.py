"""
app/models/agent_run.py — AgentRun table.

Records one execution of a single LangGraph node for a given application.
This table is what makes the observability story demoable outside LangSmith —
the /applications/{id} timeline view reads directly from here.

Every LangGraph node must write one row to this table (in addition to emitting
a LangSmith trace) before returning its updated state.
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_application_id_id_desc", "application_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The run ID returned by LangSmith — used to deep-link into the trace UI
    langsmith_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Name of the LangGraph node that produced this row (e.g. "analyze_gaps")
    node_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Serialized input/output state snapshots for the timeline view
    input: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    output: Mapped[dict | None] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Wall-clock latency of this node execution in milliseconds
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    application: Mapped["Application"] = relationship(  # noqa: F821
        "Application", back_populates="agent_runs"
    )

    def __repr__(self) -> str:
        return (
            f"<AgentRun id={self.id} application_id={self.application_id} "
            f"node={self.node_name!r} latency={self.latency_ms}ms>"
        )
