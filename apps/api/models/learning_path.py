import datetime

from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship


class UserLearningPath(Base):
    """
    STRAT-AI-ROADMAP (Section 5.5): Stores AI-generated learning paths for users.
    Ensures users don't have to re-generate paths every time they visit the dashboard.
    """

    __tablename__ = "user_learning_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    topic: Mapped[str] = mapped_column(String(255), nullable=False)

    # AI-generated content (JSON string or formatted Markdown)
    roadmap_json: Mapped[str] = mapped_column(Text, nullable=False)

    # Metadata
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="learning_paths")
