import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bank_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("question_banks.id"), nullable=True)
    coding_question_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("coding_questions.id"), nullable=True)
    created_by_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # User id of the creator — enables per-creator ownership checks on update.
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)

    assignment_type: Mapped[str] = mapped_column(String(20), default="quiz", nullable=False)  # quiz, coding
    visibility_scope: Mapped[str] = mapped_column(String(20), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # "group" | "batch" | "vertical"
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)

    due_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    passing_score_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock_after_due: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    max_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_compulsory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    bank = relationship("QuestionBank")
    coding_question = relationship("CodingQuestion")
    completions = relationship("AssignmentCompletion", back_populates="assignment")


class AssignmentCompletion(Base):
    __tablename__ = "assignment_completions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(Integer, ForeignKey("assignments.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    assignment = relationship("Assignment", back_populates="completions")