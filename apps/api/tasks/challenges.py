import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import models
from database import SessionLocal
from sqlalchemy import func
from sqlalchemy.orm import Session

from ._shared import record_task_run

logger = logging.getLogger(__name__)


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
                    models.DailyChallenge.is_mentor_override.is_(False),
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
