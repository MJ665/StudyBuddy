import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import jwt
from config import settings
from database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from models.auth import Group, MentorGroupAssignment, User, UserRole
from models.org import Batch, Department, Organization, SuperOrganization, Vertical
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Unified Security Protocol Constants
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Top of the hierarchy: PlatformAdmin > SuperOrganization > LDAdmin > Mentor/GroupAdmin > Member
PLATFORM_ADMIN_ROLE = "PlatformAdmin"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int):
    """Generates a long-lived refresh token (STRAT-SEC-01) with unique JTI."""
    import secrets

    jti = secrets.token_hex(16)
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode = {"sub": str(user_id), "exp": expire, "type": "refresh", "jti": jti}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM), expire


def resolve_user_organization_id(user: User, db: Session) -> int | None:
    """Resolve the organization a user belongs to, or None if unattributable.

    `users.organization_id` is now denormalized and backfilled, so this is
    normally a single column read; the hierarchy walk remains as a fallback for
    rows created before attribution.

    Returns None rather than guessing. The previous implementation fell back to
    `db.query(Organization).first()` — silently placing an unattributable user in
    whatever organization happened to be first — and then to a hardcoded `4`,
    an organization that does not exist. Both are tenancy violations: every
    downstream org filter is only as trustworthy as this value.
    """
    if getattr(user, "organization_id", None):
        return user.organization_id

    if user.department_id:
        dept = db.query(Department).filter(Department.id == user.department_id).first()
        if dept:
            return dept.organization_id

    if user.group_id:
        group = db.query(Group).filter(Group.id == user.group_id).first()
        if group:
            if group.department_id:
                dept = (
                    db.query(Department)
                    .filter(Department.id == group.department_id)
                    .first()
                )
                if dept:
                    return dept.organization_id
            # group -> batch -> vertical -> department
            if group.batch_id:
                row = (
                    db.query(Department.organization_id)
                    .join(Vertical, Vertical.department_id == Department.id)
                    .join(Batch, Batch.vertical_id == Vertical.id)
                    .filter(Batch.id == group.batch_id)
                    .first()
                )
                if row:
                    return row[0]

    return None


SUSPENDED_STATUSES = {"suspended", "pending", "rejected"}


def assert_tenant_active(org_id: Optional[int], db: Session, role: str = "") -> None:
    """Block users whose customer account is suspended (or not yet approved).

    Suspension was previously cosmetic: /platform flipped a status column that
    nothing ever read, so a suspended customer kept full access. This is enforced
    at BOTH token issue and token verification, so revoking access does not wait
    for an existing token to expire.

    PlatformAdmin is exempt — they must still be able to administer a suspended
    customer in order to reactivate it.
    """
    if role == PLATFORM_ADMIN_ROLE or org_id is None:
        return

    row = (
        db.query(Organization.status, Organization.super_organization_id)
        .filter(Organization.id == org_id)
        .first()
    )
    if row is None:
        return

    org_status, super_id = row
    statuses = {org_status}
    if super_id is not None:
        super_status = (
            db.query(SuperOrganization.status)
            .filter(SuperOrganization.id == super_id)
            .scalar()
        )
        statuses.add(super_status)

    blocked = {s for s in statuses if s in SUSPENDED_STATUSES}
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your organization's account is not active. Please contact your administrator.",
        )


def get_user_jwt_payload(user: User, db: Session) -> Dict:
    """Constructs the standard JWT payload with multi-tenant context."""
    org_id = resolve_user_organization_id(user, db)

    if org_id is None:
        # Platform-level identities (the vendor operator + the ID-0 system
        # identity) are cross-org BY DESIGN — they administer /platform, not
        # any single organization. Their tokens carry organization_id=None;
        # every org-scoping helper already treats None as "deny", so this
        # cannot widen data access — platform endpoints gate on the role.
        if user.role == "PlatformAdmin" or user.id == 0:
            return {
                "sub": str(user.id),
                "name": user.full_name,
                "role": user.role,
                "group_id": user.group_id,
                "organization_id": None,
            }
        # Fail closed. A token without a resolvable tenant cannot be scoped, so
        # issuing one would hand the bearer an ambiguous identity.
        logger.error(
            "Cannot resolve organization for user %s (%s); refusing to issue a token.",
            user.id,
            user.email,
        )
        raise HTTPException(
            status_code=403,
            detail="Your account is not linked to an organization. Contact your administrator.",
        )

    assert_tenant_active(org_id, db, user.role)

    return {
        "sub": str(user.id),
        "name": user.full_name,
        "role": user.role,
        "group_id": user.group_id,
        "organization_id": org_id,
    }


def verify_token(token: str = Depends(oauth2_scheme)) -> Dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        import logging

        logger = logging.getLogger("auth")

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except jwt.ExpiredSignatureError:
            logger.warning(
                f"🔐 Auth Failure: Token expired. Token start: {token[:10]}..."
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError as e:
            logger.warning(
                f"🔐 Auth Failure: Invalid token ({str(e)}). Token start: {token[:10]}..."
            )
            raise credentials_exception

        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning(
                f"🔐 Auth Failure: Missing 'sub' in payload. Payload: {payload}"
            )
            raise credentials_exception

        # ── Always enrich payload from DB to pick up role promotions ──────────
        # This ensures newly promoted Mentors are not blocked by stale JWT role claims.
        from database import SessionLocal
        from models.auth import Group, User
        from models.org import Department, Organization

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == int(user_id)).first()
            if not user:
                raise credentials_exception

            # Always use the live DB role — overrides JWT claim
            payload["role"] = user.role
            payload["group_id"] = user.group_id

            # Resolve organization_id from the DB, never from the client's token:
            # a self-asserted tenant id would defeat every downstream org filter.
            org_id = resolve_user_organization_id(user, db)
            if org_id is None:
                # Platform-level identities (vendor operator + ID-0 system) are
                # cross-org by design; org-scoping helpers treat None as
                # "deny", so this cannot widen tenant data access.
                if user.role == "PlatformAdmin" or user.id == 0:
                    payload["organization_id"] = None
                else:
                    logger.error(
                        "🔐 Cannot resolve organization for user %s; denying request.",
                        user.id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your account is not linked to an organization.",
                    )
            else:
                payload["organization_id"] = org_id
            assert_tenant_active(org_id, db, user.role)

        except HTTPException:
            raise
        except Exception as db_err:
            logger.error(f"🔐 Database enrichment failed: {db_err}")
            # Fail closed. Previously this defaulted to organization 4 — an org that
            # does not exist — which would silently mis-scope every subsequent query.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to verify account context. Please retry.",
            )
        finally:
            db.close()

        return payload
    except HTTPException:
        raise
    except Exception as e:
        import logging

        logging.getLogger("auth").error(f"🔐 Critical Auth Error: {str(e)}")
        raise credentials_exception


def verify_token_optional(
    token: Optional[str] = Depends(
        OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
    ),
) -> Optional[Dict]:
    """Decodes token but does not raise 401 if missing/invalid."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        org_id = payload.get("organization_id")
        if org_id is None and user_id is not None:
            from database import SessionLocal
            from models.auth import User

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    org_id = resolve_user_organization_id(user, db)
            except Exception as e:
                logger.warning(f"Optional auth: org resolution failed: {e}")
            finally:
                db.close()

        # Leave organization_id as None when it cannot be resolved. This is the
        # OPTIONAL auth path, so callers must already handle an anonymous result;
        # inventing an org id here (previously a hardcoded 4) would grant an
        # unauthenticated caller a concrete tenant identity.
        payload["organization_id"] = org_id
        return payload
    except Exception:
        return None


def check_scoped_role(
    user_id: int, role: str, scope_type: str, scope_id: int, db: Session
) -> bool:
    """
    Core RBAC engine (Section 6.2).
    Checks if a user has a specific role within a specific scope.
    LDAdmin always returns True (Global Override).
    """
    # 1. Quick check for global LDAdmin (from DB for security)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    if user.role in ["LDAdmin", "ld_admin", "Owner", "owner"]:
        return True

    # 2. Check scoped role table
    exists = (
        db.query(UserRole)
        .filter(
            UserRole.user_id == user_id,
            UserRole.role == role,
            UserRole.scope_type == scope_type,
            UserRole.scope_id == scope_id,
        )
        .first()
    )

    return exists is not None




# ═══════════════════════════════════════════════════════════════════════════
# MULTI-TENANT SCOPING
# ═══════════════════════════════════════════════════════════════════════════
#
# The core content tables now carry a denormalized `organization_id` (see the
# e5f5c12f133e migration). Before that, ownership was only implicit via
# user -> group -> batch -> vertical -> department -> organization, and no query
# walked that chain — so any mentor could read another organization's gradebook,
# exam attempts or reports simply by guessing an id.
#
# Use these helpers on EVERY query that returns tenant-owned rows.



def caller_org_id(current_user: Dict) -> Optional[int]:
    """The caller's organization, or None when it could not be resolved."""
    raw = current_user.get("organization_id")
    return int(raw) if raw is not None else None


def is_platform_admin(current_user: Dict) -> bool:
    """PlatformAdmin is cross-tenant BY DESIGN (it administers every org)."""
    return current_user.get("role") == PLATFORM_ADMIN_ROLE


def scope_to_org(query, model, current_user: Dict):
    """Restrict a SQLAlchemy query to the caller's organization.

    Fails CLOSED: if the caller has no resolvable organization, or the row's
    `organization_id` is NULL (un-backfilled legacy data), nothing matches.
    Returning unscoped rows in either case is what the tenancy fix exists to
    prevent.

    PlatformAdmin is intentionally exempt.
    """
    if is_platform_admin(current_user):
        return query

    org_id = caller_org_id(current_user)
    if org_id is None:
        # No tenant -> match nothing.
        return query.filter(sa_false())

    return query.filter(model.organization_id == org_id)


def assert_same_org(resource, current_user: Dict, resource_name: str = "Resource"):
    """Guard a single fetched row against cross-tenant access.

    Use after loading a row by id — the pattern behind the IDOR issues, where an
    endpoint fetched by primary key and then checked only the caller's ROLE, never
    whether the row belonged to their organization.
    """
    if resource is None:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    if is_platform_admin(current_user):
        return resource

    org_id = caller_org_id(current_user)
    row_org = getattr(resource, "organization_id", None)

    # 404 rather than 403 so the response cannot be used to probe which ids exist
    # in other tenants.
    if org_id is None or row_org is None or int(row_org) != org_id:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    return resource


def _org_of_batch(batch_id: int, db: Session) -> Optional[int]:
    row = (
        db.query(Department.organization_id)
        .join(Vertical, Vertical.department_id == Department.id)
        .join(Batch, Batch.vertical_id == Vertical.id)
        .filter(Batch.id == batch_id)
        .first()
    )
    return row[0] if row else None


def _org_of_group(group_id: int, db: Session) -> Optional[int]:
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        return None
    if group.department_id:
        dept = (
            db.query(Department).filter(Department.id == group.department_id).first()
        )
        if dept:
            return dept.organization_id
    if group.batch_id:
        return _org_of_batch(group.batch_id, db)
    return None


def assert_batch_in_org(batch_id: int, db: Session, current_user: Dict) -> None:
    """Guard reports/analytics entry points that take a batch id.

    These endpoints derive every downstream query from the supplied id, so
    validating the id itself is what prevents a mentor from pulling another
    organization's batch report.
    """
    if is_platform_admin(current_user) or batch_id is None:
        return
    org_id = caller_org_id(current_user)
    batch_org = _org_of_batch(batch_id, db)
    if org_id is None or batch_org is None or batch_org != org_id:
        raise HTTPException(status_code=404, detail="Batch not found")


def assert_group_in_org(group_id: int, db: Session, current_user: Dict) -> None:
    """Guard reports/analytics entry points that take a group id."""
    if is_platform_admin(current_user) or group_id is None:
        return
    org_id = caller_org_id(current_user)
    group_org = _org_of_group(group_id, db)
    if org_id is None or group_org is None or group_org != org_id:
        raise HTTPException(status_code=404, detail="Group not found")


def assert_user_in_org(user_id: int, db: Session, current_user: Dict) -> None:
    """Guard per-learner reports (growth atlas, consistency, velocity)."""
    if is_platform_admin(current_user) or user_id is None:
        return
    org_id = caller_org_id(current_user)
    target = db.query(User).filter(User.id == user_id).first()
    target_org = resolve_user_organization_id(target, db) if target else None
    if org_id is None or target_org is None or target_org != org_id:
        raise HTTPException(status_code=404, detail="Member not found")


# ═══════════════════════════════════════════════════════════════════════════
# SUPER-ORGANIZATION SCOPING (shared content)
# ═══════════════════════════════════════════════════════════════════════════
#
# Two different scopes exist, on purpose:
#   * CONTENT  (question banks, questions, exams, KT companies/projects) is scoped
#     to the SuperOrganization, so a customer's business units share what they author.
#   * LEARNER data (attempts, exam attempts, gradebooks, reports, users) stays scoped
#     to the Organization, so one business unit cannot read another's results.
# Use `scope_to_super_org` for the former and `scope_to_org` for the latter.


def caller_super_org_id(current_user: Dict, db: Session) -> Optional[int]:
    """Resolve the caller's SuperOrganization from their Organization.

    Returns None when it cannot be resolved; callers must then deny rather than
    fall back to an unscoped query.
    """
    cached = current_user.get("super_organization_id")
    if cached is not None:
        return int(cached)

    org_id = caller_org_id(current_user)
    if org_id is None:
        return None
    row = (
        db.query(Organization.super_organization_id)
        .filter(Organization.id == org_id)
        .first()
    )
    resolved = row[0] if row else None
    if resolved is not None:
        current_user["super_organization_id"] = int(resolved)  # memoize per request
    return resolved


def scope_to_super_org(query, model, current_user: Dict, db: Session):
    """Restrict a query for SHARED CONTENT to the caller's super organization.

    Fails closed: no resolvable super org, or a row whose `super_organization_id`
    is NULL, matches nothing. PlatformAdmin is exempt.
    """
    if is_platform_admin(current_user):
        return query

    super_id = caller_super_org_id(current_user, db)
    if super_id is None:
        return query.filter(sa_false())
    return query.filter(model.super_organization_id == super_id)


def assert_same_super_org(
    resource, current_user: Dict, db: Session, resource_name: str = "Resource"
):
    """Guard a single fetched CONTENT row against cross-customer access.

    Returns 404 (never 403) so the response cannot be used to probe which ids
    exist under other customers.
    """
    if resource is None:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    if is_platform_admin(current_user):
        return resource

    super_id = caller_super_org_id(current_user, db)
    row_super = getattr(resource, "super_organization_id", None)

    if super_id is None or row_super is None or int(row_super) != super_id:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    return resource


async def caller_super_org_id_async(current_user: Dict, db) -> Optional[int]:
    """Async twin of caller_super_org_id for AsyncSession handlers.

    `caller_super_org_id` issues a sync `db.query`, which cannot run on an
    AsyncSession. This resolves the same value with `db.execute(select(...))`.
    """
    from sqlalchemy import select as _select

    cached = current_user.get("super_organization_id")
    if cached is not None:
        return int(cached)

    org_id = caller_org_id(current_user)
    if org_id is None:
        return None
    row = await db.execute(
        _select(Organization.super_organization_id).where(Organization.id == org_id)
    )
    resolved = row.scalar_one_or_none()
    if resolved is not None:
        current_user["super_organization_id"] = int(resolved)
    return resolved


async def assert_same_super_org_async(
    resource, current_user: Dict, db, resource_name: str = "Resource"
):
    """Async twin of assert_same_super_org (404 on mismatch, fail closed)."""
    if resource is None:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    if is_platform_admin(current_user):
        return resource

    super_id = await caller_super_org_id_async(current_user, db)
    row_super = getattr(resource, "super_organization_id", None)

    if super_id is None or row_super is None or int(row_super) != super_id:
        raise HTTPException(status_code=404, detail=f"{resource_name} not found")

    return resource


# ── Dependency guards live in auth_dependencies.py (extracted verbatim to keep
# this module under the 800-line cap). Re-exported so the public surface
# `from auth_utils import require_*` is unchanged. Imported at the BOTTOM so the
# primitives (verify_token/check_scoped_role) are defined first. ──
from auth_dependencies import (  # noqa: E402
    get_mentor_ids_for_group,
    require_admin,
    require_admin_for,
    require_group_admin,
    require_group_admin_for_group,
    require_ldadmin,
    require_mentor,
    require_mentor_for,
    require_mentor_for_batch,
    require_mentor_for_batch_scope,
    require_mentor_for_group,
    require_mentor_or_above,
    require_platform_admin,
)
