import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notifications_user_unread", "user_id", "is_read"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)

    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # "new_assignment" | "deadline_reminder" | "mentor_comment" |
    # "question_fixed" | "daily_challenge" | "new_bank"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Deeplink: where to navigate when clicked
    link_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # "bank" | "assignment" | "attempt" | "daily_challenge"
    link_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
