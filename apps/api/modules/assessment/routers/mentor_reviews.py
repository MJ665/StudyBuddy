"""mentor_reviews endpoints (moved verbatim from routers/mentor.py)."""
from fastapi import APIRouter

from modules.assessment.routers.mentor_shared import *  # noqa: F401,F403
from modules.assessment.routers.mentor_shared import (  # noqa: F401
    _GLOBAL_ROLES,
    _assert_user_in_scope,
    _assert_user_in_scope_async,
    _mentor_scope_group_ids,
    _mentor_scope_group_ids_async,
)

router = APIRouter()

@router.get("/pending-reviews")
def get_pending_reviews(
    db: Session = Depends(get_db), current_user: dict = Depends(require_mentor_or_above)
):
    group_ids = _mentor_scope_group_ids(current_user, db)

    # Fetch pending quiz attempts with user data and eager loaded banks
    pending_quizzes = (
        db.query(models.Attempt, models.User)
        .options(joinedload(models.Attempt.bank))
        .join(models.User, models.Attempt.user_id == models.User.id)
        .filter(models.User.group_id.in_(group_ids), models.Attempt.is_reviewed.is_(False))
        .order_by(models.Attempt.attempted_at.desc())
        .limit(30)
        .all()
    )

    # Fetch pending coding attempts with eager loaded questions
    pending_coding = (
        db.query(models.CodingAttempt, models.User)
        .options(joinedload(models.CodingAttempt.coding_question))
        .join(models.User, models.CodingAttempt.user_id == models.User.id)
        .filter(
            models.User.group_id.in_(group_ids), models.CodingAttempt.is_verified.is_(False)
        )
        .order_by(models.CodingAttempt.attempted_at.desc())
        .limit(30)
        .all()
    )

    queue = []
    for attempt, user in pending_quizzes:
        bank = attempt.bank
        # Handle quiz attempts
        queue.append(
            {
                "id": attempt.id,
                "type": "quiz",
                "user_id": user.id,
                "user_name": user.full_name,
                "user_avatar": user.profile_photo_url,
                "group_id": user.group_id,
                "title": bank.name if bank else "Quiz",
                "chapter": bank.chapter if bank else None,
                "score": attempt.score,
                "total": attempt.total,
                "accuracy": round((attempt.score / attempt.total * 100), 1)
                if (attempt.total and attempt.total > 0)
                else 0,
                "attempted_at": attempt.attempted_at.isoformat()
                if attempt.attempted_at
                else None,
                "descriptive_answers": attempt.descriptive_answers,  # Critical for manual review
                "is_verified": attempt.is_verified,
                "comment": attempt.comment,
            }
        )

    for attempt, user in pending_coding:
        question = attempt.coding_question
        queue.append(
            {
                "id": attempt.id,
                "type": "coding",
                "user_id": user.id,
                "user_name": user.full_name,
                "user_avatar": user.profile_photo_url,
                "group_id": user.group_id,
                "title": question.title if question else "Coding Lab",
                "chapter": "Coding",
                "score": attempt.score,
                "total": 100,
                "accuracy": attempt.score or 0,
                "language": attempt.language,  # Use attempt's recorded language
                "submitted_code": attempt.submitted_code,
                "ai_feedback": attempt.ai_feedback,
                "ai_suggestions": attempt.ai_suggestions,
                "rubric_json": attempt.rubric_json,
                "execution_time_ms": attempt.execution_time_ms,
                "hints_used": attempt.hints_used,
                "attempted_at": attempt.attempted_at.isoformat()
                if attempt.attempted_at
                else None,
            }
        )

    return sorted(queue, key=lambda x: x["attempted_at"] or "", reverse=True)

@router.get("/inbox")
def get_unified_inbox(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    """Unified mentor workspace inbox (Phase 6 — mentor merge).

    ONE queue for everything awaiting this mentor: assessment reviews
    (quiz + coding attempts, from the existing pending-reviews logic) AND
    KT documents submitted for their approval. Ends the historical split
    where document reviews lived only inside the KT sub-app.
    """
    from models.kt_model import DocStatusEnum, KTDocument, KTProject

    # Assessment side — reuse the existing queue builder verbatim.
    assessment_queue = get_pending_reviews(db, current_user)

    # The unified inbox is an org-scoped L&D surface. An org-less caller
    # (PlatformAdmin, id 0 — cross-org by design) has no home org to scope KT
    # docs to, so return just the assessment queue instead of crashing on
    # int(None).
    raw_org = current_user.get("organization_id")
    if raw_org is None:
        return {
            "assessment": assessment_queue,
            "kt_documents": [],
            "counts": {
                "assessment": len(assessment_queue),
                "kt_documents": 0,
                "total": len(assessment_queue),
            },
        }

    # KT side — docs pending review, mentor-scoped exactly like
    # modules/kt/routers/insights.py::mentor_inbox (sync twin).
    org_id = int(raw_org)
    uid = int(current_user["sub"])
    role = current_user.get("role", "Member")

    q = db.query(KTDocument).filter(
        KTDocument.organization_id == org_id,
        KTDocument.status.in_(
            [DocStatusEnum.SUBMITTED, DocStatusEnum.UNDER_REVIEW]
        ),
    )
    if role == "Mentor":
        q = q.filter(
            or_(KTDocument.mentor_id == uid, KTDocument.mentor_id.is_(None))
        )
    elif role == "GroupAdmin":
        group_id = current_user.get("group_id")
        if group_id:
            proj_ids = [
                r[0]
                for r in db.query(KTProject.id)
                .filter(
                    KTProject.organization_id == org_id,
                    KTProject.group_id == group_id,
                )
                .all()
            ]
            q = q.filter(KTDocument.project_id.in_(proj_ids))

    kt_docs = (
        q.order_by(KTDocument.submitted_at.asc().nullslast()).limit(30).all()
    )
    kt_queue = [
        {
            "id": d.id,
            "type": "kt_document",
            "title": d.title,
            "doc_type": str(d.doc_type) if d.doc_type else None,
            "project_id": d.project_id,
            "author_id": d.author_id,
            "status": str(d.status.value if hasattr(d.status, "value") else d.status),
            "submitted_at": d.submitted_at.isoformat() if d.submitted_at else None,
            # Deep link into the KT workspace for the actual review UI.
            "link": "/kt",
        }
        for d in kt_docs
    ]

    return {
        "assessment": assessment_queue,
        "kt_documents": kt_queue,
        "counts": {
            "assessment": len(assessment_queue),
            "kt_documents": len(kt_queue),
            "total": len(assessment_queue) + len(kt_queue),
        },
    }

@router.post("/review")
def review_attempt(
    req: ReviewAttemptRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Strategic verification with manual quality overrides."""
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    mentor_id = int(current_user["sub"])

    if req.attempt_type == "quiz":
        attempt = (
            db.query(models.Attempt).filter(models.Attempt.id == req.attempt_id).first()
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
        attempt.is_reviewed = req.is_reviewed
        if req.override_score is not None:
            # Clamp the mentor override to the valid range [0, total].
            attempt.score = max(0, min(int(req.override_score), attempt.total or 0))
        target_user_id = attempt.user_id
    else:
        attempt = (
            db.query(models.CodingAttempt)
            .filter(models.CodingAttempt.id == req.attempt_id)
            .first()
        )
        if not attempt:
            raise HTTPException(status_code=404, detail="Coding attempt not found")
        attempt.is_verified = req.is_reviewed
        if req.override_score is not None:
            # Clamp the mentor override to [0, 100] (coding is scored out of 100).
            attempt.score = max(0, min(int(req.override_score), 100))
        target_user_id = attempt.user_id

    # SEC-102: block cross-scope tampering — the attempt's learner must be in a
    # group this mentor/admin oversees before any mutation is persisted.
    _assert_user_in_scope(target_user_id, current_user, db)

    # Add mentor comment and notification
    if req.mentor_comment and req.mentor_comment.strip():
        comment_entry = models.MentorComment(
            attempt_id=req.attempt_id if req.attempt_type == "quiz" else None,
            coding_attempt_id=req.attempt_id if req.attempt_type == "coding" else None,
            mentor_id=mentor_id,
            comment=req.mentor_comment,
            visibility="student_only",
        )
        db.add(comment_entry)

        # Push in-app notification to the learner
        notif = models.Notification(
            user_id=target_user_id,
            notification_type="mentor_comment",
            title="Mentor reviewed your submission",
            body=f"Feedback: {req.mentor_comment[:120]}{'...' if len(req.mentor_comment) > 120 else ''}",
            link_type="attempt",
            link_id=req.attempt_id,
        )
        db.add(notif)

    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="REVIEW_ATTEMPT",
        resource_type="ATTEMPT",
        resource_id=req.attempt_id,
        details={
            "type": req.attempt_type,
            "target_user_id": target_user_id,
            "score": req.override_score,
        },
    )

    return {"success": True, "message": "Attempt reviewed successfully"}

@router.post("/bulk-review")
def bulk_review_attempts(
    req: BulkReviewRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Batch verify multiple attempts at once — mentor efficiency feature."""
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    mentor_id = int(current_user["sub"])
    reviewed_count = 0

    # SEC-102: only attempts belonging to the caller's oversight scope are touched.
    scope_ids = _mentor_scope_group_ids(current_user, db)

    def _owned(uid: int) -> bool:
        row = db.query(models.User.group_id).filter(models.User.id == uid).first()
        return row is not None and row.group_id in scope_ids

    for attempt_id in req.attempt_ids:
        if req.attempt_type == "quiz":
            attempt = (
                db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
            )
            if attempt and _owned(attempt.user_id):
                attempt.is_reviewed = req.is_reviewed
                reviewed_count += 1
                if req.bulk_comment:
                    db.add(
                        models.MentorComment(
                            attempt_id=attempt_id,
                            mentor_id=mentor_id,
                            comment=req.bulk_comment,
                            visibility="student_only",
                        )
                    )
        else:
            attempt = (
                db.query(models.CodingAttempt)
                .filter(models.CodingAttempt.id == attempt_id)
                .first()
            )
            if attempt and _owned(attempt.user_id):
                attempt.is_verified = req.is_reviewed
                reviewed_count += 1

    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="BULK_REVIEW_ATTEMPTS",
        resource_type="ATTEMPT",
        resource_id=0,
        details={
            "count": reviewed_count,
            "type": req.attempt_type,
            "ids": req.attempt_ids[:10],
        },
    )

    return {"success": True, "reviewed_count": reviewed_count}

@router.get("/attempts/{attempt_id}/comments")
def get_attempt_comments(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    role = current_user.get("role")

    attempt = db.query(models.Attempt).filter(models.Attempt.id == attempt_id).first()
    # Tenant check first: the staff roles below could otherwise read any org's attempt.
    assert_same_org(attempt, current_user, "Attempt")

    if role == "Member" and attempt.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    from sqlalchemy.orm import joinedload

    comments = (
        db.query(models.MentorComment)
        .options(joinedload(models.MentorComment.mentor))
        .filter(models.MentorComment.attempt_id == attempt_id)
        .order_by(models.MentorComment.created_at.asc())
        .all()
    )

    result = []
    for c in comments:
        result.append(
            {
                "id": c.id,
                "attempt_id": c.attempt_id,
                "mentor_id": c.mentor_id,
                "mentor_name": c.mentor.full_name if c.mentor else "Unknown",
                "mentor_avatar": c.mentor.profile_photo_url if c.mentor else None,
                "comment": c.comment,
                "visibility": c.visibility,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
        )
    return result
