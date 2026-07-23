"""cohort comparative-analytics endpoint (split verbatim from cohort_analytics.py to stay under the 800-line cap)."""
from fastapi import APIRouter

from modules.reporting.routers.cohort_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/analytics/comparative")
async def get_comparative_analytics(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(require_ldadmin)
):
    """Global KPIs for the L&D Admin dashboard."""
    import json

    from cache_manager import redis_client

    redis_key = "reports:comparative_analytics"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    total_users = await db.run_sync(lambda s: s.query(models.User).count())
    active_users_30d = (
        await db.run_sync(lambda s: s.query(models.User)
        .join(models.Attempt)
        .filter(
            models.Attempt.attempted_at
            >= datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=30)
        )
        .distinct()
        .count())
    )

    # Unified attempts (PHASE-3 alignment)
    attempts = await db.run_sync(lambda s: s.query(models.Attempt).all())
    coding_attempts = await db.run_sync(lambda s: s.query(models.CodingAttempt).all())

    total_score = sum((a.score or 0) for a in attempts)
    total_points = sum((a.total or 0) for a in attempts)

    # Add coding scores (scaled to 100 for consistency)
    total_score += sum(
        (ca.score or 0) for ca in coding_attempts if ca.score is not None
    )
    total_points += sum(100 for ca in coding_attempts if ca.score is not None)

    # Calculate weak topics (accuracy < 60%)
    banks = await db.run_sync(lambda s: s.query(models.QuestionBank).all())
    weak_count = 0
    topic_accuracy = {}
    for bank in banks:
        bank_atts = [a for a in attempts if a.bank_id == bank.id]
        if not bank_atts:
            continue
        b_total_score = sum((a.score or 0) for a in bank_atts)
        b_total_points = sum((a.total or 0) for a in bank_atts)
        bank_acc = (b_total_score / b_total_points) * 100 if b_total_points > 0 else 0
        topic_accuracy[bank.name] = bank_acc
        if bank_acc < 60:
            weak_count += 1

    # Add coding topics to trends
    coding_questions = await db.run_sync(lambda s: s.query(models.CodingQuestion).all())
    for cq in coding_questions:
        cq_atts = [
            ca
            for ca in coding_attempts
            if getattr(ca, "coding_question_id") == getattr(cq, "id") and getattr(ca, "score") is not None
        ]
        if not cq_atts:
            continue
        cq_acc = sum(getattr(ca, "score") or 0 for ca in cq_atts) / len(cq_atts)
        topic_accuracy[f"Code: {cq.title}"] = cq_acc
        if cq_acc < 60:
            weak_count += 1

    # --- Enhanced Multi-Level Performance ---
    # Eager-load departments: `org.departments` is traversed below, and a lazy load
    # outside run_sync raises MissingGreenlet on an AsyncSession.
    orgs = await db.run_sync(
        lambda s: s.query(models.Organization)
        .options(selectinload(models.Organization.departments))
        .all()
    )
    org_stats = []
    for org in orgs:
        # Get all users in this org
        dept_ids = [d.id for d in org.departments]
        vert_ids = [
            v.id
            for v in await db.run_sync(lambda s: s.query(models.Vertical)
            .filter(models.Vertical.department_id.in_(dept_ids))
            .all())
        ]
        batch_ids = [
            b.id
            for b in await db.run_sync(lambda s: s.query(models.Batch)
            .filter(models.Batch.vertical_id.in_(vert_ids))
            .all())
        ]
        group_ids = [
            g.id
            for g in await db.run_sync(lambda s: s.query(models.Group)
            .filter(models.Group.batch_id.in_(batch_ids))
            .all())
        ]

        org_attempts = (
            await db.run_sync(lambda s: s.query(models.Attempt)
            .join(models.User)
            .filter(models.User.group_id.in_(group_ids))
            .all())
        )
        if not org_attempts:
            continue

        o_score = sum((a.score or 0) for a in org_attempts)
        o_points = sum((a.total or 0) for a in org_attempts)
        o_acc = (o_score / o_points * 100) if o_points > 0 else 0
        org_stats.append({"label": org.name, "value": round(o_acc, 1)})

    # Trends: most active banks/topics
    sorted_topics = sorted(topic_accuracy.items(), key=lambda x: x[1], reverse=True)[:5]
    recent_trends = [
        {
            "label": t[0],
            "value": round(t[1], 1),
            "color": "text-emerald-400"
            if t[1] > 80
            else "text-indigo-400"
            if t[1] > 60
            else "text-rose-400",
        }
        for t in sorted_topics
    ]

    # Calculate real uptake trend (last 30d vs 30d-60d)
    now = datetime.datetime.now(datetime.timezone.utc)
    # Combine user activity from both types. The sub-queries are Query objects
    # combined with .union(), so they must be built and consumed together inside
    # a single run_sync block.
    def _active_counts(sync_db):
        q30 = sync_db.query(models.Attempt.user_id).filter(
            models.Attempt.attempted_at >= now - datetime.timedelta(days=30)
        )
        c30 = sync_db.query(models.CodingAttempt.user_id).filter(
            models.CodingAttempt.attempted_at >= now - datetime.timedelta(days=30)
        )
        last_30 = (
            sync_db.query(models.User)
            .filter(models.User.id.in_(q30.union(c30)))
            .count()
        )

        q60 = sync_db.query(models.Attempt.user_id).filter(
            models.Attempt.attempted_at < now - datetime.timedelta(days=30),
            models.Attempt.attempted_at >= now - datetime.timedelta(days=60),
        )
        c60 = sync_db.query(models.CodingAttempt.user_id).filter(
            models.CodingAttempt.attempted_at < now - datetime.timedelta(days=30),
            models.CodingAttempt.attempted_at >= now - datetime.timedelta(days=60),
        )
        prev_30 = (
            sync_db.query(models.User)
            .filter(models.User.id.in_(q60.union(c60)))
            .count()
        )
        return last_30, prev_30

    active_30d, active_60d_30d = await db.run_sync(_active_counts)

    diff = active_30d - active_60d_30d
    trend_symbol = "+" if diff >= 0 else "-"
    uptake_trend = f"{trend_symbol}{abs(diff)} Active Delta"

    res = {
        "system_uptake": round((active_users_30d / total_users * 100), 1)
        if total_users > 0
        else 0,
        "uptake_trend": uptake_trend,
        "global_avg_accuracy": round((total_score / total_points * 100), 1)
        if total_points > 0
        else 0,
        "average_proficiency": round((total_score / total_points * 100), 1)
        if total_points > 0
        else 0,
        "active_users": active_users_30d,
        "weak_topics_count": weak_count,
        "recent_trends": recent_trends,
        "org_performance": org_stats[:5],
        "health_status": "Cluster Operational"
        if active_users_30d > 0
        else "Low Activity",
    }

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return res

