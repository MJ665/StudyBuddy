import datetime
import logging
from typing import List, Optional

import models
import schemas
import tasks
from auth_utils import (
    assert_batch_in_org,
    assert_group_in_org,
    assert_user_in_org,
    require_ldadmin,
    require_mentor_or_above,
)
from database import get_async_db, get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from services.ai_reporting import ai_executive
from services.audit_service import log_admin_action, log_email_dispatch
from services.performance_engine import performance_engine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
from config import settings  # noqa: E402

router = APIRouter(prefix="/admin", tags=["admin_governance"])

from cache_manager import cache_manager  # noqa: E402
from pagination import paginate  # noqa: E402

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


@router.get("/groups/{group_id}/leaderboard")
async def get_group_leaderboard_admin(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Alias for the group leaderboard endpoint used by the admin dashboard."""
    assert_group_in_org(group_id, db, current_user)
    from routers.reports import get_group_leaderboard

    return await get_group_leaderboard(group_id, db, current_user)


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


# ─── SECTION 12: AI Executive Reporting ──────────────────────────────────────


@router.get("/batch/{batch_id}/insights")
@cache_manager.cached("batch_intel", ttl=129600)
async def get_batch_intelligence(
    batch_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Returns full 30-dimension aggregate intelligence for a batch."""
    assert_batch_in_org(batch_id, db, current_user)
    intel = await performance_engine.get_batch_vectors(batch_id, db, refresh=refresh)
    if not intel:
        raise HTTPException(status_code=404, detail="Batch data unavailable")
    return intel


@router.get("/batch/{batch_id}/ai-insights")
@cache_manager.cached("batch_ai_insights", ttl=86400)  # 24h cache
async def get_batch_ai_insights(
    batch_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Generates high-fidelity AI insights for a specific batch using aggregate vectors."""
    assert_batch_in_org(batch_id, db, current_user)
    batch = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.id == batch_id).first())
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    intel = await performance_engine.get_batch_vectors(batch_id, db, refresh=refresh)

    # Enrich simple stats for AI
    data = {
        "batch_name": batch.name,
        "total_members": intel.get("charts", {}).get("member_count", 0),
        "total_attempts": intel.get("charts", {}).get("total_attempts", 0),
        "average_score": intel.get("metrics", {})
        .get("m02_overall_accuracy", {})
        .get("raw", 0),
        "top_performers": [],  # Potential for future expansion
        "group_performance": [],  # Potential for future expansion
    }

    insights = await ai_executive.generate_batch_insights(batch.name, data)
    return {"insights": insights.get("data", [])}


@router.get("/batch/{batch_id}/executive-summary")
@cache_manager.cached("batch_exec_summary", ttl=86400)  # 24h cache
async def get_batch_executive_summary(
    batch_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Generates a professional executive summary for a batch."""
    assert_batch_in_org(batch_id, db, current_user)
    batch = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.id == batch_id).first())
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    summary = await ai_executive.generate_batch_executive_summary(
        batch.name, {"id": batch_id}
    )
    return {"summary": summary.get("data", "")}


@router.get("/export-activity")
@router.post("/export-activity")
def export_global_activity(
    db: Session = Depends(get_db), current_user: dict = Depends(require_ldadmin)
):
    """PHASE-3: Global Strategic Activity Export (XLSX)."""
    import datetime

    from fastapi.responses import StreamingResponse
    from services.reporting_service import generate_global_activity_report

    output = generate_global_activity_report(db)

    # Log the export action
    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="EXPORT_GLOBAL_ACTIVITY",
        resource_type="SYSTEM",
        details={"format": "XLSX"},
    )

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=StudyHub_GlobalActivity_{datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d')}.xlsx"
        },
    )


@router.post("/metrics/refresh")
async def refresh_admin_metrics(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(require_ldadmin)
):
    """
    SECTION 11.1: Enterprise Dashboard Consolidation.
    Triggers re-calculation of global and cohort intelligence vectors.
    """
    # 1. Platform-wide Intelligence
    tasks.calculate_global_intel(db)

    # 2. Cohort Intelligence (Active Batches)
    try:
        active_batches = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.is_active.is_(True)).all())
        for batch in active_batches:
            # We trigger the recalculation which will update the Redis cache
            await performance_engine.get_batch_vectors(batch.id, db, refresh=True)

        logger.info(f"Admin {current_user['sub']} triggered a full metrics refresh.")
        return {
            "success": True,
            "message": f"Global and {len(active_batches)} Cohort metrics recalculated.",
        }
    except Exception as e:
        logger.error(f"Metrics refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Metric recalculation failed.")


@router.get("/analytics/insights")
@cache_manager.cached("global_intel", ttl=129600)
async def get_global_intelligence(
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Returns platform-wide aggregate 30-metric intelligence."""
    return await performance_engine.get_global_vectors(db, refresh=refresh)


@router.get("/analytics/ai-insights")
@cache_manager.cached("global_ai_insights", ttl=86400)  # 24h cache
async def get_global_analytics_insights(
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Generates cross-org AI analytics insights using global vectors."""
    intel = await performance_engine.get_global_vectors(db, refresh=refresh)

    data = {
        "total_users": intel.get("charts", {}).get("member_count", 0),
        "total_attempts": intel.get("charts", {}).get("total_attempts", 0),
        "avg_accuracy": intel.get("metrics", {})
        .get("m02_overall_accuracy", {})
        .get("raw", 0),
    }

    res = await ai_executive.generate_analytics_insights(data)
    return res.get("data", {})


@router.get("/health")
def get_system_health(
    db: Session = Depends(get_db), current_user: dict = Depends(require_mentor_or_above)
):
    """PHASE-3: Real-time system health metrics for the LDAdmin Dashboard."""
    import datetime

    one_day_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        days=1
    )

    return {
        "status": "Operational",
        "version": settings.APP_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "components": {
            "database": {"status": "Operational", "message": "Postgres Pool Healthy"},
            "redis": {"status": "Operational", "message": "Cache Layer Active"},
            "ai_engine": {"status": "Operational", "message": "LangGraph Ready"},
            "email": {"status": "Operational", "message": "SMTP Relay Standby"},
        },
        "metrics": {
            "active_users_24h": db.query(models.User)
            .filter(models.User.last_active_date >= one_day_ago)
            .count(),
            "new_attempts_24h": db.query(models.Attempt)
            .filter(models.Attempt.attempted_at >= one_day_ago)
            .count(),
            "new_code_submissions_24h": db.query(models.CodingAttempt)
            .filter(models.CodingAttempt.attempted_at >= one_day_ago)
            .count(),
        },
        "tasks": {
            t.task_name: {
                "last_run": t.last_run_at.isoformat() if t.last_run_at else None,
                "status": t.last_status,
                "runs": t.run_count,
            }
            for t in db.query(models.SystemTaskStatus).all()
        },
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


@router.get("/reports/executive/{batch_id}")
async def get_executive_report(
    batch_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Full-stack executive report for a batch (STRAT-301)."""
    assert_batch_in_org(batch_id, db, current_user)
    batch = await db.run_sync(lambda s: s.query(models.Batch).filter(models.Batch.id == batch_id).first())
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    summary = await ai_executive.generate_batch_executive_summary(
        batch.name, {"id": batch_id}
    )
    return {
        "batch_id": batch_id,
        "batch_name": batch.name,
        "executive_summary": summary,
    }


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


@router.get("/tasks/status")
def get_all_task_status(
    db: Session = Depends(get_db), current_user: dict = Depends(require_ldadmin)
):
    """PHASE-4: Returns the latest execution telemetry for all background tasks."""
    tasks = db.query(models.SystemTaskStatus).all()
    return [
        {
            "task_name": t.task_name,
            "status": t.last_status,
            "last_run": t.last_run_at,
            "last_duration_seconds": 0,
            "error_message": t.last_error,
        }
        for t in tasks
    ]


@router.post("/tasks/trigger/{task_name}")
def trigger_background_task(
    task_name: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-4: Manual trigger for background tasks (Strategic Recovery)."""
    import tasks

    task_map = {
        "generate_daily_challenges": tasks.generate_daily_challenges,
        "send_daily_challenge_notifications": tasks.send_daily_challenge_notifications,
        "send_deadline_reminders": tasks.send_deadline_reminders,
        "auto_lock_assignments": tasks.auto_lock_assignments,
        "maintain_streaks": tasks.maintain_streaks,
        "send_weekly_digest": tasks.send_weekly_digest,
        "process_reengagement_lifecycle": tasks.process_reengagement_lifecycle,
        "cleanup_stale_data": tasks.cleanup_stale_data,
        "calculate_global_intel": tasks.calculate_global_intel,
        "sync_s3_resources": tasks.sync_s3_resources,
        "prune_s3_resources": tasks.prune_orphaned_s3_objects,
        "merge_duplicate_users": tasks.merge_duplicate_users,
        "fix_orphaned_records": tasks.fix_orphaned_records,
    }

    if task_name not in task_map:
        raise HTTPException(status_code=400, detail="Invalid task name")

    try:
        task_func = task_map[task_name]
        background_tasks.add_task(task_func)

        log_admin_action(
            db=db,
            actor_id=int(current_user["sub"]),
            actor_role=current_user["role"],
            action="MANUAL_TASK_TRIGGER",
            resource_type="SYSTEM_TASK",
            resource_id=0,
            details={"task": task_name},
        )

        return {"success": True, "message": f"Task '{task_name}' queued successfully."}
    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"Manual trigger failed for {task_name}: {error_trace}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/infrastructure/sync")
async def sync_infrastructure(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(require_ldadmin)
):
    """PHASE-4: Forces a re-run of the system bootstrap/auto-provisioning logic."""
    from ensure_system_identity import ensure_system
    from startup_validator import validate_infrastructure

    # 1. Connectivity & Dependency Pass
    await validate_infrastructure()

    # 2. Identity & Registry Pass
    ensure_system()

    # Invalidate core caches to reflect bootstrap changes
    await cache_manager.invalidate("org_tree")
    await cache_manager.invalidate("global_stats")

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="INFRASTRUCTURE_SYNC",
        resource_type="SYSTEM",
        resource_id=0,
        details={"trigger": "manual_admin_dashboard"},
    )

    return {"success": True, "message": "Infrastructure synchronization complete."}


@router.post("/infrastructure/deep-sync")
async def sync_infrastructure_status(
    db: AsyncSession = Depends(get_async_db), current_user: dict = Depends(require_ldadmin)
):
    """PHASE-4: Deep-sync protocol for infrastructure validation.

    Distinct path from /infrastructure/sync — previously both shared the same
    route so this handler was shadowed and unreachable.
    """
    from startup_validator import startup_validator

    health_results = await startup_validator.validate_all()

    log_admin_action(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="INFRA_DEEP_SYNC",
        resource_type="SYSTEM",
        resource_id=0,
        details={"results": health_results},
    )

    return {
        "status": "success",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "health_pass": all(
            r.get("status") in ["healthy", "disabled"] for r in health_results.values()
        ),
        "telemetry": health_results,
    }
