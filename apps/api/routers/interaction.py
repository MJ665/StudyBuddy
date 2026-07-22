import json
import logging
from collections import defaultdict
from typing import Optional

import models
from auth_utils import (
    assert_same_super_org,
    assert_same_super_org_async,
    verify_token,
)
from cache_manager import redis_client
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

router = APIRouter(prefix="/interaction", tags=["interaction"])


# ── Tenant guards ────────────────────────────────────────────────────────────
# Several endpoints take a question_id / bank_id / discussion_id straight from the
# URL and act on it. Questions and banks are authored CONTENT, so they are checked
# against the caller's SUPER-organization (a sibling business unit may share the
# bank). Without these, a caller could read or comment on another customer's
# question by id — the same IDOR class already fixed on the quiz/coding sides.
def _require_question_scope(question_id: int, db, current_user: dict):
    q = db.query(models.Question).filter(models.Question.id == question_id).first()
    return assert_same_super_org(q, current_user, db, "Question")


def _require_discussion_scope(discussion_id: int, db, current_user: dict):
    d = (
        db.query(models.QuestionDiscussion)
        .filter(models.QuestionDiscussion.id == discussion_id)
        .first()
    )
    if not d:
        raise HTTPException(status_code=404, detail="Not found")
    _require_question_scope(d.question_id, db, current_user)
    return d


async def _require_question_scope_async(question_id: int, db, current_user: dict):
    q = await db.get(models.Question, question_id)
    return await assert_same_super_org_async(q, current_user, db, "Question")

# Safety cap for user-facing lists that would otherwise grow without bound.
MAX_THREAD_ROWS = 500
logger = logging.getLogger(__name__)


# --- Question Reporting ---
class ReportCreate(BaseModel):
    issue_type: str
    description: str


@router.post("/questions/{question_id}/report")
def report_question(
    question_id: int,
    data: ReportCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    _require_question_scope(question_id, db, current_user)
    user_id = int(current_user["sub"])
    report = models.QuestionReport(
        question_id=question_id,
        user_id=user_id,
        issue_type=data.issue_type,
        description=data.description,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {"message": "Report submitted successfully", "report_id": report.id}


@router.get("/reports/pending")
def pending_reports(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    if current_user.get("role") not in ["LDAdmin", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")
    reports = (
        db.query(models.QuestionReport)
        .filter(models.QuestionReport.is_resolved.is_(False))  # type: ignore
        .all()
    )
    # Serialize securely
    ret = []
    for r in reports:
        ret.append(
            {
                "id": r.id,
                "question_id": r.question_id,
                "reporter_id": r.user_id,
                "reason": r.issue_type,
                "comment": r.description,
                "is_resolved": r.is_resolved,
                "created_at": r.created_at,
            }
        )
    return ret


@router.patch("/reports/{report_id}/resolve")
def resolve_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    if current_user.get("role") not in ["LDAdmin", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    report = (
        db.query(models.QuestionReport)
        .filter(models.QuestionReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Not found")

    report.is_resolved = True
    report.resolved_by = int(current_user["sub"])
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="RESOLVE_REPORT",
        resource_type="QUESTION_REPORT",
        resource_id=report_id,
        details={"question_id": report.question_id},
    )

    return {"message": "Resolved"}


# --- Discussions ---
class DiscussionCreate(BaseModel):
    content: str
    parent_id: Optional[int] = None


@router.get("/questions/{question_id}/discussions")
async def get_discussions(
    question_id: int,
    limit: int = Query(MAX_THREAD_ROWS, ge=1, le=MAX_THREAD_ROWS),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    await _require_question_scope_async(question_id, db, current_user)

    redis_key = f"discussions:question:{question_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Discussion cache lookup failed: {e}")

    # Fetch the whole thread tree in ONE query and assemble it in memory: the old
    # code issued a user lookup per node (N+1) and walked a lazy relationship,
    # which an AsyncSession cannot do implicitly.
    # Hard cap: a hot question could otherwise return an unbounded thread tree.
    rows = await db.execute(
        select(models.QuestionDiscussion)
        .where(models.QuestionDiscussion.question_id == question_id)
        .order_by(models.QuestionDiscussion.created_at.desc())
        .limit(limit)
    )
    all_nodes = rows.scalars().all()

    user_ids = {n.user_id for n in all_nodes}
    users: dict = {}
    if user_ids:
        urows = await db.execute(
            select(models.User).where(models.User.id.in_(user_ids))
        )
        users = {u.id: u for u in urows.scalars().all()}

    children = defaultdict(list)
    for n in all_nodes:
        if n.parent_id is not None:
            children[n.parent_id].append(n)
    # Replies read oldest-first; root threads stay newest-first as before.
    for kids in children.values():
        kids.sort(key=lambda n: n.id)

    def serialize_thread(t):
        user = users.get(t.user_id)
        return {
            "id": t.id,
            "user_id": t.user_id,
            "user_name": user.full_name if user else "Unknown",
            "content": t.content,
            "upvotes": t.upvotes,
            "is_pinned": t.is_pinned,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "replies": [serialize_thread(c) for c in children.get(t.id, [])],
        }

    res = [serialize_thread(t) for t in all_nodes if t.parent_id is None]
    try:
        await redis_client.set(redis_key, json.dumps(res), ex=300)
    except Exception as e:
        logger.warning(f"Discussion cache write failed: {e}")

    return res


@router.get("/discussions")
async def get_global_discussions(
    bank_id: Optional[int] = None,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    if bank_id:
        bank = await db.get(models.QuestionBank, bank_id)
        await assert_same_super_org_async(bank, current_user, db, "Bank")

    redis_key = f"discussions:global:{bank_id}:{page}:{size}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Global discussion cache lookup failed: {e}")

    base = select(models.QuestionDiscussion).where(
        models.QuestionDiscussion.parent_id.is_(None)
    )
    count_stmt = select(func.count()).select_from(models.QuestionDiscussion).where(
        models.QuestionDiscussion.parent_id.is_(None)
    )
    if bank_id:
        join_cond = models.QuestionDiscussion.question_id == models.Question.id
        base = base.join(models.Question, join_cond).where(
            models.Question.bank_id == bank_id
        )
        count_stmt = count_stmt.join(models.Question, join_cond).where(
            models.Question.bank_id == bank_id
        )

    total = (await db.execute(count_stmt)).scalar_one()
    rows = await db.execute(
        base.order_by(models.QuestionDiscussion.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    threads = rows.scalars().all()

    # Batch every lookup the old per-thread loop did one row at a time.
    user_ids = {t.user_id for t in threads}
    question_ids = {t.question_id for t in threads}
    thread_ids = [t.id for t in threads]

    users: dict = {}
    if user_ids:
        r = await db.execute(select(models.User).where(models.User.id.in_(user_ids)))
        users = {u.id: u for u in r.scalars().all()}

    questions: dict = {}
    if question_ids:
        r = await db.execute(
            select(models.Question).where(models.Question.id.in_(question_ids))
        )
        questions = {q.id: q for q in r.scalars().all()}

    banks: dict = {}
    bank_ids = {q.bank_id for q in questions.values() if q.bank_id is not None}
    if bank_ids:
        r = await db.execute(
            select(models.QuestionBank).where(models.QuestionBank.id.in_(bank_ids))
        )
        banks = {b.id: b for b in r.scalars().all()}

    reply_counts: dict = {}
    if thread_ids:
        r = await db.execute(
            select(
                models.QuestionDiscussion.parent_id,
                func.count(models.QuestionDiscussion.id),
            )
            .where(models.QuestionDiscussion.parent_id.in_(thread_ids))
            .group_by(models.QuestionDiscussion.parent_id)
        )
        reply_counts = {pid: cnt for pid, cnt in r.all()}

    ret = []
    for t in threads:
        user = users.get(t.user_id)
        question = questions.get(t.question_id)
        bank = banks.get(question.bank_id) if question else None
        ret.append(
            {
                "id": t.id,
                "user_id": t.user_id,
                "user_name": user.full_name if user else "Unknown",
                "user_slug": (user.custom_slug if user else None)
                or (user.email.split("@")[0] if user else None),
                "content": t.content,
                "upvotes": t.upvotes,
                "is_pinned": t.is_pinned,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "question_id": t.question_id,
                "question_text": question.question if question else "Deleted Question",
                "bank_id": question.bank_id if question else None,
                "bank_name": bank.name if bank else "Deleted Bank",
                "reply_count": reply_counts.get(t.id, 0),
            }
        )

    res = {"items": ret, "total": total, "page": page, "size": size}

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=300)
    except Exception as e:
        logger.warning(f"Global discussion cache write failed: {e}")

    return res


@router.post("/questions/{question_id}/discussions")
async def add_discussion(
    question_id: int,
    data: DiscussionCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    q = await db.get(models.Question, question_id)
    await assert_same_super_org_async(q, current_user, db, "Question")

    if len(data.content) > 2000:
        raise HTTPException(status_code=400, detail="Comment too long (max 2000 chars)")

    if data.parent_id is not None:
        parent = await db.get(models.QuestionDiscussion, data.parent_id)
        if not parent or parent.question_id != question_id:
            raise HTTPException(
                status_code=400, detail="Parent comment does not belong to this question"
            )

    t = models.QuestionDiscussion(
        question_id=question_id,
        user_id=int(current_user["sub"]),
        content=data.content,
        parent_id=data.parent_id,
    )
    db.add(t)
    await db.commit()
    await db.refresh(t)

    try:
        await redis_client.delete(f"discussions:question:{question_id}")
    except Exception as e:
        logger.warning(f"Discussion cache purge failed: {e}")

    return {"message": "Comment posted", "id": t.id}


@router.post("/discussions/{discussion_id}/vote")
def vote_discussion(
    discussion_id: int,
    direction: str = "up",
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Increment/Decrement discussion upvotes."""
    d = _require_discussion_scope(discussion_id, db, current_user)

    if direction == "up":
        d.upvotes += 1
    else:
        d.upvotes = max(0, d.upvotes - 1)

    db.commit()
    return {"upvotes": d.upvotes}


@router.delete("/discussions/{discussion_id}")
def delete_discussion(
    discussion_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Allow user or admin to delete a comment."""
    d = _require_discussion_scope(discussion_id, db, current_user)

    if d.user_id != int(current_user["sub"]) and current_user["role"] not in [
        "LDAdmin",
        "GroupAdmin",
    ]:
        raise HTTPException(status_code=403)

    db.delete(d)
    db.commit()
    return {"success": True}


# --- Notifications ---
@router.get("/notifications")
def get_notifications(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    user_id = int(current_user["sub"])
    notifs = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return notifs


@router.patch("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    r = await db.execute(
        select(models.Notification).where(
            models.Notification.id == notif_id,
            models.Notification.user_id == user_id,
        )
    )
    notif = r.scalars().first()
    if notif and not notif.is_read:
        notif.is_read = True
        await db.commit()
        try:
            await redis_client.decr(f"notifications:unread:{user_id}")
        except Exception as e:
            logger.warning(f"Unread-count decrement failed: {e}")
    return {"success": True}


@router.post("/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    await db.execute(
        update(models.Notification)
        .where(
            models.Notification.user_id == user_id,
            models.Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    try:
        await redis_client.set(f"notifications:unread:{user_id}", 0)
    except Exception as e:
        logger.warning(f"Unread-count reset failed: {e}")
    return {"success": True}


@router.get("/notifications/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    redis_key = f"notifications:unread:{user_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached is not None:
            return {"unread_count": int(cached)}
    except Exception as e:
        logger.warning(f"Unread-count cache lookup failed: {e}")

    r = await db.execute(
        select(func.count())
        .select_from(models.Notification)
        .where(
            models.Notification.user_id == user_id,
            models.Notification.is_read.is_(False),
        )
    )
    count = r.scalar_one()

    try:
        await redis_client.set(redis_key, count, ex=3600)
    except Exception as e:
        logger.warning(f"Unread-count cache write failed: {e}")

    return {"unread_count": count}


@router.delete("/notifications/{notif_id}")
async def delete_notification(
    notif_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """PURGE: Remove a notification artifact from the user's registry."""
    user_id = int(current_user["sub"])
    r = await db.execute(
        select(models.Notification).where(
            models.Notification.id == notif_id,
            models.Notification.user_id == user_id,
        )
    )
    notif = r.scalars().first()

    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")

    is_unread = not notif.is_read
    await db.delete(notif)
    await db.commit()

    if is_unread:
        try:
            await redis_client.decr(f"notifications:unread:{user_id}")
        except Exception as e:
            logger.warning(f"Unread-count decrement failed: {e}")

    return {"success": True, "message": "Notification purged."}


# --- Bookmarks ---
@router.post("/questions/{question_id}/bookmark")
def toggle_bookmark(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    _require_question_scope(question_id, db, current_user)
    user_id = int(current_user["sub"])
    bookmark = (
        db.query(models.UserBookmark)
        .filter(
            models.UserBookmark.user_id == user_id,
            models.UserBookmark.question_id == question_id,
        )
        .first()
    )

    if bookmark:
        db.delete(bookmark)
        db.commit()
        return {"is_bookmarked": False, "message": "Bookmark removed"}
    else:
        new_bookmark = models.UserBookmark(user_id=user_id, question_id=question_id)
        db.add(new_bookmark)
        db.commit()
        return {"is_bookmarked": True, "message": "Bookmark added"}


@router.get("/questions/{question_id}/bookmark-status")
def get_bookmark_status(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    _require_question_scope(question_id, db, current_user)
    user_id = int(current_user["sub"])
    bookmark = (
        db.query(models.UserBookmark)
        .filter(
            models.UserBookmark.user_id == user_id,
            models.UserBookmark.question_id == question_id,
        )
        .first()
    )
    return {"is_bookmarked": bookmark is not None}


@router.get("/bookmarks")
def get_bookmarks(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    user_id = int(current_user["sub"])
    bookmarks = (
        db.query(models.UserBookmark)
        .filter(models.UserBookmark.user_id == user_id)
        .all()
    )

    ret = []
    for b in bookmarks:
        q = b.question
        if not q:
            continue
        ret.append(
            {
                "id": q.id,
                "bank_id": q.bank_id,
                "question": q.question,
                "options": q.options,
                "answer": q.answer,
                "explanation": q.user_description,
                "difficulty": q.difficulty,
                "bookmarked_at": b.created_at,
            }
        )
    return ret
