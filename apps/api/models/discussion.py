import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship


class QuestionDiscussion(Base):
    __tablename__ = "question_discussions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("question_discussions.id", ondelete="CASCADE"),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)  # max 2000 chars enforced in schema
    upvotes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Users who upvoted — makes the thumbs-up a toggle (one vote per user).
    voter_ids: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False, default=list)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), onupdate="now()", nullable=True)

    question = relationship("Question", back_populates="discussions")
    # Self-referential thread tree. `remote_side` belongs on the MANY-TO-ONE side
    # (the parent); putting it on `replies` made that attribute resolve to the
    # parent row instead of the child collection, so `t.replies` returned None on
    # root threads and reply counts were always 0.
    parent = relationship(
        "QuestionDiscussion",
        remote_side=[id],
        back_populates="replies",
    )
    replies = relationship(
        "QuestionDiscussion",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
