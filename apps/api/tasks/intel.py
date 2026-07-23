import logging
from typing import Optional

from database import SessionLocal
from sqlalchemy.orm import Session

from ._shared import record_task_run

logger = logging.getLogger(__name__)


def calculate_global_intel(db: Optional[Session] = None):
    """PHASE-4: Strategic Platform Intelligence Synthesis."""
    from services.performance_engine import performance_engine

    close_db = False
    if not db:
        db = SessionLocal()
        close_db = True

    try:
        import asyncio

        try:
            # Check if there is an existing running loop
            asyncio.get_running_loop()
            # If so, create a task and wait for it if possible,
            # but since this is a sync function called by a thread or another worker,
            # we should use run_coroutine_threadsafe or just check if it's already running.
            # In APScheduler AsyncIOScheduler, this runs in the same loop.
            asyncio.ensure_future(
                performance_engine.get_global_vectors(db, refresh=True)
            )
        except RuntimeError:
            # No running loop, use asyncio.run
            asyncio.run(performance_engine.get_global_vectors(db, refresh=True))

        record_task_run(db, "calculate_global_intel", "success")
        logger.info("✅ Global Intelligence Vectors synchronized.")
    except Exception as e:
        logger.error(f"Global Intel failure: {e}")
        record_task_run(db, "calculate_global_intel", "failure", str(e))
    finally:
        if close_db:
            db.close()


def sync_s3_resources(db: Optional[Session] = None):
    """PHASE-4: Alias for S3 Orphaned Object Pruning."""
    from .maintenance import prune_orphaned_s3_objects

    prune_orphaned_s3_objects()
    # Prune internally uses record_task_run for "prune_orphaned_s3_objects"
    # but we record it for "sync_s3_resources" as well for dashboard parity
    if not db:
        db = SessionLocal()
        record_task_run(db, "sync_s3_resources", "success")
        db.close()
    else:
        record_task_run(db, "sync_s3_resources", "success")
