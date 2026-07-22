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
    neo4j,
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


def _sprint_label(iso_date: str) -> str:
    """Bucket a reference date (YYYY-MM-DD) into a quarter 'sprint' label like 'Q1 2024'."""
    try:
        parts = iso_date.split("-")
        y, m = parts[0], parts[1]
        q = (int(m) - 1) // 3 + 1
        return f"Q{q} {y}"
    except Exception:
        return "Undated"


class KTIngestionService:
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

    @staticmethod
    def chunk_by_temporal_headers(text: str) -> List[Dict]:
        parts = re.split(
            r"(^###\s+\d{4}-\d{2}-\d{2}|^###\s+Q[1-4]\s+\d{4})",
            text,
            flags=re.MULTILINE,
        )
        current_time = datetime.datetime.now().isoformat()
        chunks = []

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

    @staticmethod
    async def run_pipeline(doc_id: str, db_or_factory):
        """Full ingestion flow: PG -> Gemini (Entities) -> Neo4j."""
        if hasattr(db_or_factory, "__call__") or "async_sessionmaker" in str(
            type(db_or_factory)
        ):
            async with db_or_factory() as db:
                await KTIngestionService._execute_pipeline(doc_id, db)
        else:
            await KTIngestionService._execute_pipeline(doc_id, db_or_factory)

    @staticmethod
    async def _execute_pipeline(doc_id: str, db: AsyncSession):
        logger.info(f"Starting KT Ingestion Pipeline for doc: {doc_id}")
        doc = await db.get(KTDocument, doc_id)
        if not doc:
            logger.error(f"KT Ingestion failed: Document {doc_id} not found.")
            return

        await db.execute(
            update(KTDocument)
            .where(KTDocument.id == doc_id)
            .values(ingestion_status=IngestionStatusEnum.CHUNKING)
        )
        await db.commit()

        raw_chunks = KTIngestionService.chunk_by_temporal_headers(doc.body_markdown)

        await db.execute(
            update(KTDocument)
            .where(KTDocument.id == doc_id)
            .values(ingestion_status=IngestionStatusEnum.EMBEDDING)
        )
        await db.commit()

        if not await neo4j.connect():
            logger.error("Neo4j not connected. Ingestion aborted.")
            await db.execute(
                update(KTDocument)
                .where(KTDocument.id == doc_id)
                .values(ingestion_status=IngestionStatusEnum.FAILED)
            )
            await db.commit()
            return

        try:
            assert neo4j.driver is not None
            # Ensure graph constraints + the Episode vector index exist (idempotent)
            await neo4j.setup_constraints()

            project = await db.get(KTProject, doc.project_id)
            project_name = project.name if project else "Unknown Project"
            company_id = str(doc.company_id)
            project_id = str(doc.project_id)

            async with neo4j.driver.session() as session:
                # Company <- Project <- Document backbone.
                # This is the exact path Neo4jKTClient.vector_search() traverses:
                # (Episode)-[:PART_OF]->(Document)-[:BELONGS_TO]->(Project)-[:OWNED_BY]->(Company)
                await session.run(
                    """
                    MERGE (c:Company {id: $company_id})
                    MERGE (p:Project {id: $project_id})
                        SET p.name = $project_name, p.company_id = $company_id
                    MERGE (p)-[:OWNED_BY]->(c)
                    MERGE (d:Document {id: $doc_id})
                        SET d.title = $title, d.company_id = $company_id,
                            d.project_id = $project_id, d.project_name = $project_name,
                            d.domain = $domain, d.doc_type = $doc_type,
                            d.access_level = $access_level, d.sensitivity = $sensitivity
                    MERGE (d)-[:BELONGS_TO]->(p)
                    """,
                    company_id=company_id,
                    project_id=project_id,
                    project_name=project_name,
                    doc_id=doc.id,
                    title=doc.title,
                    domain=doc.knowledge_domain,
                    doc_type=str(doc.doc_type) if doc.doc_type else None,
                    # Mirrored onto the graph so retrieval can enforce them. Without
                    # these properties the Cypher had nothing to filter on, which is
                    # why access_level/sensitivity were stored but never honoured.
                    access_level=str(doc.access_level) if doc.access_level else "project_only",
                    sensitivity=str(doc.sensitivity) if doc.sensitivity else "low",
                )

                episode_ids: List[str] = []
                for i, chunk in enumerate(raw_chunks):
                    text = chunk["content"]
                    emb = await gemini.embed(text)
                    if not emb:
                        continue

                    episode_id = f"{doc.id}_ep_{i}"
                    reference_time = chunk["time"]
                    sprint_label = _sprint_label(reference_time)
                    sprint_id = f"{project_id}::{sprint_label}"
                    episode_ids.append(episode_id)

                    # Episode carries the vector embedding indexed by kt_vector_index.
                    await session.run(
                        """
                        MATCH (d:Document {id: $doc_id})
                        MATCH (p:Project {id: $project_id})
                        MERGE (ep:Episode {id: $episode_id})
                            SET ep.content = $text, ep.embedding = $emb,
                                ep.reference_time = $reference_time,
                                ep.company_id = $company_id, ep.project_id = $project_id,
                                ep.doc_id = $doc_id
                        MERGE (ep)-[:PART_OF]->(d)
                        MERGE (s:Sprint {id: $sprint_id})
                            SET s.label = $sprint_label, s.project_id = $project_id,
                                s.company_id = $company_id
                        MERGE (s)-[:OF_PROJECT]->(p)
                        MERGE (ep)-[:IN_SPRINT]->(s)
                        """,
                        doc_id=doc.id,
                        project_id=project_id,
                        episode_id=episode_id,
                        text=text,
                        emb=emb,
                        reference_time=reference_time,
                        company_id=company_id,
                        sprint_id=sprint_id,
                        sprint_label=sprint_label,
                    )

                    prompt = f"Extract key technical entities (technologies, architectures, concepts) from this text.\nText: {text[:2000]}\nReturn JSON list of dicts: [{{'name': 'Docker', 'type': 'Technology'}}]"
                    try:
                        entities = await gemini.generate_json(prompt)
                        if isinstance(entities, list):
                            for ent in entities:
                                name = ent.get("name", "").strip().upper()
                                etype = ent.get("type", "Concept").strip()
                                if len(name) > 2:
                                    # :Entity + [:MENTIONS] — the schema graph_hop() expands over.
                                    await session.run(
                                        """
                                        MATCH (ep:Episode {id: $episode_id})
                                        MERGE (e:Entity {name: $name})
                                            ON CREATE SET e.type = $etype, e.company_id = $company_id
                                        MERGE (ep)-[:MENTIONS]->(e)
                                        """,
                                        episode_id=episode_id,
                                        name=name,
                                        etype=etype,
                                        company_id=company_id,
                                    )
                    except Exception as e:
                        logger.warning(
                            f"Entity extraction failed for episode {episode_id}: {e}"
                        )

                # Record episode ids on the PG document so re-ingestion can purge them.
                await db.execute(
                    update(KTDocument)
                    .where(KTDocument.id == doc_id)
                    .values(neo4j_episode_ids=episode_ids)
                )

            await db.execute(
                update(KTDocument)
                .where(KTDocument.id == doc_id)
                .values(
                    ingestion_status=IngestionStatusEnum.COMPLETE,
                    status=DocStatusEnum.INGESTED,
                    ingested_at=datetime.datetime.now(datetime.timezone.utc),
                    chunk_count=len(episode_ids),
                )
            )
            await db.commit()
            logger.info(f"KT Ingestion completed for doc: {doc_id}")

        except Exception as e:
            logger.error(f"KT Ingestion error: {e}")
            await db.execute(
                update(KTDocument)
                .where(KTDocument.id == doc_id)
                .values(ingestion_status=IngestionStatusEnum.FAILED)
            )
            await db.commit()


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

    # Calibrated from passage strength + independent-document corroboration +
    # whether the answer actually cited its sources (see compute_confidence).
    confidence = compute_confidence(chunks, answer=answer, citations=sources)

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
