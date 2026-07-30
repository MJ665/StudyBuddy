"""Proctored Exam service — a formal-assessment layer on top of the shared
Question engine. An Exam is a fixed set of questions with an overall timer, a
single secure attempt, server-side shuffling, and proctoring (tab/copy/focus
flags for Standard; + webcam/screen snapshots for Advanced).
"""
import datetime

from database import Base
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    # Content is shared across the business units of one customer, so it is
    # scoped to the SuperOrganization rather than the Organization.
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("question_banks.id"), nullable=True)
    question_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=[])
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)  # overall exam timer
    passing_score: Mapped[int] = mapped_column(Integer, default=40, nullable=False)  # percent
    max_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # 1 = single secure attempt
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    proctoring_mode: Mapped[str] = mapped_column(String(12), default="standard", nullable=False)  # none|standard|advanced
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Internal users invited by email when the exam is published. The invite email
    # carries a direct portal link; each becomes an in-app notification too.
    recipient_emails: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attempts = relationship("ExamAttempt", back_populates="exam", cascade="all, delete-orphan")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Denormalized tenant key. Isolation previously depended on walking
    # user -> group -> batch -> vertical -> department -> organization, which no
    # query actually did, so cross-tenant reads were possible. Nullable because
    # legacy rows may predate attribution; scoping helpers treat NULL as "deny".
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    exam_id: Mapped[int] = mapped_column(Integer, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(15), default="in_progress", nullable=False)  # in_progress|submitted|expired
    shuffle_seed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # deterministic server-side shuffle
    answers: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total: Mapped[float | None] = mapped_column(Float, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    flags_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # proctor flags
    started_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    exam = relationship("Exam", back_populates="attempts")
    proctor_events = relationship("ProctorEvent", back_populates="attempt", cascade="all, delete-orphan")


class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    exam_attempt_id: Mapped[int] = mapped_column(Integer, ForeignKey("exam_attempts.id", ondelete="CASCADE"), nullable=False, index=True)
    # tab_switch | copy | paste | focus_loss | fullscreen_exit | webcam_snapshot | screen_snapshot
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # S3 URL or inline data-URL for webcam/screen snapshots
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    attempt = relationship("ExamAttempt", back_populates="proctor_events")
