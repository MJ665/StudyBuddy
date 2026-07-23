import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import models
from database import SessionLocal
from sqlalchemy import func
from sqlalchemy.orm import Session
from config import settings
from services.s3_service import get_s3_client

logger = logging.getLogger(__name__)


def record_task_run(db: Session, task_name: str, status: str, error: str | None = None):
    """Updates the system_task_status table with the latest execution telemetry."""
    try:
        task = (
            db.query(models.SystemTaskStatus)
            .filter(models.SystemTaskStatus.task_name == task_name)
            .first()
        )
        if not task:
            task = models.SystemTaskStatus(task_name=task_name)
            db.add(task)

        task.last_run_at = datetime.now(timezone.utc)
        task.last_status = status
        task.last_error = error
        task.run_count += 1
        db.commit()
    except Exception as e:
        logger.error(f"Failed to record task run for {task_name}: {e}")
