"""Tasks package - Scheduled background jobs and utilities."""

from ._shared import record_task_run
from .challenges import generate_daily_challenges, send_daily_challenge_notifications
from .notifications import (
    maintain_streaks,
    notify_mentors_pending_reviews,
    process_reengagement_lifecycle,
    send_deadline_reminders,
    send_weekly_digest,
)
from .maintenance import (
    auto_lock_assignments,
    cleanup_stale_data,
    fix_orphaned_records,
    merge_duplicate_users,
    prune_orphaned_s3_objects,
)
from .intel import calculate_global_intel, sync_s3_resources

__all__ = [
    # Shared
    "record_task_run",
    # Challenges
    "generate_daily_challenges",
    "send_daily_challenge_notifications",
    # Notifications
    "send_deadline_reminders",
    "maintain_streaks",
    "send_weekly_digest",
    "process_reengagement_lifecycle",
    "notify_mentors_pending_reviews",
    # Maintenance
    "auto_lock_assignments",
    "merge_duplicate_users",
    "fix_orphaned_records",
    "cleanup_stale_data",
    "prune_orphaned_s3_objects",
    # Intel
    "calculate_global_intel",
    "sync_s3_resources",
]
