import csv
from io import StringIO

import models
from auth_utils import (
    assert_same_super_org,
    require_admin,
    scope_to_org,
    verify_token,
)
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/banks/{bank_id}/standard")
def export_standard(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Exports the high-level leaderboard data as a CSV.
    """
    # Exports carry the most data of any endpoint, so they are tenant-scoped on
    # BOTH sides: the bank by customer (shared content), the attempts by
    # organization (learner data never crosses a business unit).
    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    assert_same_super_org(bank, current_user, db, "Bank")

    attempts = (
        scope_to_org(
            db.query(models.Attempt).filter(models.Attempt.bank_id == bank_id),
            models.Attempt,
            current_user,
        )
        .order_by(models.Attempt.score.desc(), models.Attempt.time_taken.asc())
        .all()
    )

    # Deduplicate keeping best attempt
    seen_users = set()
    best_attempts = []
    for a in attempts:
        if a.user_name not in seen_users:
            best_attempts.append(a)
            seen_users.add(a.user_name)

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Rank", "Student", "Score", "Total", "Accuracy(%)", "Time(s)", "Date"]
    )

    for i, a in enumerate(best_attempts):
        acc = round((a.score / a.total) * 100) if a.total > 0 else 0
        date_str = a.attempted_at.strftime("%Y-%m-%d") if a.attempted_at else ""
        writer.writerow(
            [i + 1, a.user_name, a.score, a.total, acc, a.time_taken, date_str]
        )

    response = Response(content=output.getvalue())
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{bank.name}-leaderboard.csv"'
    )
    response.headers["Content-Type"] = "text/csv"
    return response


@router.get("/banks/{bank_id}/deep")
async def export_deep(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    """
    Exports a comprehensive CSV with every attempt, every marked answer, and all user notes.
    Uses StreamingResponse to prevent memory crashes on 1,000+ attempts.
    """
    from cache_manager import redis_client

    lock_key = f"rl:export_deep:{current_user['sub']}"
    try:
        acquired = await redis_client.set(lock_key, "locked", ex=30, nx=True)  # type: ignore
        if not acquired:
            raise HTTPException(
                status_code=429,
                detail="Export already in progress or requested too recently. Please wait.",
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        pass

    # NOTE: this handler deliberately keeps the SYNC Session. `iter_csv` below is a
    # sync generator that lazily streams rows via `yield_per(100)` while the response
    # is being sent — Starlette iterates sync generators in a threadpool, so the bulk
    # of the work already stays off the event loop. An AsyncSession cannot be used
    # there because the generator outlives the handler. Only this one lookup ran on
    # the loop, so it is pushed to the threadpool too.
    bank = await run_in_threadpool(
        lambda: db.query(models.QuestionBank)
        .filter(models.QuestionBank.id == bank_id)
        .first()
    )
    assert_same_super_org(bank, current_user, db, "Bank")

    def iter_csv():
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Attempt ID",
                "Date",
                "Student",
                "Total Score",
                "Time Taken (s)",
                "Question ID",
                "Question Text",
                "Correct Answer",
                "User Answer",
                "Is Correct",
                "User Note",
            ]
        )
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Stream the results in chunks of 100 instead of loading all into memory
        attempts = (
            scope_to_org(
                db.query(models.Attempt).filter(models.Attempt.bank_id == bank_id),
                models.Attempt,
                current_user,
            )
            .order_by(models.Attempt.attempted_at.desc())
            .yield_per(100)
        )

        for a in attempts:
            date_str = (
                a.attempted_at.strftime("%Y-%m-%d %H:%M:%S") if a.attempted_at else ""
            )

            # If the attempt has no descriptive answers detailed, we just put one summary row
            if not a.descriptive_answers:
                writer.writerow(
                    [
                        a.id,
                        date_str,
                        a.user_name,
                        f"{a.score}/{a.total}",
                        a.time_taken,
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)
                continue

            for ans in a.descriptive_answers:
                writer.writerow(
                    [
                        a.id,
                        date_str,
                        a.user_name,
                        f"{a.score}/{a.total}",
                        a.time_taken,
                        ans.get("question_id", ""),
                        ans.get("question_text", ""),
                        ans.get("correct_answer", ""),
                        ans.get("user_answer", ""),
                        str(ans.get("is_correct", "")).upper(),
                        ans.get("note", ""),
                    ]
                )
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    response = StreamingResponse(iter_csv(), media_type="text/csv")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{bank.name}-deep-export.csv"'
    )
    return response
