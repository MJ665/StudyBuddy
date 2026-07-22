from typing import Any
import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)


class DailyChallenge(Base):
    __tablename__ = "daily_challenges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    challenge_date: Mapped[Any] = mapped_column(Date, nullable=False)
    selection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # e.g. "Weakness in: bash_arrays, pipes"
    is_mentor_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "group_id", "challenge_date", name="uq_daily_challenge_group_date"
        ),
    )
