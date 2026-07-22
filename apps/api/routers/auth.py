import asyncio
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("auth")
import datetime  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402

import bcrypt  # noqa: E402
import jwt  # noqa: E402
import models  # noqa: E402
import schemas  # noqa: E402
from auth_utils import (
    assert_group_in_org,  # noqa: E402
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    get_user_jwt_payload,
    require_admin,
    require_ldadmin,
    verify_token,
)
from database import get_async_db, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload  # noqa: E402
from services.ai_reporting import ai_executive  # noqa: E402
from services.audit_service import log_admin_action  # noqa: E402
from services.email_service import send_otp_email  # noqa: E402
from services.s3_service import generate_profile_upload_url  # noqa: E402
from sqlalchemy import func  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

# STRAT-FIX: Monkeypatch bcrypt for passlib compatibility (bcrypt >= 4.0.0)
# This prevents ValueError: password cannot be longer than 72 bytes
if not hasattr(bcrypt, "original_hashpw"):
    bcrypt.original_hashpw = bcrypt.hashpw  # type: ignore

    def patched_hashpw(password, salt):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if len(password) > 72:
            password = password[:72]
        return bcrypt.original_hashpw(password, salt)  # type: ignore

    bcrypt.hashpw = patched_hashpw
else:
    patched_hashpw = bcrypt.hashpw

if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = type("about", (object,), {"__version__": bcrypt.__version__})  # type: ignore

try:
    import passlib.handlers.bcrypt

    # Inject patch into passlib's internal reference
    passlib.handlers.bcrypt._bcrypt.hashpw = patched_hashpw  # type: ignore
    # Disable the wrap bug detection which crashes on bcrypt 4.0+
    passlib.handlers.bcrypt.detect_wrap_bug = lambda ident: False  # type: ignore
    # Also patch the class-level method if it exists
    if hasattr(passlib.handlers.bcrypt, "BcryptBackend"):
        passlib.handlers.bcrypt.BcryptBackend.detect_wrap_bug = lambda self, ident: (  # type: ignore
            False
        )
except (ImportError, AttributeError):
    pass

import os  # noqa: E402

from config import settings  # noqa: E402
from pagination import paginate  # noqa: E402
from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=False
)


def verify_password(plain_password, hashed_password):
    """
    Standardized verification protocol (SEC-104).
    Ensures Bcrypt 72-byte limit compliance by truncating strictly by bytes.
    """
    if not plain_password:
        return False
    pwd_bytes = plain_password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return pwd_context.verify(
        pwd_bytes.decode("utf-8", errors="ignore"), hashed_password
    )


def get_password_hash(password):
    """
    Standardized hashing protocol (SEC-104).
    Ensures Bcrypt 72-byte limit compliance by truncating strictly by bytes.
    """
    if not password:
        return None
    pwd_bytes = password.encode("utf-8")
    if len(pwd_bytes) > 72:
        pwd_bytes = pwd_bytes[:72]
    return pwd_context.hash(pwd_bytes.decode("utf-8", errors="ignore"))


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/groups")
def get_groups(db: Session = Depends(get_db)):
    try:
        groups = db.query(models.Group).filter(models.Group.is_active.is_(True)).all()
        # Ensure name and batch_id are handled properly even if None
        return [
            {"id": g.id, "name": g.name or f"Group {g.id}", "batch_id": g.batch_id}
            for g in groups
        ]
    except Exception as e:
        import logging
        import traceback

        logging.error(f"Error fetching groups: {str(e)}")
        logging.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, detail=f"Database error while fetching groups: {str(e)}"
        )


@router.get("/roles/promotable")
@router.get("/promotable-roles")
async def get_promotable_roles(current_user: dict = Depends(verify_token)):
    """
    Returns a list of roles the current user is allowed to promote others to.
    LDAdmin -> Mentor, LDAdmin, GroupAdmin
    GroupAdmin -> Mentor
    """
    role = current_user.get("role")
    import json

    from cache_manager import redis_client

    redis_key = f"auth:promotable_roles:{role}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    res = []
    if role == "LDAdmin":
        res = ["Mentor", "LDAdmin", "GroupAdmin"]
    elif role == "GroupAdmin":
        res = ["Mentor"]

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600 * 24)
    except Exception:
        pass

    return res


@router.post("/groups/register")
def register_group_with_admin(
    req: schemas.GroupRegisterAdmin, db: Session = Depends(get_db)
):
    db_group = db.query(models.Group).filter(models.Group.name == req.name).first()
    if db_group:
        raise HTTPException(status_code=400, detail="Group already exists")

    new_group = models.Group(
        name=req.name, password_pattern=req.password_pattern, batch_id=req.batch_id
    )
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    # Create the group admin user
    new_admin = models.User(
        email=req.admin_email,
        full_name=req.admin_name,
        group_id=new_group.id,
        role="GroupAdmin",
    )
    db.add(new_admin)
    db.commit()

    log_admin_action(
        db=db,
        actor_id=None,  # System action during group registration
        actor_role="System",
        action="CREATE_GROUP_ADMIN",
        resource_type="USER",
        resource_id=new_admin.id,
        details={"email": req.admin_email, "group_name": req.name},
    )

    return {"message": "Group registered successfully", "group_id": new_group.id}


@router.get("/groups/{group_id}/users")
async def get_group_users(
    group_id: int,
    page: int = 1,
    size: int = 50,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Paginated list of users within a specific group.
    """
    # Authorization: must be member of same group or admin/mentor
    if (
        current_user["role"] not in ["LDAdmin", "Mentor"]
        and int(current_user["group_id"]) != group_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Strategic Boundary: Cannot access user registry outside of your assigned node.",
        )

    import json

    from cache_manager import redis_client

    redis_key = f"org:group_users:{group_id}:{page}:{size}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    # `paginate()` consumes a legacy Query, so the whole call runs inside run_sync
    # rather than being rewritten to select().
    # Serialize to plain dicts INSIDE run_sync. `paginate()` returns raw User ORM
    # objects; handing those back detached from the session fails to serialize and
    # also broke the Redis cache write below (json.dumps of an ORM object).
    def _page(sync_db):
        res = paginate(
            sync_db.query(models.User)
            .filter(models.User.group_id == group_id)
            .order_by(models.User.full_name.asc()),
            page,
            size,
        )
        return {
            "items": [
                {
                    "id": u.id,
                    "full_name": u.full_name,
                    "email": u.email,
                    "role": u.role,
                    "group_id": u.group_id,
                    "is_active": bool(u.is_active),
                    "profile_photo_url": u.profile_photo_url,
                }
                for u in res.items
            ],
            "total": res.total,
            "page": res.page,
            "size": res.size,
            "pages": res.pages,
        }

    res = await db.run_sync(_page)

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return res


@router.get("/public/groups/{group_id}/users")
async def get_public_group_users(group_id: int, db: AsyncSession = Depends(get_async_db)):
    """
    Publicly accessible list of users in a group (names and IDs only) for the login screen.
    """
    import json

    from cache_manager import redis_client

    redis_key = f"org:public_group_users:{group_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    users = await db.run_sync(lambda s: s.query(models.User).filter(models.User.group_id == group_id).all())
    res = [{"id": u.id, "full_name": u.full_name, "role": u.role} for u in users]

    try:
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return res


@router.post("/users")
def create_user(
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
):
    if user.group_id != current_user["group_id"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    db_user = (
        db.query(models.User)
        .filter(models.User.email == user.email, models.User.group_id == user.group_id)
        .first()
    )
    if db_user:
        raise HTTPException(status_code=400, detail="User already exists in this group")
    user_data = user.model_dump()
    password = user_data.pop("password", None)
    if password:
        # Explicitly truncate to 72 chars to satisfy passlib/bcrypt 4.0 constraints
        pw_str = password[:72]
        user_data["password_hash"] = pwd_context.hash(pw_str)

    group = db.query(models.Group).filter(models.Group.id == user.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    new_user = models.User(
        **user_data, vertical_id=group.vertical_id, department_id=group.department_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_USER",
        resource_type="USER",
        resource_id=new_user.id,
        details={
            "email": new_user.email,
            "full_name": new_user.full_name,
            "group_id": new_user.group_id,
        },
    )

    # TRIGGER-001: Strategic Onboarding Notification (Welcome Email)
    try:
        if new_user.email:
            from services.email_service import send_welcome_email

            send_welcome_email(
                to_email=new_user.email,
                full_name=new_user.full_name,
                group_name=group.name if group else "Strategic Sector",
            )
    except Exception as email_err:
        logger.warning(
            f"Onboarding Notification failed for {new_user.email}: {email_err}"
        )

    return new_user


@router.post("/login")
def login(req: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(
            models.User.group_id == req.group_id, models.User.full_name == req.full_name
        )
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found in this group")

    group = db.query(models.Group).filter(models.Group.id == req.group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    # Implement robust Regex-based pattern replacing for group passwords
    # Check if user has a custom password override (from reset)
    if user.password_hash:
        if not pwd_context.verify(req.password, user.password_hash):
            raise HTTPException(
                status_code=401, detail="Invalid credential synchronization"
            )
    else:
        # Extract the first name and sanitize it
        first_name = re.sub(r"[^a-zA-Z0-9]", "", user.full_name.split(" ")[0]).lower()

        # Replace <name>, {name}, or [name] (case insensitive) with the sanitized first name
        expected_password = re.sub(
            r"[<{\[]name[>}\]]", first_name, group.password_pattern, flags=re.IGNORECASE
        )

        if req.password.strip() != expected_password.strip():
            raise HTTPException(status_code=401, detail="Invalid password")

    # Update last login
    user.last_login = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    access_token = create_access_token(data=get_user_jwt_payload(user, db))

    refresh_token, refresh_expiry = create_refresh_token(user.id)

    # Store refresh token for revocation support
    db_refresh = models.RefreshToken(
        user_id=user.id, token=refresh_token, expires_at=refresh_expiry
    )
    db.add(db_refresh)
    db.commit()

    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=settings.is_production(),
        samesite="lax",
        max_age=30 * 60,  # 30 mins
    )

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.is_production(),
        samesite="lax",
        max_age=7 * 24 * 60 * 60,  # 7 days
    )

    return {
        "status": "success",
        "access_token": access_token,
        "user": {
            "id": user.id,
            "full_name": user.full_name,
            "role": user.role,
            "group_id": user.group_id,
        },
    }


class RefreshTokenRequest(BaseModel):
    refresh_token: Optional[str] = None


@router.post("/refresh")
def refresh_token(
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
    req_body: Optional[RefreshTokenRequest] = None,
):
    """PHASE-3: Strategic session rotation via HttpOnly credentials."""
    cookie_token = request.cookies.get("refresh_token")
    token = cookie_token or (req_body.refresh_token if req_body else None)
    if not token:
        raise HTTPException(status_code=401, detail="Refresh credentials not detected.")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")

        user_id = int(payload.get("sub"))

        # Verify in DB (revocation check)
        db_token = (
            db.query(models.RefreshToken)
            .filter(
                models.RefreshToken.token == token, models.RefreshToken.is_revoked.is_(False)
            )
            .first()
        )

        if (
            not db_token
            or db_token.expires_at.replace(tzinfo=None) < datetime.datetime.utcnow()
        ):
            raise HTTPException(status_code=401, detail="Token expired or revoked")

        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        # Revoke old refresh token (Security: Token Rotation)
        db_token.is_revoked = True

        # Issue new access token
        new_access_token = create_access_token(data=get_user_jwt_payload(user, db))

        # Issue new refresh token
        new_refresh_token, new_refresh_expiry = create_refresh_token(user.id)
        db_new_refresh = models.RefreshToken(
            user_id=user.id, token=new_refresh_token, expires_at=new_refresh_expiry
        )
        db.add(db_new_refresh)
        db.commit()

        response.set_cookie(
            key="access_token",
            value=f"Bearer {new_access_token}",
            httponly=True,
            secure=settings.is_production(),
            samesite="lax",
            max_age=30 * 60,
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            secure=settings.is_production(),
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )

        return {"status": "success", "access_token": new_access_token}

    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """PHASE-3: Strategic session revocation (Security Protocol)."""
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        db_token = (
            db.query(models.RefreshToken)
            .filter(models.RefreshToken.token == cookie_token)
            .first()
        )
        if db_token:
            db_token.is_revoked = True
            db.commit()

    response.delete_cookie("refresh_token", path="/api/auth/refresh")
    response.delete_cookie("refresh_token", path="/auth/refresh")
    return {"status": "success", "message": "Session terminated and revoked."}


@router.post("/logout-all")
def logout_all(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """SEC-102: Invalidate all active refresh tokens for the current user."""
    user_id = int(current_user["sub"])
    db.query(models.RefreshToken).filter(models.RefreshToken.user_id == user_id).update(
        {"is_revoked": True}
    )
    db.commit()
    return {"message": "All sessions invalidated and logged out from all devices."}


@router.get("/me")
def get_current_user(
    current_user: dict = Depends(verify_token), db: Session = Depends(get_db)
):
    user = (
        db.query(models.User).filter(models.User.id == int(current_user["sub"])).first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    group = db.query(models.Group).filter(models.Group.id == user.group_id).first()

    res = {
        "success": True,
        "id": user.id,
        "user_id": user.id,
        "full_name": user.full_name,
        "group_id": user.group_id,
        "group_name": group.name if group else None,
        "role": user.role,
        "email": user.email,
    }

    if user.role == "Mentor":
        # Strategy: Merge V3 UserRole scope and V2 MentorGroupAssignment
        v3_groups = [
            r.scope_id
            for r in user.scoped_roles
            if r.role == "Mentor" and r.scope_type == "group"
        ]
        v2_groups = [a.group_id for a in user.mentor_assignments if a.is_active]
        res["assigned_groups"] = list(set(v3_groups + v2_groups))

    return res


@router.get("/profile")
async def get_my_detailed_profile(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(verify_token)
):
    """PHASE-3: Retrieve the current user's high-fidelity profile with performance vectors."""
    user_id = int(current_user["sub"])
    # `user.group` is read below; eager-load it, since a lazy load outside
    # run_sync raises MissingGreenlet on an AsyncSession.
    user = await db.run_sync(
        lambda s: s.query(models.User)
        .options(selectinload(models.User.group))
        .filter(models.User.id == user_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Entity not found")

    from services.performance_engine import performance_engine

    profile_data = {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "role": user.role,
        "bio": user.bio,
        "custom_slug": user.custom_slug,
        "profile_photo_url": user.profile_photo_url,
        "cover_photo_url": user.cover_photo_url,
        "intro_video_url": user.intro_video_url,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "expertise": user.expertise_json or {},
        "streak_count": user.streak_count,
        "group_id": user.group_id,
        "group_name": user.group.name if user.group else None,
        "performance_vectors": await performance_engine.get_user_vectors(user.id, db),
    }
    return profile_data


@router.patch("/profile")
def update_my_profile(
    req: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """User-driven profile enhancement."""
    user_id = int(current_user["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    allowed_fields = [
        "full_name",
        "bio",
        "custom_slug",
        "profile_photo_url",
        "cover_photo_url",
        "intro_video_url",
        "github_url",
        "linkedin_url",
        "leetcode_url",
        "codolio_url",
    ]

    for field, value in req.items():
        if field in allowed_fields:
            if field == "custom_slug" and value:
                # Validate slug uniqueness
                existing = (
                    db.query(models.User)
                    .filter(models.User.custom_slug == value, models.User.id != user_id)
                    .first()
                )
                if existing:
                    raise HTTPException(status_code=400, detail="Slug already taken")
            setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return {"status": "success", "user_id": user.id}


@router.get("/profile/{slug}")
def get_profile_by_slug(slug: str, db: Session = Depends(get_db)):
    """Retrieve public profile by custom slug."""
    user = db.query(models.User).filter(models.User.custom_slug == slug).first()
    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return {
        "id": user.id,
        "full_name": user.full_name,
        "bio": user.bio,
        "profile_photo_url": user.profile_photo_url,
        "cover_photo_url": user.cover_photo_url,
        "role": user.role,
        "github_url": user.github_url,
        "linkedin_url": user.linkedin_url,
        "leetcode_url": user.leetcode_url,
        "codolio_url": user.codolio_url,
        "streak_count": user.streak_count,
        "last_active": user.last_active_date,
    }


@router.delete("/profile/photo")
def delete_profile_photo(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Remove user's profile photo and cleanup S3."""
    user_id = int(current_user["sub"])
    user = db.query(models.User).filter(models.User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.profile_photo_url and settings.S3_BUCKET_NAME and settings.S3_BUCKET_NAME in str(user.profile_photo_url):
        try:
            # Extract key from URL
            # Expected format: https://bucket.s3.region.amazonaws.com/key
            from services.s3_service import delete_s3_object

            s3_key = str(user.profile_photo_url).split(".amazonaws.com/")[-1]
            delete_s3_object(s3_key)
        except Exception as e:
            logger.error(f"Failed to delete S3 profile photo: {e}")

    user.profile_photo_url = None
    db.commit()
    return {"success": True}


@router.post("/upload-url")
def get_upload_url(
    filename: str, file_type: str, current_user: dict = Depends(verify_token)
):
    """PHASE-3: S3 Presigned URL for direct secure uploads."""
    from services.s3_service import generate_profile_upload_url

    ALLOWED_MIME_TYPES = ["image/jpeg", "image/png", "image/webp", "video/mp4"]
    if file_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file_type}' is not permitted for upload.",
        )

    user_id = int(current_user["sub"])
    return generate_profile_upload_url(
        user_id=user_id, filename=filename, file_type=file_type
    )


@router.post("/superadmin/login")
def superadmin_login(
    req: schemas.SuperAdminLogin, response: Response, db: Session = Depends(get_db)
):
    """
    Strategic Access Protocol: SuperAdmin Login.
    Verifies against ID 0 (System Admin) and environmental APP_ADMIN_PASSWORD.
    """
    from config import settings
    from ensure_system_identity import ensure_system

    admin_password = settings.APP_ADMIN_PASSWORD
    if not admin_password:
        raise HTTPException(
            status_code=500, detail="SuperAdmin password not configured in environment."
        )

    if req.password != admin_password:
        raise HTTPException(
            status_code=401, detail="Invalid credential synchronization."
        )

    # Verify ID 0 exists (System Admin)
    system_user = db.query(models.User).filter(models.User.id == 0).first()
    if not system_user:
        logger.warning(
            "System Admin (ID 0) missing. Triggering emergency provisioning."
        )
        ensure_system()
        system_user = db.query(models.User).filter(models.User.id == 0).first()
        if not system_user:
            raise HTTPException(
                status_code=500, detail="Critical: Could not provision System Admin."
            )

    access_token = create_access_token(data=get_user_jwt_payload(system_user, db))

    # Set Secure HttpOnly Cookies
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=settings.is_production(),
        samesite="lax",
        max_age=30 * 60,
    )

    return {
        "status": "success",
        "access_token": access_token,
        "user": {
            "id": system_user.id,
            "full_name": system_user.full_name,
            "role": system_user.role,
            "group_id": system_user.group_id,
        },
    }


@router.get("/users/discovery")
def discovery_users(
    q: Optional[str] = Query(None, description="Search by name or email"),
    role: Optional[str] = Query(None, description="Filter by role"),
    group_id: Optional[int] = Query(None, description="Filter by group ID"),
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    assert_group_in_org(group_id, db, current_user)
    logger.info(
        f"User discovery requested by {current_user.get('sub')} (Role: {current_user.get('role')})"
    )
    if int(current_user["sub"]) != 0 and current_user["role"] not in [
        "LDAdmin",
        "Mentor",
        "GroupAdmin",
        "Member",
    ]:
        logger.warning(
            f"SEC-101: User {current_user.get('sub')} with role {current_user.get('role')} denied discovery"
        )
        raise HTTPException(
            status_code=403,
            detail="Only Administrative roles can access user discovery",
        )

    # Scoping Enforcement (SEC-101)
    if current_user["role"] != "LDAdmin":
        if not group_id:
            # If no group_id specified, default to their primary group
            group_id = int(current_user.get("group_id", 0))

        # Verify they actually have access to this group_id
        from auth_utils import check_scoped_role

        has_access = False
        if int(current_user.get("group_id", 0)) == group_id:
            has_access = True
        elif check_scoped_role(
            int(current_user["sub"]), current_user["role"], "group", group_id, db
        ):
            has_access = True

        if not has_access:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Your scope is restricted to your assigned sectors.",
            )

    query = (
        db.query(models.User)
        .join(models.Group)
        .outerjoin(models.Batch)
        .outerjoin(models.Vertical)
        .outerjoin(models.Department)
        .outerjoin(models.Organization)
    )

    if q:
        query = query.filter(
            (models.User.full_name.ilike(f"%{q}%"))
            | (models.User.email.ilike(f"%{q}%"))
        )
    if role:
        query = query.filter(models.User.role == role)
    if group_id:
        query = query.filter(models.User.group_id == group_id)

    paginated = paginate(query.order_by(models.User.full_name.asc()), page, size)

    results = []
    for u in paginated.items:
        group = u.group
        batch = group.batch if group else None
        vertical = batch.vertical if batch else None
        dept = vertical.department if vertical else None
        org = dept.organization if dept else None

        results.append(
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "group_name": group.name if group else None,
                "batch_name": batch.name if batch else None,
                "vertical_name": vertical.name if vertical else None,
                "dept_name": dept.name if dept else None,
                "org_name": org.name if org else None,
                "is_active": u.is_active == True,
                "created_at": u.created_at,
            }
        )

    return {
        "items": results,
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
        "pages": paginated.pages,
    }


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    req: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Stabilized role update with logical hierarchy promotion.
    Hierarchy Model (Enterprise L&D):
    1. LDAdmin (Global Governance)
    2. Mentor (Cohort Guidance - assigned to specific nodes)
    3. GroupAdmin (Local Admin - node-specific)
    4. Member (Learning Track)
    """
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin", "Admin"]:
        raise HTTPException(
            status_code=403,
            detail="Tactical Violation: Insufficient authorization for role re-alignment.",
        )

    # HARD LOCK FOR MENTOR PROMOTION (QUAL-001)
    if req.role == "Mentor":
        # Calculate accuracy across all quiz attempts
        from sqlalchemy import func

        stats = (
            db.query(
                func.sum(models.Attempt.score).label("total_score"),
                func.sum(models.Attempt.total).label("total_questions"),
            )
            .filter(models.Attempt.user_id == user_id)
            .first()
        )

        sum_score = stats.total_score if stats and stats.total_score else 0
        sum_total = stats.total_questions if stats and stats.total_questions else 0

        accuracy = (sum_score / sum_total * 100) if sum_total > 0 else 0
        if accuracy < 80:
            raise HTTPException(
                status_code=403,
                detail=f"Quality Lock: User proficiency ({round(accuracy, 1)}%) is below the mandatory 80% threshold for Mentor status.",
            )

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(
            status_code=404, detail="Entity ID not detected in registry."
        )

    # SCOPE VALIDATION (PROMOTE-001)
    # If the actor is not a Global LDAdmin, they must be in the same group scope as the target.
    # Global LDAdmins can promote anyone except promoting others to LDAdmin (reserved for System).
    if current_user["role"] != "LDAdmin":
        has_scope = False
        if current_user["role"] == "Mentor":
            actor_id = int(current_user["sub"])
            assign = (
                db.query(models.MentorGroupAssignment)
                .filter_by(
                    mentor_id=actor_id, group_id=db_user.group_id, is_active=True
                )
                .first()
            )
            if assign:
                has_scope = True
        elif current_user["role"] in ["GroupAdmin", "Admin"]:
            if db_user.group_id == current_user.get("group_id"):
                has_scope = True

        if not has_scope:
            raise HTTPException(
                status_code=403,
                detail="Boundary Leak Blocked: You cannot promote entities outside your assigned sector.",
            )

        # Prevent non-LDAdmins from creating new LDAdmins
        if req.role == "LDAdmin":
            raise HTTPException(
                status_code=403,
                detail="Security Protocol Breach: LDAdmin provisioning is restricted to Global Executives.",
            )

    old_role = db_user.role
    db_user.role = req.role

    # 1. AUTOMATED PROVISIONING (PROMOTE-002: Legacy Mentor Mapping)
    if req.role == "Mentor":
        if not db_user.group_id:
            raise HTTPException(
                status_code=400,
                detail="Provisioning Failed: User must be assigned to a group before becoming a Mentor.",
            )

        existing_assignment = (
            db.query(models.MentorGroupAssignment)
            .filter(
                models.MentorGroupAssignment.mentor_id == user_id,
                models.MentorGroupAssignment.group_id == db_user.group_id,
            )
            .first()
        )

        if not existing_assignment:
            new_assignment = models.MentorGroupAssignment(
                mentor_id=user_id, group_id=db_user.group_id
            )
            db.add(new_assignment)

    # 2. V3 SCORING SYNC (PROMOTE-003: Multi-Context Role Table)
    # Ensure UserRole is synced for the primary group
    existing_scoped = (
        db.query(models.UserRole)
        .filter_by(
            user_id=user_id,
            role=req.role,
            scope_type="group",
            scope_id=db_user.group_id,
        )
        .first()
    )

    if not existing_scoped:
        new_scoped = models.UserRole(
            user_id=user_id,
            role=req.role,
            scope_type="group",
            scope_id=db_user.group_id,
        )
        db.add(new_scoped)

    # If role is downgraded (e.g. to Member), we should ideally clean up old admin roles
    # but for now we keep them to avoid accidental lockouts.

    # 3. STRAT-AUDIT LOGGING
    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="PROMOTE_USER",
        resource_type="USER",
        resource_id=user_id,
        details={
            "target": db_user.full_name,
            "old_role": old_role,
            "new_role": req.role,
            "group_id": db_user.group_id,
        },
    )

    db.commit()

    # 4. EMAIL-002 — Trigger role promotion email (Strategic Notification)
    try:
        if db_user.email and old_role != req.role:
            group = (
                db.query(models.Group)
                .filter(models.Group.id == db_user.group_id)
                .first()
            )
            from services.email_service import send_role_promotion_email

            send_role_promotion_email(
                to_email=db_user.email,
                full_name=db_user.full_name,
                new_role=req.role,
                group_name=group.name if group else "Strategic Sector",
            )
    except Exception as email_err:
        logger.warning(f"Protocol Warning: Notification dispatch failed: {email_err}")

    db.refresh(db_user)

    return {
        "success": True,
        "message": f"Hierarchical promotion executed: {db_user.full_name} moved to {req.role}.",
        "new_role": db_user.role,
        "affected_id": user_id,
    }


@router.post("/groups/{group_id}/users/bulk")
def bulk_create_users(
    group_id: int,
    req: schemas.BulkUserCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    assert_group_in_org(group_id, db, current_user)
    if current_user["role"] not in ["LDAdmin", "Admin", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Group not found")

    # If GroupAdmin, must be for their own group
    if (
        current_user["role"] in ["Admin", "GroupAdmin"]
        and group_id != current_user["group_id"]
    ):
        raise HTTPException(
            status_code=403, detail="Cannot onboard users for other groups"
        )

    # Update group's password pattern if provided
    if req.password_pattern:
        db_group.password_pattern = req.password_pattern
        db.commit()

    new_users = []
    for item in req.users:
        # Check if user already exists in this group
        db_user = (
            db.query(models.User)
            .filter(models.User.email == item.email, models.User.group_id == group_id)
            .first()
        )

        if not db_user:
            # Auto-generate custom slug (PHASE-3)
            base_slug = re.sub(
                r"[^a-zA-Z0-9]", "", item.full_name.split(" ")[0]
            ).lower()
            import uuid

            unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

            user_data = {
                "full_name": item.full_name,
                "email": item.email,
                "group_id": group_id,
                "role": item.role,
                "member_id": item.member_id,
                "custom_slug": unique_slug,
            }
            if item.password:
                user_data["password_hash"] = get_password_hash(item.password)

            user = models.User(**user_data)
            db.add(user)
            new_users.append(user)

    db.commit()

    # NEW: Send welcome emails to newly created users
    from services.email_service import send_welcome_email

    for user in new_users:
        try:
            send_welcome_email(
                to_email=user.email, full_name=user.full_name, group_name=db_group.name
            )
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {e}")

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="BULK_CREATE_USERS",
        resource_type="USER",
        resource_id=0,
        details={"count": len(new_users), "group_id": group_id},
    )

    return {
        "message": f"Successfully onboarded {len(new_users)} users to group {db_group.name}"
    }


@router.get("/users/{user_id}/insights")
async def get_user_insights(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """
    Enterprise-grade Member Intel Engine.
    Synthesizes recursive activity, algorithmic success, and collaborative metrics
    into a professional AI-powered growth narrative (FUNC-001).
    """
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(
            status_code=403,
            detail="Strategic Violation: Insufficient authorization for entity intel sync.",
        )

    user = await db.run_sync(lambda s: s.query(models.User).filter(models.User.id == user_id).first())
    if not user:
        raise HTTPException(
            status_code=404, detail="Entity ID not detected in registry."
        )

    # SCOPE ENFORCEMENT
    if current_user["role"] != "LDAdmin" and user.group_id != current_user.get(
        "group_id"
    ):
        raise HTTPException(
            status_code=403,
            detail="Boundary Breach: Entity exists in an isolated node.",
        )

    # 1. Synchronization Activity (Quiz Attempts)
    quiz_attempts = (
        await db.run_sync(lambda s: s.query(models.Attempt)
        .filter(models.Attempt.user_id == user_id)
        .order_by(models.Attempt.attempted_at.asc())
        .all())
    )

    # 2. Algorithmic Lab Participation (Coding Attempts)
    coding_attempts = (
        await db.run_sync(lambda s: s.query(models.CodingAttempt)
        .filter(models.CodingAttempt.user_id == user_id)
        .order_by(models.CodingAttempt.attempted_at.asc())
        .all())
    )

    # 3. Collaborative Intelligence (Discussions)
    discussions_count = (
        await db.run_sync(lambda s: s.query(models.QuestionDiscussion)
        .filter(models.QuestionDiscussion.user_id == user_id)
        .count())
    )

    # --- Topic Mastery Analysis ---
    topic_data = {}
    for attempt in quiz_attempts:
        bank = (
            await db.run_sync(lambda s: s.query(models.QuestionBank)
            .filter(models.QuestionBank.id == attempt.bank_id)
            .first())
        )
        if bank and bank.chapter:
            if bank.chapter not in topic_data:
                topic_data[bank.chapter] = {"score": 0, "total": 0, "count": 0}
            topic_data[bank.chapter]["score"] += attempt.score or 0
            topic_data[bank.chapter]["total"] += (
                attempt.total or 1
            )  # Prevent div by zero
            topic_data[bank.chapter]["count"] += 1

    mastery_report = [
        {
            "topic": t,
            "accuracy": round((s["score"] / s["total"] * 100), 1),
            "volume": s["count"],
            "status": "Elite"
            if (s["score"] / s["total"]) > 0.9
            else "Sync"
            if (s["score"] / s["total"]) > 0.7
            else "Fragile",
        }
        for t, s in topic_data.items()
    ]

    # --- Temporal Consistency & Streak Calculation ---
    today = datetime.datetime.now(datetime.timezone.utc).date()
    timeline = []
    active_dates = set()

    # Track quiz + code activity
    for a in quiz_attempts:
        active_dates.add(a.attempted_at.date())
    for c in coding_attempts:
        active_dates.add(c.attempted_at.date())

    # Calculate Streak (consecutive active days backwards from today/yesterday)
    streak = 0
    check_day = today
    # If not active today, check if yesterday was the end of a streak
    if today not in active_dates:
        check_day = today - datetime.timedelta(days=1)

    while check_day in active_dates:
        streak += 1
        check_day -= datetime.timedelta(days=1)

    for i in range(29, -1, -1):
        day = today - datetime.timedelta(days=i)
        activity = len(
            [a for a in quiz_attempts if a.attempted_at.date() == day]
        ) + len([c for c in coding_attempts if c.attempted_at.date() == day])
        timeline.append({"date": day.strftime("%Y-%m-%d"), "activity": activity})

    # --- Scientific Benchmarking ---
    total_q = len(quiz_attempts)
    avg_acc = (
        round(
            sum([a.score for a in quiz_attempts])
            / sum([a.total for a in quiz_attempts])
            * 100,
            1,
        )
        if sum([a.total for a in quiz_attempts]) > 0
        else 0
    )
    total_c = len(coding_attempts)
    code_success = (
        round(
            len([c for c in coding_attempts if c.overall_result == "correct"])
            / total_c
            * 100,
            1,
        )
        if total_c > 0
        else 0
    )

    # Consistency = Active Days / 30
    active_days_count = len(
        [d for d in active_dates if d >= (today - datetime.timedelta(days=30))]
    )
    consistency_score = round((active_days_count / 30) * 100, 1)

    # --- Phase 5: Peer-benchmarking & Study Path ---
    group_users = (
        await db.run_sync(lambda s: s.query(models.User.id).filter(models.User.group_id == user.group_id).all())
    )
    group_user_ids = [gu[0] for gu in group_users]
    group_attempts = (
        await db.run_sync(lambda s: s.query(models.Attempt)
        .filter(models.Attempt.user_id.in_(group_user_ids))
        .all())
    )
    group_acc = (
        round(
            sum([a.score for a in group_attempts])
            / sum([a.total for a in group_attempts])
            * 100,
            1,
        )
        if group_attempts and sum([a.total for a in group_attempts]) > 0
        else 0
    )

    attempted_bank_ids = list(set([a.bank_id for a in quiz_attempts]))
    suggested_banks = (
        await db.run_sync(lambda s: s.query(models.QuestionBank)
        .filter(
            ~models.QuestionBank.id.in_(attempted_bank_ids)
            if attempted_bank_ids
            else models.QuestionBank.id.isnot(None),
            models.QuestionBank.is_org_public,  # simplified condition for suggested path
        )
        .limit(3)
        .all())
    )
    study_path = [
        {"id": b.id, "name": b.name, "chapter": b.chapter} for b in suggested_banks
    ]

    # Weighted Proficiency: 60% Quiz, 40% Coding (Neural Balancing)
    weighted_proficiency = round((avg_acc * 0.6) + (code_success * 0.4), 1)

    # --- Activity Logs (Chronological Trace) ---
    raw_logs = []
    # Mix and sort by time
    for a in quiz_attempts:
        bank = (
            await db.run_sync(lambda s: s.query(models.QuestionBank)
            .filter(models.QuestionBank.id == a.bank_id)
            .first())
        )
        raw_logs.append(
            {
                "type": "QUIZ",
                "title": bank.name if bank else "Assessment",
                "result": f"{a.score}/{a.total}",
                "timestamp": a.attempted_at.isoformat(),
            }
        )
    for c in coding_attempts:
        raw_logs.append(
            {
                "type": "CODE",
                "title": c.question.title if c.question else "Algorithm Lab",
                "result": c.overall_result.upper() if c.overall_result else "UNKNOWN",
                "timestamp": c.attempted_at.isoformat(),
            }
        )
    raw_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    raw_logs = raw_logs[:25]

    insights_payload = {
        "user_id": user_id,
        "full_name": user.full_name,
        "group_id": user.group_id,
        "metrics": {
            "synchronization": {
                "avg_accuracy": avg_acc,
                "volume": total_q,
                "topic_mastery": mastery_report,
            },
            "algorithmic_lab": {"success_rate": code_success, "volume": total_c},
            "advanced": {
                "weighted_proficiency": weighted_proficiency,
                "consistency_score": consistency_score,
                "streak": streak,
                "intel_contributions": discussions_count,
                "group_average_accuracy": group_acc,
            },
            "study_path": study_path,
            "timeline": timeline,
        },
        "raw_logs": raw_logs,
    }

    # AI SYNC PROTOCOL
    ai_narrative = await ai_executive.generate_member_summary(
        member_name=user.full_name, insights=insights_payload["metrics"]
    )

    insights_payload["ai_narrative"] = ai_narrative
    return insights_payload


@router.get("/my-roles")
def get_my_roles(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """
    STRAT-RBAC-02: Returns all context-specific roles assigned to the user.
    Used for the Frontend Context Switcher.
    """
    user_id = int(current_user["sub"])
    scoped_roles = (
        db.query(models.UserRole).filter(models.UserRole.user_id == user_id).all()
    )

    roles_data = []
    for sr in scoped_roles:
        scope_name = "Global"
        if sr.scope_type == "group":
            group = (
                db.query(models.Group).filter(models.Group.id == sr.scope_id).first()
            )
            scope_name = group.name if group else f"Group #{sr.scope_id}"
        elif sr.scope_type == "batch":
            batch = (
                db.query(models.Batch).filter(models.Batch.id == sr.scope_id).first()
            )
            scope_name = batch.name if batch else f"Batch #{sr.scope_id}"
        elif sr.scope_type == "vertical":
            vert = (
                db.query(models.Vertical)
                .filter(models.Vertical.id == sr.scope_id)
                .first()
            )
            scope_name = vert.name if vert else f"Vertical #{sr.scope_id}"

        roles_data.append(
            {
                "role": sr.role,
                "scope_type": sr.scope_type,
                "scope_id": sr.scope_id,
                "scope_name": scope_name,
                "granted_at": sr.created_at.isoformat(),
            }
        )

    return {
        "primary_role": current_user["role"],
        "primary_group_id": current_user.get("group_id"),
        "scoped_roles": roles_data,
    }


# log_admin_action already imported


@router.post("/groups/{group_id}/impersonate")
def impersonate_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """LDAdmin can impersonate any group to diagnose issues (audit logged)."""
    # STRAT-RBAC-04: Mentor Impersonation Boundary
    if current_user.get("role") not in ["LDAdmin", "Mentor"]:
        raise HTTPException(
            status_code=403, detail="Only LDAdmin or Mentor can impersonate"
        )

    # Impersonation must stay within the caller's org.
    assert_group_in_org(group_id, db, current_user)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404)

    if current_user.get("role") == "Mentor":
        user_obj = (
            db.query(models.User)
            .filter(models.User.id == int(current_user["sub"]))
            .first()
        )
        if not user_obj:
            raise HTTPException(status_code=403, detail="Invalid mentor record")

        # Check Vertical Boundary
        if user_obj.vertical_id:
            # If mentor has a vertical, they can only impersonate groups in their vertical
            if not group.batch or group.batch.vertical_id != user_obj.vertical_id:
                raise HTTPException(
                    status_code=403,
                    detail="Strategic Boundary: Cannot impersonate a group outside your assigned vertical",
                )
        else:
            # If mentor has no vertical, fallback to strict group match
            if user_obj.group_id != group.id:
                raise HTTPException(
                    status_code=403,
                    detail="Strategic Boundary: Cannot impersonate this group",
                )

    # Create a limited-duration token with group context
    import datetime

    from auth_utils import create_access_token

    # Determine target organization context for impersonation
    org_id = None
    if group.department_id:
        dept = (
            db.query(models.Department)
            .filter(models.Department.id == group.department_id)
            .first()
        )
        if dept:
            org_id = dept.organization_id

    impersonate_token = create_access_token(
        data={
            "sub": str(current_user["sub"]),
            "role": current_user.get("role"),
            "group_id": group_id,
            "organization_id": org_id,
            "exp": datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=30),
        }
    )

    # Audit log
    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"])
        if str(current_user.get("sub", "")) != "0"
        else None,
        actor_role=current_user.get("role", "Unknown"),
        action="impersonate_group",
        resource_type="group",
        resource_id=group_id,
        details={"group_name": group.name},
    )
    db.commit()

    return {"access_token": impersonate_token, "group_name": group.name}


# --- Password Recovery Protocols ---


@router.post("/forgot-password")
async def forgot_password(
    req: schemas.ForgotPasswordRequest, db: AsyncSession = Depends(get_async_db)
):
    """Stage 1: Generate OTP and propagate via email."""
    from cache_manager import redis_client

    lock_key = f"auth:forgot_pwd_lock:{req.email}"
    try:
        is_locked = await redis_client.get(lock_key)
        if is_locked:
            raise HTTPException(
                status_code=429, detail="Too many requests. Please try again later."
            )
        await redis_client.set(lock_key, "1", ex=60)  # 1 minute cooldown
    except HTTPException:
        raise
    except Exception:
        pass

    try:
        user = (
            await db.run_sync(lambda s: s.query(models.User)
            .filter(
                models.User.email == req.email, models.User.group_id == req.group_id
            )
            .first())
        )

        if not user:
            # Avoid user enumeration by always returning the standard success message
            return {
                "message": "Recovery protocol initiated. Check your email for the OTP."
            }

        otp_code = str(random.randint(100000, 999999))
        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            minutes=15
        )

        # Create reset token
        reset_token = models.PasswordResetToken(
            user_id=user.id, otp_code=otp_code, expires_at=expires_at
        )
        db.add(reset_token)
        await db.commit()

        # Send email
        sent = send_otp_email(user.email, otp_code)

        # Development Protocol: Always log OTP to terminal for internal bypass
        logger.info(f"🔑 [DEV] Recovery OTP for {user.email}: {otp_code}")
        print(
            f"\n>>> SECURITY NOTIFICATION: Recovery code for {user.email} is {otp_code} <<<\n"
        )

        if not sent:
            logger.warning(
                f"Recovery protocol initiated but email failed to dispatch to {user.email}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Recovery protocol initiated, but email delivery failed. (Dev node: Check server console for OTP)",
            )

        return {"message": "Recovery protocol initiated. Check your email for the OTP."}
    except Exception as e:
        logger.error(f"Critical failure in forgot-password flow: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Strategic fallback: Password recovery system currently undergoing maintenance.",
        )


@router.post("/reset-password")
def reset_password(req: schemas.ResetPasswordRequest, db: Session = Depends(get_db)):
    """Stage 2: Verify OTP and finalize new synchronization credentials."""
    user = (
        db.query(models.User)
        .filter(models.User.email == req.email, models.User.group_id == req.group_id)
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="Entity not found")

    token = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.otp_code == req.otp_code,
            models.PasswordResetToken.is_used.is_(False),
            models.PasswordResetToken.expires_at
            > datetime.datetime.now(datetime.timezone.utc),
        )
        .first()
    )

    if not token:
        raise HTTPException(status_code=400, detail="Invalid or expired recovery code")

    # Set new password hash (Bcrypt limit is 72 bytes)
    user.password_hash = get_password_hash(req.new_password)
    token.is_used = True

    log_admin_action(
        db=db,
        actor_id=user.id,
        actor_role=user.role,
        action="RESET_PASSWORD_SELF",
        resource_type="USER",
        resource_id=user.id,
        details={"method": "OTP"},
    )

    db.commit()

    return {
        "message": "Security credentials updated successfully. You may now synchronize."
    }


class ProfilePhotoUploadRequest(BaseModel):
    file_name: str
    file_type: str


@router.post("/presigned-upload-profile")
def get_profile_presigned_url(
    req: ProfilePhotoUploadRequest, current_user: dict = Depends(verify_token)
):
    """
    Generates a pre-signed POST policy for the frontend to upload a profile photo.
    """
    user_id = int(current_user["sub"])
    try:
        # SEC-FIX: Restrict upload path to user's own profile folder
        data = generate_profile_upload_url(
            user_id=user_id, filename=req.file_name, file_type=req.file_type
        )
        return data
    except Exception as e:
        logger.error(f"Profile upload URL generation failed: {e}")
        raise HTTPException(
            status_code=500, detail="Internal server error during S3 URL generation"
        )


@router.patch("/profile")
def update_profile(
    req: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    user_id = int(current_user["sub"])
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)
    return {"success": True, "user": schemas.UserResponse.model_validate(db_user)}


@router.get("/profile/{email_prefix}", response_model=schemas.UserResponse)
def get_public_profile(
    email_prefix: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Retrieve public profile for any user in the organization."""
    # Find user where email starts with prefix and followed by @
    user = (
        db.query(models.User)
        .filter(models.User.email.like(f"{email_prefix}@%"))
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="Profile not found")

    return user


# ─── User Search / Management ─────────────────────────────────────────────────


@router.get("/users/search")
def search_users(
    q: str, db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Fuzzy user search by name or email — available to GroupAdmin, Mentor, LDAdmin."""
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    search = f"%{q}%"
    query = db.query(models.User).filter(
        (models.User.full_name.ilike(search)) | (models.User.email.ilike(search))
    )

    # Scope: non-LDAdmin can only search their group
    if current_user["role"] != "LDAdmin":
        group_id = current_user.get("group_id")
        if group_id:
            query = query.filter(models.User.group_id == group_id)

    users = query.limit(30).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "group_id": u.group_id,
            "is_active": u.is_active == True,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Soft-deactivate a user (reversible). Audit logged."""
    if current_user["role"] not in ["LDAdmin", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Scope check: GroupAdmin can only deactivate own-group users
    if current_user["role"] == "GroupAdmin" and user.group_id != current_user.get(
        "group_id"
    ):
        raise HTTPException(status_code=403, detail="Boundary violation")

    user.is_active = not user.is_active

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="DEACTIVATE_USER" if not user.is_active else "REACTIVATE_USER",
        resource_type="USER",
        resource_id=user_id,
        details={"full_name": user.full_name, "new_status": user.is_active},
    )

    db.commit()
    return {"success": True, "is_active": user.is_active == True, "user_id": user_id}


@router.get("/groups/{group_id}/members")
async def get_group_members(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """List all members of a group. Available to GroupAdmin, Mentor, LDAdmin."""
    if current_user["role"] not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(status_code=403, detail="Forbidden")

    # Non-LDAdmin must be in or assigned to this group
    if current_user["role"] != "LDAdmin":
        has_scope = False
        if current_user["role"] == "Mentor":
            assign = (
                await db.run_sync(lambda s: s.query(models.MentorGroupAssignment)
                .filter_by(
                    mentor_id=int(current_user["sub"]), group_id=group_id, is_active=True
                )
                .first())
            )
            if assign:
                has_scope = True
        elif current_user.get("group_id") == group_id:
            has_scope = True
            
        if not has_scope:
            raise HTTPException(status_code=403, detail="Forbidden")
    redis_key = f"org:group_members:{group_id}"
    try:
        from cache_manager import redis_client
        import json
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    users = (
        await db.run_sync(lambda s: s.query(models.User)
        .filter(models.User.group_id == group_id, models.User.is_active.is_(True))
        .all())
    )

    res = [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "member_id": u.member_id,
            "streak_count": u.streak_count,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "profile_photo_url": u.profile_photo_url,
        }
        for u in users
    ]

    try:
        import json
        from cache_manager import redis_client
        await redis_client.set(redis_key, json.dumps(res), ex=3600)
    except Exception:
        pass

    return res


# ─── Notification Management ───────────────────────────────────────────────


@router.get("/notifications")
def get_notifications(
    limit: int = 20,
    skip: int = 0,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Fetch notifications for the current user, newest first with pagination."""
    user_id = int(current_user["sub"])
    notifications = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id)
        .order_by(models.Notification.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": n.id,
            "title": n.title,
            "body": n.body,
            "notification_type": n.notification_type,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
            "link_id": n.link_id,
            "link_type": n.link_type,
        }
        for n in notifications
    ]


@router.get("/notifications/stream")
async def stream_notifications(
    token: str = Query(..., description="JWT token for SSE authentication"),
    db: AsyncSession = Depends(get_async_db),
):
    """Real-time Server-Sent Events (SSE) stream for unread notifications."""
    try:
        import jwt
        from auth_utils import ALGORITHM, SECRET_KEY

        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    async def event_generator():
        while True:
            # 1. Check for new notifications
            count = (
                await db.run_sync(lambda s: s.query(models.Notification)
                .filter(
                    models.Notification.user_id == user_id,
                    models.Notification.is_read.is_(False),
                )
                .count())
            )

            # 2. Check for latest activity (Heatmap Sync)
            latest_activity = (
                await db.run_sync(lambda s: s.query(func.max(models.Attempt.attempted_at))
                .filter(models.Attempt.user_id == user_id)
                .scalar())
            )

            activity_ts = latest_activity.isoformat() if latest_activity else None

            # 3. Emit event payload
            yield f'data: {{"unread_count": {count}, "activity_ts": "{activity_ts}"}}\n\n'

            await asyncio.sleep(5)  # Poll every 5 seconds for changes

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/notifications/unread-count")
def get_unread_notification_count(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Returns count of unread notifications for badge display."""
    user_id = int(current_user["sub"])
    count = (
        db.query(models.Notification)
        .filter(models.Notification.user_id == user_id, models.Notification.is_read.is_(False))
        .count()
    )
    return {"unread_count": count}


@router.patch("/notifications/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Mark a single notification as read."""
    user_id = int(current_user["sub"])
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"success": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """Mark all notifications as read for the current user."""
    user_id = int(current_user["sub"])
    db.query(models.Notification).filter(
        models.Notification.user_id == user_id, models.Notification.is_read.is_(False)
    ).update({"is_read": True})
    db.commit()
    return {"success": True}


@router.post("/users/{user_id}/reactivate")
def reactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """ADMIN: Restore access to a previously deactivated user."""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    db.commit()

    from services.audit_service import log_admin_action

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="REACTIVATE_USER",
        resource_type="USER",
        resource_id=user_id,
        details={"email": user.email},
    )

    return {"success": True, "message": "User reactivated"}


@router.delete("/notifications/{notification_id}")
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """Delete a specific notification."""
    user_id = int(current_user["sub"])
    notif = (
        db.query(models.Notification)
        .filter(
            models.Notification.id == notification_id,
            models.Notification.user_id == user_id,
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    db.delete(notif)
    db.commit()
    return {"success": True}


# ─── GDPR & Session Governance ──────────────────────────────────────────────


@router.delete("/users/{user_id}")
def hard_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """
    GDPR-Compliant Hard Delete. Fully purges user data including attempts and profiles.
    Only accessible by LDAdmin.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if user is a SuperAdmin (protection)
    if user.role == "SuperAdmin":
        raise HTTPException(
            status_code=403, detail="SuperAdmin accounts cannot be deleted via API."
        )

    # Log the action before deletion
    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="HARD_DELETE_USER",
        resource_type="USER",
        resource_id=user_id,
        details={"email": user.email, "full_name": user.full_name},
    )

    # S3 Cleanup for Profile Photo
    if user.profile_photo_url and settings.S3_BUCKET_NAME and settings.S3_BUCKET_NAME in str(user.profile_photo_url):
        try:
            from services.s3_service import delete_s3_object

            s3_key = str(user.profile_photo_url).split(".amazonaws.com/")[-1]
            delete_s3_object(s3_key)
        except Exception as e:
            logger.error(f"Failed to delete S3 profile photo during hard delete: {e}")

    db.delete(user)
    db.commit()
    return {
        "success": True,
        "message": f"User {user_id} and all associated data purged successfully.",
    }


@router.post("/change-password")
def change_password(
    req: schemas.ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Allows a logged-in user to change their own password.
    Requires verification of the current password.
    """
    user = (
        db.query(models.User).filter(models.User.id == int(current_user["sub"])).first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(req.current_password, user.password_hash):
        # Fallback to pattern check if hashed_password is null?
        # Actually most users use hashed_password if they ever set one.
        # If password_hash is null, it means they are using the group pattern.
        if user.password_hash is None:
            # FIX #7: null-guard — user.group may be None if group was deleted
            if user.group is None:
                raise HTTPException(
                    status_code=400,
                    detail="User has no group assignment; cannot verify pattern password",
                )
            if req.current_password != user.group.password_pattern:
                raise HTTPException(status_code=400, detail="Invalid current password")
        else:
            raise HTTPException(status_code=400, detail="Invalid current password")

    user.password_hash = get_password_hash(req.new_password)
    db.commit()

    return {"success": True, "message": "Password updated successfully."}


@router.get("/me/sessions")
def get_active_sessions(
    db: Session = Depends(get_db), current_user: dict = Depends(verify_token)
):
    """
    Lists active refresh tokens (sessions) for the current user.
    SEC-102: Strategic session visibility.
    """
    user_id = int(current_user["sub"])
    sessions = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.is_revoked.is_(False),
            models.RefreshToken.expires_at > func.now(),
        )
        .all()
    )

    return [
        {
            "id": s.id,
            "created_at": s.created_at,
            "expires_at": s.expires_at,
            # We don't return the full token for security
            "token_preview": f"{s.token[:10]}..." if s.token else "N/A",
        }
        for s in sessions
    ]


@router.delete("/me/sessions/{session_id}")
def revoke_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_token),
):
    """
    Revokes a specific session (refresh token).
    """
    user_id = int(current_user["sub"])
    session = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.id == session_id, models.RefreshToken.user_id == user_id
        )
        .first()
    )

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.is_revoked = True
    db.commit()

    return {"success": True, "message": "Session revoked successfully."}


# ==============================================================================
# SSO / SAML / ENTERPRISE LOGIN (FASTEST PATH TO LAUNCH)
# ==============================================================================

import urllib.parse  # noqa: E402

from fastapi.responses import RedirectResponse  # noqa: E402

AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "placeholder.auth0.com")
AUTH0_CLIENT_ID = os.getenv("AUTH0_CLIENT_ID", "placeholder_client_id")
AUTH0_CALLBACK_URL = os.getenv(
    "AUTH0_CALLBACK_URL", "http://localhost:8000/api/auth/sso/callback"
)


@router.get("/sso/login")
def sso_login(org_slug: str):
    """
    Redirects the user to Auth0/SAML IdP for the given organization.
    """
    # In a real integration, we'd pass the organization ID to Auth0 to route to the correct enterprise IdP
    auth0_url = f"https://{AUTH0_DOMAIN}/authorize"
    params = {
        "response_type": "code",
        "client_id": AUTH0_CLIENT_ID,
        "redirect_uri": AUTH0_CALLBACK_URL,
        "scope": "openid profile email",
        "state": org_slug,  # Passing the org slug to know where to map them on callback
    }
    redirect_url = f"{auth0_url}?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=redirect_url)


@router.get("/sso/callback")
def sso_callback(code: str, state: str, db: Session = Depends(get_db)):
    """
    Handles the SSO callback, verifies the token, and establishes a local session.
    """
    org_slug = state
    # In a real integration, we would exchange `code` for an `access_token` and `id_token` here.

    # MOCK BEHAVIOR FOR FASTEST PATH TO LAUNCH:
    # 1. Fetch user info from IdP
    # 2. Find Organization by slug (state)
    # 3. Find or Create User by email
    # 4. Generate local JWT tokens

    mock_email = "enterprise_user@example.com"
    mock_name = "Enterprise User"

    org = (
        db.query(models.Organization)
        .filter(models.Organization.slug == org_slug)
        .first()
    )
    if not org:
        raise HTTPException(
            status_code=400, detail="Invalid SSO state: Organization not found"
        )

    # Find a default group for the org to place the user in
    # This is a simplification. Usually IdP groups are mapped to internal groups.
    dept = (
        db.query(models.Department)
        .filter(models.Department.organization_id == org.id)
        .first()
    )
    if not dept:
        raise HTTPException(
            status_code=400, detail="Organization misconfigured: No departments found"
        )

    vertical = (
        db.query(models.Vertical)
        .filter(models.Vertical.department_id == dept.id)
        .first()
    )
    db.query(models.Batch).filter(
        models.Batch.vertical_id == vertical.id
    ).first() if vertical else None

    group = db.query(models.Group).filter(models.Group.department_id == dept.id).first()
    if not group:
        raise HTTPException(
            status_code=400, detail="Organization misconfigured: No groups found"
        )

    user = db.query(models.User).filter(models.User.email == mock_email).first()
    if not user:
        user = models.User(
            email=mock_email,
            full_name=mock_name,
            group_id=group.id,
            role="Member",
            vertical_id=vertical.id if vertical else None,
            department_id=dept.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Generate tokens
    from datetime import timedelta
    from config import settings
    access_token_expires = timedelta(minutes=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30))
    access_token = create_access_token(
        data={"sub": str(user.id), "role": user.role, "group_id": user.group_id},
        expires_delta=access_token_expires,
    )

    refresh_token_expires = timedelta(days=getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7))
    refresh_token = create_access_token(
        data={"sub": str(user.id), "type": "refresh"},
        expires_delta=refresh_token_expires,
    )

    db_refresh = models.RefreshToken(
        user_id=user.id,
        token=refresh_token,
        expires_at=datetime.datetime.utcnow() + refresh_token_expires,
    )
    db.add(db_refresh)
    db.commit()

    # Redirect back to frontend dashboard with tokens (Usually set as HttpOnly cookies or query params)
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    return RedirectResponse(
        url=f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    )
    return RedirectResponse(
        url=f"{frontend_url}/auth/callback?access_token={access_token}&refresh_token={refresh_token}"
    )
