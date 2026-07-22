from typing import Any
import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship


class CodingQuestion(Base):
    __tablename__ = "coding_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Authored content: shared across the customer's business units, like question banks.
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)  # markdown
    language: Mapped[str] = mapped_column(String(30), nullable=False)
    initial_code: Mapped[str | None] = mapped_column(Text, nullable=True)  # Starter template (Legacy)
    initial_code_s3_path: Mapped[str | None] = mapped_column(String(500), nullable=True)  # S3 Path

    # Stored server-side, never exposed to students via API
    expected_approach: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_solution: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_criteria: Mapped[Any] = mapped_column(ARRAY(String), nullable=False)

    concept_tags: Mapped[Any | None] = mapped_column(ARRAY(String), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(20), default="Medium", nullable=False)

    # Pre-written hints (used as fallback if Gemini is unavailable)
    hint_1: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_2: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_3: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_hints_allowed: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Assignment control
    is_compulsory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_org_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    test_cases = relationship(
        "CodingTestCase", backref="question", cascade="all, delete-orphan"
    )
    assignments = relationship("Assignment", back_populates="coding_question")
    coding_attempts = relationship(
        "CodingAttempt", back_populates="coding_question", cascade="all, delete-orphan"
    )




class CodingHintCache(Base):
    __tablename__ = "coding_hint_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coding_question_id: Mapped[int] = mapped_column(Integer, ForeignKey("coding_questions.id", ondelete="CASCADE"), nullable=False)
    attempt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("coding_attempts.id", ondelete="CASCADE"), nullable=True)
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

class CodingTestCase(Base):
    __tablename__ = "coding_test_cases"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    coding_question_id: Mapped[int] = mapped_column(Integer, ForeignKey("coding_questions.id", ondelete="CASCADE"), nullable=False)
    input_data: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)