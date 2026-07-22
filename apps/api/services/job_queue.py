"""Durable background job queue backed by Postgres.

Why not FastAPI BackgroundTasks: those run in-process and vanish on restart. KT
document ingestion took ~30s of AI + graph work that way, so any deploy during
that window silently lost a member's contribution.

Why Postgres rather than RQ/Celery: the app already owns a Postgres connection and
deploys as a single long-running container. `FOR UPDATE SKIP LOCKED` gives correct
multi-consumer semantics with no extra broker, no extra process to deploy, and the
job record is written in the SAME database as the work it describes — so a job can
never be "queued" while the row it refers to rolled back.

Register a handler with @job_handler("name"), enqueue with enqueue(), and the
worker started in main.py drains the queue.
"""

import asyncio
import datetime
import logging
import os
import socket
import traceback
from typing import Any, Awaitable, Callable, Dict, Optional

from models.job import BackgroundJob, JobStatus
from sqlalchemy import select, text, update

logger = logging.getLogger(__name__)

# job_type -> coroutine handler
_HANDLERS: Dict[str, Callable[..., Awaitable[Any]]] = {}

POLL_INTERVAL_SECONDS = float(os.environ.get("JOB_POLL_INTERVAL", "5"))
BATCH_SIZE = int(os.environ.get("JOB_BATCH_SIZE", "5"))
# A claim older than this means the worker holding it died.
STALE_CLAIM_MINUTES = int(os.environ.get("JOB_STALE_CLAIM_MINUTES", "15"))
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"


def job_handler(job_type: str):
    """Register a coroutine as the handler for `job_type`."""

    def decorator(fn: Callable[..., Awaitable[Any]]):
        _HANDLERS[job_type] = fn
        return fn

    return decorator


def registered_handlers() -> Dict[str, Callable]:
    return dict(_HANDLERS)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _backoff_seconds(attempt: int) -> int:
    """Exponential backoff, capped. attempt=1 -> 10s, 2 -> 20s, 3 -> 40s ... max 10m."""
    return min(600, 10 * (2 ** max(0, attempt - 1)))


async def enqueue(
    db,
    job_type: str,
    payload: Optional[dict] = None,
    max_attempts: int = 5,
    delay_seconds: int = 0,
) -> BackgroundJob:
    """Persist a job. Call this INSIDE the same transaction as the work it describes.

    Deliberately does NOT commit: the caller commits, so a rolled-back request
    cannot leave an orphaned job pointing at a row that never existed.
    """
    if job_type not in _HANDLERS:
        # Fail loudly at enqueue time rather than silently never running.
        raise ValueError(
            f"No handler registered for job_type {job_type!r}. "
            f"Known: {sorted(_HANDLERS)}"
        )
    job = BackgroundJob(
        job_type=job_type,
        payload=payload or {},
        status=JobStatus.PENDING,
        max_attempts=max_attempts,
        run_after=_now() + datetime.timedelta(seconds=delay_seconds) if delay_seconds else _now(),
    )
    db.add(job)
    await db.flush()  # assign an id without ending the caller's transaction
    return job


async def recover_stale_jobs(session_factory) -> int:
    """Return jobs abandoned by a dead worker to the pending pool.

    Without this, a crash mid-job leaves the row stuck in `running` forever — the
    exact silent-loss failure this queue exists to prevent.
    """
    cutoff = _now() - datetime.timedelta(minutes=STALE_CLAIM_MINUTES)
    async with session_factory() as db:
        result = await db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.status == JobStatus.RUNNING,
                BackgroundJob.locked_at < cutoff,
            )
            .values(
                status=JobStatus.PENDING,
                locked_at=None,
                locked_by=None,
                run_after=_now(),
                updated_at=_now(),
            )
        )
        await db.commit()
        n = result.rowcount or 0
    if n:
        logger.warning(f"Job queue: recovered {n} stale job(s) from a dead worker")
    return n


async def _claim_batch(db, limit: int) -> list:
    """Atomically claim runnable jobs.

    SKIP LOCKED lets several workers/replicas drain the same queue without ever
    handing the same job to two of them.
    """
    rows = await db.execute(
        text(
            """
            SELECT id FROM background_jobs
            WHERE status = :pending
              AND (run_after IS NULL OR run_after <= :now)
            ORDER BY id
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"pending": JobStatus.PENDING, "now": _now(), "limit": limit},
    )
    ids = [r[0] for r in rows]
    if not ids:
        return []

    await db.execute(
        update(BackgroundJob)
        .where(BackgroundJob.id.in_(ids))
        .values(
            status=JobStatus.RUNNING,
            locked_at=_now(),
            locked_by=WORKER_ID,
            updated_at=_now(),
        )
    )
    claimed = (
        (await db.execute(select(BackgroundJob).where(BackgroundJob.id.in_(ids))))
        .scalars()
        .all()
    )
    await db.commit()
    return claimed


async def _finish(session_factory, job_id: int, error: Optional[str], max_attempts: int, attempts: int):
    async with session_factory() as db:
        if error is None:
            await db.execute(
                update(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .values(
                    status=JobStatus.SUCCEEDED,
                    completed_at=_now(),
                    updated_at=_now(),
                    locked_at=None,
                    locked_by=None,
                    last_error=None,
                )
            )
        elif attempts >= max_attempts:
            logger.error(f"Job {job_id} FAILED permanently after {attempts} attempts: {error}")
            await db.execute(
                update(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .values(
                    status=JobStatus.FAILED,
                    last_error=error[:4000],
                    completed_at=_now(),
                    updated_at=_now(),
                    locked_at=None,
                    locked_by=None,
                )
            )
        else:
            delay = _backoff_seconds(attempts)
            logger.warning(f"Job {job_id} attempt {attempts} failed; retrying in {delay}s: {error}")
            await db.execute(
                update(BackgroundJob)
                .where(BackgroundJob.id == job_id)
                .values(
                    status=JobStatus.PENDING,
                    last_error=error[:4000],
                    run_after=_now() + datetime.timedelta(seconds=delay),
                    updated_at=_now(),
                    locked_at=None,
                    locked_by=None,
                )
            )
        await db.commit()


async def run_once(session_factory, limit: int = BATCH_SIZE) -> int:
    """Claim and execute one batch. Returns how many jobs ran."""
    async with session_factory() as db:
        claimed = await _claim_batch(db, limit)

    for job in claimed:
        handler = _HANDLERS.get(job.job_type)
        attempts = (job.attempts or 0) + 1
        async with session_factory() as db:
            await db.execute(
                update(BackgroundJob)
                .where(BackgroundJob.id == job.id)
                .values(attempts=attempts, updated_at=_now())
            )
            await db.commit()

        if handler is None:
            await _finish(
                session_factory, job.id,
                f"No handler registered for job_type {job.job_type!r}",
                job.max_attempts, job.max_attempts,  # unrunnable -> terminal immediately
            )
            continue

        try:
            await handler(**(job.payload or {}))
            await _finish(session_factory, job.id, None, job.max_attempts, attempts)
        except Exception:
            await _finish(
                session_factory, job.id, traceback.format_exc(), job.max_attempts, attempts
            )

    return len(claimed)


async def worker_loop(session_factory, stop_event: Optional[asyncio.Event] = None):
    """Long-running drain loop. Started from the app lifespan."""
    logger.info(f"Job queue worker started ({WORKER_ID}); handlers={sorted(_HANDLERS)}")
    await recover_stale_jobs(session_factory)
    while not (stop_event and stop_event.is_set()):
        try:
            ran = await run_once(session_factory)
            # Only sleep when idle, so bursts drain promptly.
            if ran == 0:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # A worker must never die on a transient DB blip.
            logger.error(f"Job queue worker error: {e}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL_SECONDS)
    logger.info("Job queue worker stopped")
