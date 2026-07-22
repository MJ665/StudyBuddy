"""Durable background jobs.

KT ingestion and transactional email previously ran on FastAPI `BackgroundTasks`,
which are IN-PROCESS: a deploy, crash, or worker restart mid-flight dropped the
work silently with no record and no retry. For document ingestion that means a
member's contribution never reaches the knowledge graph and nobody is told.

Jobs are persisted here BEFORE the work starts, claimed with
`FOR UPDATE SKIP LOCKED` (so multiple app replicas can run workers without
double-processing), retried with exponential backoff, and recovered on startup if
a worker died holding a claim.
"""

import datetime

from database import Base
from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # terminal: retries exhausted


class BackgroundJob(Base):
    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=JobStatus.PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Backoff: a job is only eligible once `run_after` has passed.
    run_after: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    # Claim bookkeeping — lets a startup sweep reclaim jobs whose worker died.
    locked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # The claim query filters on exactly this shape.
        Index("ix_background_jobs_claim", "status", "run_after"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<BackgroundJob {self.id} {self.job_type} {self.status} attempts={self.attempts}>"
