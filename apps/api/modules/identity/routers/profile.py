"""profile endpoints (moved verbatim from routers/auth.py)."""
from services.s3_service import sign_media_url
from fastapi import APIRouter

from modules.identity.routers.auth_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/profile")
async def get_my_detailed_profile(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(verify_token)
):
    """PHASE-3: Retrieve the current user's high-fidelity profile with performance vectors."""
    user_id = int(current_user["sub"])
    # `user.group` is read below; eager-load it, since a lazy load outside
    # run_sync raises MissingGreenlet on an AsyncSession.
    user = await db.run_sync(
        lambda s: s.query(models.User)
        .options(selectinload(models.User.group))
        .filter(models.User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Entity not found")

    from services.performance_engine import performance_engine

    profile_data = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "bio": user.bio,
        "custom_slug": user.custom_slug,
        "profile_photo_url": sign_media_url(user.profile_photo_url),
        "cover_photo_url": sign_media_url(user.cover_photo_url),
        "intro_video_url": user.intro_video_url,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "expertise": user.expertise_json or {},
        "streak_count": user.streak_count,
        "group_id": user.group_id,
        "group_name": user.group.name if user.group else None,
        "performance_vectors": await performance_engine.get_user_vectors(user.id, db),
    }
    return profile_data

@router.patch("/profile")
def update_my_profile(
    req: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """User-driven profile enhancement."""
    user_id = int(current_user["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_fields = [
        "full_name",
        "bio",
        "custom_slug",
        "profile_photo_url",
        "cover_photo_url",
        "intro_video_url",
        "github_url",
        "linkedin_url",
        "leetcode_url",
        "codolio_url",
    ]

    for field, value in req.items():
        if field in allowed_fields:
            if field == "custom_slug" and value:
                # Validate slug uniqueness
                existing = (
                    db.query(models.User)
                    .filter(models.User.custom_slug == value, models.User.id != user_id)
                    .first()
                )
                if existing:
                    raise HTTPException(status_code=400, detail="Slug already taken")
            setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return {"status": "success", "user_id": user.id}

@router.get("/profile/{slug}")
def get_profile_by_slug(slug: str, db: Session = Depends(get_db)):
    """Retrieve public profile by custom slug."""
    user = db.query(models.User).filter(models.User.custom_slug == slug).first()
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": user.id,
        "full_name": user.full_name,
        "bio": user.bio,
        "profile_photo_url": sign_media_url(user.profile_photo_url),
        "cover_photo_url": sign_media_url(user.cover_photo_url),
        "role": user.role,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "streak_count": user.streak_count,
        "last_active": user.last_active_date,
    }

@router.delete("/profile/photo")
def delete_profile_photo(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Remove user's profile photo and cleanup S3."""
    user_id = int(current_user["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.profile_photo_url and settings.S3_BUCKET_NAME and settings.S3_BUCKET_NAME in str(user.profile_photo_url):
        try:
            # Extract key from URL
            # Expected format: https://bucket.s3.region.amazonaws.com/key
            from services.s3_service import delete_s3_object

            s3_key = str(user.profile_photo_url).split(".amazonaws.com/")[-1]
            delete_s3_object(s3_key)
        except Exception as e:
            logger.error(f"Failed to delete S3 profile photo: {e}")

    user.profile_photo_url = None
    db.commit()
    return {"success": True}

@router.post("/upload-url")
def get_upload_url(
    filename: str, file_type: str, current_user: dict = Depends(verify_token)
):
    """PHASE-3: S3 Presigned URL for direct secure uploads."""
    from services.s3_service import generate_profile_upload_url

    ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "video/mp4"]
    if file_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_type}' is not permitted for upload.",
        )

    user_id = int(current_user["sub"])
    return generate_profile_upload_url(
        user_id=user_id, filename=filename, file_type=file_type
    )

@router.get("/users/discovery")
def discovery_users(
    q: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    group_id: Optional[int] = Query(None, description="Filter by group ID"),
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    assert_group_in_org(group_id, db, current_user)
    logger.info(
        f"User discovery requested by {current_user.get('sub')} (Role: {current_user.get('role')})"
    )
    if int(current_user["sub"]) != 0 and current_user["role"] not in [
        "LDAdmin",
        "Mentor",
        "GroupAdmin",
        "Member",
    ]:
        logger.warning(
            f"SEC-101: User {current_user.get('sub')} with role {current_user.get('role')} denied discovery"
        )
        raise HTTPException(
            status_code=403,
            detail="Only Administrative roles can access user discovery",
        )

    # Scoping Enforcement (SEC-101)
    if current_user["role"] != "LDAdmin":
        if not group_id:
            # If no group_id specified, default to their primary group
            group_id = int(current_user.get("group_id", 0))

        # Verify they actually have access to this group_id
        from auth_utils import check_scoped_role

        has_access = False
        if int(current_user.get("group_id", 0)) == group_id:
            has_access = True
        elif check_scoped_role(
            int(current_user["sub"]), current_user["role"], "group", group_id, db
        ):
            has_access = True

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Your scope is restricted to your assigned sectors.",
            )

    query = (
        db.query(models.User)
        .join(models.Group)
        .outerjoin(models.Batch)
        .outerjoin(models.Vertical)
        .outerjoin(models.Department)
        .outerjoin(models.Organization)
    )

    # L&D admins see their whole ENTERPRISE (super-org) — not every customer's
    # users. This also makes the L&D filter dropdowns show a consistent set.
    from auth_utils import caller_super_org_id, is_ld_admin_plus, is_platform_admin

    if not is_platform_admin(current_user) and is_ld_admin_plus(current_user):
        _sid = caller_super_org_id(current_user, db)
        if _sid is None:
            return {"items": [], "total": 0, "page": page, "size": size, "pages": 0}
        query = query.filter(models.Organization.super_organization_id == _sid)

    if q:
        query = query.filter(
            (models.User.full_name.ilike(f"%{q}%"))
            | (models.User.email.ilike(f"%{q}%"))
        )
    if role:
        query = query.filter(models.User.role == role)
    if group_id:
        query = query.filter(models.User.group_id == group_id)

    paginated = paginate(query.order_by(models.User.full_name.asc()), page, size)

    results = []
    for u in paginated.items:
        group = u.group
        batch = group.batch if group else None
        vertical = batch.vertical if batch else None
        dept = vertical.department if vertical else None
        org = dept.organization if dept else None

        results.append(
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "group_name": group.name if group else None,
                "batch_name": batch.name if batch else None,
                "vertical_name": vertical.name if vertical else None,
                "dept_name": dept.name if dept else None,
                "org_name": org.name if org else None,
                "is_active": u.is_active == True,
                "created_at": u.created_at,
            }
        )

    return {
        "items": results,
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
        "pages": paginated.pages,
    }

@router.get("/users/{user_id}/insights")
async def get_user_insights(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Enterprise-grade Member Intel Engine.
    Synthesizes recursive activity, algorithmic success, and collaborative metrics
    into a professional AI-powered growth narrative (FUNC-001).
    """
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(
            status_code=403,
            detail="Strategic Violation: Insufficient authorization for entity intel sync.",
        )

    user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.id == user_id).first())
    if not user:
        raise HTTPException(
            status_code=404, detail="Entity ID not detected in registry."
        )

    # SCOPE ENFORCEMENT
    if current_user["role"] != "LDAdmin" and user.group_id != current_user.get(
        "group_id"
    ):
        raise HTTPException(
            status_code=403,
            detail="Boundary Breach: Entity exists in an isolated node.",
        )

    # 1. Synchronization Activity (Quiz Attempts)
    quiz_attempts = (
        await db.run_sync(lambda s: s.query(models.Attempt)
        .filter(models.Attempt.user_id == user_id)
        .order_by(models.Attempt.attempted_at.asc())
        .all())
    )

    # 2. Algorithmic Lab Participation (Coding Attempts)
    coding_attempts = (
        await db.run_sync(lambda s: s.query(models.CodingAttempt)
        .filter(models.CodingAttempt.user_id == user_id)
        .order_by(models.CodingAttempt.attempted_at.asc())
        .all())
    )

    # 3. Collaborative Intelligence (Discussions)
    discussions_count = (
        await db.run_sync(lambda s: s.query(models.QuestionDiscussion)
        .filter(models.QuestionDiscussion.user_id == user_id)
        .count())
    )

    # --- Topic Mastery Analysis ---
    topic_data = {}
    for attempt in quiz_attempts:
        bank = (
            await db.run_sync(lambda s: s.query(models.QuestionBank)
            .filter(models.QuestionBank.id == attempt.bank_id)
            .first())
        )
        if bank and bank.chapter:
            if bank.chapter not in topic_data:
                topic_data[bank.chapter] = {"score": 0, "total": 0, "count": 0}
            topic_data[bank.chapter]["score"] += attempt.score or 0
            topic_data[bank.chapter]["total"] += (
                attempt.total or 1
            )  # Prevent div by zero
            topic_data[bank.chapter]["count"] += 1

    mastery_report = [
        {
            "topic": t,
            "accuracy": round((s["score"] / s["total"] * 100), 1),
            "volume": s["count"],
            "status": "Elite"
            if (s["score"] / s["total"]) > 0.9
            else "Sync"
            if (s["score"] / s["total"]) > 0.7
            else "Fragile",
        }
        for t, s in topic_data.items()
    ]

    # --- Temporal Consistency & Streak Calculation ---
    today = datetime.datetime.now(datetime.timezone.utc).date()
    timeline = []
    active_dates = set()

    # Track quiz + code activity
    for a in quiz_attempts:
        active_dates.add(a.attempted_at.date())
    for c in coding_attempts:
        active_dates.add(c.attempted_at.date())

    # Calculate Streak (consecutive active days backwards from today/yesterday)
    streak = 0
    check_day = today
    # If not active today, check if yesterday was the end of a streak
    if today not in active_dates:
        check_day = today - datetime.timedelta(days=1)

    while check_day in active_dates:
        streak += 1
        check_day -= datetime.timedelta(days=1)

    for i in range(29, -1, -1):
        day = today - datetime.timedelta(days=i)
        activity = len(
            [a for a in quiz_attempts if a.attempted_at.date() == day]
        ) + len([c for c in coding_attempts if c.attempted_at.date() == day])
        timeline.append({"date": day.strftime("%Y-%m-%d"), "activity": activity})

    # --- Scientific Benchmarking ---
    total_q = len(quiz_attempts)
    avg_acc = (
        round(
            sum([a.score for a in quiz_attempts])
            / sum([a.total for a in quiz_attempts])
            * 100,
            1,
        )
        if sum([a.total for a in quiz_attempts]) > 0
        else 0
    )
    total_c = len(coding_attempts)
    code_success = (
        round(
            len([c for c in coding_attempts if c.overall_result == "correct"])
            / total_c
            * 100,
            1,
        )
        if total_c > 0
        else 0
    )

    # Consistency = Active Days / 30
    active_days_count = len(
        [d for d in active_dates if d >= (today - datetime.timedelta(days=30))]
    )
    consistency_score = round((active_days_count / 30) * 100, 1)

    # --- Phase 5: Peer-benchmarking & Study Path ---
    group_users = (
        await db.run_sync(lambda s: s.query(models.User.id).filter(models.User.group_id == user.group_id).all())
    )
    group_user_ids = [gu[0] for gu in group_users]
    group_attempts = (
        await db.run_sync(lambda s: s.query(models.Attempt)
        .filter(models.Attempt.user_id.in_(group_user_ids))
        .all())
    )
    group_acc = (
        round(
            sum([a.score for a in group_attempts])
            / sum([a.total for a in group_attempts])
            * 100,
            1,
        )
        if group_attempts and sum([a.total for a in group_attempts]) > 0
        else 0
    )

    attempted_bank_ids = list(set([a.bank_id for a in quiz_attempts]))
    suggested_banks = (
        await db.run_sync(lambda s: s.query(models.QuestionBank)
        .filter(
            ~models.QuestionBank.id.in_(attempted_bank_ids)
            if attempted_bank_ids
            else models.QuestionBank.id.isnot(None),
            models.QuestionBank.is_org_public,  # simplified condition for suggested path
        )
        .limit(3)
        .all())
    )
    study_path = [
        {"id": b.id, "name": b.name, "chapter": b.chapter} for b in suggested_banks
    ]

    # Weighted Proficiency: 60% Quiz, 40% Coding (Neural Balancing)
    weighted_proficiency = round((avg_acc * 0.6) + (code_success * 0.4), 1)

    # --- Activity Logs (Chronological Trace) ---
    raw_logs = []
    # Mix and sort by time
    for a in quiz_attempts:
        bank = (
            await db.run_sync(lambda s: s.query(models.QuestionBank)
            .filter(models.QuestionBank.id == a.bank_id)
            .first())
        )
        raw_logs.append(
            {
                "type": "QUIZ",
                "title": bank.name if bank else "Assessment",
                "result": f"{a.score}/{a.total}",
                "timestamp": a.attempted_at.isoformat(),
            }
        )
    for c in coding_attempts:
        raw_logs.append(
            {
                "type": "CODE",
                "title": c.question.title if c.question else "Algorithm Lab",
                "result": c.overall_result.upper() if c.overall_result else "UNKNOWN",
                "timestamp": c.attempted_at.isoformat(),
            }
        )
    raw_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    raw_logs = raw_logs[:25]

    insights_payload = {
        "user_id": user_id,
        "full_name": user.full_name,
        "group_id": user.group_id,
        "metrics": {
            "synchronization": {
                "avg_accuracy": avg_acc,
                "volume": total_q,
                "topic_mastery": mastery_report,
            },
            "algorithmic_lab": {"success_rate": code_success, "volume": total_c},
            "advanced": {
                "weighted_proficiency": weighted_proficiency,
                "consistency_score": consistency_score,
                "streak": streak,
                "intel_contributions": discussions_count,
                "group_average_accuracy": group_acc,
            },
            "study_path": study_path,
            "timeline": timeline,
        },
        "raw_logs": raw_logs,
    }

    # AI SYNC PROTOCOL
    ai_narrative = await ai_executive.generate_member_summary(
        member_name=user.full_name, insights=insights_payload["metrics"]
    )

    insights_payload["ai_narrative"] = ai_narrative
    return insights_payload

@router.post("/presigned-upload-profile")
def get_profile_presigned_url(
    req: ProfilePhotoUploadRequest, current_user: dict = Depends(verify_token)
):
    """
    Generates a pre-signed POST policy for the frontend to upload a profile photo.
    """
    user_id = int(current_user["sub"])
    try:
        # SEC-FIX: Restrict upload path to user's own profile folder
        data = generate_profile_upload_url(
            user_id=user_id, filename=req.file_name, file_type=req.file_type
        )
        return data
    except Exception as e:
        logger.error(f"Profile upload URL generation failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during S3 URL generation"
        )

@router.get("/profile/{email_prefix}", response_model=schemas.UserResponse)
def get_public_profile(
    email_prefix: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Retrieve public profile for any user in the organization."""
    # Find user where email starts with prefix and followed by @
    user = (
        db.query(models.User)
        .filter(models.User.email.like(f"{email_prefix}@%"))
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return user

@router.get("/users/search")
def search_users(
    q: str, db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Fuzzy user search by name or email — available to GroupAdmin, Mentor, LDAdmin."""
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    search = f"%{q}%"
    query = db.query(models.User).filter(
        (models.User.full_name.ilike(search)) | (models.User.email.ilike(search))
    )

    # Scope: non-LDAdmin can only search their group
    if current_user["role"] != "LDAdmin":
        group_id = current_user.get("group_id")
        if group_id:
            query = query.filter(models.User.group_id == group_id)

    users = query.limit(30).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "group_id": u.group_id,
            "is_active": u.is_active == True,
        }
        for u in users
    ]
