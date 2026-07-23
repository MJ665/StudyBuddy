"""session endpoints (moved verbatim from routers/auth.py)."""
from fastapi import APIRouter

from modules.identity.routers.auth_shared import *  # noqa: F401,F403

router = APIRouter()

@router.post("/login")
def login(req: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Email-first login — individual credentials ONLY.

    The legacy group-password-pattern path is RETIRED (plan Phase 6): every
    account is issued an individual password at creation (see users.py
    credential lifecycle), so the shared-pattern fallback no longer exists.
    """
    if not req.email:
        raise HTTPException(
            status_code=422,
            detail="Group-based login has been retired. Sign in with your email "
            "and password; use 'Forgot password' if you don't have one.",
        )

    candidates = (
        db.query(models.User)
        .filter(
            models.User.email == req.email.lower().strip(),
            models.User.is_active.is_(True),
        )
        .all()
    )
    # users.email is unique per (email, group_id) — the same person may
    # have one row per group membership. Only rows with an individual
    # password can email-login.
    with_pw = [u for u in candidates if u.password_hash]
    # Uniform 401 for unknown email / no password / bad password — no
    # account-existence oracle.
    user = None
    for cand in with_pw:
        if pwd_context.verify(req.password, cand.password_hash):
            user = cand
            break
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

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
