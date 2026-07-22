import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship


class MentorComment(Base):
    """PED-301: Unified feedback artifact for mentor-student engagement."""

    __tablename__ = "mentor_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("attempts.id"), nullable=True)
    coding_attempt_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("coding_attempts.id"), nullable=True)
    mentor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(50), default="student_only", nullable=False)  # student_only | group

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    # Relationships
    attempt = relationship("Attempt", back_populates="mentor_comments")
    coding_attempt = relationship("CodingAttempt", back_populates="mentor_comments")
    mentor = relationship("User")
