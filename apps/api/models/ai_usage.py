import datetime

from database import Base
from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column


class AIUsage(Base):
    """One row per AI (Gemini) call — powers the Platform Admin cost dashboard.

    Recorded best-effort by services/ai_meter.py; a failure to record never
    breaks the underlying AI call. Tagged by organization + feature so the
    /platform view can break cost down per tenant and per capability.
    """

    __tablename__ = "ai_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # e.g. "quiz_generation", "descriptive_grading", "code_evaluation",
    # "kt_chat", "kt_embedding", "kt_entity_extraction".
    feature: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    est_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
