"""Handlers for durable background jobs.

Importing this module registers every handler. `main.py` imports it at startup so
the registry is populated before any enqueue() call validates against it.

Payloads must be JSON-serialisable primitives — a job outlives the process that
created it, so it cannot capture ORM objects or sessions.
"""

import logging

from services.job_queue import job_handler

logger = logging.getLogger(__name__)

JOB_KT_INGEST = "kt.ingest_document"
JOB_EMAIL = "email.send"
JOB_KT_ENRICH = "kt.enrich_document"


@job_handler(JOB_KT_INGEST)
async def ingest_kt_document(document_id: str) -> None:
    """Run the KT ingestion pipeline for a document.

    Previously a FastAPI BackgroundTask: ~30s of AI + Neo4j work that a deploy
    would silently discard, leaving the document permanently un-ingested with no
    error surfaced to the contributor or the mentor who approved it.
    """
    from database import db_session_factory
    from modules.kt.services import ingestion_service

    logger.info(f"[job] KT ingestion starting for document {document_id}")
    await ingestion_service.run_pipeline(document_id, db_session_factory)
    logger.info(f"[job] KT ingestion finished for document {document_id}")


@job_handler(JOB_EMAIL)
async def send_email(method: str, args: list | None = None, kwargs: dict | None = None) -> None:
    """Send a transactional email via `email_service`, by method name.

    Dispatching by name keeps the payload JSON-serialisable. An unknown method
    raises, so the job retries and then lands in `failed` where it is visible —
    rather than disappearing the way an in-process task did.
    """
    from services import email_service as email_svc

    fn = getattr(email_svc, method, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Unknown email method {method!r}")

    result = fn(*(args or []), **(kwargs or {}))
    if hasattr(result, "__await__"):
        await result


@job_handler(JOB_KT_ENRICH)
async def enrich_kt_document(document_id: str, body_markdown: str, title: str) -> None:
    """AI auto-tagging + quality scoring for a newly created document.

    Ran as an in-process BackgroundTask, so a restart left the document
    permanently without tags or a quality score and nothing retried it.
    """
    from database import db_session_factory
    from models.kt_model import KTDocument
    from services.kt_workflows import KTIngestionService
    from sqlalchemy import update

    auto_tags = await KTIngestionService.auto_tag(body_markdown, title)

    async with db_session_factory() as s:
        doc = await s.get(KTDocument, document_id)
        if doc is None:
            return  # document deleted before enrichment ran; nothing to do
        quality, completeness = await KTIngestionService.compute_quality(doc)
        await s.execute(
            update(KTDocument)
            .where(KTDocument.id == document_id)
            .values(
                auto_tags=auto_tags,
                quality_score=quality,
                header_completeness=completeness,
            )
        )
        await s.commit()
