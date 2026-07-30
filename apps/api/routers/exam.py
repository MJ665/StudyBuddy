"""Proctored Exam service endpoints.

Reuses the shared Question engine + grading dispatch. Enforces an overall timer,
a single secure attempt (server-side), deterministic server-side shuffling (so a
reload can't reshuffle to peek), and proctoring event capture.
"""
import datetime
import random

import models
from auth_utils import (
    assert_same_org,
    assert_same_super_org,
    caller_org_id,
    caller_super_org_id,
    require_mentor_or_above,
    scope_to_org,
    scope_to_super_org,
    verify_token,
)
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

router = APIRouter(prefix="/exams", tags=["exam"])


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _shuffled(items: list, seed: int) -> list:
    out = list(items)
    random.Random(seed).shuffle(out)
    return out


# ── Authoring ────────────────────────────────────────────────────────────────


class ExamCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str | None = None
    bank_id: int | None = None
    question_ids: list[int] = Field(default_factory=list)
    duration_minutes: int = Field(default=60, ge=1, le=600)
    passing_score: int = Field(default=40, ge=0, le=100)
    max_attempts: int = Field(default=1, ge=1, le=10)
    shuffle_questions: bool = True
    shuffle_options: bool = True
    proctoring_mode: str = Field(default="standard", pattern="^(none|standard|advanced)$")
    is_published: bool = False
    recipient_emails: list[str] = Field(default_factory=list)


@router.post("")
def create_exam(
    body: ExamCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    q_ids = list(body.question_ids)
    if body.bank_id:
        # The bank must belong to the caller's org, otherwise an exam could be
        # seeded with another tenant's questions by passing their bank_id.
        bank = (
            db.query(models.QuestionBank)
            .filter(models.QuestionBank.id == body.bank_id)
            .first()
        )
        assert_same_super_org(bank, current_user, db, "Question bank")
        if not q_ids:
            q_ids = [
                q.id
                for q in scope_to_super_org(
                    db.query(models.Question).filter(
                        models.Question.bank_id == body.bank_id
                    ),
                    models.Question,
                    current_user,
                    db,
                ).all()
            ]
    elif q_ids:
        # Explicit ids must also be within the caller's org.
        owned = {
            q.id
            for q in scope_to_super_org(
                db.query(models.Question).filter(models.Question.id.in_(q_ids)),
                models.Question,
                current_user,
                db,
            ).all()
        }
        foreign = [q for q in q_ids if q not in owned]
        if foreign:
            raise HTTPException(404, "One or more questions were not found.")
    if not q_ids:
        raise HTTPException(400, "An exam needs at least one question (bank_id or question_ids).")

    exam = models.Exam(
        organization_id=caller_org_id(current_user),
        super_organization_id=caller_super_org_id(current_user, db),
        title=body.title,
        description=body.description,
        bank_id=body.bank_id,
        question_ids=q_ids,
        duration_minutes=body.duration_minutes,
        passing_score=body.passing_score,
        max_attempts=body.max_attempts,
        shuffle_questions=body.shuffle_questions,
        shuffle_options=body.shuffle_options,
        proctoring_mode=body.proctoring_mode,
        is_published=body.is_published,
        recipient_emails=[e.strip().lower() for e in body.recipient_emails if e and e.strip()],
        created_by=int(current_user["sub"]),
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)

    invited = 0
    if exam.is_published and exam.recipient_emails:
        invited = _notify_exam_recipients(exam, current_user, db)

    return {
        "id": exam.id,
        "title": exam.title,
        "question_count": len(q_ids),
        "invited": invited,
    }


def _notify_exam_recipients(
    exam: "models.Exam", current_user: dict, db: Session
) -> int:
    """Resolve recipient emails to internal users in the caller's super-org and
    notify each by email (with a direct portal link) + in-app notification.

    Best-effort: an email/push failure never aborts exam creation.
    """
    import os

    emails = list(exam.recipient_emails or [])
    if not emails:
        return 0

    # Resolve emails to active users, then keep only those the caller can reach.
    # Learner/user data is ORG-scoped (unlike the exam itself, which is shared
    # super-org content), so recipients are filtered to the caller's org — a
    # PlatformAdmin (org-less, cross-org by design) may invite any matched user.
    candidates = (
        db.query(models.User)
        .filter(
            models.User.email.in_(emails),
            models.User.is_active.is_(True),
        )
        .all()
    )
    if not candidates:
        return 0

    from auth_utils import (
        is_ld_admin_plus,
        is_platform_admin,
        resolve_user_organization_id,
    )

    caller_org = caller_org_id(current_user)
    if is_platform_admin(current_user):
        users = candidates
    elif is_ld_admin_plus(current_user):
        # LDAdmin+ manages the whole enterprise (super-org), so recipients in any
        # org of the caller's super-org are reachable — not just the home org.
        # (Fixes Bug 9: '0 recipients notified' when invitees live in sibling
        # orgs created under the same enterprise.)
        from auth_utils import _super_org_of_org, caller_super_org_id

        caller_super = caller_super_org_id(current_user, db)
        users = []
        for u in candidates:
            u_org = resolve_user_organization_id(u, db)
            u_super = _super_org_of_org(u_org, db) if u_org is not None else None
            if caller_super is not None and u_super == caller_super:
                users.append(u)
            elif caller_org is not None and u_org == caller_org:
                users.append(u)
    else:
        users = [
            u
            for u in candidates
            if caller_org is not None
            and resolve_user_organization_id(u, db) == caller_org
        ]
    if not users:
        return 0

    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
    portal_url = f"{frontend_url}/exam/{exam.id}"

    notified = 0
    for u in users:
        notif = models.Notification(
            user_id=u.id,
            notification_type="exam_invite",
            title=f"📝 Exam Published: {exam.title}",
            body="You have been invited to take a proctored exam.",
            link_type="exam",
            link_id=exam.id,
        )
        db.add(notif)
        notified += 1

        # Mobile push (best-effort; never blocks).
        try:
            from services.push_service import send_push_to_user

            send_push_to_user(
                db,
                u.id,
                f"Exam Published: {exam.title}",
                "You have been invited to take a proctored exam.",
                url=f"/exam/{exam.id}",
            )
        except Exception:
            pass

        if u.email:
            try:
                from services.email_service import send_exam_invite

                send_exam_invite(
                    to_email=u.email,
                    full_name=u.full_name,
                    exam_title=exam.title,
                    portal_url=portal_url,
                    duration_minutes=exam.duration_minutes,
                    passing_score=exam.passing_score,
                )
            except Exception as e:
                print(f"Exam invite email failed for {u.email}: {e}")

    db.commit()
    return notified


@router.get("")
def list_exams(
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    # via caller_org_id so the claim is coerced to int; asyncpg rejects
    # `integer = varchar` where psycopg2 silently coerced it.
    # Exams are shared CONTENT: visible to every business unit of the customer.
    exams = (
        scope_to_super_org(
            db.query(models.Exam), models.Exam, current_user, db
        )
        .order_by(models.Exam.created_at.desc())
        .all()
    )
    return {
        "exams": [
            {
                "id": e.id,
                "title": e.title,
                "duration_minutes": e.duration_minutes,
                "question_count": len(e.question_ids or []),
                "proctoring_mode": e.proctoring_mode,
                "is_published": e.is_published,
            }
            for e in exams
        ]
    }


# ── Taking an exam ───────────────────────────────────────────────────────────


@router.post("/{exam_id}/start")
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Single secure attempt: reuse an in-progress attempt or create one; block
    once max_attempts submitted attempts exist."""
    uid = int(current_user["sub"])
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    assert_same_super_org(exam, current_user, db, "Exam")
    if not exam.is_published:
        raise HTTPException(404, "Exam not found or not published")

    existing = (
        db.query(models.ExamAttempt)
        .filter(models.ExamAttempt.exam_id == exam_id, models.ExamAttempt.user_id == uid)
        .order_by(models.ExamAttempt.started_at.desc())
        .all()
    )
    in_progress = next((a for a in existing if a.status == "in_progress"), None)
    submitted = [a for a in existing if a.status != "in_progress"]
    if in_progress:
        attempt = in_progress
    else:
        if len(submitted) >= exam.max_attempts:
            raise HTTPException(403, "You have used all attempts for this exam.")
        attempt = models.ExamAttempt(
            exam_id=exam_id, user_id=uid, status="in_progress",
            organization_id=exam.organization_id,
            shuffle_seed=random.randint(1, 2_000_000_000),
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

    return _exam_paper(exam, attempt, db)


def _exam_paper(exam: models.Exam, attempt: models.ExamAttempt, db: Session) -> dict:
    """Render the paper for the candidate — shuffled deterministically, NO answers."""
    qs = {
        q.id: q
        for q in db.query(models.Question)
        .filter(models.Question.id.in_(exam.question_ids or []))
        .all()
    }
    ordered_ids = exam.question_ids or []
    if exam.shuffle_questions:
        ordered_ids = _shuffled(ordered_ids, attempt.shuffle_seed)

    deadline = attempt.started_at + datetime.timedelta(minutes=exam.duration_minutes)
    questions = []
    for qid in ordered_ids:
        q = qs.get(qid)
        if not q:
            continue
        opts = list(q.options or [])
        if exam.shuffle_options and q.question_type in ("mcq_single", "mcq_multi"):
            opts = _shuffled(opts, attempt.shuffle_seed + qid)
        questions.append(
            {
                "id": q.id,
                "question": q.question,
                "question_type": getattr(q, "question_type", "mcq_single"),
                "options": opts,  # NO answer / correct_options leaked
                "content_format": getattr(q, "content_format", "text"),
                "media_urls": getattr(q, "media_urls", None),
                "points": getattr(q, "points", 1),
            }
        )
    return {
        "attempt_id": attempt.id,
        "exam_id": exam.id,
        "title": exam.title,
        "proctoring_mode": exam.proctoring_mode,
        "duration_minutes": exam.duration_minutes,
        "deadline": deadline.isoformat(),
        "server_time": _now().isoformat(),
        "questions": questions,
    }


class ExamSubmit(BaseModel):
    answers: dict[str, str | list] = Field(default_factory=dict)  # {question_id: answer}


@router.post("/attempts/{attempt_id}/submit")
async def submit_exam(
    attempt_id: int,
    body: ExamSubmit,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    uid = int(current_user["sub"])
    attempt = await db.get(models.ExamAttempt, attempt_id)
    if not attempt or attempt.user_id != uid:
        raise HTTPException(404, "Attempt not found")
    if attempt.status != "in_progress":
        raise HTTPException(409, "This attempt was already submitted.")

    exam = await db.get(models.Exam, attempt.exam_id)
    if not exam:
        raise HTTPException(404, "Exam not found")
    deadline = attempt.started_at + datetime.timedelta(minutes=exam.duration_minutes)
    expired = _now() > deadline + datetime.timedelta(seconds=30)  # small grace

    _qrows = await db.execute(
        select(models.Question).where(
            models.Question.id.in_(exam.question_ids or [])
        )
    )
    qs = {q.id: q for q in _qrows.scalars().all()}

    # Unified engine — same grading loop as practice quizzes. Exams use raw
    # points (no difficulty weighting). This also fixes a real defect: this
    # path never JSON-decoded multi-select answers, so mcq_multi questions
    # were always graded wrong in exams.
    from modules.assessment.services.attempt_engine import grade_answer_set

    graded = await grade_answer_set(
        qs,
        exam.question_ids or [],
        body.answers,
        difficulty_weights=None,
        collect_details=False,
    )
    earned = graded.earned_points
    max_total = graded.max_points

    pct = (earned / max_total * 100.0) if max_total > 0 else 0.0
    attempt.answers = body.answers
    attempt.score = round(earned, 3)
    attempt.total = round(max_total, 3)
    attempt.passed = pct >= exam.passing_score
    attempt.status = "expired" if expired else "submitted"
    attempt.submitted_at = _now()
    await db.commit()

    return {
        "attempt_id": attempt.id,
        "score": attempt.score,
        "total": attempt.total,
        "percent": round(pct, 1),
        "passed": attempt.passed,
        "status": attempt.status,
        "flags": attempt.flags_count,
    }


# ── Proctoring ───────────────────────────────────────────────────────────────


class ProctorEventIn(BaseModel):
    event_type: str = Field(
        pattern=(
            "^(tab_switch|copy|paste|focus_loss|fullscreen_exit|webcam_snapshot|"
            "screen_snapshot|no_face|multiple_faces|camera_blocked|camera_denied)$"
        )
    )
    detail: str | None = None
    media_url: str | None = None


# Event types that are integrity FLAGS (everything except plain snapshots).
_PROCTOR_SNAPSHOT_TYPES = ("webcam_snapshot", "screen_snapshot")


@router.post("/attempts/{attempt_id}/proctor-event")
def log_proctor_event(
    attempt_id: int,
    body: ProctorEventIn,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    uid = int(current_user["sub"])
    attempt = db.query(models.ExamAttempt).filter(models.ExamAttempt.id == attempt_id).first()
    if not attempt or attempt.user_id != uid:
        raise HTTPException(404, "Attempt not found")
    ev = models.ProctorEvent(
        exam_attempt_id=attempt_id,
        event_type=body.event_type,
        detail=body.detail,
        media_url=body.media_url,
    )
    db.add(ev)
    # Non-media events are integrity flags.
    if body.event_type not in _PROCTOR_SNAPSHOT_TYPES:
        attempt.flags_count = (attempt.flags_count or 0) + 1
    db.commit()
    return {"logged": True, "flags": attempt.flags_count}


@router.get("/attempts/{attempt_id}/proctor-events")
def get_proctor_events(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    """Proctor review: full event timeline + webcam snapshots for one attempt.

    Returns snapshots (with media_url) and flag events (no_face, multiple_faces,
    tab_switch, …) so the review UI can render a snapshot gallery + flag timeline.
    """
    attempt = (
        db.query(models.ExamAttempt)
        .filter(models.ExamAttempt.id == attempt_id)
        .first()
    )
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    # Same-super-org guard via the parent exam; attempts themselves stay org-scoped.
    exam = db.query(models.Exam).filter(models.Exam.id == attempt.exam_id).first()
    assert_same_super_org(exam, current_user, db, "Exam")

    events = (
        db.query(models.ProctorEvent)
        .filter(models.ProctorEvent.exam_attempt_id == attempt_id)
        .order_by(models.ProctorEvent.created_at.asc())
        .all()
    )
    snapshots = [
        {
            "id": e.id,
            "media_url": e.media_url,
            "at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
        if e.event_type in _PROCTOR_SNAPSHOT_TYPES and e.media_url
    ]
    flags = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "detail": e.detail,
            "at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in events
        if e.event_type not in _PROCTOR_SNAPSHOT_TYPES
    ]
    return {
        "attempt_id": attempt_id,
        "user_id": attempt.user_id,
        "flags_count": attempt.flags_count or 0,
        "snapshots": snapshots,
        "flags": flags,
    }


@router.get("/me/attempts")
def my_exam_attempts(
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """The caller's own exam results — surfaced on their profile alongside
    quiz + coding attempts. Only completed (non-in-progress) attempts."""
    uid = int(current_user["sub"])
    attempts = (
        db.query(models.ExamAttempt)
        .filter(
            models.ExamAttempt.user_id == uid,
            models.ExamAttempt.status != "in_progress",
        )
        .order_by(models.ExamAttempt.submitted_at.desc().nullslast())
        .all()
    )
    exam_ids = list({a.exam_id for a in attempts})
    titles = {
        e.id: e.title
        for e in db.query(models.Exam).filter(models.Exam.id.in_(exam_ids)).all()
    } if exam_ids else {}
    def _pct(a: "models.ExamAttempt") -> float:
        tot = a.total or 0.0
        return round((a.score or 0.0) / tot * 100.0, 1) if tot > 0 else 0.0

    return {
        "attempts": [
            {
                "id": a.id,
                "exam_id": a.exam_id,
                "exam_title": titles.get(a.exam_id, "Exam"),
                "score": a.score,
                "total": a.total,
                "percent": _pct(a),
                "passed": a.passed,
                "status": a.status,
                "flags": a.flags_count,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
            for a in attempts
        ]
    }


@router.get("/{exam_id}/attempts")
def exam_attempts_for_review(
    exam_id: int,
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    """Proctor review: attempts with score + integrity flag counts."""
    exam = db.query(models.Exam).filter(models.Exam.id == exam_id).first()
    assert_same_super_org(exam, current_user, db, "Exam")
    # Attempts stay ORG-scoped: a sibling unit may reuse the exam but must not see
    # this unit's candidates.
    attempts = (
        scope_to_org(
            db.query(models.ExamAttempt).filter(
                models.ExamAttempt.exam_id == exam_id
            ),
            models.ExamAttempt,
            current_user,
        )
        .order_by(models.ExamAttempt.started_at.desc())
        .limit(limit)  # cap: a large cohort would otherwise return every attempt
        .all()
    )

    # Bug 8: resolve candidate identities so the review UI shows name + email
    # instead of "User 2 / User 78".
    user_ids = list({a.user_id for a in attempts})
    users = (
        db.query(models.User).filter(models.User.id.in_(user_ids)).all()
        if user_ids
        else []
    )
    user_map = {u.id: u for u in users}

    return {
        "attempts": [
            {
                "id": a.id,
                "user_id": a.user_id,
                "user_name": (user_map.get(a.user_id).full_name if user_map.get(a.user_id) else None)
                or f"User {a.user_id}",
                "user_email": user_map.get(a.user_id).email if user_map.get(a.user_id) else None,
                "status": a.status,
                "score": a.score,
                "total": a.total,
                "passed": a.passed,
                "flags": a.flags_count,
                "submitted_at": a.submitted_at.isoformat() if a.submitted_at else None,
            }
            for a in attempts
        ]
    }
