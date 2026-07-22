"""pgvector similarity search — drop-in replacement for neo4j.vector_search.

Returns the exact chunk shape the chat stack consumes
({episode_id, content, doc_id, score}), so kt_langraph's proven
rerank/citation/streaming logic works unchanged.

Access semantics replicated from Neo4jKTClient.vector_search:
- FAIL CLOSED: empty project_ids retrieves nothing, never everything.
- Scope: company_id + project_id IN grants.
- Sensitivity: doc sensitivity (default 'low') must be in allowed list.
- Optional reference_time date-range filter.
Additionally (new): only chunks of INGESTED, non-deprecated documents are
retrievable — business rule "docs are chat-retrievable only when indexed".
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import db_session_factory
from models.kt_model import DocStatusEnum, KTDocument
from modules.kt.models import KTDocumentChunk

logger = logging.getLogger("kt.retrieval")

# Mirrors kt_engine defaults: without an explicit grant, high-sensitivity
# content is not retrievable.
DEFAULT_SENSITIVITIES = ["low", "medium"]


async def vector_search(
    query_embedding: List[float],
    company_id: str,
    project_ids: List[str],
    top_k: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    allowed_sensitivities: List[str] | None = None,
    db: Optional[AsyncSession] = None,
) -> List[Dict]:
    if not project_ids or not query_embedding:
        return []

    sensitivities = allowed_sensitivities or DEFAULT_SENSITIVITIES

    # Cosine similarity in [0, 1]-ish (1 - distance), matching the ordering
    # semantics callers expect from the old Neo4j index score.
    distance = KTDocumentChunk.embedding.cosine_distance(query_embedding)

    stmt = (
        select(
            KTDocumentChunk.document_id,
            KTDocumentChunk.chunk_index,
            KTDocumentChunk.text,
            (1 - distance).label("score"),
        )
        .join(KTDocument, KTDocument.id == KTDocumentChunk.document_id)
        .where(
            KTDocument.company_id == company_id,
            KTDocumentChunk.project_id.in_(project_ids),
            func.coalesce(KTDocument.sensitivity, "low").in_(sensitivities),
            KTDocument.status == DocStatusEnum.INGESTED,
        )
        .order_by(distance)
        .limit(top_k)
    )
    if date_from:
        stmt = stmt.where(KTDocumentChunk.reference_time >= date_from)
    if date_to:
        stmt = stmt.where(KTDocumentChunk.reference_time <= date_to)

    async def _run(session: AsyncSession) -> List[Dict]:
        rows = (await session.execute(stmt)).fetchall()
        return [
            {
                "episode_id": f"{r.document_id}_ep_{r.chunk_index}",
                "content": r.text,
                "doc_id": r.document_id,
                "score": float(r.score),
            }
            for r in rows
        ]

    try:
        if db is not None:
            return await _run(db)
        async with db_session_factory() as session:
            return await _run(session)
    except Exception as e:  # noqa: BLE001 — degrade to refusal, never 500 chat
        logger.error("pgvector search failed: %s", e)
        return []
