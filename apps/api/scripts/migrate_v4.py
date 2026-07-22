import logging
import os
import sys

# Ensure the root path is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration_v4")


def check_and_create_system_tables():
    """PHASE-4: Add system monitoring tables for scheduler stability."""
    with engine.connect() as conn:
        # 1. Create system_task_status table
        logger.info("Verifying system_task_status table...")
        conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS system_task_status (
                task_name VARCHAR(100) PRIMARY KEY,
                last_run_at TIMESTAMP WITH TIME ZONE,
                last_status VARCHAR(20),
                last_error TEXT,
                run_count INTEGER DEFAULT 0 NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """)
        )

        # Initialize rows for known tasks
        tasks = [
            "generate_daily_challenges",
            "send_daily_challenge_notifications",
            "send_deadline_reminders",
            "auto_lock_assignments",
            "maintain_streaks",
            "send_weekly_digest",
            "process_reengagement_lifecycle",
            "cleanup_stale_data",
        ]

        for task in tasks:
            conn.execute(
                text("""
                INSERT INTO system_task_status (task_name, last_status)
                VALUES (:task, 'pending')
                ON CONFLICT (task_name) DO NOTHING
            """),
                {"task": task},
            )

        conn.commit()
        logger.info("✅ Migration V4: System monitoring tables synchronized.")


if __name__ == "__main__":
    check_and_create_system_tables()
