import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


class Course(Base):
    """Fully dynamic — no hardcoded course names."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # e.g. "Linux", "Bash", "Python", "Docker", "Terraform"
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)  # for frontend icon display
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    vertical_courses = relationship("VerticalCourse", back_populates="course")
    question_banks = relationship("QuestionBank", back_populates="course")


class VerticalCourse(Base):
    """Join table: which courses are available to which vertical."""

    __tablename__ = "vertical_courses"
    __table_args__ = (
        UniqueConstraint("vertical_id", "course_id", name="uq_vertical_course"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vertical_id: Mapped[int] = mapped_column(Integer, ForeignKey("verticals.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    vertical = relationship("Vertical", back_populates="vertical_courses")
    course = relationship("Course", back_populates="vertical_courses")


class GroupCourseSubscription(Base):
    """
    FUNC-008: Group-level Course Entitlement.
    Ensures cohorts only see courses mandated by their specific L&D roadmap.
    """

    __tablename__ = "group_course_subscriptions"
    __table_args__ = (
        UniqueConstraint("group_id", "course_id", name="uq_group_course"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    course_id: Mapped[int] = mapped_column(Integer, ForeignKey("courses.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)