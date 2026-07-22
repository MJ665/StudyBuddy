import os
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import models
from cache_manager import cache_manager
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger("performance_engine")

# Concurrent per-user vector computations during batch/global aggregation.
# Bounded so a large cohort cannot exhaust the DB connection pool.
AGGREGATE_CONCURRENCY = int(os.environ.get("AGGREGATE_CONCURRENCY", "5"))


class PerformanceEngine:
    """
    SECTION 12: Strategic Performance Intelligence (30 Scientific Vectors).
    Calculates granular learning trajectories for enterprise talent mapping.
    """

    @staticmethod
    def _calculate_slope(ys: List[float]) -> float:
        """Linear regression slope to determine velocity."""
        if len(ys) < 2:
            return 0.0
        xs = list(range(len(ys)))
        n = len(xs)
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x**2 for x in xs)
        denominator = n * sum_x2 - sum_x**2
        return (
            round((n * sum_xy - sum_x * sum_y) / denominator, 2)
            if denominator != 0
            else 0.0
        )

    @cache_manager.cached("user_vectors", ttl=129600)  # 36h cache
    async def get_user_vectors(
        self, user_id: int, db, refresh: bool = False
    ) -> Dict[str, Any]:
        """Async entry point. Keeps the event loop free while the 30 metrics are computed.

        The computation below is ~700 lines of purely SYNCHRONOUS SQLAlchemy work and
        contains no awaits, yet it was declared `async def` — so every caller ran all
        of it directly on the event loop, blocking every other request for its
        duration. This wrapper keeps the existing `await` contract for all callers
        while moving the blocking work off the loop:

          * AsyncSession -> `run_sync`, executing it on the async connection with a
            proper greenlet context (so lazy loads inside still work);
          * sync Session -> a threadpool, exactly how FastAPI runs `def` endpoints.
        """
        from fastapi.concurrency import run_in_threadpool
        from sqlalchemy.ext.asyncio import AsyncSession

        if isinstance(db, AsyncSession):
            result = await db.run_sync(
                lambda sync_db: self._compute_user_vectors(user_id, sync_db, refresh)
            )
        else:
            result = await run_in_threadpool(
                self._compute_user_vectors, user_id, db, refresh
            )

        # Fire-and-forget vector sync, scheduled here where a loop exists.
        if result:
            try:
                import asyncio

                from services.vector_service import vector_service

                asyncio.create_task(
                    vector_service.upsert_user_performance_vector(
                        user_id, result.get("metrics", {})
                    )
                )
            except Exception as e:  # never fail a read because a sync could not start
                logger.warning(f"vector sync could not be scheduled: {e}")

        return result

    def _compute_user_vectors(
        self, user_id: int, db: Session, refresh: bool = False
    ) -> Dict[str, Any]:
        """Calculates 30 high-fidelity performance vectors for a user. SYNCHRONOUS."""
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return {}

        # Data Retrieval
        quiz_attempts = (
            db.query(models.Attempt).filter(models.Attempt.user_id == user_id).all()
        )
        coding_attempts = (
            db.query(models.CodingAttempt)
            .filter(models.CodingAttempt.user_id == user_id)
            .all()
        )

        now = datetime.now(timezone.utc)
        now.date()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # ── METRIC 1: Total Quiz Attempts ──────────────────────────────────────
        total_quiz = len(quiz_attempts)

        # ── METRIC 2: Overall Quiz Accuracy ───────────────────────────────────
        valid_quiz = [a for a in quiz_attempts if a.total and a.total > 0]
        overall_accuracy = (
            round(
                sum((a.score / a.total) * 100 for a in valid_quiz) / len(valid_quiz), 1
            )
            if valid_quiz
            else 0.0
        )

        # ── METRIC 3: Best Quiz Score ──────────────────────────────────────────
        best_quiz = round(
            max(((a.score / a.total) * 100 for a in valid_quiz), default=0), 1
        )

        # ── METRIC 4: Worst Quiz Score ─────────────────────────────────────────
        worst_quiz = round(
            min(((a.score / a.total) * 100 for a in valid_quiz), default=0), 1
        )

        # ── METRIC 5: Quiz Attempts (Last 7 Days) ─────────────────────────────
        recent_quiz_7d = sum(
            1
            for a in quiz_attempts
            if a.attempted_at
            and (
                a.attempted_at.replace(tzinfo=timezone.utc)
                if a.attempted_at.tzinfo is None
                else a.attempted_at
            )
            > week_ago
        )

        # ── METRIC 6: Quiz Attempts (Last 30 Days) ────────────────────────────
        recent_quiz_30d = sum(
            1
            for a in quiz_attempts
            if a.attempted_at
            and (
                a.attempted_at.replace(tzinfo=timezone.utc)
                if a.attempted_at.tzinfo is None
                else a.attempted_at
            )
            > month_ago
        )

        # ── METRIC 7: Streak (Consecutive Active Days) ────────────────────────
        streak = user.streak_count or 0

        # ── METRIC 8: Average Time Per Quiz (seconds) ─────────────────────────
        timed = [a for a in quiz_attempts if a.time_taken and a.time_taken > 0]
        avg_time = round(sum(a.time_taken for a in timed) / len(timed)) if timed else 0

        # ── METRIC 9: Speed Rating ────────────────────────────────────────────
        speed_rating = (
            "Fast" if avg_time < 120 else "Moderate" if avg_time < 300 else "Thorough"
        )

        # ── METRIC 10: Review Rate (% attempts verified by mentor) ────────────
        reviewed = sum(1 for a in quiz_attempts if a.is_reviewed)
        review_rate = round((reviewed / total_quiz) * 100, 1) if total_quiz > 0 else 0.0

        # ── METRIC 11: Topic Mastery Map ──────────────────────────────────────
        topic_stats: dict = defaultdict(lambda: {"scores": [], "count": 0})
        for a in valid_quiz:
            topic = (a.bank.chapter if a.bank else "General") or "General"
            topic_stats[topic]["scores"].append((a.score / a.total) * 100)
            topic_stats[topic]["count"] += 1

        topic_mastery = [
            {
                "topic": t,
                "avg_accuracy": round(sum(d["scores"]) / len(d["scores"]), 1),
                "attempts": d["count"],
                "mastery": "Expert"
                if sum(d["scores"]) / len(d["scores"]) >= 85
                else "Proficient"
                if sum(d["scores"]) / len(d["scores"]) >= 70
                else "Learning"
                if sum(d["scores"]) / len(d["scores"]) >= 50
                else "Developing",
            }
            for t, d in topic_stats.items()
        ]
        best_topic = max(topic_mastery, key=lambda x: x["avg_accuracy"], default=None)
        worst_topic = min(topic_mastery, key=lambda x: x["avg_accuracy"], default=None)

        # ── METRIC 12: Coding Lab Attempts ────────────────────────────────────
        total_coding = len(coding_attempts)

        # ── METRIC 13: Coding AI Score Average ────────────────────────────────
        ai_scored_vals = [int(c.score) for c in coding_attempts if c.score is not None]
        avg_ai_score = (
            round(sum(ai_scored_vals) / len(ai_scored_vals), 1)
            if ai_scored_vals
            else 0.0
        )

        # ── METRIC 14: Coding Success Rate ────────────────────────────────────
        passed_coding = sum(
            1 for c in coding_attempts if c.score is not None and c.score >= 70
        )
        coding_success_rate = (
            round((passed_coding / total_coding) * 100, 1) if total_coding > 0 else 0.0
        )

        # ── METRIC 15: Coding Languages Used ──────────────────────────────────
        lang_set = set()
        for c in coding_attempts:
            if c.coding_question and c.coding_question.language:
                lang_set.add(c.coding_question.language)
        languages_used = sorted(lang_set)

        # ── METRIC 16: Assignment Completion Rate ─────────────────────────────
        target_filters = [
            (models.Assignment.target_type == "group")
            & (models.Assignment.target_id == user.group_id)
        ]
        if user.group and user.group.batch_id:
            target_filters.append(
                (models.Assignment.target_type == "batch")
                & (models.Assignment.target_id == user.group.batch_id)
            )
            batch = (
                db.query(models.Batch)
                .filter(models.Batch.id == user.group.batch_id)
                .first()
            )
            if batch and batch.vertical_id:
                target_filters.append(
                    (models.Assignment.target_type == "vertical")
                    & (models.Assignment.target_id == batch.vertical_id)
                )

        total_assignments = (
            db.query(models.Assignment)
            .filter(models.Assignment.is_active.is_(True), or_(*target_filters))
            .count()
        )
        completed_assignments = (
            db.query(models.AssignmentCompletion)
            .filter(
                models.AssignmentCompletion.user_id == user_id,
            )
            .count()
        )
        assignment_rate = (
            round((completed_assignments / total_assignments) * 100, 1)
            if total_assignments > 0
            else 0.0
        )

        # ── METRIC 17: Learning Velocity (slope) ──────────────────────────────
        sorted_attempts = sorted(
            valid_quiz,
            key=lambda a: a.attempted_at or datetime.min.replace(tzinfo=timezone.utc),
        )
        scores_only = [(a.score / a.total) * 100 for a in sorted_attempts]
        velocity = self._calculate_slope(scores_only)
        velocity_label = (
            "Improving 📈"
            if velocity > 0.5
            else "Stable 📊"
            if velocity > -0.5
            else "Declining 📉"
        )

        # ── METRIC 18: Consistency Score (StdDev-based) ───────────────────────
        if len(valid_quiz) >= 2:
            mean_s = sum(scores_only) / len(scores_only)
            variance = sum((s - mean_s) ** 2 for s in scores_only) / len(scores_only)
            std_dev = variance**0.5
            consistency_score = max(0, round(100 - std_dev, 1))
            consistency_label = (
                "Highly Consistent"
                if consistency_score >= 85
                else "Consistent"
                if consistency_score >= 70
                else "Variable"
                if consistency_score >= 50
                else "Erratic"
            )
        else:
            consistency_score = 0.0
            consistency_label = "Insufficient data"
            std_dev = 0.0

        # ── METRIC 19: First Attempt vs Retry Accuracy ────────────────────────
        bank_attempts: dict = defaultdict(list)
        for a in valid_quiz:
            bank_attempts[a.bank_id].append((a.score / a.total) * 100)
        first_attempt_scores = [accs[0] for accs in bank_attempts.values() if accs]
        retry_scores = [
            acc for accs in bank_attempts.values() for acc in accs[1:] if len(accs) > 1
        ]
        first_attempt_avg = (
            round(sum(first_attempt_scores) / len(first_attempt_scores), 1)
            if first_attempt_scores
            else 0.0
        )
        retry_avg = (
            round(sum(retry_scores) / len(retry_scores), 1) if retry_scores else 0.0
        )

        # ── METRIC 20: Total Study Days (unique dates with activity) ──────────
        active_dates = set()
        for a in quiz_attempts:
            if a.attempted_at is not None:
                active_dates.add(
                    a.attempted_at.date()
                    if hasattr(a.attempted_at, "date")
                    else a.attempted_at
                )
        for c in coding_attempts:
            if c.attempted_at is not None:
                active_dates.add(
                    c.attempted_at.date()
                    if hasattr(c.attempted_at, "date")
                    else c.attempted_at
                )
        total_active_days = len(active_dates)

        # ── METRIC 21: Average Attempts Per Active Day ────────────────────────
        avg_per_day = (
            round(total_quiz / total_active_days, 1) if total_active_days > 0 else 0.0
        )

        # ── METRIC 22: Questions Answered ─────────────────────────────────────
        total_questions_answered = sum(a.total or 0 for a in quiz_attempts)

        # ── METRIC 23: Questions Correct ──────────────────────────────────────
        total_correct = sum(a.score or 0 for a in quiz_attempts)

        # ── METRIC 24: Daily Challenge Participation ──────────────────────────
        daily_participations = (
            db.query(func.count(models.Attempt.id))
            .filter(
                models.Attempt.user_id == user_id, models.Attempt.is_daily_challenge
            )
            .scalar()
            or 0
        )

        # ── METRIC 25: Last Active Date ───────────────────────────────────────
        last_active = user.last_active_date
        if last_active:
            if not last_active.tzinfo:
                last_active = last_active.replace(tzinfo=timezone.utc)
            days_since_active = (now - last_active).days
        else:
            days_since_active = None

        activity_status = (
            "Active Today"
            if days_since_active == 0
            else f"Active {days_since_active}d ago"
            if days_since_active
            else "Unknown"
        )

        # ── METRIC 26: Peer Ranking (within group) ────────────────────────────
        group_user_ids = [
            u.id
            for u in db.query(models.User.id)
            .filter(
                models.User.group_id == user.group_id,
                models.User.role == "Member",
                models.User.is_active.is_(True),
            )
            .all()
        ]

        group_accuracies_res = (
            db.query(
                models.Attempt.user_id,
                func.avg((models.Attempt.score * 100.0) / models.Attempt.total).label(
                    "acc"
                ),
            )
            .filter(
                models.Attempt.user_id.in_(group_user_ids), models.Attempt.total > 0
            )
            .group_by(models.Attempt.user_id)
            .all()
        )

        group_accuracies = [
            {"user_id": r.user_id, "acc": float(r.acc)} for r in group_accuracies_res
        ]
        group_accuracies.sort(key=lambda x: x["acc"], reverse=True)
        peer_rank = next(
            (i + 1 for i, g in enumerate(group_accuracies) if g["user_id"] == user_id),
            None,
        )
        group_size = len(group_accuracies)

        # If no peer ranking possible, set default safely
        if peer_rank is None or group_size == 0:
            percentile = 100.0 if total_quiz > 0 else 0.0
            peer_rank = 1 if group_size == 0 else (group_size + 1)
        else:
            percentile = (
                round((1 - (peer_rank - 1) / group_size) * 100, 0)
                if group_size > 1
                else 100.0
            )

        # ── METRIC 27: Retention Decay Rate ───────────────────────────────────
        # Heuristic: Decay rate increases with inactivity
        base_decay = 5.0  # 5% per week baseline
        decay_rate = round(
            base_decay + (days_since_active if days_since_active else 14) * 0.5, 1
        )

        # ── METRIC 28: Engagement Profile ─────────────────────────────────────
        if overall_accuracy >= 80 and streak >= 7:
            engagement_profile = "Champion Learner 🏆"
        elif overall_accuracy >= 70 and recent_quiz_7d >= 5:
            engagement_profile = "Power Learner ⚡"
        elif streak >= 3:
            engagement_profile = "Consistent Practitioner 🔥"
        elif recent_quiz_30d >= 10:
            engagement_profile = "Active Participant 📚"
        elif total_quiz < 3:
            engagement_profile = "Getting Started 🌱"
        else:
            engagement_profile = "Occasional Learner 🌙"

        # ── METRIC 29: Risk Level ──────────────────────────────────────────────
        if days_since_active is None or days_since_active > 14:
            risk_level = "High Risk 🔴"
        elif days_since_active > 7 or overall_accuracy < 40:
            risk_level = "Medium Risk 🟡"
        elif assignment_rate < 50 and total_assignments > 0:
            risk_level = "Moderate 🟠"
        else:
            risk_level = "On Track 🟢"

        # ── METRIC 30: 7-Day Activity Trend ───────────────────────────────────
        activity_trend = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_date = day.date()
            count = sum(
                1
                for a in quiz_attempts
                if getattr(a, "attempted_at", None) is not None
                and (
                    getattr(a.attempted_at, "date")()
                    if hasattr(a.attempted_at, "date")
                    else a.attempted_at
                )
                == day_date  # type: ignore
            ) + sum(
                1
                for c in coding_attempts
                if getattr(c, "attempted_at", None) is not None
                and (
                    getattr(c.attempted_at, "date")()
                    if hasattr(c.attempted_at, "date")
                    else c.attempted_at
                )
                == day_date  # type: ignore
            )
            activity_trend.append(
                {
                    "day": day.strftime("%a"),
                    "date": day_date.isoformat(),
                    "count": count,
                }
            )

        # Structured Metrics for Frontend
        metrics = {
            "m01_total_quiz_attempts": {
                "label": "Total Quiz Attempts",
                "value": total_quiz,
                "type": "quantitative",
                "icon": "📝",
                "raw": total_quiz,
            },
            "m02_overall_accuracy": {
                "label": "Overall Accuracy",
                "value": f"{overall_accuracy}%",
                "type": "quantitative",
                "icon": "🎯",
                "raw": overall_accuracy,
            },
            "m03_best_quiz_score": {
                "label": "Best Quiz Score",
                "value": f"{best_quiz}%",
                "type": "quantitative",
                "icon": "🏆",
                "raw": best_quiz,
            },
            "m04_worst_quiz_score": {
                "label": "Worst Quiz Score",
                "value": f"{worst_quiz}%",
                "type": "quantitative",
                "icon": "📉",
                "raw": worst_quiz,
            },
            "m05_quiz_7d": {
                "label": "Attempts (Last 7 Days)",
                "value": recent_quiz_7d,
                "type": "quantitative",
                "icon": "📅",
                "raw": recent_quiz_7d,
            },
            "m06_quiz_30d": {
                "label": "Attempts (Last 30 Days)",
                "value": recent_quiz_30d,
                "type": "quantitative",
                "icon": "📆",
                "raw": recent_quiz_30d,
            },
            "m07_streak": {
                "label": "Current Streak",
                "value": f"{streak} days",
                "type": "quantitative",
                "icon": "🔥",
                "raw": streak,
            },
            "m08_avg_time": {
                "label": "Avg Time Per Quiz",
                "value": f"{avg_time}s",
                "type": "quantitative",
                "icon": "⏱️",
                "raw": avg_time,
            },
            "m09_speed_rating": {
                "label": "Speed Rating",
                "value": speed_rating,
                "type": "qualitative",
                "icon": "🚀",
                "raw": avg_time,
            },
            "m10_review_rate": {
                "label": "Mentor Review Rate",
                "value": f"{review_rate}%",
                "type": "quantitative",
                "icon": "👨‍🏫",
                "raw": review_rate,
            },
            "m11_topic_breadth": {
                "label": "Topic Breadth",
                "value": f"{len(topic_stats)} Domains",
                "type": "quantitative",
                "icon": "📚",
                "raw": len(topic_stats),
            },
            "m12_coding_attempts": {
                "label": "Coding Lab Attempts",
                "value": total_coding,
                "type": "quantitative",
                "icon": "💻",
                "raw": total_coding,
            },
            "m13_avg_ai_score": {
                "label": "Avg AI Code Score",
                "value": f"{avg_ai_score}%",
                "type": "quantitative",
                "icon": "🤖",
                "raw": avg_ai_score,
            },
            "m14_coding_success": {
                "label": "Coding Pass Rate",
                "value": f"{coding_success_rate}%",
                "type": "quantitative",
                "icon": "✅",
                "raw": coding_success_rate,
            },
            "m15_languages": {
                "label": "Languages Used",
                "value": ", ".join(languages_used) or "None yet",
                "type": "qualitative",
                "icon": "🔤",
                "raw": len(languages_used),
            },
            "m16_assignment_rate": {
                "label": "Assignment Completion",
                "value": f"{assignment_rate}%",
                "type": "quantitative",
                "icon": "📋",
                "raw": assignment_rate,
            },
            "m17_velocity": {
                "label": "Learning Velocity",
                "value": f"{velocity:+.1f}%",
                "type": "quantitative",
                "icon": "📈",
                "raw": velocity,
            },
            "m17b_velocity_label": {
                "label": "Trajectory",
                "value": velocity_label,
                "type": "qualitative",
                "icon": "📡",
                "raw": velocity,
            },
            "m18_consistency": {
                "label": "Consistency Score",
                "value": f"{consistency_score}%",
                "type": "quantitative",
                "icon": "📊",
                "raw": consistency_score,
            },
            "m18b_consistency_label": {
                "label": "Consistency Profile",
                "value": consistency_label,
                "type": "qualitative",
                "icon": "⚖️",
                "raw": consistency_score,
            },
            "m19_first_attempt": {
                "label": "First Attempt Avg",
                "value": f"{first_attempt_avg}%",
                "type": "quantitative",
                "icon": "1️⃣",
                "raw": first_attempt_avg,
            },
            "m19b_retry_avg": {
                "label": "Retry Avg",
                "value": f"{retry_avg}%",
                "type": "quantitative",
                "icon": "🔄",
                "raw": retry_avg,
            },
            "m20_active_days": {
                "label": "Total Active Days",
                "value": total_active_days,
                "type": "quantitative",
                "icon": "📅",
                "raw": total_active_days,
            },
            "m21_avg_per_day": {
                "label": "Avg Attempts/Day",
                "value": avg_per_day,
                "type": "quantitative",
                "icon": "⚡",
                "raw": avg_per_day,
            },
            "m22_questions_answered": {
                "label": "Questions Answered",
                "value": total_questions_answered,
                "type": "quantitative",
                "icon": "❓",
                "raw": total_questions_answered,
            },
            "m23_questions_correct": {
                "label": "Questions Correct",
                "value": total_correct,
                "type": "quantitative",
                "icon": "✔️",
                "raw": total_correct,
            },
            "m24_daily_participation": {
                "label": "Daily Challenge Joins",
                "value": daily_participations,
                "type": "quantitative",
                "icon": "🌟",
                "raw": daily_participations,
            },
            "m25_activity_status": {
                "label": "Activity Status",
                "value": activity_status,
                "type": "qualitative",
                "icon": "🟢",
                "raw": days_since_active if days_since_active is not None else 99,
            },
            "m26_percentile": {
                "label": "Group Percentile",
                "value": f"Top {int(100 - percentile)}%",
                "type": "quantitative",
                "icon": "🏅",
                "raw": percentile,
            },
            "m27_decay_rate": {
                "label": "Retention Decay",
                "value": f"{decay_rate}%/wk",
                "type": "quantitative",
                "icon": "📉",
                "raw": decay_rate,
            },
            "m28_engagement": {
                "label": "Engagement Profile",
                "value": engagement_profile,
                "type": "qualitative",
                "icon": "💡",
                "raw": streak,
            },
            "m29_risk": {
                "label": "Risk Assessment",
                "value": risk_level,
                "type": "status",
                "icon": "🛡️",
                "raw": overall_accuracy,
            },
            "m30_predictive_kpi": {
                "label": "Future Readiness",
                "value": "Accelerated" if velocity > 0 else "Stable",
                "type": "status",
                "icon": "🚀",
                "raw": (overall_accuracy + velocity * 10),
            },
        }

        # Vector synchronization (STRAT-VECTOR-01) is scheduled by the async
        # wrapper, not here: this body now runs in a worker thread / greenlet with
        # no running event loop, where asyncio.create_task() raises RuntimeError.

        # SECTION 12: Radar Data & Weighted Proficiency Normalization
        radar_mapping = {
            "Accuracy": "m02_overall_accuracy",
            "Consistency": "m18_consistency",
            "Velocity": "m17_velocity",
            "Coding": "m14_coding_success",
            "Assignment": "m16_assignment_rate",
        }
        radar_data = []
        weighted_sum = 0.0
        weights = {
            "Accuracy": 0.4,
            "Consistency": 0.2,
            "Velocity": 0.1,
            "Coding": 0.2,
            "Assignment": 0.1,
        }

        for axis, m_key in radar_mapping.items():
            raw = metrics[m_key]["raw"]
            if axis == "Velocity":
                val = max(0.0, min(100.0, (raw + 5.0) * 10.0))
            else:
                val = max(0.0, min(100.0, float(raw)))

            # Neutral baseline per dimension (STRAT-RADAR-01)
            is_quiz_dim = axis in ["Accuracy", "Consistency", "Velocity"]
            if (
                (is_quiz_dim and total_quiz == 0)
                or (axis == "Coding" and total_coding == 0)
                or (axis == "Assignment" and total_assignments == 0)
            ):
                val = 50.0

            radar_data.append({"subject": axis, "A": val, "fullMark": 100})
            weighted_sum += val * weights[axis]

        weighted_proficiency = round(weighted_sum, 1)

        return {
            "metrics": metrics,
            "charts": {
                "topic_mastery": topic_mastery,
                "activity_trend": activity_trend,
                "peer_rank": peer_rank,
                "group_size": group_size,
                "std_dev": round(std_dev, 2),
                "best_topic": best_topic,
                "worst_topic": worst_topic,
                "radar_data": radar_data,
                "weighted_proficiency": weighted_proficiency,
            },
            "raw_vectors": {k: v.get("raw", 0) for k, v in metrics.items()},
            "generated_at": now.isoformat(),
        }

    @staticmethod
    def _batch_member_stmt(batch_id: int):
        from sqlalchemy import select

        return select(models.User).where(
            models.User.group_id.in_(
                select(models.Group.id).where(models.Group.batch_id == batch_id)
            ),
            models.User.role == "Member",
        )

    @cache_manager.cached("batch_vectors", ttl=129600)  # 36h cache
    async def get_batch_vectors(
        self, batch_id: int, db, refresh: bool = False
    ) -> Dict[str, Any]:
        """Calculates aggregate 30-metric vectors for an entire batch.

        Accepts either session type so routers can migrate independently.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = self._batch_member_stmt(batch_id)
        if isinstance(db, AsyncSession):
            users = (await db.execute(stmt)).scalars().all()
        else:
            users = db.execute(stmt).scalars().all()
        return await self._aggregate_vectors(users, db, refresh)

    @cache_manager.cached("global_vectors", ttl=129600)  # 36h cache
    async def get_global_vectors(
        self, db, refresh: bool = False
    ) -> Dict[str, Any]:
        """Calculates platform-wide 30-metric performance vectors."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = select(models.User).where(models.User.role == "Member")
        if isinstance(db, AsyncSession):
            users = (await db.execute(stmt)).scalars().all()
        else:
            users = db.execute(stmt).scalars().all()
        return await self._aggregate_vectors(users, db, refresh)

    async def _aggregate_vectors(
        self, users: List[models.User], db, refresh: bool
    ) -> Dict[str, Any]:
        """Core logic to aggregate individual user vectors into a single 30-metric profile."""
        if not users:
            return {}

        all_metrics = []
        all_topic_stats: Dict[str, dict] = defaultdict(lambda: {"total_acc": 0, "count": 0})
        total_attempts = 0

        # Each user's vectors are ~700 lines of queries. Running them sequentially
        # made a batch report O(users) round trips; running them with a shared
        # Session would corrupt state, because SQLAlchemy Sessions are NOT
        # thread-safe and `get_user_vectors` hands the session to a worker
        # thread/greenlet. So each concurrent task gets its OWN session, with a
        # semaphore so a large cohort cannot exhaust the connection pool.
        import asyncio

        from database import db_session_factory

        semaphore = asyncio.Semaphore(AGGREGATE_CONCURRENCY)

        async def _vectors_for(user_id: int):
            async with semaphore:
                async with db_session_factory() as own_session:
                    try:
                        return await self.get_user_vectors(
                            user_id, own_session, refresh=refresh
                        )
                    except Exception as e:
                        # One bad user must not sink the whole batch report.
                        logger.warning(f"vectors failed for user {user_id}: {e}")
                        return None

        results = await asyncio.gather(*(_vectors_for(u.id) for u in users))

        for uv in results:
            if not uv or "metrics" not in uv:
                continue

            all_metrics.append(uv["metrics"])
            total_attempts += uv["metrics"]["m01_total_quiz_attempts"]["raw"]

            # Aggregate topic mastery
            for t in uv["charts"].get("topic_mastery", []):
                all_topic_stats[t["topic"]]["total_acc"] += t["avg_accuracy"]
                all_topic_stats[t["topic"]]["count"] += 1

        if not all_metrics:
            return {}

        # ── Aggregation Calculation ──────────────────────────────────────────
        count = len(all_metrics)

        def avg_metric(key):
            vals = [
                m[key]["raw"]
                for m in all_metrics
                if isinstance(m[key]["raw"], (int, float))
            ]
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        def sum_metric(key):
            return sum(
                m[key]["raw"]
                for m in all_metrics
                if isinstance(m[key]["raw"], (int, float))
            )

        # Aggregate 30 Metrics
        agg_metrics = {}
        # We'll map the 30 metrics to their aggregate equivalents
        for key in all_metrics[0].keys():
            m_template = all_metrics[0][key]
            is_quant = m_template["type"] == "quantitative"

            if is_quant:
                raw_val = (
                    avg_metric(key)
                    if any(
                        x in key
                        for x in [
                            "accuracy",
                            "rate",
                            "score",
                            "velocity",
                            "percentile",
                            "decay",
                            "consistency",
                        ]
                    )
                    else sum_metric(key)
                )

                # Special cases for formatting
                formatted_val = (
                    f"{raw_val}%"
                    if any(
                        x in key
                        for x in ["accuracy", "rate", "score", "consistency", "decay"]
                    )
                    else f"{raw_val:+.1f}%"
                    if "velocity" in key
                    else f"Top {int(100 - raw_val)}%"
                    if "percentile" in key
                    else str(raw_val)
                )

                agg_metrics[key] = {
                    "label": m_template["label"],
                    "value": formatted_val,
                    "type": m_template["type"],
                    "icon": m_template["icon"],
                    "raw": raw_val,
                }
            else:
                # For qualitative metrics, we take the mode or a summary
                vals = [m[key]["value"] for m in all_metrics]
                mode_val = max(set(vals), key=vals.count) if vals else "N/A"
                agg_metrics[key] = {
                    "label": m_template["label"],
                    "value": mode_val,
                    "type": m_template["type"],
                    "icon": m_template["icon"],
                    "raw": 0,
                }

        # Aggregate Topic Mastery Chart
        agg_topic_mastery = [
            {
                "topic": t,
                "avg_accuracy": round(d["total_acc"] / d["count"], 1),
                "attempts": d["count"],
                "mastery": "Expert"
                if d["total_acc"] / d["count"] >= 85
                else "Proficient"
                if d["total_acc"] / d["count"] >= 70
                else "Learning"
                if d["total_acc"] / d["count"] >= 50
                else "Developing",
            }
            for t, d in all_topic_stats.items()
        ]
        agg_topic_mastery.sort(key=lambda x: x["avg_accuracy"], reverse=True)

        # SECTION 12: Aggregated Radar Data
        radar_mapping = {
            "Accuracy": "m02_overall_accuracy",
            "Consistency": "m18_consistency",
            "Velocity": "m17_velocity",
            "Coding": "m14_coding_success",
            "Assignment": "m16_assignment_rate",
        }
        agg_radar_data = []
        agg_weighted_sum = 0.0
        weights = {
            "Accuracy": 0.4,
            "Consistency": 0.2,
            "Velocity": 0.1,
            "Coding": 0.2,
            "Assignment": 0.1,
        }

        for axis, m_key in radar_mapping.items():
            raw = agg_metrics[m_key]["raw"]
            if axis == "Velocity":
                val = max(0.0, min(100.0, (raw + 5.0) * 10.0))
            else:
                val = max(0.0, min(100.0, float(raw)))

            # Neutral baseline per dimension (STRAT-RADAR-01)
            is_quiz_dim = axis in ["Accuracy", "Consistency", "Velocity"]
            if (
                (
                    is_quiz_dim
                    and agg_metrics.get("m01_total_quiz_attempts", {}).get("raw", 0)
                    == 0
                )
                or (
                    axis == "Coding"
                    and agg_metrics.get("m12_coding_attempts", {}).get("raw", 0) == 0
                )
                or (
                    axis == "Assignment"
                    and agg_metrics.get("m16_assignment_rate", {}).get("raw", 0) == 0
                )
            ):
                val = 50.0

            agg_radar_data.append({"subject": axis, "A": val, "fullMark": 100})
            agg_weighted_sum += val * weights[axis]

        return {
            "metrics": agg_metrics,
            "charts": {
                "topic_mastery": agg_topic_mastery,
                "best_topic": agg_topic_mastery[0] if agg_topic_mastery else None,
                "worst_topic": agg_topic_mastery[-1] if agg_topic_mastery else None,
                "member_count": count,
                "total_attempts": total_attempts,
                "radar_data": agg_radar_data,
                "weighted_proficiency": round(agg_weighted_sum, 1),
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


performance_engine = PerformanceEngine()
