"""Shared imports/helpers/schemas for the split quiz router (moved verbatim from routers/quiz.py — do not re-type)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger("quiz")

from datetime import datetime, timezone  # noqa: E402

from typing import Any, Dict, List, Optional  # noqa: E402

import models  # noqa: E402

import schemas  # noqa: E402

from auth_utils import SECRET_KEY  # noqa: E402

from auth_utils import (  # noqa: E402
    assert_group_in_org,
    assert_same_org,
    assert_same_super_org,
    caller_org_id,
    caller_super_org_id,
    require_admin,
    scope_to_org,
    verify_token,
)

from database import get_async_db, get_db  # noqa: E402

from services.audit_service import log_admin_action  # noqa: E402

from sqlalchemy import and_, func, or_, select  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

DIFFICULTY_WEIGHTS = {
    "Easy": 1.0,
    "Medium": 1.5,
    "Hard": 2.0,
}

def resolve_answer(answer: str, options: list) -> str:
    """
    Resolves letter-based answers (A/B/C/D) to full text options.
    Handles both legacy letter answers and full text answers.
    """
    if not answer:
        return ""
    trimmed = answer.strip()
    upper = trimmed.upper()
    if upper in ["A", "B", "C", "D"] and len(upper) == 1:
        idx = ord(upper) - 65
        if options and idx < len(options) and options[idx]:
            return str(options[idx])
    return trimmed

from cache_manager import cache_manager  # noqa: E402

from pagination import paginate  # noqa: E402

import csv  # noqa: E402

import io  # noqa: E402

from fastapi import File, UploadFile  # noqa: E402

try:
    import openpyxl
except ImportError:
    openpyxl = None

def check_attempt_eligibility(
    user_id: int, bank_id: int, db: Session
) -> tuple[bool, str]:
    from datetime import datetime

    bank = (
        db.query(models.QuestionBank).filter(models.QuestionBank.id == bank_id).first()
    )
    if not bank:
        return False, "Bank not found"

    # I-a: Access scope (SEC) — a non-public bank with an EXPLICIT subscriber-group
    # list must include the learner's group, unless an active assignment grants
    # access. Conservative: banks with no subscriber list stay open (no regression).
    _u = db.query(models.User).filter(models.User.id == user_id).first()
    _gid = _u.group_id if _u else None
    _public = bool(getattr(bank, "is_org_public", False)) or getattr(
        bank, "visibility_scope", ""
    ) == "org-public"
    _subs = bank.subscriber_groups or []
    if _gid and _subs and not _public and _gid not in _subs:
        _tfs = [
            (models.Assignment.target_type == "group")
            & (models.Assignment.target_id == _gid)
        ]
        _grp = _u.group if _u else None
        if _grp and _grp.batch_id:
            _tfs.append(
                (models.Assignment.target_type == "batch")
                & (models.Assignment.target_id == _grp.batch_id)
            )
        _granted = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.bank_id == bank_id,
                models.Assignment.is_active.is_(True),
                or_(*_tfs),
            )
            .first()
        )
        if not _granted:
            return False, "This quiz is not available to your group."

    # I: Check Assignment specifics (Mandates)
    user_obj = db.query(models.User).filter(models.User.id == user_id).first()
    if user_obj and user_obj.group_id:
        group = user_obj.group
        target_filters = [
            (models.Assignment.target_type == "group")
            & (models.Assignment.target_id == user_obj.group_id)
        ]
        if group.batch_id:
            target_filters.append(
                (models.Assignment.target_type == "batch")
                & (models.Assignment.target_id == group.batch_id)
            )
            if group.batch.vertical_id:
                target_filters.append(
                    (models.Assignment.target_type == "vertical")
                    & (models.Assignment.target_id == group.batch.vertical_id)
                )

        active_assignment = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.bank_id == bank_id,
                models.Assignment.is_active.is_(True),
                or_(*target_filters),
            )
            .first()
        )

        if active_assignment:
            # Check deadline lockout
            if (
                active_assignment.lock_after_due
                and active_assignment.due_date
                and active_assignment.due_date.replace(tzinfo=timezone.utc)
                < datetime.now(timezone.utc)
            ):
                return (
                    False,
                    f"Assignment deadline passed on {active_assignment.due_date.strftime('%Y-%m-%d')}. Locked.",
                )

            # Check attempt limits and completion status for this specific assignment
            completion = (
                db.query(models.AssignmentCompletion)
                .filter(
                    models.AssignmentCompletion.assignment_id == active_assignment.id,
                    models.AssignmentCompletion.user_id == user_id,
                )
                .first()
            )
            if completion:
                if completion.status == "completed" or completion.status == "passed":
                    return (
                        False,
                        "You have already completed this assignment successfully.",
                    )
                if (
                    active_assignment.max_attempts
                    and completion.attempts_used >= active_assignment.max_attempts
                ):
                    return (
                        False,
                        f"Maximum {active_assignment.max_attempts} attempts reached for this mandatory assignment.",
                    )

    # II: Standard Bank-level limits
    if bank.max_total_attempts:
        total = (
            db.query(models.Attempt)
            .filter(
                models.Attempt.user_id == user_id, models.Attempt.bank_id == bank_id
            )
            .count()
        )
        if total >= bank.max_total_attempts:
            return (
                False,
                f"Maximum {bank.max_total_attempts} total attempts reached for this bank",
            )

    if bank.max_attempts_per_day:
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_count = (
            db.query(models.Attempt)
            .filter(
                models.Attempt.user_id == user_id,
                models.Attempt.bank_id == bank_id,
                models.Attempt.attempted_at >= today_start,
            )
            .count()
        )
        if today_count >= bank.max_attempts_per_day:
            return False, "Daily attempt limit reached. Try again tomorrow."

    return True, "ok"

from services.redis_service import redis_client  # noqa: E402

CERT_TOKEN_TTL_SECONDS = 900

def _certificate_token(attempt_id: int, expires_at: int) -> str:
    import hashlib
    import hmac as _hmac

    msg = f"cert:{attempt_id}:{expires_at}".encode()
    return _hmac.new(SECRET_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]

def _verify_certificate_token(attempt_id: int, expires_at: int, token: str) -> None:
    import hmac as _hmac
    import time as _time

    if expires_at < int(_time.time()):
        raise HTTPException(status_code=403, detail="Certificate link has expired.")
    if not _hmac.compare_digest(_certificate_token(attempt_id, expires_at), token or ""):
        raise HTTPException(status_code=403, detail="Invalid certificate link.")
