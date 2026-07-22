"""Gradebook + item analysis for a question bank (mentor / L&D facing)."""
import csv
import io

import models
from auth_utils import (
    assert_same_super_org,
    require_mentor_or_above,
    scope_to_org,
)
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from services.analytics import compute_gradebook, compute_item_analysis
from sqlalchemy.orm import Session

router = APIRouter(prefix="/gradebook", tags=["gradebook"])


def _load_bank(bank_id: int, db: Session, current_user: dict):
    """Fetch a bank and prove it belongs to the caller's organization.

    Fetching by primary key and then checking only the caller's ROLE is what let
    a mentor in one org read another org's gradebook.
    """
    bank = db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    # Banks are shared CONTENT -> super-org scope. The attempts fetched below stay
    # ORG-scoped, so a sibling business unit can reuse the bank without seeing
    # this unit's learner results.
    return assert_same_super_org(bank, current_user, db, "Question bank")


def _attempt_rows(bank_id: int, db: Session, current_user: dict) -> list:
    q = db.query(models.Attempt).filter(models.Attempt.bank_id == bank_id)
    return scope_to_org(q, models.Attempt, current_user).all()


@router.get("/bank/{bank_id}")
def gradebook(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    bank = _load_bank(bank_id, db, current_user)
    rows = [
        {
            "user_id": a.user_id,
            "user_name": a.user_name,
            "score": a.score,
            "total": a.total,
        }
        for a in _attempt_rows(bank_id, db, current_user)
    ]
    return {"bank": bank.name, "gradebook": compute_gradebook(rows)}


@router.get("/bank/{bank_id}/export.csv")
def gradebook_csv(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    _load_bank(bank_id, db, current_user)  # 404 on a bank outside the caller's org
    rows = [
        {"user_id": a.user_id, "user_name": a.user_name, "score": a.score, "total": a.total}
        for a in _attempt_rows(bank_id, db, current_user)
    ]
    grades = compute_gradebook(rows)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "user_name", "best_score", "best_total", "best_pct", "attempts"])
    for g in grades:
        w.writerow([g["user_id"], g["user_name"], g["best_score"], g["best_total"], g["best_pct"], g["attempts"]])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="gradebook_bank_{bank_id}.csv"'},
    )


@router.get("/bank/{bank_id}/item-analysis")
def item_analysis(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_mentor_or_above),
):
    """Difficulty + discrimination per question, computed from stored attempts."""
    _load_bank(bank_id, db, current_user)  # 404 on a bank outside the caller's org
    attempts = []
    for a in _attempt_rows(bank_id, db, current_user):
        detailed = a.descriptive_answers or []
        items = {}
        if isinstance(detailed, list):
            for d in detailed:
                if isinstance(d, dict) and d.get("question_id") is not None:
                    items[d["question_id"]] = bool(d.get("is_correct"))
        if items:
            attempts.append({"total": a.score or 0, "items": items})

    analysis = compute_item_analysis(attempts)
    # enrich with question text
    qids = [x["question_id"] for x in analysis]
    q_text = {
        q.id: q.question
        for q in db.query(models.Question).filter(models.Question.id.in_(qids)).all()
    }
    for x in analysis:
        x["question"] = (q_text.get(x["question_id"], "") or "")[:160]
    return {"bank_id": bank_id, "responses": len(attempts), "items": analysis}
