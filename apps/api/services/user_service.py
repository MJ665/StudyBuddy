import datetime
import json
import logging

import models
from services.ai_reporting import ai_executive
from services.performance_engine import performance_engine
from services.redis_service import redis_client
from sqlalchemy import or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class UserService:
    async def get_user_registry(self, user_id: int, db):
        """Async entry point; the body below is synchronous SQLAlchemy work.

        It was declared `async def` but never awaited anything, so all 127 lines
        of queries ran directly on the event loop and blocked every other request.
        Accepts either session type while routers migrate incrementally.
        """
        from fastapi.concurrency import run_in_threadpool
        from sqlalchemy.ext.asyncio import AsyncSession

        if isinstance(db, AsyncSession):
            return await db.run_sync(
                lambda sync_db: self._compute_user_registry(user_id, sync_db)
            )
        return await run_in_threadpool(self._compute_user_registry, user_id, db)

    def _compute_user_registry(self, user_id: int, db: Session):
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None

        quiz_attempts = (
            db.query(models.Attempt)
            .filter(models.Attempt.user_id == user_id)
            .order_by(models.Attempt.attempted_at.desc())
            .all()
        )
        coding_attempts = (
            db.query(models.CodingAttempt)
            .filter(models.CodingAttempt.user_id == user_id)
            .order_by(models.CodingAttempt.attempted_at.desc())
            .all()
        )

        # Bank and Question lookups
        bank_names = {
            b.id: b.name
            for b in db.query(models.QuestionBank)
            .filter(models.QuestionBank.id.in_([a.bank_id for a in quiz_attempts]))
            .all()
        }
        coding_question_names = {
            q.id: q.title
            for q in db.query(models.CodingQuestion)
            .filter(
                models.CodingQuestion.id.in_(
                    [a.coding_question_id for a in coding_attempts]
                )
            )
            .all()
        }

        # Topic Breakdown
        topic_data: dict[str, dict[str, list[float]]] = {}
        for a in quiz_attempts:
            if a.total and a.total > 0:
                name = bank_names.get(a.bank_id, "General")
                if name not in topic_data:
                    topic_data[name] = {"scores": []}
                topic_data[name]["scores"].append((a.score / a.total) * 100)

        topic_breakdown = {
            t: {"avg": sum(v["scores"]) / len(v["scores"])}
            for t, v in topic_data.items()
        }

        # Assignment Completion logic (Aligned with AssignmentService)
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

        total_asgn = (
            db.query(models.Assignment)
            .filter(models.Assignment.is_active.is_(True), or_(*target_filters))
            .count()
        )
        done_asgn = (
            db.query(models.AssignmentCompletion)
            .filter(
                models.AssignmentCompletion.user_id == user_id,
            )
            .count()
        )

        # Ranking
        rank = 1
        group_size = (
            db.query(models.User)
            .filter(models.User.group_id == user.group_id, models.User.is_active.is_(True))
            .count()
        )

        return {
            "user_id": user_id,
            "full_name": user.full_name,
            "quiz_attempts": [
                {
                    "id": a.id,
                    "bank_name": bank_names.get(a.bank_id, "Unknown"),
                    "score": a.score,
                    "total": a.total,
                    "attempted_at": a.attempted_at.isoformat()
                    if a.attempted_at
                    else None,
                }
                for a in quiz_attempts
            ],
            "coding_attempts": [
                {
                    "id": a.id,
                    "question_id": a.coding_question_id,
                    "question_title": coding_question_names.get(
                        int(str(a.coding_question_id)) if a.coding_question_id is not None else 0, "Unknown"
                    ),
                    "score": a.score,
                    "attempted_at": a.attempted_at.isoformat()
                    if a.attempted_at is not None
                    else None,
                }
                for a in coding_attempts
            ],
            "topic_breakdown": topic_breakdown,
            "group_rank": rank,
            "group_size": group_size,
            "completion_rate": (done_asgn / total_asgn * 100) if total_asgn > 0 else 0,
            "assignments_completed": done_asgn,
            "total_assignments": total_asgn,
        }

    async def get_user_atlas(self, user_id: int, db):
        """Accepts EITHER a sync Session or an AsyncSession.

        Routers are migrating to AsyncSession one at a time, so this shared service
        has to work for both rather than forcing a big-bang cutover.
        """
        from sqlalchemy.ext.asyncio import AsyncSession

        if isinstance(db, AsyncSession):
            user = await db.get(models.User, user_id)
        else:
            user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            return None

        redis_key = f"user_atlas:{user_id}"
        try:
            cached = await redis_client.get(redis_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"user_atlas cache lookup failed: {e}")

        vectors = await performance_engine.get_user_vectors(user_id, db)
        atlas_envelope = await ai_executive.generate_member_growth_atlas(
            user.full_name, {"vectors": vectors}
        )

        result = {
            "vectors": vectors,
            "atlas": atlas_envelope.get("data", []),
            "from_cache": False,
        }

        try:
            await redis_client.set(redis_key, json.dumps(result), ex=21600)  # 6h TTL
        except Exception as e:
            logger.warning(f"user_atlas cache write failed: {e}")

        return result

    async def get_user_heatmap(self, user_id: int, db):
        """Async entry point; the body below is synchronous SQLAlchemy work.

        It was declared `async def` but never awaited anything, so all 56 lines
        of queries ran directly on the event loop and blocked every other request.
        Accepts either session type while routers migrate incrementally.
        """
        from fastapi.concurrency import run_in_threadpool
        from sqlalchemy.ext.asyncio import AsyncSession

        if isinstance(db, AsyncSession):
            return await db.run_sync(
                lambda sync_db: self._compute_user_heatmap(user_id, sync_db)
            )
        return await run_in_threadpool(self._compute_user_heatmap, user_id, db)

    def _compute_user_heatmap(self, user_id: int, db: Session):
        today = datetime.date.today()
        start = today - datetime.timedelta(days=363)

        quiz_dates = (
            db.query(models.Attempt.attempted_at)
            .filter(
                models.Attempt.user_id == user_id,
                models.Attempt.attempted_at
                >= datetime.datetime.combine(start, datetime.time.min),
            )
            .all()
        )

        code_dates = (
            db.query(models.CodingAttempt.attempted_at)
            .filter(
                models.CodingAttempt.user_id == user_id,
                models.CodingAttempt.attempted_at
                >= datetime.datetime.combine(start, datetime.time.min),
            )
            .all()
        )

        day_counts: dict[datetime.date, int] = {}
        for (ts,) in quiz_dates:
            day = ts.date() if ts else None
            if day:
                day_counts[day] = day_counts.get(day, 0) + 1
        for (ts,) in code_dates:
            day = ts.date() if ts else None
            if day:
                day_counts[day] = day_counts.get(day, 0) + 1

        heatmap = []
        total_active_days = 0
        max_day_count = 0
        for i in range(364):
            day = start + datetime.timedelta(days=i)
            count = day_counts.get(day, 0)
            heatmap.append(
                {
                    "date": day.strftime("%Y-%m-%d"),
                    "count": count,
                    "weekday": day.weekday(),
                }
            )
            if count > 0:
                total_active_days += 1
            if count > max_day_count:
                max_day_count = count

        return {
            "heatmap": heatmap,
            "total_active_days": total_active_days,
            "max_day_count": max_day_count,
        }


user_service = UserService()
