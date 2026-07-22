import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import models
from database import SessionLocal
from sqlalchemy import func
from sqlalchemy.orm import Session

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


from config import settings  # noqa: E402
from services.s3_service import get_s3_client  # noqa: E402


def generate_daily_challenges(
    group_id: Optional[int] = None, external_db: Optional[Session] = None
):
    """
    STRAT-DCC-02: Advanced Weakness-Based Seeding.
    Runs at midnight IST or on-demand via LDAdmin dash.

    Pedagogical Logic:
    1. Identify target group(s).
    2. For each group, aggregate performance metrics across all members.
    3. Calculate 'Proficiency Floor': Identify banks/chapters where aggregate accuracy < 65%.
    4. Weighted Selection: Pick from 'Floor' banks first; otherwise recent progress banks.
    """
    db = external_db or SessionLocal()
    try:
        today = date.today()
        query = db.query(models.Group).filter(models.Group.is_active.is_(True))
        if group_id:
            query = query.filter(models.Group.id == group_id)
        groups = query.all()
        created_count = 0

        for group in groups:
            # Skip if already has a non-override challenge today
            existing = (
                db.query(models.DailyChallenge)
                .filter(
                    models.DailyChallenge.group_id == group.id,
                    models.DailyChallenge.challenge_date == today,
                    not models.DailyChallenge.is_mentor_override,
                )
                .first()
            )
            if existing:
                continue

            # Exclude recent questions (Strategic Variety: 60-day window)
            recent_qids = {
                row[0]
                for row in db.query(models.DailyChallenge.question_id)
                .filter(
                    models.DailyChallenge.group_id == group.id,
                    models.DailyChallenge.challenge_date
                    >= (today - timedelta(days=60)),
                )
                .all()
            }

            selected_q = None
            reason = "Automatic Discovery"

            # 1. SCOPING (Vertical -> Batch -> Group)
            if group.batch_id:
                batch = (
                    db.query(models.Batch)
                    .filter(models.Batch.id == group.batch_id)
                    .first()
                )
                if batch and batch.vertical_id:
                    course_ids = [
                        c.course_id
                        for c in db.query(models.VerticalCourse)
                        .filter_by(vertical_id=batch.vertical_id, is_active=True)
                        .all()
                    ]

                    if course_ids:
                        bank_ids = [
                            b.id
                            for b in db.query(models.QuestionBank.id)
                            .filter(models.QuestionBank.course_id.in_(course_ids))
                            .all()
                        ]

                        if bank_ids:
                            # 2. WEAKNESS AGGREGATION (Group-wide)
                            user_ids = [
                                u.id
                                for u in db.query(models.User.id)
                                .filter_by(group_id=group.id)
                                .all()
                            ]

                            if user_ids:
                                # Find chapters where this group struggles (< 65% accuracy)
                                # This ensures the daily seed is pedagogically relevant
                                performance = (
                                    db.query(
                                        models.Attempt.bank_id,
                                        func.sum(models.Attempt.score).label("s"),
                                        func.sum(models.Attempt.total).label("t"),
                                    )
                                    .filter(
                                        models.Attempt.user_id.in_(user_ids),
                                        models.Attempt.bank_id.in_(bank_ids),
                                    )
                                    .group_by(models.Attempt.bank_id)
                                    .all()
                                )

                                floor_banks = []
                                for row in performance:
                                    # Unpack tuple positionally: (bank_id, score_sum, total_sum)
                                    _bid, _s, _t = row[0], row[1], row[2]
                                    _t = int(_t) if _t is not None else 0
                                    _s = int(_s) if _s is not None else 0
                                    if _t > 0 and (_s / _t) < 0.65:
                                        floor_banks.append(_bid)

                                if floor_banks:
                                    selected_q = (
                                        db.query(models.Question)
                                        .filter(
                                            models.Question.bank_id.in_(floor_banks),
                                            ~models.Question.id.in_(recent_qids),
                                        )
                                        .order_by(func.random())
                                        .first()
                                    )
                                    if selected_q:
                                        reason = "Collective Weakness (Accuracy < 65%)"

                            # 3. FALLBACK: Progress alignment
                            if not selected_q:
                                selected_q = (
                                    db.query(models.Question)
                                    .filter(
                                        models.Question.bank_id.in_(bank_ids),
                                        ~models.Question.id.in_(recent_qids),
                                    )
                                    .order_by(func.random())
                                    .first()
                                )
                                if selected_q:
                                    reason = "Vertical Progress Alignment"

            # 4. ABSOLUTE FALLBACK: Broad discovery
            if not selected_q:
                selected_q = (
                    db.query(models.Question)
                    .filter(~models.Question.id.in_(recent_qids))
                    .order_by(func.random())
                    .first()
                )
                if selected_q:
                    reason = "Broad Knowledge Discovery"

            if selected_q:
                challenge = models.DailyChallenge(
                    group_id=group.id,
                    question_id=selected_q.id,
                    challenge_date=today,
                    selection_reason=reason,
                    is_mentor_override=False,
                )
                db.add(challenge)
                created_count += 1

        db.commit()
        logger.info(f"🎯 Strategic Seed: {created_count} challenges generated.")
        record_task_run(db, "generate_daily_challenges", "success")
        return created_count

    except Exception as e:
        db.rollback()
        logger.error(f"Seeding failure: {e}")
        record_task_run(db, "generate_daily_challenges", "failure", str(e))
        raise e
    finally:
        if external_db is None:
            db.close()


def send_daily_challenge_notifications():
    """Runs at 9 AM IST. Notifies all active group members who haven't attempted today.
    Also sends streak-break alert emails for users with active streaks >= 3 days."""
    db = SessionLocal()
    try:
        from services.email_service import send_streak_break_email

        today = date.today()
        challenges = (
            db.query(models.DailyChallenge)
            .filter(models.DailyChallenge.challenge_date == today)
            .all()
        )

        sent = 0
        for challenge in challenges:
            group_users = (
                db.query(models.User)
                .filter(
                    models.User.group_id == challenge.group_id, models.User.is_active.is_(True)
                )
                .all()
            )

            question = (
                db.query(models.Question)
                .filter(models.Question.id == challenge.question_id)
                .first()
            )

            q_preview = ""
            if question:
                q_preview = (
                    question.question[:80] + "..."
                    if len(question.question) > 80
                    else question.question
                )

            for user in group_users:
                # Don't notify if already attempted today's challenge
                already_attempted = (
                    db.query(models.Attempt)
                    .filter(
                        models.Attempt.user_id == user.id,
                        models.Attempt.is_daily_challenge,
                        func.date(models.Attempt.attempted_at) == today,
                    )
                    .count()
                )

                if not already_attempted:
                    notif = models.Notification(
                        user_id=user.id,
                        notification_type="daily_challenge",
                        title="🎯 Daily Challenge Available!",
                        body=q_preview or "Your daily challenge is ready.",
                        link_type="daily_challenge",
                        link_id=challenge.id,
                    )
                    db.add(notif)
                    sent += 1

                    # Streak break warning: if user has streak >= 3 and hasn't acted today
                    streak = getattr(user, "streak_count", 0) or 0
                    if streak >= 3 and user.email:
                        try:
                            send_streak_break_email(user.email, user.full_name, streak)
                        except Exception as e:
                            logger.warning(f"Streak email failed for {user.email}: {e}")

        db.commit()
        logger.info(
            f"Daily challenge notifications sent: {sent} across {len(challenges)} groups"
        )
        record_task_run(db, "send_daily_challenge_notifications", "success")

    except Exception as e:
        logger.error(f"Error sending challenge notifications: {e}", exc_info=True)
        record_task_run(db, "send_daily_challenge_notifications", "failure", str(e))
        db.rollback()
    finally:
        db.close()


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


def auto_lock_assignments():
    """Runs periodically to lock assignments that are past due and have lock_after_due=True."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        past_due = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.is_active.is_(True),
                models.Assignment.lock_after_due,
                models.Assignment.due_date < now,
            )
            .all()
        )

        locked_count = 0
        for assignment in past_due:
            assignment.is_active = False
            locked_count += 1

        if locked_count > 0:
            db.commit()
            logger.info(f"Auto-locked {locked_count} past due assignments.")

        record_task_run(db, "auto_lock_assignments", "success")

    except Exception as e:
        logger.error(f"Error auto-locking assignments: {e}", exc_info=True)
        record_task_run(db, "auto_lock_assignments", "failure", str(e))
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


def merge_duplicate_users():
    """Stub for merging duplicate users."""
    db = SessionLocal()
    try:
        record_task_run(db, "merge_duplicate_users", "success")
    except Exception as e:
        record_task_run(db, "merge_duplicate_users", "failure", str(e))
    finally:
        db.close()


def fix_orphaned_records():
    """Stub for fixing orphaned records."""
    db = SessionLocal()
    try:
        record_task_run(db, "fix_orphaned_records", "success")
    except Exception as e:
        record_task_run(db, "fix_orphaned_records", "failure", str(e))
    finally:
        db.close()


def cleanup_stale_data():
    """
    STRAT-CLN-01: Automated Data Integrity Cleanup.
    Runs periodically to remove artifacts that degrade platform quality.

    1. Correct zero-score artifacts in coding_attempts (abandoned/failed tests).
    2. Mark assignments older than 90 days as inactive.
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # 1. Cleanup zero-score coding attempts (older than 24h)
        # These are usually abandoned runs or catastrophic test failures
        threshold_24h = now - timedelta(hours=24)

        # Pydantic Validation Guardrail
        from schemas_tasks import StaleCodingAttempt

        stale_candidates = (
            db.query(models.CodingAttempt)
            .filter(
                models.CodingAttempt.attempted_at < threshold_24h,
                models.CodingAttempt.score == 0,
            )
            .all()
        )

        valid_stale_ids = []
        for candidate in stale_candidates:
            try:
                # Force strictly structural validation
                StaleCodingAttempt(
                    id=candidate.id,
                    score=candidate.score,  # type: ignore
                    attempted_at=candidate.attempted_at,  # type: ignore
                )
                valid_stale_ids.append(candidate.id)
            except Exception as val_e:
                logger.warning(
                    f"Validation failed for Stale Data candidate {candidate.id}: {val_e}"
                )

        deleted_coding = 0
        if valid_stale_ids:
            deleted_coding = (
                db.query(models.CodingAttempt)
                .filter(models.CodingAttempt.id.in_(valid_stale_ids))
                .delete(synchronize_session=False)
            )

        # 2. Expire old assignments (older than 90 days)
        threshold_90d = now - timedelta(days=90)
        expired_assignments = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.is_active.is_(True),
                models.Assignment.created_at < threshold_90d,
            )
            .update({"is_active": False}, synchronize_session=False)
        )

        db.commit()
        logger.info(
            f"🧹 Cleanup complete: {deleted_coding} zero-score attempts removed, {expired_assignments} old assignments expired."
        )
        record_task_run(db, "cleanup_stale_data", "success")

    except Exception as e:
        logger.error(f"Cleanup task failure: {e}", exc_info=True)
        record_task_run(db, "cleanup_stale_data", "failure", str(e))
        db.rollback()
    finally:
        db.close()


def prune_orphaned_s3_objects():
    """
    STRAT-S3-01: Orphaned Object Pruning.
    Runs weekly. Identifies and deletes S3 objects that are no longer referenced in the DB.

    Logic:
    1. Scan DB for all referenced S3 keys (Resource model and User asset URLs).
    2. List all objects in the S3 bucket.
    3. Delete objects that are NOT in the referenced list and are older than 24h.
    """
    db = SessionLocal()
    try:
        s3 = get_s3_client()
        if not settings.AWS_ACCESS_KEY_ID:
            logger.warning("S3 Cleanup skipped: AWS credentials not configured.")
            return

        # 1. Gather all referenced keys from DB
        referenced_keys = set()

        # Resource keys
        for row in db.query(models.Resource.s3_key).all():
            if row[0]:
                referenced_keys.add(row[0])

        # User assets (URLs)
        user_assets = db.query(
            models.User.profile_photo_url,
            models.User.cover_photo_url,
            models.User.intro_video_url,
        ).all()

        for profile, cover, video in user_assets:
            for url in [profile, cover, video]:
                if url and settings.S3_BUCKET_NAME in url:
                    # Extract key from URL
                    # URL format: https://bucket.s3.region.amazonaws.com/key
                    try:
                        key = url.split(".amazonaws.com/")[-1]
                        referenced_keys.add(key)
                    except Exception as e:
                        logger.error(f"Failed to parse S3 key from URL {url}: {e}")
                        continue

        # 2. List S3 objects and compare
        paginator = s3.get_paginator("list_objects_v2")
        deleted_count = 0
        total_objects = 0

        for page in paginator.paginate(Bucket=settings.S3_BUCKET_NAME):
            if "Contents" not in page:
                continue

            for obj in page["Contents"]:
                total_objects += 1
                key = obj["Key"]

                # Check if it's an orphan
                if key not in referenced_keys:
                    # Pydantic Validation Guardrail
                    from schemas_tasks import StaleS3Object

                    try:
                        valid_orphan = StaleS3Object(
                            key=key, last_modified=obj["LastModified"]
                        )
                        s3.delete_object(
                            Bucket=settings.S3_BUCKET_NAME, Key=valid_orphan.key
                        )
                        deleted_count += 1
                    except Exception as val_e:
                        logger.warning(
                            f"S3 Object {key} failed Stale validation: {val_e}"
                        )

        logger.info(
            f"🗑️ S3 Cleanup complete: {deleted_count} orphaned objects pruned from {total_objects} total."
        )
        record_task_run(db, "prune_orphaned_s3_objects", "success")

    except Exception as e:
        logger.error(f"S3 cleanup task failure: {e}", exc_info=True)
        record_task_run(db, "prune_orphaned_s3_objects", "failure", str(e))
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
    prune_orphaned_s3_objects()
    # Prune internally uses record_task_run for "prune_orphaned_s3_objects"
    # but we record it for "sync_s3_resources" as well for dashboard parity
    if not db:
        db = SessionLocal()
        record_task_run(db, "sync_s3_resources", "success")
        db.close()
    else:
        record_task_run(db, "sync_s3_resources", "success")


if __name__ == "__main__":
    generate_daily_challenges()
    send_daily_challenge_notifications()
    send_deadline_reminders()
    auto_lock_assignments()
    maintain_streaks()
    cleanup_stale_data()
    prune_orphaned_s3_objects()
    notify_mentors_pending_reviews()
