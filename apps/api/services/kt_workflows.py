import datetime
import logging
import re
import time
from typing import Dict, List, Tuple

from models.kt_model import DocStatusEnum, IngestionStatusEnum, KTDocument, KTProject
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .kt_engine import (
    build_rag_prompt,
    compute_confidence,
    gemini,
    rerank_llm,
    RAG_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)


_REFUSAL_MARKERS = (
    "i don't have enough knowledge",
    "i do not have enough knowledge",
    "i don't have enough information",
    "i do not have enough information",
    "cannot answer",
    "no relevant information",
)


def _is_refusal(answer: str | None) -> bool:
    """True when the model declined to answer for lack of grounding.

    Used to decide whether a query counts as answered for knowledge-gap tracking.
    """
    if not answer:
        return True
    low = answer.strip().lower()
    return any(marker in low for marker in _REFUSAL_MARKERS)


async def llm_groundedness(chunks: list, answer: str) -> float:
    """LLM-judged groundedness in [0,1]: how fully `answer` is supported by the
    retrieved `chunks`. This is the second signal in the owner's "Both"
    confidence (retrieval composite + LLM check). One cheap Gemini call; metered."""
    if not chunks or not answer or _is_refusal(answer):
        return 0.0
    ctx = "\n\n".join(
        f"[{i + 1}] {(c.get('content') or '')[:600]}" for i, c in enumerate(chunks[:6])
    )
    prompt = (
        f"SOURCES:\n{ctx}\n\nANSWER:\n{answer}\n\n"
        "Rate from 0.0 to 1.0 how fully the ANSWER is supported by the SOURCES "
        "(1.0 = every claim is directly supported; 0.0 = unsupported/contradicted). "
        "Reply with ONLY the number."
    )
    try:
        raw = await gemini.generate(
            prompt,
            system="You are a strict grounding evaluator. Output only a number between 0.0 and 1.0.",
        )
        m = re.search(r"[01](?:\.\d+)?", raw or "")
        return max(0.0, min(1.0, float(m.group(0)))) if m else 0.5
    except Exception:
        return 0.5


class KTIngestionService:
    # NOTE (Phase 6): the Neo4j ingestion pipeline (run_pipeline /
    # _execute_pipeline / chunk_by_temporal_headers) was removed — ingestion
    # lives in modules/kt/services/ingestion_service.py on pgvector. Only the
    # AI enrichment helpers below remain in use (job_handlers, documents.py).
    @staticmethod
    async def auto_tag(content: str, title: str) -> List[str]:
        prompt = f"Generate 5-8 relevant technical tags for this KT document.\nTitle: {title}\nContent: {content[:2000]}\nReturn JSON list of strings."
        try:
            tags = await gemini.generate_json(
                prompt, system="You are a tagging engine. Return ONLY JSON list."
            )
            return tags if isinstance(tags, list) else []
        except Exception:
            return []

    @staticmethod
    async def compute_quality(doc: KTDocument) -> Tuple[float, float]:
        """Returns (quality_score, header_completeness)."""
        fields = [
            doc.title,
            doc.doc_type,
            doc.knowledge_domain,
            doc.problem_statement,
            doc.outcome,
        ]
        filled = len([f for f in fields if f])
        completeness = (filled / len(fields)) * 100

        prompt = f"Evaluate the quality of this KT document (0-100).\nTitle: {doc.title}\nContent: {doc.body_markdown[:3000]}\nReturn JSON: {{'score': 85}}"
        try:
            res = await gemini.generate_json(
                prompt, system="You are a document auditor."
            )
            quality = float(res.get("score", 70))
        except Exception:
            quality = 70.0

        return quality, completeness
async def run_rag_query(
    query: str,
    company_id: str,
    project_ids: List[str],
    history: List[Dict],
    db: AsyncSession,
    allowed_sensitivities: List[str] | None = None,
) -> Dict:
    start = time.time()

    query_emb = await gemini.embed_query(query)

    # pgvector (Phase 2) — replaced neo4j.vector_search; same chunk contract.
    from modules.kt.services.retrieval import vector_search as pg_vector_search

    raw_chunks = await pg_vector_search(
        query_embedding=query_emb,
        company_id=company_id,
        project_ids=project_ids,
        top_k=20,
        allowed_sensitivities=allowed_sensitivities,
        db=db,
    )

    if not raw_chunks:
        return {
            "answer": "I don't have enough project context to answer this query.",
            "sources": [],
            "confidence": 0.0,
            "was_answered": False,
            "latency_ms": int((time.time() - start) * 1000),
        }

    chunks = await rerank_llm(query, raw_chunks, top_n=8)

    doc_ids = list({c["doc_id"] for c in chunks if c.get("doc_id")})
    rows = await db.execute(
        select(
            KTDocument.id,
            KTDocument.title,
            KTDocument.doc_type,
            KTProject.name.label("project_name"),
        )
        .join(KTProject, KTDocument.project_id == KTProject.id)
        .where(KTDocument.id.in_(doc_ids), KTDocument.company_id == company_id)
    )
    doc_map = {
        r.id: {
            "title": r.title,
            "doc_type": str(r.doc_type),
            "project_name": r.project_name,
        }
        for r in rows.fetchall()
    }

    sources = []
    for i, chunk in enumerate(chunks, 1):
        doc = doc_map.get(chunk.get("doc_id", ""), {})
        excerpt = chunk["content"][:200]
        sources.append(
            {
                "id": f"source_{i}",
                "title": doc.get("title", "Unknown Doc"),
                "doc_type": doc.get("doc_type", "UNKNOWN"),
                "project_name": doc.get("project_name", "Unknown Project"),
                "doc_id": chunk.get("doc_id"),
                "relevance": float(chunk.get("score", 0.0)),
                "excerpt": excerpt + "...",
            }
        )

    context = "\n\n".join(
        [
            f"Source [{i + 1}] ({s['title']}):\n{c['content']}"
            for i, (s, c) in enumerate(zip(sources, chunks))
        ]
    )

    prompt = build_rag_prompt(query, context, history)

    answer = await gemini.generate(prompt, system=RAG_SYSTEM_PROMPT)

    # "Both" confidence: blend the retrieval composite (passage strength +
    # corroboration + citation grounding) with an LLM groundedness judgement.
    retrieval_conf = compute_confidence(chunks, answer=answer, citations=sources)
    grounded = await llm_groundedness(chunks, answer)
    confidence = 0.6 * retrieval_conf + 0.4 * (grounded * 100.0)

    # `was_answered` drives knowledge-gap tracking in routers/kt.py. It was never
    # returned here, so `rag.get("was_answered")` was always None and no gap was
    # ever recorded. An answer only counts if we actually had sources to ground it.
    return {
        "answer": answer,
        "sources": sources,
        "confidence": round(confidence, 1),
        "was_answered": bool(chunks) and not _is_refusal(answer),
        "latency_ms": int((time.time() - start) * 1000),
    }
