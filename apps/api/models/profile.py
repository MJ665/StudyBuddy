import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship


class ProfileComment(Base):
    """PED-302: Social feedback loop for public profiles."""

    __tablename__ = "profile_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    target_user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    target_user = relationship(
        "User", foreign_keys=[target_user_id], backref="received_comments"
    )
    author = relationship("User", foreign_keys=[author_id], backref="authored_comments")
