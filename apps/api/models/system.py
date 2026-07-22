import datetime

from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Integer, String, Text


class SystemTaskStatus(Base):
    """
    Tracks the execution of background/scheduled tasks.
    Enables administrative visibility into task performance and failures.
    """

    __tablename__ = "system_task_status"

    task_name: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_run_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "success", "failure"
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)