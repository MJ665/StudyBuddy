from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship


class QuestionBank(Base):
    __tablename__ = "question_banks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Denormalized tenant key. Isolation previously depended on walking
    # user -> group -> batch -> vertical -> department -> organization, which no
    # query actually did, so cross-tenant reads were possible. Nullable because
    # legacy rows may predate attribution; scoping helpers treat NULL as "deny".
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    # Content is shared across the business units of one customer, so it is
    # scoped to the SuperOrganization rather than the Organization.
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    course_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("courses.id"), nullable=True)
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    # FK to users.id — replaces the old created_by text field

    sprint_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    chapter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    difficulty: Mapped[str] = mapped_column(String(50), default="Medium", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quick_references: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)

    # UI Customization (NEW)
    icon_slug: Mapped[str] = mapped_column(String(50), default="folder", nullable=False)
    # e.g. "python", "database", "linux", "cloud"

    visibility_scope: Mapped[str] = mapped_column(String(20), default="group-private", nullable=False)
    # "group-private", "vertical", "org-public"
    subscriber_groups: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)  # List of group_ids

    # Bank type (NEW)
    bank_type: Mapped[str] = mapped_column(String(20), default="practice", nullable=False)
    # "practice" | "official"

    # Quiz settings
    time_per_question: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_questions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    show_timer: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    shuffle: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    allow_descriptive: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Attempt policy (NEW)
    max_attempts_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_total_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retake_policy: Mapped[str] = mapped_column(String(20), default="all_count", nullable=False)
    # "all_count" | "best_counts" | "last_counts"
    lock_after_due: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Sharing (NEW)
    is_org_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_daily_challenge: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cloned_from_bank_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("question_banks.id"), nullable=True)

    questions = relationship("Question", back_populates="bank", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="bank", cascade="all, delete-orphan")
    course = relationship("Course", back_populates="question_banks")

    __table_args__ = (
        Index("ix_question_banks_chapter", "chapter"),
        Index("ix_question_banks_course_id", "course_id"),
    )

class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Denormalized tenant key. Isolation previously depended on walking
    # user -> group -> batch -> vertical -> department -> organization, which no
    # query actually did, so cross-tenant reads were possible. Nullable because
    # legacy rows may predate attribution; scoping helpers treat NULL as "deny".
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    # Content is shared across the business units of one customer, so it is
    # scoped to the SuperOrganization rather than the Organization.
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    bank_id: Mapped[int] = mapped_column(Integer, ForeignKey("question_banks.id", ondelete="CASCADE"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    user_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    has_code: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    code_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    concept_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # ── Multi-type assessment engine ─────────────────────────────────────────
    # mcq_single | mcq_multi | true_false | short_answer | essay
    # (designed to extend to numeric/fill_blank/match). Back-compat: legacy rows
    # default to mcq_single and keep using `options`/`answer`.
    question_type: Mapped[str] = mapped_column(String(20), default="mcq_single", nullable=False)
    correct_options: Mapped[list[int] | None] = mapped_column(ARRAY(Integer), nullable=True)  # multi-select correct indices
    model_answer: Mapped[str | None] = mapped_column(Text, nullable=True)  # reference answer for AI free-text grading
    rubric: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)  # grading criteria for free-text
    content_format: Mapped[str] = mapped_column(String(12), default="text", nullable=False)  # text | markdown | latex
    media_urls: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)  # images in question/options
    points: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # weight

    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    bank = relationship("QuestionBank", back_populates="questions")
    reports = relationship(
        "QuestionReport", back_populates="question", cascade="all, delete-orphan"
    )
    discussions = relationship("QuestionDiscussion", back_populates="question")

    __table_args__ = (Index("ix_questions_bank_id", "bank_id"),)
