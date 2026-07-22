import datetime
import os
from typing import List, Optional

import models
from auth_utils import assert_group_in_org, assert_same_org, require_mentor_or_above, verify_token
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.ai_reporting import ai_executive
from services.performance_engine import performance_engine
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/mentor", tags=["mentor"])


@router.get("/batch/{batch_id}/insights")
async def get_batch_insights(
    batch_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    """PHASE-3: Generate high-level strategic batch insights for mentors (STRAT-INSIGHT-01)."""
    # Logic to check batch oversight is handled by the PerformanceEngine's aggregation
    # but we can add a manual scope check here if needed.

    stats = await performance_engine.get_batch_vectors(batch_id, db)
    if not stats:
        raise HTTPException(
            status_code=404,
            detail="Batch data insufficient for intelligence synthesis. Ensure members have activity.",
        )

    # Strategic synthesis via AI
    batch_name = (
        await db.scalar(select(models.Batch.name).where(models.Batch.id == batch_id))
    ) or f"Batch {batch_id}"
    insights = await ai_executive.generate_batch_insights(batch_name, stats["metrics"])

    return {
        "batch_id": batch_id,
        "batch_name": batch_name,
        "metrics": stats["metrics"],
        "charts": stats["charts"],
        "insights": insights,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


class ReviewAttemptRequest(BaseModel):
    attempt_id: int
    attempt_type: str = "quiz"  # "quiz" or "coding"
    is_reviewed: bool = True
    mentor_comment: Optional[str] = None
    override_score: Optional[float] = None


class BulkReviewRequest(BaseModel):
    attempt_ids: List[int]
    attempt_type: str = "quiz"
    is_reviewed: bool = True
    bulk_comment: Optional[str] = None


_GLOBAL_ROLES = {"LDAdmin", "ld_admin", "Owner", "owner"}


def _mentor_scope_group_ids(current_user: dict, db: Session) -> set[int]:
    """Group ids the caller may act on.

    - Global admins (LDAdmin/Owner): every group inside THEIR organization
      (still tenant-scoped — an admin never reaches another org's data).
    - Mentors: groups assigned via the legacy MentorGroupAssignment table or the
      V3 scoped UserRole table.
    Used to close IDOR on attempt/student endpoints (SEC-102).
    """
    from models.auth import UserRole

    uid = int(current_user["sub"])
    org_id = current_user.get("organization_id")

    if current_user.get("role") in _GLOBAL_ROLES:
        rows = (
            db.query(models.Group.id)
            .join(models.Department, models.Group.department_id == models.Department.id)
            .filter(models.Department.organization_id == org_id)
            .all()
        )
        return {g.id for g in rows}

    ids = {
        a.group_id
        for a in db.query(models.MentorGroupAssignment)
        .filter(models.MentorGroupAssignment.mentor_id == uid)
        .all()
    }
    ids |= {
        r.scope_id
        for r in db.query(UserRole)
        .filter(
            UserRole.user_id == uid,
            UserRole.role.in_(["Mentor", "mentor"]),
            UserRole.scope_type == "group",
        )
        .all()
        if r.scope_id is not None
    }
    return ids


async def _mentor_scope_group_ids_async(current_user: dict, db: AsyncSession) -> set[int]:
    """Async twin of `_mentor_scope_group_ids`.

    The sync version is still used by the (threadpooled) sync handlers; both must
    exist while routers migrate one at a time.
    """
    from models.auth import UserRole

    uid = int(current_user["sub"])
    # JWT claims can carry organization_id as a STRING. psycopg2 silently coerced
    # it; asyncpg does not and raises `operator does not exist: integer = varchar`.
    _raw_org = current_user.get("organization_id")
    org_id = int(_raw_org) if _raw_org is not None else None

    if current_user.get("role") in _GLOBAL_ROLES:
        rows = await db.execute(
            select(models.Group.id)
            .join(models.Department, models.Group.department_id == models.Department.id)
            .where(models.Department.organization_id == org_id)
        )
        return set(rows.scalars().all())

    rows = await db.execute(
        select(models.MentorGroupAssignment.group_id).where(
            models.MentorGroupAssignment.mentor_id == uid
        )
    )
    ids = set(rows.scalars().all())

    rows = await db.execute(
        select(UserRole.scope_id).where(
            UserRole.user_id == uid,
            UserRole.role.in_(["Mentor", "mentor"]),
            UserRole.scope_type == "group",
        )
    )
    ids |= {sid for sid in rows.scalars().all() if sid is not None}
    return ids


async def _assert_user_in_scope_async(
    target_user_id: int, current_user: dict, db: AsyncSession
) -> None:
    """Async twin of `_assert_user_in_scope`."""
    scope_ids = await _mentor_scope_group_ids_async(current_user, db)
    group_id = await db.scalar(
        select(models.User.group_id).where(models.User.id == target_user_id)
    )
    if group_id is None or group_id not in scope_ids:
        raise HTTPException(
            status_code=403,
            detail="This submission is outside your oversight scope.",
        )


def _assert_user_in_scope(target_user_id: int, current_user: dict, db: Session) -> None:
    """Raise 403 unless target_user_id belongs to a group the caller oversees."""
    scope_ids = _mentor_scope_group_ids(current_user, db)
    target = (
        db.query(models.User.group_id)
        .filter(models.User.id == target_user_id)
        .first()
    )
    if target is None or target.group_id not in scope_ids:
        raise HTTPException(
            status_code=403,
            detail="This submission is outside your oversight scope.",
        )


@router.get("/groups")
def get_mentor_groups(
    db: Session = Depends(get_db), current_user: dict = Depends(require_mentor_or_above)
):
    group_ids = _mentor_scope_group_ids(current_user, db)
    groups = db.query(models.Group).filter(models.Group.id.in_(group_ids)).all()
    return [{"id": g.id, "name": g.name, "batch_id": g.batch_id} for g in groups]


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

    # KT side — docs pending review, mentor-scoped exactly like
    # modules/kt/routers/insights.py::mentor_inbox (sync twin).
    org_id = int(current_user["organization_id"])
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


@router.get("/group/{group_id}/students")
async def get_group_students(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    await db.run_sync(lambda sd: assert_group_in_org(group_id, sd, current_user))
    from services.performance_engine import performance_engine

    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if current_user.get("role") == "Mentor":
        mentor_id = int(current_user["sub"])
        assign = await db.scalar(
            select(models.MentorGroupAssignment).where(
                models.MentorGroupAssignment.mentor_id == mentor_id,
                models.MentorGroupAssignment.group_id == group_id,
                models.MentorGroupAssignment.is_active.is_(True),
            )
        )
        if not assign:
            raise HTTPException(status_code=403, detail="Not assigned to this group")

    students = (
        (
            await db.execute(
                select(models.User).where(
                    models.User.group_id == group_id,
                    models.User.role == "Member",
                    models.User.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    # Attempt aggregates for the WHOLE group in ONE grouped query. This was two
    # queries per student inside the loop below — an N+1 that grew with class size.
    _ids = [s.id for s in students]
    _agg: dict = {}
    if _ids:
        _rows = await db.execute(
            select(
                models.Attempt.user_id,
                func.count(models.Attempt.id),
                func.avg(
                    case(
                        (
                            models.Attempt.total > 0,
                            models.Attempt.score * 100.0 / models.Attempt.total,
                        ),
                        else_=None,
                    )
                ),
            )
            .where(models.Attempt.user_id.in_(_ids))
            .group_by(models.Attempt.user_id)
        )
        _agg = {uid: (cnt or 0, avg) for uid, cnt, avg in _rows.all()}

    result = []
    for s in students:
        total_attempts, avg_score = _agg.get(s.id, (0, None))
        # Get enriched metrics from engine
        vectors = await performance_engine.get_user_vectors(s.id, db)
        metrics = vectors.get("metrics", {})

        result.append(
            {
                "id": s.id,
                "full_name": s.full_name,
                "email": s.email,
                "profile_photo_url": s.profile_photo_url,
                "streak_count": s.streak_count or 0,
                "last_active_date": s.last_active_date.isoformat()
                if s.last_active_date
                else None,
                "total_attempts": total_attempts,
                "avg_accuracy": round(float(avg_score), 1) if avg_score else 0.0,
                "risk_level": metrics.get("m29_risk", {}).get("value", "Stable"),
                "proficiency": metrics.get("m02_overall_accuracy", {}).get("raw", 0),
                "velocity": metrics.get("m17_velocity", {}).get("raw", 0),
            }
        )

    return result


@router.get("/student/{student_id}/profile")
def get_student_profile(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    student = db.query(models.User).filter(models.User.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # SEC-102: enforce oversight scope on cross-user PII access.
    _assert_user_in_scope(student_id, current_user, db)

    attempts = (
        db.query(models.Attempt)
        .filter(models.Attempt.user_id == student_id)
        .order_by(models.Attempt.attempted_at.desc())
        .limit(20)
        .all()
    )

    formatted_attempts = []
    for a in attempts:
        bank = (
            db.query(models.QuestionBank)
            .filter(models.QuestionBank.id == a.bank_id)
            .first()
        )
        formatted_attempts.append(
            {
                "id": a.id,
                "bank_name": bank.name if bank else "Unknown",
                "score": a.score,
                "total": a.total,
                "accuracy": round((a.score / a.total) * 100, 1) if a.total > 0 else 0,
                "time_taken": a.time_taken,
                "attempted_at": a.attempted_at.isoformat() if a.attempted_at else None,
                "is_reviewed": a.is_reviewed,
            }
        )

    return {
        "student": {
            "id": student.id,
            "full_name": student.full_name,
            "email": student.email,
            "profile_photo_url": student.profile_photo_url,
            "streak_count": student.streak_count or 0,
            "last_active_date": student.last_active_date.isoformat()
            if student.last_active_date
            else None,
            "github_url": student.github_url,
            "leetcode_url": student.leetcode_url,
            "expertise_json": student.expertise_json,
        },
        "attempts": formatted_attempts,
    }


@router.post("/student/{student_id}/ai-insight")
async def get_ai_student_insight(
    student_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    AI-powered mentor insight: Analyzes a student's performance history
    and generates personalised coaching recommendations via Gemini.
    """
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="AI service not configured")

    student = await db.get(models.User, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # SEC-102: enforce oversight scope on cross-user PII access.
    await _assert_user_in_scope_async(student_id, current_user, db)

    # Gather performance data
    attempts = (
        (
            await db.execute(
                select(models.Attempt).where(models.Attempt.user_id == student_id)
            )
        )
        .scalars()
        .all()
    )
    coding_attempts = (
        (
            await db.execute(
                select(models.CodingAttempt).where(
                    models.CodingAttempt.user_id == student_id
                )
            )
        )
        .scalars()
        .all()
    )

    if not attempts and not coding_attempts:
        return {
            "insight": "This student has no attempts yet. Encourage them to start practicing!",
            "from_cache": False,
        }

    # Build topic-level accuracy map.
    # Banks are fetched ONCE for all attempts; this was a query per attempt.
    _bank_ids = {a.bank_id for a in attempts if a.bank_id is not None}
    _banks: dict = {}
    if _bank_ids:
        _rows = await db.execute(
            select(models.QuestionBank).where(models.QuestionBank.id.in_(_bank_ids))
        )
        _banks = {b.id: b for b in _rows.scalars().all()}

    topic_stats: dict = {}
    for a in attempts:
        bank = _banks.get(a.bank_id)
        topic = (bank.chapter if bank else "General") or "General"
        if topic not in topic_stats:
            topic_stats[topic] = {"scores": [], "total": 0}
        acc = (a.score / a.total * 100) if a.total > 0 else 0
        topic_stats[topic]["scores"].append(acc)
        topic_stats[topic]["total"] += 1

    topic_summary = []
    for topic, data in topic_stats.items():
        avg = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
        topic_summary.append(
            f"{topic}: {round(avg, 1)}% avg ({data.total} attempts)"
        )

    overall_accuracy = 0.0
    if attempts:
        all_accs = [(a.score / a.total * 100) for a in attempts if a.total > 0]
        overall_accuracy = sum(all_accs) / len(all_accs) if all_accs else 0.0

    coding_score_avg = 0.0
    if coding_attempts:
        scores = [c.score for c in coding_attempts if c.score is not None]
        coding_score_avg = sum(scores) / len(scores) if scores else 0.0

    f"""You are an expert L&D coach analyzing a learner's performance for their mentor.

Student: {student.full_name}
Quiz Overall Accuracy: {round(overall_accuracy, 1)}%
Total Quiz Attempts: {len(attempts)}
Coding AI Score Avg: {round(coding_score_avg, 1)}%
Current Streak: {student.streak_count or 0} days

Topic Breakdown:
{chr(10).join(topic_summary) if topic_summary else "No topic data yet."}

Generate a concise (3-4 sentences), actionable coaching insight for the mentor covering:
1. One strength to reinforce
2. One critical weakness or knowledge gap to address
3. One specific next step recommendation
Keep it professional, data-driven, and specific to this learner's data."""

    # Refactored to use centralized ExecutiveAIService
    from services.ai_reporting import ai_executive

    # Prepare intel payload for synthesis
    intel = {
        "overall_accuracy": overall_accuracy,
        "quiz_count": len(attempts),
        "coding_score": coding_score_avg,
        "streak": student.streak_count or 0,
        "topics": topic_summary,
    }

    res = await ai_executive.generate_user_insights(student.full_name, intel)
    return res


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


@router.get("/group/{group_id}/stats")
def get_group_stats(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    assert_group_in_org(group_id, db, current_user)
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    if current_user.get("role") == "Mentor":
        mentor_id = int(current_user["sub"])
        assign = (
            db.query(models.MentorGroupAssignment)
            .filter_by(mentor_id=mentor_id, group_id=group_id, is_active=True)
            .first()
        )
        if not assign:
            raise HTTPException(status_code=403, detail="Access denied")

    # Top Performers
    attempts = (
        db.query(models.Attempt, models.User)
        .join(models.User, models.Attempt.user_id == models.User.id)
        .filter(models.User.group_id == group_id)
        .all()
    )

    user_stats: dict = {}
    for a, u in attempts:
        if u.id not in user_stats:
            user_stats[u.id] = {
                "full_name": u.full_name,
                "scores": [],
                "streak": u.streak_count or 0,
            }
        if a.total > 0:
            user_stats[u.id]["scores"].append((a.score / a.total) * 100)

    top_performers = sorted(
        [
            {
                "name": s["full_name"],
                "score": f"{round(sum(s['scores']) / len(s['scores']), 1) if s['scores'] else 0}%",
                "streak": s["streak"],
            }
            for s in user_stats.values()
        ],
        key=lambda x: float(x["score"].strip("%")),
        reverse=True,
    )[:5]

    # 7-day velocity
    today = datetime.datetime.now(datetime.timezone.utc)
    velocity_data = []
    for i in range(6, -1, -1):
        day = today - datetime.timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day.replace(hour=23, minute=59, second=59)
        count = (
            db.query(models.Attempt)
            .join(models.User)
            .filter(
                models.User.group_id == group_id,
                models.Attempt.attempted_at >= day_start,
                models.Attempt.attempted_at <= day_end,
            )
            .count()
        )
        velocity_data.append({"day": day.strftime("%a"), "count": count})

    # Curriculum Insights (Weak Topics)
    chapters: dict = {}
    for a, u in attempts:
        bank = (
            db.query(models.QuestionBank)
            .filter(models.QuestionBank.id == a.bank_id)
            .first()
        )
        if bank and bank.chapter:
            if bank.chapter not in chapters:
                chapters[bank.chapter] = {"total": 0, "correct": 0}
            chapters[bank.chapter]["total"] += a.total
            chapters[bank.chapter]["correct"] += a.score

    curriculum_insights = []
    for ch, stats in chapters.items():
        acc = (stats["correct"] / stats.total * 100) if stats.total > 0 else 0
        curriculum_insights.append(
            {
                "topic": ch,
                "accuracy": round(acc, 1),
                "status": "Healthy"
                if acc >= 80
                else "Stable"
                if acc >= 60
                else "Requires Focus",
            }
        )

    # Group health summary
    total_members = (
        db.query(func.count(models.User.id))
        .filter(
            models.User.group_id == group_id,
            models.User.role == "Member",
            models.User.is_active.is_(True),
        )
        .scalar()
        or 0
    )

    pending_reviews = (
        db.query(func.count(models.Attempt.id))
        .join(models.User)
        .filter(models.User.group_id == group_id, models.Attempt.is_reviewed.is_(False))
        .scalar()
        or 0
    )

    return {
        "top_performers": top_performers,
        "assignment_velocity": velocity_data,
        "curriculum_insights": sorted(curriculum_insights, key=lambda x: x["accuracy"])[
            :6
        ],
        "summary": {
            "total_members": total_members,
            "pending_reviews": pending_reviews,
            "total_attempts_7d": sum(v["count"] for v in velocity_data),
        },
    }


@router.get("/group/{group_id}/feed")
def get_group_activity_feed(
    group_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Live activity feed for the mentor dashboard showing recent learner actions."""
    assert_group_in_org(group_id, db, current_user)
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Verify mentor access
    if current_user.get("role") == "Mentor":
        mentor_id = int(current_user["sub"])
        assign = (
            db.query(models.MentorGroupAssignment)
            .filter_by(mentor_id=mentor_id, group_id=group_id, is_active=True)
            .first()
        )
        if not assign:
            raise HTTPException(status_code=403, detail="Not assigned to this group")

    from sqlalchemy.orm import joinedload

    # Recent quiz attempts
    recent_attempts = (
        db.query(models.Attempt, models.User)
        .options(joinedload(models.Attempt.bank))
        .join(models.User, models.Attempt.user_id == models.User.id)
        .filter(models.User.group_id == group_id)
        .order_by(models.Attempt.attempted_at.desc())
        .limit(limit)
        .all()
    )

    feed = []
    for attempt, user in recent_attempts:
        bank = attempt.bank
        acc = (
            round((attempt.score / attempt.total * 100), 1) if attempt.total > 0 else 0
        )
        feed.append(
            {
                "type": "quiz_attempt",
                "user_name": user.full_name,
                "user_avatar": user.profile_photo_url,
                "action": f"completed '{bank.name if bank else 'Quiz'}' with {acc}% accuracy",
                "score": attempt.score,
                "total": attempt.total,
                "accuracy": acc,
                "timestamp": attempt.attempted_at.isoformat()
                if attempt.attempted_at
                else None,
                "is_reviewed": attempt.is_reviewed,
                "attempt_id": attempt.id,
                "sentiment": "positive"
                if acc >= 70
                else "neutral"
                if acc >= 40
                else "negative",
            }
        )

    return sorted(feed, key=lambda x: x["timestamp"] or "", reverse=True)


@router.get("/group/{group_id}/ai-summary")
async def get_group_ai_summary(
    group_id: int,
    force: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """PHASE-3: Generate a high-level pedagogical summary of the entire group for the mentor."""
    await db.run_sync(lambda sd: assert_group_in_org(group_id, sd, current_user))
    if current_user.get("role") not in ["Mentor", "LDAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    group = await db.get(models.Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    students = (
        (
            await db.execute(
                select(models.User).where(
                    models.User.group_id == group_id,
                    models.User.role == "Member",
                    models.User.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )

    if not students:
        return {"summary": "No active students found in this group to analyze."}

    # Aggregate key metrics
    total_accuracy = 0
    total_velocity = 0
    risk_counts = {"High": 0, "Medium": 0, "Stable": 0}

    from services.performance_engine import performance_engine

    for s in students:
        v = await performance_engine.get_user_vectors(s.id, db)
        m = v.get("metrics", {})
        total_accuracy += m.get("m02_overall_accuracy", {}).get("raw", 0)
        total_velocity += m.get("m17_velocity", {}).get("raw", 0)
        risk = m.get("m29_risk", {}).get("value", "Stable")
        if "High" in risk:
            risk_counts["High"] += 1
        elif "Medium" in risk:
            risk_counts["Medium"] += 1
        else:
            risk_counts["Stable"] += 1

    avg_acc = total_accuracy / len(students)
    avg_vel = total_velocity / len(students)

    res = await ai_executive.generate_pedagogical_summary(
        group.name,
        {
            "avg_accuracy": avg_acc,
            "avg_velocity": avg_vel,
            "risk_counts": risk_counts,
            "student_count": len(students),
        },
        force=force,
    )
    return res
