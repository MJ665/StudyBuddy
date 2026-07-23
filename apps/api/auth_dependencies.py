"""FastAPI auth *dependency* callables (require_* role guards).

Split out of auth_utils.py (verbatim) to keep that module under the 800-line
cap. auth_utils re-exports every name here, so `from auth_utils import
require_ldadmin` (and friends) keep working unchanged.
"""
import logging
from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, status
from database import get_db
from models.auth import Group, MentorGroupAssignment, User, UserRole
from sqlalchemy.orm import Session

from auth_utils import (
    PLATFORM_ADMIN_ROLE,
    check_scoped_role,
    verify_token,
)

logger = logging.getLogger(__name__)


def require_group_admin(
    current_user: dict = Depends(verify_token), db: Session = Depends(get_db)
):
    """Blocks anyone except someone with GroupAdmin (scoped) or LDAdmin (global) roles."""
    if current_user["role"] == "LDAdmin":
        return current_user

    user_id = int(current_user["sub"])
    # If they are a GroupAdmin for ANY group, we allow general entry to admin panels,
    # but specific group data requires scoped checks.
    if current_user["role"] in ["GroupAdmin", "Admin", "Mentor"]:
        return current_user

    # Double check DB for secondary roles
    role_exists = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.role.in_(["GroupAdmin", "LDAdmin", "Admin"]),
        )
        .first()
    )

    if not role_exists:
        raise HTTPException(
            status_code=403, detail="Administrative privileges required"
        )

    return current_user


def require_mentor(
    current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
) -> Dict:
    """Blocks anyone except Mentor or LDAdmin."""
    if current_user.get("role") == "LDAdmin":
        return current_user

    user_id = int(current_user["sub"])
    if current_user.get("role") == "Mentor":
        return current_user

    # Check UserRole for secondary mentor assignments
    exists = (
        db.query(UserRole)
        .filter(UserRole.user_id == user_id, UserRole.role.in_(["Mentor", "mentor"]))
        .first()
    )
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Mentor permissions required"
        )

    return current_user


def require_mentor_for_group(
    group_id: int,
    current_user: Dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict:
    """Ensures Mentor is actually assigned to this specific group via UserRole (V3) or MentorGroupAssignment (V2)."""
    if current_user.get("role") == "LDAdmin":
        return current_user

    user_id = int(current_user.get("sub") or 0)

    # Check V3 UserRole table first (Strategic Mapping)
    if check_scoped_role(user_id, "Mentor", "group", group_id, db):
        return current_user

    # Fallback to V2 Legacy table
    assign = (
        db.query(MentorGroupAssignment)
        .filter_by(mentor_id=user_id, group_id=group_id, is_active=True)
        .first()
    )
    if assign:
        return current_user

    raise HTTPException(
        status_code=403,
        detail="Access denied: You do not have Mentor oversight for this sector.",
    )


def require_group_admin_for_group(
    group_id: int,
    current_user: Dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict:
    """Ensures GroupAdmin can only access their own group via DB lookup."""
    if current_user.get("role") == "LDAdmin":
        return current_user

    user_id = int(current_user.get("sub") or 0)
    if check_scoped_role(user_id, "GroupAdmin", "group", group_id, db):
        return current_user

    # Fallback to primary group_id in token (for legacy)
    if (
        current_user.get("role") in ["GroupAdmin", "Admin"]
        and int(current_user.get("group_id", -1)) == group_id
    ):
        return current_user

    raise HTTPException(
        status_code=403,
        detail="Access denied: Your administrative scope is restricted to your primary sector.",
    )


def require_ldadmin(
    current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
) -> Dict:
    """Blocks anyone except L&D Super Admin (Verified against DB).

    PlatformAdmin is admitted because it sits ABOVE LDAdmin in the hierarchy
    (PlatformAdmin > SuperOrganization > LDAdmin). Without this the platform
    operator was locked out of the very screens it must support customers on.
    """
    user_id = int(current_user["sub"])
    user = db.query(User).filter(User.id == user_id).first()

    if not user or user.role not in ("LDAdmin", PLATFORM_ADMIN_ROLE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Global LDAdmin status required for this operation.",
        )

    return current_user


def require_platform_admin(
    current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
) -> Dict:
    """Blocks anyone except the Platform Super Admin — the top of the hierarchy,
    above LDAdmin. Governs org approval/suspension and the /platform dashboard.
    Verified against the DB so a stale JWT cannot escalate."""
    user_id = int(current_user["sub"])
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != "PlatformAdmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform Administrator access required.",
        )
    return current_user


def require_mentor_or_above(
    current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
) -> Dict:
    """Mentor, GroupAdmin, LDAdmin — or PlatformAdmin, which outranks them all.

    NOTE: this only establishes ROLE. It cannot express "within my organization",
    which is why every endpoint using it must ALSO apply a tenant check
    (`assert_same_org` / `scope_to_org` / `assert_batch_in_org`).
    """
    role = current_user.get("role")
    if role in [
        "Mentor",
        "GroupAdmin",
        "LDAdmin",
        "mentor",
        "group_admin",
        "ld_admin",
        "Owner",
        "owner",
        PLATFORM_ADMIN_ROLE,
    ]:
        return current_user

    # Secondary check in UserRole table for scoped roles
    user_id = int(current_user["sub"])
    exists = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.role.in_(
                [
                    "Mentor",
                    "GroupAdmin",
                    "LDAdmin",
                    "mentor",
                    "group_admin",
                    "ld_admin",
                    "Owner",
                    "owner",
                ]
            ),
        )
        .first()
    )

    if not exists:
        raise HTTPException(
            status_code=403, detail="Mentor or Administrative privileges required"
        )

    return current_user


def require_admin_for(group_id: int):
    """
    Factory: returns a FastAPI Depends-compatible function that enforces
    GroupAdmin access to a *specific* group. Resolves SEC-101 (RBAC data leakage).
    """

    def _check(
        current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
    ) -> Dict:
        return require_group_admin_for_group(group_id, current_user, db)

    return _check


def get_mentor_ids_for_group(db: Session, group_id: int) -> List[int]:
    """Retrieves all user IDs with Mentor role assigned to a specific group."""
    # 1. Check V3 Scoped Roles
    scoped_mentors = (
        db.query(UserRole.user_id)
        .filter(
            UserRole.role.in_(["Mentor", "mentor"]),
            UserRole.scope_type == "group",
            UserRole.scope_id == group_id,
        )
        .all()
    )

    # 2. Check V2 Legacy Assignments
    legacy_mentors = (
        db.query(MentorGroupAssignment.mentor_id)
        .filter(MentorGroupAssignment.group_id == group_id)
        .all()
    )

    return list(set([m[0] for m in scoped_mentors] + [m[0] for m in legacy_mentors]))


def require_mentor_for(group_id: int):
    """
    Factory: enforces Mentor scope for a specific group.
    """

    def _check(
        current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
    ) -> Dict:
        return require_mentor_for_group(group_id, current_user, db)

    return _check


# Legacy mapping
require_admin = require_group_admin


def require_mentor_for_batch(
    batch_id: int,
    current_user: Dict = Depends(verify_token),
    db: Session = Depends(get_db),
) -> Dict:
    """Ensures Mentor has access to at least one group in the specified batch or is a Batch-level Mentor."""
    if current_user.get("role") == "LDAdmin":
        return current_user

    user_id = int(current_user.get("sub") or 0)

    # Check Batch-level role first (V3)
    if check_scoped_role(user_id, "Mentor", "batch", batch_id, db):
        return current_user

    # Fallback: check if they oversee any group within this batch
    group_ids = [
        g.id for g in db.query(Group.id).filter(Group.batch_id == batch_id).all()
    ]
    if not group_ids:
        raise HTTPException(
            status_code=404, detail="Batch has no groups for oversight."
        )

    # Check UserRole for any of these groups
    exists = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.role.in_(["Mentor", "mentor"]),
            UserRole.scope_type == "group",
            UserRole.scope_id.in_(group_ids),
        )
        .first()
    )

    if exists:
        return current_user

    # Check Legacy table for any of these groups
    legacy_assign = (
        db.query(MentorGroupAssignment)
        .filter(
            MentorGroupAssignment.mentor_id == user_id,
            MentorGroupAssignment.group_id.in_(group_ids),
            MentorGroupAssignment.is_active == True,
        )
        .first()
    )

    if legacy_assign:
        return current_user

    raise HTTPException(
        status_code=403,
        detail="Access denied: You do not have Mentor oversight for this batch.",
    )


def require_mentor_for_batch_scope(batch_id: int):
    """Factory for batch-scoped mentor access."""

    def _check(
        current_user: Dict = Depends(verify_token), db: Session = Depends(get_db)
    ) -> Dict:
        return require_mentor_for_batch(batch_id, current_user, db)

    return _check
