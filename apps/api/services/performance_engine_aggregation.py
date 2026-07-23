import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List

import models
from cache_manager import cache_manager
from sqlalchemy.orm import Session

logger = logging.getLogger("performance_engine")

# Concurrent per-user vector computations during batch/global aggregation.
# Bounded so a large cohort cannot exhaust the DB connection pool.
AGGREGATE_CONCURRENCY = int(os.environ.get("AGGREGATE_CONCURRENCY", "5"))


class _AggregationMixin:
    """Mixin providing batch and global performance vector aggregation."""

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
