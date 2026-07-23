"""Shared imports/helpers/schemas for the split mentor router (moved verbatim from routers/mentor.py — do not re-type)."""

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
