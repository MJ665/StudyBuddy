"""users endpoints (moved verbatim from routers/auth.py)."""
from fastapi import APIRouter

from modules.identity.routers.auth_shared import *  # noqa: F401,F403

router = APIRouter()

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
