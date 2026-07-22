"""courses endpoints (moved verbatim from routers/quiz.py)."""
from fastapi import APIRouter

from modules.assessment.routers.quiz_shared import *  # noqa: F401,F403
from modules.assessment.routers.quiz_shared import (  # noqa: F401
    _certificate_token,
    _verify_certificate_token,
)

router = APIRouter()

@router.get("/courses")
async def get_courses(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    import json

    from cache_manager import redis_client

    # A group belongs to exactly one org; bind it to the caller's org.
    await db.run_sync(
        lambda sd: assert_group_in_org(group_id, sd, current_user)
    )

    redis_key = f"quiz:courses:{group_id}:{current_user['role']}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    if int(group_id) == 0 and current_user["role"] == "LDAdmin":
        # Admin view: fetch all active courses
        courses = await db.run_sync(lambda s: s.query(models.Course).filter(models.Course.is_active.is_(True)).all())
        res = [c.__dict__ for c in courses]
        for item in res:
            item.pop("_sa_instance_state", None)
        try:
            await redis_client.set(redis_key, json.dumps(res), ex=3600)
        except Exception:
            pass
        return courses

    group_id = int(group_id)
    group = await db.run_sync(lambda s: s.query(models.Group).filter(models.Group.id == group_id).first())
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    course_ids = set()

    # 1. Vertical-wide courses (V3 inheritance)
    if group.batch_id:
        batch = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.id == group.batch_id).first())
        if batch:
            vc_list = (
                await db.run_sync(lambda s: s.query(models.VerticalCourse)
                .filter(
                    models.VerticalCourse.vertical_id == batch.vertical_id,
                    models.VerticalCourse.is_active.is_(True),
                )
                .all())
            )
            for vc in vc_list:
                course_ids.add(vc.course_id)

    # 2. Group-specific subscriptions (Granular control)
    g_subs = (
        await db.run_sync(lambda s: s.query(models.GroupCourseSubscription)
        .filter(
            models.GroupCourseSubscription.group_id == group_id,
            models.GroupCourseSubscription.is_active.is_(True),
        )
        .all())
    )
    for sub in g_subs:
        course_ids.add(sub.course_id)

    # 3. Fallback: If no specific subscriptions exist, return all active courses
    # This ensures newly created courses (which have no banks yet) are visible to admins and users.
    if not course_ids:
        courses = await db.run_sync(lambda s: s.query(models.Course).filter(models.Course.is_active.is_(True)).all())
    else:
        courses = (
            await db.run_sync(lambda s: s.query(models.Course)
            .filter(models.Course.id.in_(list(course_ids)), models.Course.is_active.is_(True))
            .all())
        )

    res = [c.__dict__ for c in courses]
    for item in res:
        item.pop("_sa_instance_state", None)
    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return courses

@router.get("/courses/{course_id}/coding")
def get_course_coding_questions(
    course_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    # Verify course access via VerticalCourse
    course = db.query(models.Course).filter(models.Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    questions = (
        db.query(models.CodingQuestion)
        .filter(
            models.CodingQuestion.course_id == course_id,
            models.CodingQuestion.is_active.is_(True),
        )
        .all()
    )
    return questions

@router.post("/courses")
async def create_course(
    course: schemas.CourseCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_admin),
):
    # Standard: Courses are created by admins
    # In V3, courses can be global or vertical-scoped.
    # To keep compatibility with the current schemas.CourseCreate(name, group_id):
    # We create the course and link it to the group's vertical.
    
    from cache_manager import redis_client

    batch = None
    if course.group_id:
        group = (
            await db.run_sync(lambda s: s.query(models.Group).filter(models.Group.id == course.group_id).first())
        )
        if not group or not group.batch_id:
            raise HTTPException(
                status_code=400, detail="Group must belong to a batch to add courses"
            )

        batch = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.id == group.batch_id).first())
        if not batch:
            raise HTTPException(status_code=400, detail="Batch not found")

    new_course = models.Course(name=course.name)
    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)

    if course.group_id and batch:
        vc = models.VerticalCourse(vertical_id=batch.vertical_id, course_id=new_course.id)
        db.add(vc)
        await db.commit()

    # Invalidate cache for courses
    try:
        keys = await redis_client.list_keys("quiz:courses:*")
        if keys:
            for key in keys:
                await redis_client.delete(key)
    except Exception as e:
        print(f"Error invalidating course cache: {e}")

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_COURSE",
        resource_type="COURSE",
        resource_id=new_course.id,
        details={"name": new_course.name, "group_id": course.group_id},
    )

    return new_course

@router.post("/subscribe/vertical")
def subscribe_vertical(
    vertical_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Admin endpoint to link a course to a vertical (all batches/groups in it)."""
    existing = (
        db.query(models.VerticalCourse)
        .filter(
            models.VerticalCourse.vertical_id == vertical_id,
            models.VerticalCourse.course_id == course_id,
        )
        .first()
    )
    if existing:
        existing.is_active = True
        db.commit()
        return {"message": "Vertical subscription re-activated"}

    vc = models.VerticalCourse(vertical_id=vertical_id, course_id=course_id)
    db.add(vc)
    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="SUBSCRIBE_VERTICAL",
        resource_type="VERTICAL",
        resource_id=vertical_id,
        details={"course_id": course_id},
    )

    return {"message": "Course mandated for entire vertical pipeline"}

@router.post("/subscribe/group")
def subscribe_group(
    group_id: int,
    course_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """Admin endpoint to link a course to a specific group only."""
    assert_group_in_org(group_id, db, current_user)
    existing = (
        db.query(models.GroupCourseSubscription)
        .filter(
            models.GroupCourseSubscription.group_id == group_id,
            models.GroupCourseSubscription.course_id == course_id,
        )
        .first()
    )
    if existing:
        existing.is_active = True
        db.commit()
        return {"message": "Group subscription re-activated"}

    sub = models.GroupCourseSubscription(group_id=group_id, course_id=course_id)
    db.add(sub)
    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="SUBSCRIBE_GROUP",
        resource_type="GROUP",
        resource_id=group_id,
        details={"course_id": course_id},
    )

    return {"message": "Course successfully assigned to specific cohort"}

@router.get("/challenges")
def get_challenges(
    course_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    query = db.query(models.CodingQuestion).filter(models.CodingQuestion.is_active.is_(True))

    if course_id:
        query = query.filter(models.CodingQuestion.course_id == course_id)

    if current_user.get("role") != "LDAdmin":
        # Global Visibility: LDAdmin content is visible to everyone
        # Group Visibility: Course linked content is visible to those in the group
        user_group = (
            db.query(models.Group)
            .filter(models.Group.id == current_user["group_id"])
            .first()
        )
        accessible_course_ids = []
        if user_group and user_group.batch_id:
            batch = (
                db.query(models.Batch)
                .filter(models.Batch.id == user_group.batch_id)
                .first()
            )
            if batch:
                vc_list = (
                    db.query(models.VerticalCourse)
                    .filter(models.VerticalCourse.vertical_id == batch.vertical_id)
                    .all()
                )
                accessible_course_ids = [vc.course_id for vc in vc_list]

        query = query.filter(
            (models.CodingQuestion.course_id.in_(accessible_course_ids))
            | (
                db.query(models.User.role)
                .filter(models.User.id == models.CodingQuestion.created_by)
                .as_scalar()
                == "LDAdmin"
            )
            | (models.CodingQuestion.created_by == 0)
        )

    return query.order_by(models.CodingQuestion.created_at.desc()).all()

@router.get("/challenges/daily/results")
def get_daily_challenge_results(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Get today's group performance on the daily challenge."""
    from datetime import date

    today = date.today()
    group_id = int(current_user["group_id"])

    challenge = (
        db.query(models.DailyChallenge)
        .filter(
            models.DailyChallenge.group_id == group_id,
            models.DailyChallenge.challenge_date == today,
        )
        .first()
    )

    if not challenge:
        raise HTTPException(status_code=404, detail="No challenge for today")

    # Count group members who attempted today's challenge
    group_users = (
        db.query(models.User)
        .filter(models.User.group_id == group_id, models.User.is_active.is_(True))
        .all()
    )
    user_ids = [u.id for u in group_users]

    challenge_attempts = (
        db.query(models.Attempt)
        .filter(models.Attempt.is_daily_challenge, models.Attempt.user_id.in_(user_ids))
        .all()
    )

    # Filter for today
    today_attempts = [a for a in challenge_attempts if a.attempted_at.date() == today]

    correct_count = sum(1 for a in today_attempts if a.score > 0)
    total_count = len(today_attempts)

    return {
        "date": today,
        "participants": total_count,
        "correct": correct_count,
        "total_group_users": len(group_users),
    }

@router.get("/challenges/daily")
def get_daily_challenge(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    from datetime import date

    today = date.today()

    # LDAdmin / superadmin have no group — return a representative challenge or 204
    raw_gid = current_user.get("group_id")
    group_id = int(raw_gid) if raw_gid else 0
    if group_id == 0 or current_user.get("role") == "LDAdmin":
        # Return the first available challenge for today (admin preview) or empty
        challenge = (
            db.query(models.DailyChallenge)
            .filter(models.DailyChallenge.challenge_date == today)
            .first()
        )
        if not challenge:
            return {"message": "No daily challenges created yet.", "challenge": None}
        group_id = challenge.group_id

    challenge = (
        db.query(models.DailyChallenge)
        .filter(
            models.DailyChallenge.group_id == group_id,
            models.DailyChallenge.challenge_date == today,
        )
        .first()
    )

    if not challenge:
        # Fallback: trigger inline generation and re-query
        try:
            from tasks import generate_daily_challenges

            created_count = generate_daily_challenges()
            logger.info(
                f"🎯 [DAILY_CHALLENGE_V2_FIX] Generated: {created_count} challenges for {today}"
            )
            db.expire_all()
            challenge = (
                db.query(models.DailyChallenge)
                .filter(
                    models.DailyChallenge.group_id == group_id,
                    models.DailyChallenge.challenge_date == today,
                )
                .first()
            )
        except Exception as e:
            logger.error(f"Inline challenge generation failed: {e}")
            pass

    if not challenge:
        # If still not found, return a clear message instead of a hard 404
        logger.warning(
            f"No daily challenge found for group {group_id} on {today} even after sync."
        )
        return {
            "id": None,
            "date": str(today),
            "message": "Today's daily challenge is being synchronized. Please refresh in a moment.",
            "challenge": None,
        }

    q = (
        db.query(models.Question)
        .filter(models.Question.id == challenge.question_id)
        .first()
    )
    if not q:
        raise HTTPException(
            status_code=404, detail="Daily challenge question not found"
        )

    return {
        "id": challenge.id,
        "date": str(today),
        "question": {
            "id": q.id,
            "question": q.question,
            "options": q.options,
            "difficulty": q.difficulty,
            "bank_id": q.bank_id,
            "has_code": q.has_code if hasattr(q, "has_code") else False,
            "code_language": q.code_language if hasattr(q, "code_language") else None,
        },
    }
