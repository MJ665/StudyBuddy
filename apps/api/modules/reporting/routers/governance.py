"""governance endpoints (moved verbatim from routers/admin.py)."""
from fastapi import APIRouter

from modules.reporting.routers.admin_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/target-levels")
def get_target_levels(current_user: dict = Depends(require_ldadmin)):
    """
    Returns the organizational hierarchy target levels for access control and reporting.
    """
    return [
        {"id": "group", "name": "Group (Specific)"},
        {"id": "batch", "name": "Batch (All Groups in Batch)"},
        {"id": "vertical", "name": "Vertical (All Batches)"},
        {"id": "dept", "name": "Department (All Verticals)"},
        {"id": "org", "name": "Organization (Global)"}
    ]

@router.get("/audit")
@cache_manager.cached("admin_audit", ttl=60)
def get_audit_logs(
    target_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    query_str: Optional[str] = None,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: High-fidelity audit retrieval with recursive search for L&D Global Administrators."""
    query = db.query(models.AdminAuditLog)

    if target_type:
        query = query.filter(models.AdminAuditLog.resource_type == target_type)
    if actor_id:
        query = query.filter(models.AdminAuditLog.actor_id == actor_id)
    if query_str:
        from sqlalchemy import String, cast, or_

        search_pattern = f"%{query_str}%"
        query = query.filter(
            or_(
                models.AdminAuditLog.action.ilike(search_pattern),
                models.AdminAuditLog.resource_type.ilike(search_pattern),
                cast(models.AdminAuditLog.details, String).ilike(search_pattern),
            )
        )

    query = query.order_by(models.AdminAuditLog.timestamp.desc())
    paginated = paginate(query, page, size)

    formatted_logs = [
        {
            "id": log.id,
            "admin_name": log.actor.full_name if log.actor else "System",
            "actor_role": log.actor_role,
            "action": log.action,
            "target_type": log.resource_type,
            "target_id": log.resource_id,
            "metadata": log.details,
            "ip_address": log.ip_address,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
        }
        for log in paginated.items
    ]

    return {
        "items": formatted_logs,
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
        "pages": paginated.pages,
    }

@router.get("/email-logs")
@cache_manager.cached("admin_email_logs", ttl=30)
def get_email_logs(
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Visibility into all outgoing system communications."""
    query = db.query(models.EmailLog).order_by(models.EmailLog.sent_at.desc())
    paginated = paginate(query, page, size)

    return {
        "items": [
            {
                "id": log.id,
                "recipient": log.recipient_email,
                "type": log.email_type,
                "subject": log.subject,
                "status": log.status,
                # EmailLog has no `error_message` column — reading it raised
                # AttributeError and 500'd this endpoint on every call.
                "error": getattr(log, "error_message", None),
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                # EmailLog has NO relationships and no error_message column;
                # both were hallucinated and 500'd this endpoint on every call.
                "user_id": log.user_id,
            }
            for log in paginated.items
        ],
        "total": paginated.total,
        "page": paginated.page,
        "size": paginated.size,
    }

@router.get("/security-stats")
@cache_manager.cached("security_stats", ttl=600)
def get_security_highlights(
    db: Session = Depends(get_db), current_user: dict = Depends(require_ldadmin)
):
    """Summary of administrative actions over the last 30 days."""
    import datetime

    thirty_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=30
    )

    total_actions = (
        db.query(models.AdminAuditLog)
        .filter(models.AdminAuditLog.timestamp >= thirty_days_ago)
        .count()
    )
    role_changes = (
        db.query(models.AdminAuditLog)
        .filter(
            models.AdminAuditLog.timestamp >= thirty_days_ago,
            models.AdminAuditLog.action == "PROMOTE_USER",
        )
        .count()
    )

    recent_admins = (
        db.query(models.User.full_name)
        .join(models.AdminAuditLog, models.AdminAuditLog.actor_id == models.User.id)
        .distinct()
        .limit(5)
        .all()
    )

    result = {
        "thirty_day_velocity": total_actions,
        "role_mutations": role_changes,
        "active_governance_nodes": [a[0] for a in recent_admins],
    }

    return result

@router.post("/seed-daily")
def seed_daily_on_demand(
    group_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """
    On-demand daily challenge seed — wired to the 'Seed Daily' button in the L&D admin dashboard.
    Enforced by Global LDAdmin privileges (AUD-Logged).
    """
    assert_group_in_org(group_id, db, current_user)
    try:
        tasks.generate_daily_challenges(group_id=group_id)

        # Log the action (Strategic Audit)
        log_admin_action(
            db=db,
            actor_id=int(current_user["sub"]),
            actor_role=current_user["role"],
            action="SEED_DAILY_CHALLENGES",
            resource_type="GROUP" if group_id else "SYSTEM",
            resource_id=group_id,
            details={
                "triggered_by": current_user.get("full_name"),
                "target_group": group_id,
            },
        )

        return {
            "success": True,
            "message": f"Daily challenges seeded for {'group ' + str(group_id) if group_id else 'all active nodes'}.",
        }
    except Exception as e:
        import traceback

        print(f"Seed daily failed: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notify-intervention")
def notify_intervention(
    req: schemas.InterventionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """
    SECTION 12: Trigger targeted performance interventions.
    Enables L&D Executives to synchronize learning paths via direct email triggers.
    """
    from services.email_service import send_intervention_email

    users = db.query(models.User).filter(models.User.id.in_(req.user_ids)).all()
    success_count = 0

    for user in users:
        if user.email:
            sent = send_intervention_email(
                to_email=user.email,
                full_name=user.full_name,
                message=req.message,
                admin_name=current_user.get("full_name", "L&D Executive"),
            )

            # Log the email dispatch (Strategic Audit)
            log_email_dispatch(
                db=db,
                recipient_email=user.email,
                email_type="PERFORMANCE_INTERVENTION",
                subject="📊 Strategic Performance Notification",
                user_id=user.id,
                status="sent" if sent else "failed",
                commit=False,
            )

            if sent:
                success_count += 1

    # Log the action
    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="PERFORMANCE_INTERVENTION",
        resource_type="USER_BATCH",
        resource_id=None,
        details={
            "recipient_count": len(users),
            "sent_success": success_count,
            "message_summary": req.message[:100] + "..."
            if len(req.message) > 100
            else req.message,
        },
    )

    return {
        "success": True,
        "message": f"Dispatched {success_count} intervention notifications successfully.",
        "recipients": [u.full_name for u in users],
    }

@router.get("/reports", response_model=List[schemas.QuestionReportResponse])
def get_question_reports(
    resolved: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Retrieves all question reports for administrative audit."""
    query = db.query(models.QuestionReport)
    if resolved is not None:
        query = query.filter(models.QuestionReport.is_resolved == resolved)

    reports = query.order_by(models.QuestionReport.created_at.desc()).all()

    # Map explicitly: the response schema uses reporter_id/reason/comment while the
    # model columns are user_id/issue_type/description. `model_validate(r)` therefore
    # raised 3 validation errors and 500'd this endpoint, and `r.reporter_id` does
    # not exist at all. (interaction.py already maps these by hand.)
    reporter_ids = {r.user_id for r in reports if r.user_id is not None}
    reporters = {}
    if reporter_ids:
        reporters = {
            u.id: u
            for u in db.query(models.User).filter(models.User.id.in_(reporter_ids)).all()
        }

    question_ids = {r.question_id for r in reports if r.question_id is not None}
    questions = {}
    if question_ids:
        questions = {
            q.id: q
            for q in db.query(models.Question)
            .filter(models.Question.id.in_(question_ids))
            .all()
        }

    enriched = []
    for r in reports:
        q = questions.get(r.question_id)
        reporter = reporters.get(r.user_id)
        enriched.append(
            {
                "id": r.id,
                "question_id": r.question_id,
                "reporter_id": r.user_id,
                "reason": r.issue_type,
                "comment": r.description,
                "is_resolved": r.is_resolved,
                "resolved_by": r.resolved_by,
                "resolved_at": r.resolved_at,
                "created_at": r.created_at,
                "question_text": q.question if q else "DELETED_QUESTION",
                "reporter_name": reporter.full_name if reporter else "UNKNOWN_USER",
            }
        )

    return enriched

@router.patch("/reports/{report_id}/resolve")
def resolve_question_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Marks a question report as resolved."""
    report = (
        db.query(models.QuestionReport)
        .filter(models.QuestionReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.is_resolved = True
    report.resolved_by = int(current_user["sub"])
    report.resolved_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()

    log_admin_action(
        db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="RESOLVE_REPORT",
        resource_type="QUESTION_REPORT",
        resource_id=report_id,
        details={"question_id": report.question_id},
    )

    return {"success": True}

@router.post("/users/{user_id}/reset-password")
def admin_reset_password(
    user_id: int,
    req: schemas.AdminPasswordReset,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Emergency password override for L&D Global Administrators (AUD-Logged)."""
    assert_user_in_org(user_id, db, current_user)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from routers.auth import get_password_hash

    user.password_hash = get_password_hash(req.new_password)
    db.commit()

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="FORCE_RESET_PASSWORD",
        resource_type="USER",
        resource_id=user_id,
        details={"admin": current_user.get("full_name")},
    )

    return {
        "success": True,
        "message": f"Password reset successfully for {user.full_name}.",
    }

@router.post("/bulk-action")
def bulk_admin_action(
    req: schemas.BulkActionRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Perform bulk administrative actions on users."""
    users = db.query(models.User).filter(models.User.id.in_(req.user_ids)).all()
    count = 0

    for user in users:
        if req.action == "deactivate":
            user.is_active = False
            count += 1
        elif req.action == "activate":
            user.is_active = True
            count += 1
        elif req.action == "delete":
            db.delete(user)
            count += 1

    db.commit()

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action=f"BULK_{req.action.upper()}_USERS",
        resource_type="USER_BATCH",
        resource_id=0,
        details={"count": count, "ids": req.user_ids[:10]},
    )

    return {"message": f"Successfully performed {req.action} on {count} users."}
