"""KT ingestion pipeline on Postgres/pgvector — replaces the Neo4j pipeline.

Flow (mirrors the doc-status contract of the old services/kt_workflows.py so
every existing endpoint/UI keeps working):

    approved doc --feed--> JOB_KT_INGEST (durable queue)
        → status CHUNKING   (chunk body_markdown by temporal headers)
        → status EMBEDDING  (Gemini gemini-embedding-001, 3072 dims, metered)
        → rows in kt_document_chunks (pgvector)
        → status COMPLETE + doc.status INGESTED + chunk_count + ingested_at
      on any error → status FAILED + ingestion_error (NEVER silent — the
      silent-failure mode is what killed KT v1)

Re-ingestion: existing chunks for the document are deleted in the same
transaction before the new rows land.
"""

import datetime
import logging
import re
from typing import Dict, List

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.kt_model import DocStatusEnum, IngestionStatusEnum, KTDocument
from modules.kt.models import KTDocumentChunk

logger = logging.getLogger("kt.ingestion")


def chunk_by_temporal_headers(text: str) -> List[Dict]:
    """Split markdown on '### YYYY-MM-DD' / '### Q1 2024' headers.

    Same proven logic as the legacy pipeline (kt_workflows), kept verbatim so
    chunking behavior — and therefore retrieval quality — is unchanged.
    Returns [{"content": str, "time": "YYYY-MM-DD"}].
    """
    parts = re.split(
        r"(^###\s+\d{4}-\d{2}-\d{2}|^###\s+Q[1-4]\s+\d{4})",
        text,
        flags=re.MULTILINE,
    )
    current_time = datetime.datetime.now().isoformat()
    chunks: List[Dict] = []

    if len(parts) <= 1:
        return [{"content": text, "time": current_time[:10]}]

    if parts[0].strip():
        chunks.append({"content": parts[0].strip(), "time": current_time[:10]})

    for i in range(1, len(parts), 2):
        header = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""

        t_match = re.search(r"(\d{4}-\d{2}-\d{2})", header)
        if t_match:
            t = t_match.group(1)
        else:
            q_match = re.search(r"Q([1-4])\s+(\d{4})", header)
            if q_match:
                q, y = q_match.groups()
                m = (int(q) - 1) * 3 + 1
                t = f"{y}-{m:02d}-01"
            else:
                t = current_time[:10]

        if content:
            chunks.append({"content": f"{header}\n{content}", "time": t})
    return chunks


def _doc_context_preamble(doc: KTDocument) -> str:
    """Structured KT fields prepended to the first chunk's context.

    The legacy graph pipeline threw this knowledge away; problem statement,
    decisions, outcome and lessons are exactly what successors ask about,
    so they must be retrievable.
    """
    parts: List[str] = []
    if doc.problem_statement:
        parts.append(f"Problem statement: {doc.problem_statement}")
    if doc.decisions_made:
        parts.append(f"Decisions made: {doc.decisions_made}")
    if doc.outcome:
        parts.append(f"Outcome: {doc.outcome}")
    if doc.conclusion:
        parts.append(f"Conclusion: {doc.conclusion}")
    if doc.lessons_learned:
        parts.append(f"Lessons learned: {'; '.join(doc.lessons_learned)}")
    if doc.open_questions:
        parts.append(f"Open questions: {'; '.join(doc.open_questions)}")
    return "\n".join(parts)


async def purge_chunks(db: AsyncSession, doc_id: str) -> None:
    """Remove a document's chunks from the vector store (deprecate/delete/
    re-ingest). Caller owns the commit."""
    await db.execute(
        delete(KTDocumentChunk).where(KTDocumentChunk.document_id == doc_id)
    )


async def _set_ingestion_state(db: AsyncSession, doc_id: str, **values) -> None:
    await db.execute(
        update(KTDocument).where(KTDocument.id == doc_id).values(**values)
    )
    await db.commit()


async def run_pipeline(doc_id: str, db_or_factory) -> None:
    """Entry point — same signature as the legacy KTIngestionService.run_pipeline
    so services/job_handlers.py swaps with a one-line import change."""
    if callable(db_or_factory) and not isinstance(db_or_factory, AsyncSession):
        async with db_or_factory() as db:
            await _execute(doc_id, db)
    else:
        await _execute(doc_id, db_or_factory)


async def _execute(doc_id: str, db: AsyncSession) -> None:
    # Local import: kt_engine owns the metered Gemini client (embed()); the
    # rest of that module (Neo4j client) is untouched and dies in Phase 6.
    from services.kt_engine import gemini

    logger.info("pgvector ingestion starting for doc %s", doc_id)
    doc = await db.get(KTDocument, doc_id)
    if not doc:
        logger.error("ingestion failed: document %s not found", doc_id)
        return

    try:
        await _set_ingestion_state(
            db, doc_id,
            ingestion_status=IngestionStatusEnum.CHUNKING, ingestion_error=None,
        )

        raw_chunks = chunk_by_temporal_headers(doc.body_markdown or "")
        preamble = _doc_context_preamble(doc)
        if preamble:
            raw_chunks.insert(
                0,
                {
                    "content": f"Document overview — {doc.title}\n{preamble}",
                    "time": (doc.date_range_start or doc.created_at
                             or datetime.datetime.now()).strftime("%Y-%m-%d"),
                },
            )
        raw_chunks = [c for c in raw_chunks if c["content"].strip()]
        if not raw_chunks:
            raise ValueError("document has no ingestible content (empty body)")

        await _set_ingestion_state(
            db, doc_id, ingestion_status=IngestionStatusEnum.EMBEDDING
        )

        rows: List[KTDocumentChunk] = []
        failed_embeds = 0
        for i, chunk in enumerate(raw_chunks):
            emb = await gemini.embed(chunk["content"])
            if not emb:
                failed_embeds += 1
                continue
            rows.append(
                KTDocumentChunk(
                    document_id=doc.id,
                    project_id=str(doc.project_id),
                    organization_id=doc.organization_id,
                    chunk_index=i,
                    title=doc.title,
                    text=chunk["content"],
                    reference_time=chunk["time"],
                    embedding=emb,
                    tokens=max(1, len(chunk["content"]) // 4),
                )
            )

        if not rows:
            raise RuntimeError(
                f"embedding failed for all {len(raw_chunks)} chunks "
                "(Gemini unavailable or returning empty vectors)"
            )

        # Re-ingestion: replace previous chunks atomically with the insert.
        await db.execute(
            delete(KTDocumentChunk).where(KTDocumentChunk.document_id == doc.id)
        )
        db.add_all(rows)
        await db.execute(
            update(KTDocument)
            .where(KTDocument.id == doc_id)
            .values(
                ingestion_status=IngestionStatusEnum.COMPLETE,
                status=DocStatusEnum.INGESTED,
                ingested_at=datetime.datetime.now(datetime.timezone.utc),
                chunk_count=len(rows),
                ingestion_error=(
                    f"{failed_embeds} of {len(raw_chunks)} chunks failed to embed"
                    if failed_embeds else None
                ),
            )
        )
        await db.commit()
        logger.info(
            "pgvector ingestion complete for doc %s: %d chunks (%d embed failures)",
            doc_id, len(rows), failed_embeds,
        )

    except Exception as e:  # noqa: BLE001 — always record, never silent
        logger.error("pgvector ingestion FAILED for doc %s: %s", doc_id, e)
        await db.rollback()
        await _set_ingestion_state(
            db, doc_id,
            ingestion_status=IngestionStatusEnum.FAILED,
            ingestion_error=str(e)[:2000],
        )
        raise
