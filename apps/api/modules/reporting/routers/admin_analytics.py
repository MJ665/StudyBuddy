"""admin_analytics endpoints (moved verbatim from routers/admin.py)."""
from fastapi import APIRouter

from modules.reporting.routers.admin_shared import *  # noqa: F401,F403

router = APIRouter()

@router.get("/groups/{group_id}/leaderboard")
async def get_group_leaderboard_admin(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Alias for the group leaderboard endpoint used by the admin dashboard."""
    await db.run_sync(lambda s: assert_group_in_org(group_id, s, current_user))
    from routers.reports import get_group_leaderboard

    return await get_group_leaderboard(group_id, db, current_user)

@router.get("/batch/{batch_id}/insights")
@cache_manager.cached("batch_intel", ttl=129600)
async def get_batch_intelligence(
    batch_id: int,
    refresh: bool = False,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """Returns full 30-dimension aggregate intelligence for a batch."""
    await db.run_sync(lambda s: assert_batch_in_org(batch_id, s, current_user))
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
    await db.run_sync(lambda s: assert_batch_in_org(batch_id, s, current_user))
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
    await db.run_sync(lambda s: assert_batch_in_org(batch_id, s, current_user))
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

@router.get("/reports/executive/{batch_id}")
async def get_executive_report(
    batch_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    """PHASE-3: Full-stack executive report for a batch (STRAT-301)."""
    await db.run_sync(lambda s: assert_batch_in_org(batch_id, s, current_user))
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
