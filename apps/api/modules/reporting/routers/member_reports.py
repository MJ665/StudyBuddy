"""member_reports endpoints (moved verbatim from routers/reports.py)."""
from fastapi import APIRouter

from modules.reporting.routers.reports_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/member/{user_id}/growth-atlas")
async def get_member_growth_atlas(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """PHASE-3: Generate exactly 30 granular growth insights for a learner."""
    # assert_user_in_org is the ONE sync implementation of this rule; run it
    # against this async session's own connection (AsyncSession has no .query).
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    from services.user_service import user_service

    res = await user_service.get_user_atlas(user_id, db)
    if not res:
        raise HTTPException(status_code=404, detail="Member not found")
    return res

@router.get("/analytics/consistency/{user_id}")
def get_user_consistency(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """
    Section 12 Method #15 — Consistency Index (CV: Coefficient of Variation)
    CV = (SD / mean) × 100 — lower = more consistent
    """
    assert_user_in_org(user_id, db, current_user)
    attempts = db.query(models.Attempt).filter(models.Attempt.user_id == user_id).all()
    if not attempts:
        return {"cv": None, "interpretation": "No data"}

    scores = [
        (a.score / a.total * 100) if a.total and a.total > 0 else 0 for a in attempts
    ]
    mean = sum(scores) / len(scores)
    if mean == 0:
        return {"cv": None, "mean": 0, "interpretation": "Zero mean — no scoring data"}
    std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores))
    cv = (std / mean) * 100

    interpretation = (
        "Highly Consistent"
        if cv < 15
        else "Consistent"
        if cv < 30
        else "Moderate Variance"
        if cv < 50
        else "High Variance — Irregular Performance"
    )

    return {
        "user_id": user_id,
        "attempt_count": len(scores),
        "mean_accuracy": round(mean, 1),
        "std_dev": round(std, 2),
        "cv": round(cv, 1),
        "interpretation": interpretation,
    }

@router.get("/analytics/learning-velocity/{user_id}")
async def get_learning_velocity(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """
    Section 12 Method #1 — Learning Velocity Curve (Linear Regression over time)
    Returns slope (positive = improving) and per-attempt accuracy trend.
    """
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    import json

    redis_key = f"reports:learn_vel:{user_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    attempts = (
        await db.run_sync(lambda s: s.query(models.Attempt)
        .filter(models.Attempt.user_id == user_id)
        .order_by(models.Attempt.attempted_at)
        .all())
    )

    if len(attempts) < 2:
        return {"velocity": 0, "trend": [], "interpretation": "Insufficient data"}

    xs = list(range(len(attempts)))
    ys = [(a.score / a.total * 100) if a.total and a.total > 0 else 0 for a in attempts]

    n = len(xs)
    sum_x = sum(xs)
    sum_y = sum(ys)
    sum_xy = sum(x * y for x, y in zip(xs, ys))
    sum_x2 = sum(x**2 for x in xs)

    denominator = n * sum_x2 - sum_x**2
    slope = (n * sum_xy - sum_x * sum_y) / denominator if denominator != 0 else 0

    interpretation = (
        "Strong positive velocity"
        if slope > 2
        else "Improving"
        if slope > 0.5
        else "Stable"
        if slope > -0.5
        else "Declining — intervention recommended"
    )

    res = {
        "user_id": user_id,
        "slope": round(slope, 3),
        "interpretation": interpretation,
        "trend": [
            {
                "attempt": i + 1,
                "accuracy": round(y, 1),
                "date": str(attempts[i].attempted_at.date()),
            }
            for i, y in enumerate(ys)
        ],
    }
    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass
    return res

@router.get("/member/{user_id}/registry")
async def get_member_registry(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """FUNC-004: Comprehensive usage registry for a specific member."""
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    from services.user_service import user_service

    res = await user_service.get_user_registry(user_id, db)
    if not res:
        raise HTTPException(status_code=404, detail="User not found")
    return res

@router.get("/analytics/heatmap/{user_id}")
async def get_user_activity_heatmap(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Returns 52 weeks (364 days) of daily activity counts — quiz + coding attempts.
    Powers the GitHub-style contribution heatmap on the UserProfile page.
    Accessible by: Self, Mentor (own group), GroupAdmin (own group), LDAdmin.
    """
    await db.run_sync(lambda s: assert_user_in_org(user_id, s, current_user))
    import json

    redis_key = f"reports:heatmap:{user_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # Scope check: self, group-scoped admin/mentor, or LDAdmin
    calling_id = int(current_user["sub"])
    calling_role = current_user.get("role", "Member")

    if calling_id != user_id and calling_role not in [
        "LDAdmin",
        "Mentor",
        "GroupAdmin",
    ]:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.id == user_id).first())
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Boundary check for non-LDAdmin
    if calling_role not in ["LDAdmin"] and calling_id != user_id:
        if user.group_id != current_user.get("group_id"):
            raise HTTPException(status_code=403, detail="Boundary violation")

    today = datetime.date.today()
    start = today - datetime.timedelta(days=363)  # 52 weeks

    # Gather all activity timestamps
    quiz_dates = (
        await db.run_sync(lambda s: s.query(models.Attempt.attempted_at)
        .filter(
            models.Attempt.user_id == user_id,
            models.Attempt.attempted_at
            >= datetime.datetime.combine(start, datetime.time.min),
        )
        .all())
    )

    code_dates = (
        await db.run_sync(lambda s: s.query(models.CodingAttempt.attempted_at)
        .filter(
            models.CodingAttempt.user_id == user_id,
            models.CodingAttempt.attempted_at
            >= datetime.datetime.combine(start, datetime.time.min),
        )
        .all())
    )

    # Build day → count map
    day_counts: dict = {}
    for (ts,) in quiz_dates:
        day = ts.date() if ts else None
        if day:
            day_counts[day] = day_counts.get(day, 0) + 1
    for (ts,) in code_dates:
        day = ts.date() if ts else None
        if day:
            day_counts[day] = day_counts.get(day, 0) + 1

    # Build ordered list of all 364 days
    heatmap = []
    for i in range(364):
        day = start + datetime.timedelta(days=i)
        heatmap.append(
            {
                "date": day.strftime("%Y-%m-%d"),
                "count": day_counts.get(day, 0),
                "weekday": day.weekday(),  # 0=Mon,6=Sun
            }
        )

    total_active_days = sum(1 for d in heatmap if d["count"] > 0)
    max_day_count = max((d["count"] for d in heatmap), default=0)

    res = {
        "user_id": user_id,
        "heatmap": heatmap,
        "total_active_days": total_active_days,
        "max_day_count": max_day_count,
        "period_start": start.strftime("%Y-%m-%d"),
        "period_end": today.strftime("%Y-%m-%d"),
    }
    try:
        await redis_client.set(redis_key, json.dumps(res), ex=21600)
    except Exception:
        pass
    return res
