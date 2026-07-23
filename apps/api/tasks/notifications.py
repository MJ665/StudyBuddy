import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import models
from database import SessionLocal
from sqlalchemy import func
from sqlalchemy.orm import Session

from ._shared import record_task_run

logger = logging.getLogger(__name__)


def send_deadline_reminders():
    """Runs at 9 AM IST. Sends reminders for assignments due within 24 hours."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=24)

        upcoming = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.is_active.is_(True),
                models.Assignment.due_date >= now,
                models.Assignment.due_date <= window_end,
            )
            .all()
        )

        sent = 0
        for assignment in upcoming:
            bank = (
                db.query(models.QuestionBank)
                .filter(models.QuestionBank.id == assignment.bank_id)
                .first()
            )
            bank_name = bank.name if bank else f"Assignment #{assignment.id}"

            # Get target users
            users_to_remind = []
            if assignment.target_type == "group":
                users_to_remind = (
                    db.query(models.User)
                    .filter(
                        models.User.group_id == assignment.target_id,
                        models.User.is_active.is_(True),
                    )
                    .all()
                )
            elif assignment.target_type == "batch":
                groups = (
                    db.query(models.Group)
                    .filter(models.Group.batch_id == assignment.target_id)
                    .all()
                )
                for g in groups:
                    users_to_remind.extend(
                        db.query(models.User)
                        .filter(models.User.group_id == g.id, models.User.is_active.is_(True))
                        .all()
                    )

            # Only remind users who haven't passed
            for user in users_to_remind:
                completion = (
                    db.query(models.AssignmentCompletion)
                    .filter(
                        models.AssignmentCompletion.assignment_id == assignment.id,
                        models.AssignmentCompletion.user_id == user.id,
                    )
                    .first()
                )

                if not completion or completion.status not in ("passed", "completed"):
                    due_str = (
                        assignment.due_date.strftime("%I:%M %p UTC")
                        if assignment.due_date
                        else ""
                    )
                    notif = models.Notification(
                        user_id=user.id,
                        notification_type="deadline_reminder",
                        title=f"⏰ Due soon: {bank_name}",
                        body=f"This assignment is due at {due_str}. Complete it now!",
                        link_type="bank",
                        link_id=assignment.bank_id,
                    )
                    db.add(notif)
                    sent += 1

                    # 4.3 FIX: Send email as well
                    if user.email:
                        from services.email_service import send_deadline_reminder_email

                        try:
                            send_deadline_reminder_email(
                                user.email, user.full_name, bank_name, due_str
                            )
                        except Exception as e:
                            logger.warning(
                                f"Email reminder failed for {user.email}: {e}"
                            )

        db.commit()
        logger.info(
            f"Deadline reminders sent: {sent} for {len(upcoming)} upcoming assignments"
        )
        record_task_run(db, "send_deadline_reminders", "success")

    except Exception as e:
        logger.error(f"Error sending deadline reminders: {e}", exc_info=True)
        record_task_run(db, "send_deadline_reminders", "failure", str(e))
        db.rollback()
    finally:
        db.close()


def maintain_streaks():
    """
    SECTION 14.1: Automated Streak Maintenance and Grace Period.
    Recalculates streaks from attempt history with a 48-hour inactivity threshold.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        today = now.date()

        # Process all active users to ensure resets happen correctly
        users = db.query(models.User).filter(models.User.is_active.is_(True)).all()
        updated = 0

        for user in users:
            # ── 1. Grace Period Check (SEC-14.1) ──────────────────────────────
            last_active = user.last_active_date
            if last_active:
                # Ensure timezone awareness
                la_utc = (
                    last_active.replace(tzinfo=timezone.utc)
                    if last_active.tzinfo is None
                    else last_active
                )
                inactivity_seconds = (now - la_utc).total_seconds()

                # If inactive for > 48 hours, reset streak immediately
                if inactivity_seconds > 172800:
                    if user.streak_count != 0:
                        user.streak_count = 0
                        updated += 1
                    continue
            else:
                if user.streak_count != 0:
                    user.streak_count = 0
                    updated += 1
                continue

            # ── 2. Real-time Streak Recalculation ───────────────────────────
            # Fetch all distinct active dates for this user
            quiz_days = {
                row[0]
                for row in db.query(func.date(models.Attempt.attempted_at))
                .filter(models.Attempt.user_id == user.id)
                .distinct()
                .all()
                if row[0]
            }
            code_days = {
                row[0]
                for row in db.query(func.date(models.CodingAttempt.attempted_at))
                .filter(models.CodingAttempt.user_id == user.id)
                .distinct()
                .all()
                if row[0]
            }
            active_days = quiz_days | code_days

            if not active_days:
                user.streak_count = 0
                continue

            # Calculate streak backwards from the most recent active day
            # (which we already know is within the last 48 hours)
            sorted_days = sorted(list(active_days), reverse=True)
            last_day = sorted_days[0]

            streak = 0
            check = last_day
            while check in active_days:
                streak += 1
                check -= timedelta(days=1)

            if user.streak_count != streak:
                user.streak_count = streak
                updated += 1

        db.commit()
        logger.info(f"Streak maintenance complete: {updated} users updated.")
        record_task_run(db, "maintain_streaks", "success")
    except Exception as e:
        logger.error(f"Streak maintenance error: {e}", exc_info=True)
        record_task_run(db, "maintain_streaks", "failure", str(e))
        db.rollback()
    finally:
        db.close()


def send_weekly_digest():
    """
    Runs every Sunday at 7 PM IST.
    Sends personalized weekly learning summary emails to all active users.
    """
    db = SessionLocal()
    try:
        from services.email_service import send_weekly_digest_email

        now = date.today()
        week_start = now - timedelta(days=7)

        active_users = db.query(models.User).filter(models.User.is_active.is_(True)).all()
        sent = 0

        for user in active_users:
            if not user.email:
                continue

            # Gather this week's stats
            week_quiz = (
                db.query(models.Attempt)
                .filter(
                    models.Attempt.user_id == user.id,
                    func.date(models.Attempt.attempted_at) >= week_start,
                )
                .all()
            )

            week_code = (
                db.query(models.CodingAttempt)
                .filter(
                    models.CodingAttempt.user_id == user.id,
                    func.date(models.CodingAttempt.attempted_at) >= week_start,
                )
                .all()
            )

            total_attempts = len(week_quiz) + len(week_code)
            if total_attempts == 0:
                continue  # Don't spam inactive users

            avg_accuracy = 0
            if week_quiz:
                total_score = sum(a.score for a in week_quiz)
                total_q = sum(a.total for a in week_quiz)
                avg_accuracy = (
                    round((total_score / total_q * 100), 1) if total_q > 0 else 0
                )

            topics_covered = len(set(a.bank_id for a in week_quiz))

            stats = {
                "attempts": total_attempts,
                "avg_accuracy": avg_accuracy,
                "topics": topics_covered,
                "streak": getattr(user, "streak_count", 0) or 0,
            }

            try:
                send_weekly_digest_email(user.email, user.full_name, stats)
                sent += 1
            except Exception as e:
                logger.warning(f"Weekly digest failed for {user.email}: {e}")

        logger.info(f"Weekly digest sent to {sent} users.")
        record_task_run(db, "send_weekly_digest", "success")
    except Exception as e:
        logger.error(f"Weekly digest error: {e}", exc_info=True)
        record_task_run(db, "send_weekly_digest", "failure", str(e))
    finally:
        db.close()


def process_reengagement_lifecycle():
    """
    STRAT-REL-01: Dormant User Recovery.
    Runs daily. Identifies users inactive for 3, 7, or 14 days and triggers
    context-aware re-engagement emails.
    """
    db = SessionLocal()
    try:
        from services.email_service import send_reengagement_email

        today = date.today()

        # Load all active users once
        active_users = (
            db.query(models.User)
            .filter(models.User.is_active.is_(True), models.User.email is not None)
            .all()
        )

        if not active_users:
            record_task_run(db, "process_reengagement_lifecycle", "success")
            return

        user_ids = [u.id for u in active_users]

        # Bulk fetch max attempt dates
        quiz_max_dates = (
            db.query(models.Attempt.user_id, func.max(models.Attempt.attempted_at))
            .filter(models.Attempt.user_id.in_(user_ids))
            .group_by(models.Attempt.user_id)
            .all()
        )

        code_max_dates = (
            db.query(
                models.CodingAttempt.user_id,
                func.max(models.CodingAttempt.attempted_at),
            )
            .filter(models.CodingAttempt.user_id.in_(user_ids))
            .group_by(models.CodingAttempt.user_id)
            .all()
        )

        quiz_map = {row[0]: row[1] for row in quiz_max_dates}
        code_map = {row[0]: row[1] for row in code_max_dates}

        # Check users inactive for specific thresholds
        thresholds = [3, 7, 14]
        for days in thresholds:
            target_date = today - timedelta(days=days)

            for user in active_users:
                last_active = None

                last_quiz = quiz_map.get(user.id)
                last_code = code_map.get(user.id)

                last_quiz_date = last_quiz.date() if last_quiz else None
                last_code_date = last_code.date() if last_code else None

                if last_quiz_date and last_code_date:
                    last_active = max(last_quiz_date, last_code_date)
                elif last_quiz_date:
                    last_active = last_quiz_date
                elif last_code_date:
                    last_active = last_code_date

                # If no attempts, check last_login
                if not last_active and user.last_login:
                    last_active = user.last_login.date()

                if last_active == target_date:
                    import asyncio

                    from services.redis_service import redis_client

                    idem_key = f"reengage:{user.id}:{days}:{today}"
                    already_sent = asyncio.run(redis_client.get(idem_key))
                    if already_sent:
                        continue

                    try:
                        send_reengagement_email(user.email, user.full_name, days)
                        asyncio.run(redis_client.set(idem_key, "1", ex=86400))
                        logger.info(f"Re-engagement ({days}d) sent to {user.email}")
                    except Exception as e:
                        logger.error(
                            f"Failed to send re-engagement to {user.email}: {e}"
                        )

        record_task_run(db, "process_reengagement_lifecycle", "success")
    except Exception as e:
        logger.error(f"Re-engagement lifecycle error: {e}", exc_info=True)
        record_task_run(db, "process_reengagement_lifecycle", "failure", str(e))
    finally:
        db.close()


def notify_mentors_pending_reviews():
    """
    SECTION 15: Mentor Feedback Loop.
    Identifies groups with pending reviews and notifies assigned mentors.
    """
    db = SessionLocal()
    try:
        from auth_utils import get_mentor_ids_for_group

        # Find all groups with at least one pending review
        # A review is pending if is_reviewed is False
        groups_with_pending = (
            db.query(models.Attempt.group_id)
            .filter(models.Attempt.is_reviewed.is_(False))
            .distinct()
            .all()
        )

        sent = 0
        for (group_id,) in groups_with_pending:
            if not group_id:
                continue

            # Get pending count
            count = (
                db.query(models.Attempt)
                .filter(
                    models.Attempt.group_id == group_id, not models.Attempt.is_reviewed
                )
                .count()
            )

            # Get mentors for this group
            mentor_ids = get_mentor_ids_for_group(db, group_id)

            for m_id in mentor_ids:
                # Create notification
                notif = models.Notification(
                    user_id=m_id,
                    notification_type="pending_reviews",
                    title="📋 Pending Reviews Awaiting Action",
                    body=f"There are {count} student artifacts in your sector requiring pedagogical review.",
                    link_type="mentor_dashboard",
                    link_id=group_id,
                )
                db.add(notif)
                sent += 1

        db.commit()
        logger.info(f"Mentor notifications sent: {sent} alerts for pending reviews.")
        record_task_run(db, "notify_mentors_pending_reviews", "success")
    except Exception as e:
        logger.error(f"Mentor notification failure: {e}")
        record_task_run(db, "notify_mentors_pending_reviews", "failure", str(e))
    finally:
        db.close()
