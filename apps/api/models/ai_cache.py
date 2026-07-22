import datetime
from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Integer, Text


class AICache(Base):
    """Caches Gemini AI responses keyed on question_id + user_answer to avoid redundant API calls."""

    __tablename__ = "ai_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_answer: Mapped[str] = mapped_column(Text, nullable=False)
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_response: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
