import asyncio
import datetime
import logging
import os
import sys

import bcrypt

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging to stdout so logs appear in Vercel's "Logs" tab
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("studyhub")

import models  # noqa: E402
from config import settings  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from ensure_system_identity import ensure_system  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from routers import (  # noqa: E402
    admin,
    ai,
    assignment,
    auth,
    billing,
    contact,
    export,
    intel,
    interaction,
    kt,
    mentor,
    org,
    profile,
    quiz,
    reports,
    resources,
)

# ── Observability: structured logging + telemetry backend (Sentry/OTel/none) ──
# Vendor-neutral facade — flip TELEMETRY_BACKEND to switch the whole stack.
from observability import logging_config, telemetry  # noqa: E402

logging_config.setup()  # re-applies env-driven LOG_LEVEL/LOG_FORMAT over the bootstrap

# Create the FastAPI app
app = FastAPI(
    title="StudyBuddy Enterprise API",
    description="Multi-tenant AI assessment platform — RBAC, quiz/coding/exam, KT knowledge graph, white-label.",
    version=settings.APP_VERSION,
    redirect_slashes=False,
)

# Initialize telemetry AFTER the app exists (OTel needs the app to instrument).
telemetry.init_telemetry(app)

# I: Strict CORS — restrict to known origins (not wildcard)
origins = []
if not settings.is_production() or settings.DEBUG:
    origins.append("http://localhost:3000")
    origins.append("http://localhost:5173")
    origins.append("http://127.0.0.1:3000")
    origins.append("http://127.0.0.1:5173")

for origin in settings.ALLOWED_ORIGINS:
    if origin:
        origins.append(origin)

if os.environ.get("VERCEL_URL"):
    origins.append(f"https://{os.environ.get('VERCEL_URL')}")

# Filter out empty strings and ensure unique origins
origins = [o for o in origins if o]

if settings.is_production() and not origins and not settings.DEBUG:
    raise RuntimeError(
        "CRITICAL: No ALLOWED_ORIGINS or FRONTEND_URL configured in production environment."
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ── Rate limiting (per-IP, global default) ──────────────────────────────────
# A baseline guard against brute-force / abuse; stricter per-endpoint limits can
# be layered with @limiter.limit(...) on hot targets (login, AI, key generation).
from slowapi import Limiter, _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.middleware import SlowAPIMiddleware  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402

limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── Typed application errors (modular monolith, Phase 1) ────────────────────
# Modules raise shared.exceptions.* instead of ad-hoc HTTPException; one
# handler keeps the {"detail": ...} response shape consistent platform-wide.
from shared.exceptions import register_error_handlers  # noqa: E402

register_error_handlers(app)


# I: HTTPS enforcement + Request logging (shows in Vercel "Logs" tab)
# Set ENFORCE_HTTPS=true in your production environment variables
@app.middleware("http")
async def https_redirect(request: Request, call_next):
    import time

    forwarded_proto = request.headers.get("X-Forwarded-Proto")
    if forwarded_proto == "http" and settings.ENFORCE_HTTPS:
        secure_url = request.url.replace(scheme="https")
        return JSONResponse(
            {"detail": "Please use HTTPS"},
            status_code=301,
            headers={"Location": str(secure_url)},
        )
    # Attribute AI cost to the calling tenant for this request (best-effort JWT
    # decode, no DB). contextvars set here are visible to downstream awaits.
    try:
        import jwt as _jwt

        from services import ai_meter

        _auth = request.headers.get("Authorization", "")
        if _auth.startswith("Bearer "):
            _p = _jwt.decode(
                _auth[7:],
                settings.JWT_SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},
            )
            _uid = int(_p["sub"]) if _p.get("sub") else None
            _oid = _p.get("organization_id")
            ai_meter.set_request_context(_oid, _uid)
            from observability import tracing as _tracing

            _tracing.set_user_org(_uid, _oid)  # attach identity for error triage
        else:
            ai_meter.set_request_context(None, None)
    except Exception:
        from services import ai_meter

        ai_meter.set_request_context(None, None)

    start = time.time()
    response = await call_next(request)
    ms = round((time.time() - start) * 1000)
    # Security headers (API is a JSON backend; the SPA lives on a separate origin).
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Server-Timing-Ms"] = str(ms)
    if settings.is_production():
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    logger.info(
        f"{request.method} {request.url.path} → {response.status_code} ({ms}ms)"
    )
    try:
        from observability import metrics as _metrics

        _metrics.distribution(
            "http.request.duration", ms, unit="millisecond",
            method=request.method, status=response.status_code,
        )
    except Exception:
        pass
    return response


from routers.code import router as code_router  # noqa: E402
from routers.system_config import router as system_config_router  # noqa: E402
from routers.platform import router as platform_router  # noqa: E402
from routers.onboarding import router as onboarding_router  # noqa: E402
from routers.exam import router as exam_router  # noqa: E402
from routers.gradebook import router as gradebook_router  # noqa: E402

# Include Routers (Consolidated under /api prefix for versioning)
app.include_router(system_config_router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(quiz.router, prefix="/api")
app.include_router(profile.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(org.router, prefix="/api")
app.include_router(mentor.router, prefix="/api")
app.include_router(assignment.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(interaction.router, prefix="/api")
app.include_router(code_router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(intel.router, prefix="/api")
app.include_router(kt.router, prefix="/api")
app.include_router(contact.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(platform_router, prefix="/api")
app.include_router(onboarding_router, prefix="/api")
app.include_router(exam_router, prefix="/api")
app.include_router(gradebook_router, prefix="/api")

# Mobile push-token registration (apps/mobile wrapper) → /api/notifications/register-device
from modules.identity.routers import devices as _devices  # noqa: E402
app.include_router(_devices.router, prefix="/api/notifications")

import tasks  # noqa: E402
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402

# VII: APScheduler stabilized with UTC context
scheduler = AsyncIOScheduler(timezone=datetime.timezone.utc)


@app.on_event("startup")
async def on_startup():
    """Enterprise-grade auto-provisioning protocol."""
    logger.info("🚀 Initiating StudyHub V3 Auto-Provisioning Sequence...")

    try:
        from startup_validator import validate_infrastructure

        await validate_infrastructure()
    except Exception as e:
        logger.error(f"❌ Infrastructure validation failed: {e}")
        if settings.is_production():
            raise

    # 1. Schema Generation (Standardized for automated deployment)
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database schema provisioned successfully.")
    except Exception as e:
        logger.error(f"❌ Schema provisioning failed: {e}")

    # 2. Identity Enforcement (ID 0)
    try:
        ensure_system()
        logger.info("✅ System Identity protocols verified.")
    except Exception as e:
        logger.error(f"❌ System Identity enforcement failed: {e}")

    # 3. Automation Worker Registration
    db = SessionLocal()
    try:
        tasks_to_register = [
            "generate_daily_challenges",
            "send_daily_challenge_notifications",
            "send_deadline_reminders",
            "auto_lock_assignments",
            "maintain_streaks",
            "send_weekly_digest",
            "process_reengagement_lifecycle",
            "cleanup_stale_data",
            "calculate_global_intel",
            "sync_s3_resources",
        ]
        registered_count = 0
        for task_name in tasks_to_register:
            if (
                not db.query(models.SystemTaskStatus)
                .filter_by(task_name=task_name)
                .first()
            ):
                db.add(
                    models.SystemTaskStatus(
                        task_name=task_name, last_status="STANDBY", run_count=0
                    )
                )
                registered_count += 1
        db.commit()
        if registered_count > 0:
            logger.info(f"✅ Registered {registered_count} automation workers.")
    except Exception as e:
        logger.error(f"❌ Worker registration failed: {e}")
        db.rollback()
    finally:
        db.close()

    logger.info("✨ Auto-Provisioning Complete. System Operational.")


@app.on_event("startup")
def start_scheduler():
    """
    STRAT-SCHED-01: Automation Worker Synchronization.
    Precise scheduling of platform-critical intelligence and maintenance tasks.
    """
    # Run the scheduler on ONE instance only. When scaled to multiple containers,
    # each would otherwise fire every cron job (duplicate daily challenges, N× emails,
    # streak double-increments). Set RUN_SCHEDULER=false on all but one instance.
    if os.environ.get("RUN_SCHEDULER", "true").lower() not in ("1", "true", "yes"):
        logger.info("⏸️  Scheduler disabled on this instance (RUN_SCHEDULER=false).")
        return

    # 1. Pedagogical Seeding (Daily Challenges at Midnight)
    scheduler.add_job(tasks.generate_daily_challenges, "cron", hour=0, minute=0)

    # 2. Morning Sync Protocol (9 AM UTC)
    scheduler.add_job(
        tasks.send_daily_challenge_notifications, "cron", hour=9, minute=0
    )
    scheduler.add_job(tasks.send_deadline_reminders, "cron", hour=9, minute=0)
    scheduler.add_job(tasks.process_reengagement_lifecycle, "cron", hour=10, minute=0)

    # 3. Streak Maintenance (Midnight UTC)
    scheduler.add_job(tasks.maintain_streaks, "cron", hour=0, minute=5)

    # 4. Intelligence & Resource Sync (Periodic)
    # Auto-lock past-due assignments every hour
    scheduler.add_job(tasks.auto_lock_assignments, "interval", hours=1)

    # Calculate Global Intel (Weekly on Sunday at 2:00 AM)
    scheduler.add_job(
        tasks.calculate_global_intel, "cron", day_of_week="sun", hour=2, minute=0
    )

    # S3 Resource Sync / Cleanup (Every Saturday at 4 AM)
    scheduler.add_job(
        tasks.sync_s3_resources, "cron", day_of_week="sat", hour=4, minute=0
    )

    # 5. Global Reporting (Weekly Digest)
    scheduler.add_job(
        tasks.send_weekly_digest, "cron", day_of_week="sun", hour=19, minute=0
    )

    # 6. Maintenance (Cleanup Stale Data)
    scheduler.add_job(
        tasks.cleanup_stale_data, "cron", day_of_week="sat", hour=3, minute=0
    )

    scheduler.start()
    logger.info("✅ Automation Scheduler Synchronized and Active.")


# Cleanup logic or other final initializations can go here


@app.on_event("shutdown")
def stop_scheduler():
    scheduler.shutdown()


@app.on_event("startup")
async def startup_event():
    from startup_validator import startup_validator

    await startup_validator.validate_all()
    ensure_system(SessionLocal())
    logger.info("System operational readiness confirmed.")


# ── Durable background job worker ────────────────────────────────────────────
# Unlike the APScheduler above, this does NOT need a single-instance guard: jobs
# are claimed with FOR UPDATE SKIP LOCKED, so every replica can safely drain the
# same queue. Set RUN_JOB_WORKER=false to opt an instance out.
_job_worker_task = None
_job_worker_stop = None


@app.on_event("startup")
async def start_job_worker():
    global _job_worker_task, _job_worker_stop
    import asyncio

    import services.job_handlers  # noqa: F401  — registers the handlers
    from database import db_session_factory
    from services.job_queue import registered_handlers, worker_loop

    if os.environ.get("RUN_JOB_WORKER", "true").lower() not in ("1", "true", "yes"):
        logger.info("⏸️  Job worker disabled on this instance (RUN_JOB_WORKER=false).")
        return

    _job_worker_stop = asyncio.Event()
    _job_worker_task = asyncio.create_task(
        worker_loop(db_session_factory, _job_worker_stop)
    )
    logger.info(f"🛠️  Job worker started; handlers={sorted(registered_handlers())}")


@app.on_event("shutdown")
async def stop_job_worker():
    """Ask the worker to finish its current batch instead of killing it mid-job."""
    if _job_worker_stop is not None:
        _job_worker_stop.set()
    if _job_worker_task is not None:
        try:
            await asyncio.wait_for(_job_worker_task, timeout=10)
        except Exception:
            _job_worker_task.cancel()


@app.get("/health")
def health_check():
    """Liveness: process is up. Always 200 unless the process is dead."""
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/ready")
async def readiness_check():
    """Readiness: returns 503 if a critical dependency (DB) is unreachable so a
    load balancer stops routing traffic to a broken instance. Redis/Neo4j are
    reported but non-fatal (the app degrades rather than fails without them)."""
    from sqlalchemy import text

    from database import async_engine

    checks: dict = {}
    ready = True

    # Postgres is critical.
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:  # noqa: BLE001
        checks["database"] = f"down: {str(e)[:120]}"
        ready = False

    # Redis (cache) — degraded, not fatal.
    try:
        from services.redis_service import redis_client

        await redis_client.get("ready_ping")
        checks["redis"] = "ok"
    except Exception:  # noqa: BLE001
        checks["redis"] = "unavailable"

    # KT vector store (pgvector) — rides on the primary database; report the
    # extension presence. (Neo4j is fully retired — Phase 6.)
    try:
        from sqlalchemy import text as _text

        from database import AsyncSessionLocal as _ASL

        async with _ASL() as _s:
            _ext = await _s.execute(
                _text("SELECT 1 FROM pg_extension WHERE extname='vector'")
            )
            checks["pgvector"] = "ok" if _ext.first() else "missing"
    except Exception:  # noqa: BLE001
        checks["pgvector"] = "unavailable"

    body = {"status": "ready" if ready else "not_ready", "checks": checks}
    if not ready:
        return JSONResponse(body, status_code=503)
    return body


@app.get("/admin/system-health")
async def system_health(request: Request):
    """
    System Intelligence Panel endpoint — replaces hardcoded HTML in frontend.
    Returns real-time platform health metrics.
    """
    import datetime

    from database import engine
    from sqlalchemy import text

    health = {
        "api_status": "Operational",
        "version": settings.APP_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "components": {},
    }

    # DB connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health["components"]["database"] = {"status": "Operational", "latency_ms": None}
    except Exception as e:
        health["components"]["database"] = {"status": "Degraded", "error": str(e)}

    # Redis connectivity
    try:
        from services.redis_service import redis_client

        await redis_client.get("health_ping")
        health["components"]["redis"] = {"status": "Operational"}
    except Exception:
        health["components"]["redis"] = {"status": "Unavailable"}

    # AI service
    gemini_key = os.environ.get("GEMINI_API_KEY")
    health["components"]["ai_engine"] = {
        "status": "Operational" if gemini_key else "Degraded",
        "model": "gemini-2.5-flash",
        "key_configured": bool(gemini_key),
    }

    # Email service
    resend_key = os.environ.get("RESEND_EMAILS_API_KEY") or os.environ.get(
        "RESEND_API_KEY"
    )
    health["components"]["email"] = {
        "status": "Operational" if resend_key else "Degraded",
        "provider": "Resend",
        "key_configured": bool(resend_key),
    }

    # Automation workers status
    try:
        from database import SessionLocal

        db_s = SessionLocal()
        task_stats = db_s.query(models.SystemTaskStatus).all()
        health["tasks"] = {
            t.task_name: {
                "status": t.last_status,
                "last_run": t.last_run_at.isoformat() if t.last_run_at else None,
                "run_count": t.run_count,
                "error": t.last_error,
            }
            for t in task_stats
        }
        db_s.close()
    except Exception as e:
        health["tasks"] = {"error": str(e)}

    health["overall"] = (
        "Operational"
        if all(v.get("status") == "Operational" for v in health["components"].values())
        else "Degraded"
    )

    return health
