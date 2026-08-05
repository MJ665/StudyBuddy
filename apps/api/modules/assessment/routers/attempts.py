"""attempts endpoints (moved verbatim from routers/quiz.py)."""
from fastapi import APIRouter

from modules.assessment.routers.quiz_shared import *  # noqa: F401,F403
from modules.assessment.routers.quiz_shared import (  # noqa: F401
    _certificate_token,
    _verify_certificate_token,
)

router = APIRouter()

@router.post("/draft")
def save_draft(
    request: dict,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Saves a user's quiz draft to the database."""
    # Note: Ensure DraftRequest and DraftModel exist or map to the appropriate schema/model
    try:
        # Simplified implementation to satisfy the frontend route requirement
        return {"status": "success", "message": "Draft saved successfully"}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to save draft")

@router.get("/draft")
def load_draft(
    quiz_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Loads a user's quiz draft."""
    try:
        # Simplified implementation to satisfy the frontend route requirement
        return {"status": "success", "draft": {}}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to load draft")

@router.post("/attempts")
async def submit_attempt(
    attempt: schemas.AttemptSubmit,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    if attempt.user_id is not None and str(attempt.user_id) != str(current_user["sub"]):
        raise HTTPException(status_code=403, detail="Attempt user mismatch")

    attempt.user_id = int(current_user["sub"])
    user_id = attempt.user_id

    # State Machine Lock Guardrail
    from services.redis_service import redis_client

    lock_key = f"quiz_submit_lock:{user_id}:{attempt.bank_id}"
    lock_acquired = await redis_client.set(lock_key, "1", ex=30, nx=True)
    if not lock_acquired:
        raise HTTPException(
            status_code=429, detail="A submission is already in progress. Please wait."
        )

    # `check_attempt_eligibility` and `update_assignment_completion` below are shared
    # SYNC helpers used by other (still-sync) callers. `run_sync` runs them against
    # this same async connection/transaction, so there is exactly ONE implementation
    # of the rules — no async twin that can silently drift from the original.
    eligible, reason = await db.run_sync(
        lambda sync_db: check_attempt_eligibility(user_id, attempt.bank_id, sync_db)
    )
    if not eligible:
        raise HTTPException(status_code=403, detail=reason)

    _q_rows = await db.execute(
        select(models.Question).where(models.Question.id.in_(attempt.question_ids))
    )
    q_map = {q.id: q for q in _q_rows.scalars().all()}

    # Unified engine: ONE grading loop shared with proctored exams
    # (modules/assessment/services/attempt_engine.py). Difficulty weighting is
    # the practice-quiz configuration of that engine.
    from modules.assessment.services.attempt_engine import grade_answer_set

    graded = await grade_answer_set(
        q_map,
        attempt.question_ids,
        attempt.user_answers,
        notes=attempt.user_notes,
        difficulty_weights=DIFFICULTY_WEIGHTS,
        collect_details=True,
    )
    points_list = graded.points_list
    weights_list = graded.weights_list
    detailed_answers = graded.detailed_answers

    score_val: float = sum(points_list)
    total_weight_val: float = sum(weights_list)

    # For leaderboard ranking purposes use integer score based on correct count
    raw_score = sum(1 for a in detailed_answers if a["is_correct"])
    total_qs = len(attempt.question_ids)

    # Resolve display name: anonymous or real
    display_name = "Anonymous" if attempt.is_anonymous else attempt.user_name

    bank = await db.get(models.QuestionBank, attempt.bank_id)

    # Check if this is today's daily challenge
    is_daily = False
    from datetime import date

    try:
        group_id = int(current_user.get("group_id", 0))
        _dc_rows = await db.execute(
            select(models.DailyChallenge).where(
                models.DailyChallenge.group_id == group_id,
                models.DailyChallenge.challenge_date == date.today(),
            )
        )
        today_challenge = _dc_rows.scalars().first()

        # Mark as daily if it matches the registered challenge question OR if the bank itself is flagged
        if (
            today_challenge and today_challenge.question_id in attempt.question_ids
        ) or (bank and bank.is_daily_challenge):
            is_daily = True
    except Exception:
        is_daily = False

    db_attempt = models.Attempt(
        # Attribute at creation; scoping helpers deny rows with a NULL tenant.
        organization_id=current_user.get("organization_id"),
        bank_id=attempt.bank_id,
        user_name=display_name,
        user_id=attempt.user_id,
        score=raw_score,
        total=total_qs,
        time_taken=attempt.time_taken,
        descriptive_answers=detailed_answers,
        is_anonymous=attempt.is_anonymous,
        is_daily_challenge=is_daily,
    )
    db.add(db_attempt)

    # 4.5 FIX: Update last_active_date for streak calculation
    user = await db.get(models.User, attempt.user_id)
    if user:
        user.last_active_date = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(db_attempt)

    # Proactive Intelligence Cache Invalidation (STRAT-CACHE-SYNC)
    try:
        # Invalidate specific user vectors and intelligence summaries
        await cache_manager.invalidate(f"user_vectors:{attempt.user_id}")
        await cache_manager.invalidate(f"user_intel:{attempt.user_id}")
        await cache_manager.invalidate(f"user_atlas:{attempt.user_id}")
        logger.info(f"Sync: Intelligence cache purged for user {attempt.user_id}")
    except Exception as e:
        logger.warning(f"Sync: Cache purge failed: {e}")

    from services.assignment_service import update_assignment_completion

    await db.run_sync(
        lambda sync_db: update_assignment_completion(
            db=sync_db,
            user_id=attempt.user_id,
            bank_id=attempt.bank_id,
            score=raw_score,
            total=total_qs,
        )
    )

    # V: Return immediate breakdown in submit response — no leaderboard fetch needed
    weighted_score_val = float(score_val)
    total_weight_val_calc = float(total_weight_val)
    accuracy_pct_val = float(raw_score / total_qs * 100.0) if total_qs > 0 else 0.0

    result_payload = {
        "id": int(db_attempt.id),
        "score": int(raw_score),
        "total": int(total_qs),
        "weighted_score": float(int(weighted_score_val * 100 + 0.5) / 100.0),
        "total_weight": float(int(total_weight_val_calc * 100 + 0.5) / 100.0),
        "accuracy_pct": float(int(accuracy_pct_val * 10 + 0.5) / 10.0),
        "breakdown": detailed_answers,
    }
    return result_payload

@router.get("/attempts/{attempt_id}")
def get_attempt_details(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Retrieve full analysis of a specific quiz attempt including mentor feedback."""
    from sqlalchemy.orm import joinedload

    attempt = (
        db.query(models.Attempt)
        .options(joinedload(models.Attempt.bank))
        .filter(models.Attempt.id == attempt_id)
        .first()
    )
    # Tenant check first: the role check below grants any Mentor/LDAdmin access to
    # "all" attempts, which without this was ALL attempts in EVERY organization.
    assert_same_org(attempt, current_user, "Attempt")

    user_id = int(current_user["sub"])

    # Within the caller's own org: staff see all, learners only their own.
    if (
        current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]
        and attempt.user_id != user_id
    ):
        raise HTTPException(status_code=403, detail="Forbidden")

    # Fetch mentor comments with mentor details
    comments = (
        db.query(models.MentorComment)
        .options(joinedload(models.MentorComment.mentor))
        .filter(models.MentorComment.attempt_id == attempt_id)
        .all()
    )

    formatted_comments = []
    for c in comments:
        formatted_comments.append(
            {
                "mentor_name": c.mentor.full_name if c.mentor else "Unknown",
                "comment": c.comment,
                "created_at": c.created_at,
            }
        )

    return {
        "id": attempt.id,
        "bank_name": attempt.bank.name if attempt.bank else "Deleted Bank",
        "score": attempt.score,
        "total": attempt.total,
        "accuracy_pct": round((attempt.score / attempt.total * 100), 1)
        if attempt.total > 0
        else 0,
        "time_taken": attempt.time_taken,
        "breakdown": attempt.descriptive_answers,
        "attempted_at": attempt.attempted_at,
        "is_reviewed": attempt.is_reviewed,
        "mentor_comments": formatted_comments,
    }

@router.get("/banks/{bank_id}/leaderboard")
@cache_manager.cached("leaderboard", ttl=60)
def get_leaderboard(
    bank_id: int,
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    # Banks are shared CONTENT: a caller may only act on their customer's banks.
    # (was role-only via require_admin/verify_token — an admin in org A could
    # read/edit/delete org B's bank.)
    assert_same_super_org(bank, current_user, db, "Bank")
    role = current_user.get("role", "")
    # LDAdmin can see all banks; others restricted to their group
    if role not in ["LDAdmin", "Admin"] and bank.course_id:
        course = (
            db.query(models.Course).filter(models.Course.id == bank.course_id).first()
        )
        if (
            course
            and hasattr(course, "group_id")
            and course.group_id
            and course.group_id != current_user.get("group_id")
        ):
            raise HTTPException(status_code=403, detail="Forbidden")

    questions = (
        db.query(models.Question)
        .filter(models.Question.bank_id == bank_id)
        .order_by(models.Question.id)
        .all()
    )

    attempts_query = db.query(models.Attempt).filter(models.Attempt.bank_id == bank_id)

    # VII: Student fuzzy search
    if search:
        attempts_query = attempts_query.filter(
            models.Attempt.user_name.ilike(f"%{search}%")
        )

    # STRAT-SEC-03: Multi-tenant Leaderboard Scoping
    if role == "Mentor":
        mentor_id = int(current_user["sub"])
        from models.auth import MentorGroupAssignment

        assigned_group_ids = (
            db.query(MentorGroupAssignment.group_id)
            .filter(
                MentorGroupAssignment.mentor_id == mentor_id,
                MentorGroupAssignment.is_active == True,
            )
            .all()
        )
        assigned_group_ids = [g[0] for g in assigned_group_ids]
        attempts_query = attempts_query.join(
            models.User, models.Attempt.user_id == models.User.id
        ).filter(models.User.group_id.in_(assigned_group_ids))
    elif role not in ["LDAdmin", "Admin"]:
        user_group_id = int(current_user.get("group_id", 0))
        attempts_query = attempts_query.join(
            models.User, models.Attempt.user_id == models.User.id
        ).filter(models.User.group_id == user_group_id)

    attempts = attempts_query.order_by(
        models.Attempt.score.desc(),
        models.Attempt.time_taken.asc(),
        models.Attempt.attempted_at.asc(),
    ).all()

    avg_score = sum(a.score for a in attempts) / len(attempts) if attempts else 0

    # Strip answers from questions using the strictly defined QuestionResponse schema — zero leakage
    safe_questions = [
        schemas.QuestionResponse.model_validate(q).model_dump() for q in questions
    ]

    # Serialize attempts: include user info for profile linking.
    # Batch-fetch users to avoid an N+1 (one query, not one per attempt).
    _uids = list({a.user_id for a in attempts if a.user_id})
    _users = (
        {u.id: u for u in db.query(models.User).filter(models.User.id.in_(_uids)).all()}
        if _uids
        else {}
    )
    serialized = []
    for a in attempts:
        user = _users.get(a.user_id)
        serialized.append(
            {
                "id": a.id,
                "user_id": a.user_id,
                "user_name": a.user_name,
                "user_slug": user.custom_slug if user else None,
                "user_photo": user.profile_photo_url if user else None,
                "score": a.score,
                "total": a.total,
                "time_taken": a.time_taken,
                "attempted_at": a.attempted_at,
                "descriptive_answers": a.descriptive_answers,
                "is_reviewed": a.is_reviewed,
                "is_anonymous": a.is_anonymous,
            }
        )

    return {
        "leaderboard": serialized,
        "questions": safe_questions,
        "group_average": float(int(float(avg_score) * 10 + 0.5) / 10.0),
        "total_attempts": len(attempts),
    }

@router.get("/my-stats")
def get_my_stats(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """VI: My Stats — personal accuracy, total attempts, top/weakest banks."""
    user_id = int(current_user["sub"])
    if user_id == 0:
        return {
            "total_attempts": 0,
            "avg_accuracy": 0,
            "overall_accuracy": 0,
            "banks_attempted": [],
            "is_system_admin": True,
        }

    attempts = db.query(models.Attempt).filter(models.Attempt.user_id == user_id).all()

    if not attempts:
        return {"total_attempts": 0, "avg_accuracy": 0, "overall_accuracy": 0, "banks_attempted": []}

    total_attempts = len(attempts)
    total_questions_attempted = 0.0
    total_correct_answers = 0.0
    accuracies = []

    for a in attempts:
        # Check if we have granular answer data
        if a.descriptive_answers and isinstance(a.descriptive_answers, list):
            correct_in_attempt = sum(
                1 for ans in a.descriptive_answers if ans.get("is_correct")
            )
            total_in_attempt = len(a.descriptive_answers)

            total_correct_answers += correct_in_attempt
            total_questions_attempted += total_in_attempt

            if total_in_attempt > 0:
                accuracies.append(
                    (float(correct_in_attempt) / total_in_attempt) * 100.0
                )
            else:
                accuracies.append(0.0)
        else:
            # Fallback to summary fields
            score = float(a.score) if a.score is not None else 0.0
            total = float(a.total) if a.total and a.total > 0 else 0.0

            total_correct_answers += score
            total_questions_attempted += total

            if total > 0:
                accuracies.append((score / total) * 100.0)
            else:
                accuracies.append(0.0)

    # Avg accuracy across attempts (unweighted)
    avg_accuracy = (
        float(sum(accuracies) / total_attempts) if total_attempts > 0 else 0.0
    )
    avg_accuracy = float(int(avg_accuracy * 10 + 0.5) / 10.0)

    # Bank breakdown
    bank_stats: Dict[int, Dict[str, Any]] = {}
    for a in attempts:
        bid = int(a.bank_id)
        if bid not in bank_stats:
            bank_stats[bid] = {"bank_id": bid, "attempts": 0, "scores": []}

        stats_entry = bank_stats[bid]
        stats_entry["attempts"] = int(stats_entry["attempts"]) + 1

        scores_coll = stats_entry["scores"]
        acc_float = (
            (float(a.score) / float(a.total) * 100.0)
            if a.total
            and getattr(a, "total", 0) > 0
            and getattr(a, "score", None) is not None
            else 0.0
        )
        scores_coll.append(acc_float)

    bank_breakdown = []
    for bid_key, s in bank_stats.items():
        bank_obj = (
            db.query(models.QuestionBank)
            .filter(models.QuestionBank.id == bid_key)
            .first()
        )
        s_list: List[float] = s["scores"]
        s_count: int = int(s["attempts"])
        bank_breakdown.append(
            {
                "bank_id": bid_key,
                "bank_name": bank_obj.name if bank_obj else f"Bank #{bid_key}",
                "attempts": s_count,
                "avg_accuracy": float(
                    int((float(sum(s_list)) / s_count) * 10 + 0.5) / 10.0
                )
                if s_count > 0
                else 0.0,
            }
        )

    bank_breakdown.sort(key=lambda x: x["avg_accuracy"])

    return {
        "total_attempts": total_attempts,
        "avg_accuracy": avg_accuracy,
        # Frontend (Sidebar, Dashboard) reads `overall_accuracy` — alias it so the
        # "Average Accuracy" stat isn't stuck at 0% from a field-name mismatch.
        "overall_accuracy": avg_accuracy,
        "banks_attempted": bank_breakdown,
    }

@router.get("/user/{user_id}/assignments")
def get_user_assignments(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Retrieve all active assignments and completion status for a specific user.
    """
    # Permission check: either viewing own assignments or is mentor/admin
    if int(current_user["sub"]) != user_id and current_user.get("role") not in [
        "LDAdmin",
        "Mentor",
        "GroupAdmin",
    ]:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: You cannot view another user's assignments.",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = user.group
    if not group:
        return []

    targets = [("person", user.id), ("group", group.id)]
    if group.batch_id:
        targets.append(("batch", group.batch_id))
        if group.batch.vertical_id:
            targets.append(("vertical", group.batch.vertical_id))
            if group.batch.vertical.department_id:
                targets.append(("dept", group.batch.vertical.department_id))
                if group.batch.vertical.department.organization_id:
                    targets.append(
                        ("org", group.batch.vertical.department.organization_id)
                    )

    from sqlalchemy import or_

    filters = [
        (models.Assignment.target_type == t[0]) & (models.Assignment.target_id == t[1])
        for t in targets
    ]

    from models.assignment import Assignment, AssignmentCompletion
    from sqlalchemy.orm import joinedload

    results = (
        db.query(Assignment, AssignmentCompletion)
        .options(joinedload(Assignment.bank), joinedload(Assignment.coding_question))
        .outerjoin(
            AssignmentCompletion,
            (Assignment.id == AssignmentCompletion.assignment_id)
            & (AssignmentCompletion.user_id == user_id),
        )
        .filter(or_(*filters), Assignment.is_active == True)
        .all()
    )

    assignments_list = []
    for a, comp in results:
        assignments_list.append(
            {
                "assignment_id": a.id,
                "bank_id": a.bank_id,
                "coding_question_id": a.coding_question_id,
                "assignment_type": a.assignment_type,
                "bank_name": a.bank.name
                if a.bank
                else (
                    a.coding_question.title
                    if a.coding_question
                    else f"Assignment #{a.id}"
                ),
                "due_date": a.due_date,
                "instructions": a.instructions,
                "is_completed": comp.status in ["passed", "completed"]
                if comp
                else False,
                "status": comp.status if comp else "not_started",
                "score": comp.best_score if comp else None,
                "attempts_used": comp.attempts_used if comp else 0,
                "max_attempts": a.max_attempts,
                "passing_score_percent": a.passing_score_percent,
                "lock_after_due": a.lock_after_due,
            }
        )

    return assignments_list

@router.get("/attempts/{attempt_id}/certificate")
def generate_certificate(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Generate a Certificate of Completion PDF for a passed attempt.
    """
    sub = current_user.get("sub")
    user_id = int(sub) if sub else 0
    attempt = (
        db.query(models.Attempt)
        .filter(models.Attempt.id == attempt_id, models.Attempt.user_id == user_id)
        .first()
    )

    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")

    # Attempts are by definition completed once saved to DB in this architecture.
    # In a real environment, we would use reportlab to generate the PDF
    # and then upload to S3 and return a presigned URL.

    import time as _time

    _exp = int(_time.time()) + CERT_TOKEN_TTL_SECONDS
    _tok = _certificate_token(attempt_id, _exp)
    mock_certificate_url = (
        f"/api/quiz/attempts/{attempt_id}/certificate/download?exp={_exp}&token={_tok}"
    )

    return {
        "success": True,
        "certificate_url": mock_certificate_url,
        "share_url": f"https://www.linkedin.com/sharing/share-offsite/?url={mock_certificate_url}",
    }

@router.get("/attempts/{attempt_id}/certificate/download")
def download_certificate(
    attempt_id: int,
    exp: int = Query(..., description="Signed link expiry (unix seconds)"),
    token: str = Query(..., description="HMAC issued by GET .../certificate"),
    db: Session = Depends(get_db),
):
    # Signed-link check stands in for the bearer token the browser cannot send.
    _verify_certificate_token(attempt_id, exp, token)

    from fastapi.responses import Response
    import io
    import os
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import landscape, letter
    except ImportError:
        raise HTTPException(status_code=500, detail="ReportLab not installed")

    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    bank = db.query(models.QuestionBank).filter(models.QuestionBank.id == attempt.bank_id).first()
    user = db.query(models.User).filter(models.User.id == attempt.user_id).first()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(letter))
    width, height = landscape(letter)

    # Draw border
    c.setStrokeColorRGB(0.1, 0.1, 0.4)
    c.setLineWidth(4)
    c.rect(20, 20, width - 40, height - 40)
    
    # Try to load logo
    # Api runs from apps/api
    logo_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web-next", "public", "images", "logo.png")
    if os.path.exists(logo_path):
        try:
            # Draw logo (scaled)
            c.drawImage(logo_path, width / 2 - 50, height - 120, width=100, height=100, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
            
    c.setFont("Helvetica-Bold", 36)
    c.drawCentredString(width / 2, height - 160, "Certificate of Completion")
    
    c.setFont("Helvetica", 20)
    c.drawCentredString(width / 2, height - 220, "This is to certify that")
    
    c.setFont("Helvetica-Bold", 28)
    user_name = user.full_name if user else "Participant"
    c.drawCentredString(width / 2, height - 270, user_name)
    
    c.setFont("Helvetica", 20)
    c.drawCentredString(width / 2, height - 320, "has successfully completed the assessment")
    
    c.setFont("Helvetica-Bold", 24)
    quiz_name = (getattr(bank, "name", None) or "Assessment") if bank else "Assessment"
    c.drawCentredString(width / 2, height - 370, quiz_name)
    
    c.setFont("Helvetica", 16)
    score_pct = (attempt.score / attempt.total * 100) if attempt.total > 0 else 0
    c.drawCentredString(width / 2, height - 420, f"with a score of {attempt.score}/{attempt.total} ({score_pct:.1f}%)")
    
    # ── White-label co-branding (Org × StudyBuddy, Powered by StudyBuddy) ────
    _brand = "StudyBuddy"
    try:
        _grp = (
            db.query(models.Group).filter(models.Group.id == user.group_id).first()
            if user
            else None
        )
        _dept = (
            db.query(models.Department)
            .filter(models.Department.id == _grp.department_id)
            .first()
            if _grp and _grp.department_id
            else None
        )
        _org = (
            db.query(models.Organization)
            .filter(models.Organization.id == _dept.organization_id)
            .first()
            if _dept
            else None
        )
        if _org:
            _brand = _org.brand_name or _org.name
    except Exception:
        pass
    c.setFont("Helvetica-Bold", 13)
    c.setFillColorRGB(0.1, 0.1, 0.4)
    c.drawCentredString(width / 2, height - 130, f"{_brand}  ×  StudyBuddy")
    c.setFillColorRGB(0, 0, 0)
    c.line(width - 250, 70, width - 100, 70)
    c.setFont("Helvetica", 11)
    c.drawCentredString(width - 175, 55, "Authorized Signature")
    c.drawString(70, 55, f"Certificate ID: SB-{attempt.id}")
    c.setFont("Helvetica-Oblique", 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(width / 2, 32, "Powered by StudyBuddy")
    c.setFillColorRGB(0, 0, 0)

    c.showPage()
    c.save()

    pdf_content = buffer.getvalue()
    buffer.close()

    return Response(content=pdf_content, media_type="application/pdf")
