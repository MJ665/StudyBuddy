from typing import Any
import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


class Attempt(Base):
    __tablename__ = "attempts"
    __table_args__ = (
        Index("ix_attempts_bank_user", "bank_id", "user_id"),
        Index("ix_attempts_user_bank", "user_id", "bank_id"),
        Index("ix_attempts_bank_id", "bank_id"),
        Index("ix_attempts_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Denormalized tenant key. Isolation previously depended on walking
    # user -> group -> batch -> vertical -> department -> organization, which no
    # query actually did, so cross-tenant reads were possible. Nullable because
    # legacy rows may predate attribution; scoping helpers treat NULL as "deny".
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_banks.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    is_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Manual verification (NEW)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Daily challenge tracking (NEW)
    is_daily_challenge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    time_taken: Mapped[int | None] = mapped_column(Integer, nullable=True)
    descriptive_answers: Mapped[dict | list | Any | None] = mapped_column(JSONB, nullable=True)


    attempted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    bank = relationship(
        "QuestionBank", foreign_keys=[bank_id], back_populates="attempts", lazy="joined"
    )
    user = relationship("User", foreign_keys=[user_id], back_populates="attempts")
    mentor_comments = relationship("MentorComment", back_populates="attempt", cascade="all, delete-orphan")


class CodingAttempt(Base):
    """Stores coding practice module submissions with AI evaluation."""

    __tablename__ = "coding_attempts"
    __table_args__ = (
        Index("ix_coding_attempts_question_user", "coding_question_id", "user_id"),
        Index("ix_coding_attempts_user_question", "user_id", "coding_question_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Learner data: organization-scoped only. A sibling business unit may reuse the
    # question but must never see this unit's submissions.
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    coding_question_id = Column(
        Integer, ForeignKey("coding_questions.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    submitted_code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(50), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, default=0)  # 0-100

    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    rubric_json: Mapped[dict | list | Any | None] = mapped_column(JSONB, nullable=True)

    time_spent_seconds: Mapped[int | None] = mapped_column(Integer, default=0)
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, default=0)
    hints_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # New V3 Meta Fields
    leaderboard_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    rank_computation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overall_result: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "correct", "wrong", "partial"
    time_taken_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Manual Mentor Review
    mentor_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mentor_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool | None] = mapped_column(Boolean, default=False)

    attempted_at = Column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    # Relationships
    user = relationship("User", back_populates="coding_attempts")
    coding_question = relationship("CodingQuestion", back_populates="coding_attempts")
    mentor_comments = relationship(
        "MentorComment", back_populates="coding_attempt", cascade="all, delete-orphan"
    )


class CodingHint(Base):
    """Tracks hint history for a user on a specific question."""

    __tablename__ = "coding_hints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coding_question_id: Mapped[int] = mapped_column(Integer, ForeignKey("coding_questions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    hint_level: Mapped[int] = mapped_column(Integer, default=1)
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )