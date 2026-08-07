"""GraphRAG retrieval blend (Phase 6).

Given a query and the documents surfaced by pgvector, resolve seed entities,
traverse the Postgres knowledge graph (kt_graph_edges) N hops, and assemble the
connected relationships into a single grounded "graph context" block. That block
is returned in the same chunk shape the chat stack consumes, so it flows through
the existing rerank/citation/streaming logic unchanged — vector similarity and
graph structure are blended, not replaced.

Fail-closed and best-effort: empty project scope → nothing; any error → None
(chat degrades to pure vector RAG, never 500s).
"""

import logging
import re
from typing import Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import db_session_factory
from modules.kt.models import KTGraphEdge, KTGraphNode

logger = logging.getLogger("kt.graph_rag")

MAX_HOPS = 2
MAX_TRIPLES = 25
_STOP = {
    "the", "and", "for", "what", "how", "why", "who", "when", "where", "which",
    "did", "was", "were", "does", "with", "from", "this", "that", "our", "your",
    "about", "into", "have", "has", "are", "can", "you", "tell", "explain",
}


def _tokens(query: str) -> List[str]:
    return [
        w for w in re.findall(r"[a-zA-Z0-9]+", (query or "").lower())
        if len(w) >= 3 and w not in _STOP
    ]


async def graph_context(
    query: str,
    company_id: str,
    project_ids: List[str],
    seed_doc_ids: Optional[List[str]] = None,
    db: Optional[AsyncSession] = None,
) -> Optional[Dict]:
    if not project_ids:
        return None

    async def _run(session: AsyncSession) -> Optional[Dict]:
        # 1. Seed entities: query-term matches within scope, plus every entity
        #    from the documents pgvector already surfaced.
        toks = _tokens(query)
        node_filters = []
        for t in toks:
            node_filters.append(KTGraphNode.norm_name.ilike(f"%{t}%"))
        seed_norms: set = set()

        base_scope = [
            KTGraphNode.company_id == company_id,
            KTGraphNode.project_id.in_(project_ids),
        ]
        if node_filters:
            rows = (
                await session.execute(
                    select(KTGraphNode.norm_name).where(*base_scope, or_(*node_filters)).limit(40)
                )
            ).all()
            seed_norms.update(r.norm_name for r in rows)

        if seed_doc_ids:
            rows = (
                await session.execute(
                    select(KTGraphNode.norm_name).where(
                        KTGraphNode.project_id.in_(project_ids),
                        KTGraphNode.document_id.in_(seed_doc_ids),
                    ).limit(60)
                )
            ).all()
            seed_norms.update(r.norm_name for r in rows)

        if not seed_norms:
            return None

        # 2. Traverse edges up to MAX_HOPS within scope.
        edge_scope = [
            KTGraphEdge.company_id == company_id,
            KTGraphEdge.project_id.in_(project_ids),
        ]
        frontier = set(seed_norms)
        visited = set(seed_norms)
        triples: List[tuple] = []
        seen_triples: set = set()
        doc_ids: set = set()

        for _hop in range(MAX_HOPS):
            if not frontier or len(triples) >= MAX_TRIPLES:
                break
            rows = (
                await session.execute(
                    select(
                        KTGraphEdge.source_name,
                        KTGraphEdge.target_name,
                        KTGraphEdge.norm_source,
                        KTGraphEdge.norm_target,
                        KTGraphEdge.relation,
                        KTGraphEdge.document_id,
                    ).where(
                        *edge_scope,
                        or_(
                            KTGraphEdge.norm_source.in_(frontier),
                            KTGraphEdge.norm_target.in_(frontier),
                        ),
                    ).limit(200)
                )
            ).all()

            next_frontier: set = set()
            for r in rows:
                key = (r.norm_source, r.relation.lower(), r.norm_target)
                if key not in seen_triples:
                    seen_triples.add(key)
                    triples.append((r.source_name, r.relation, r.target_name))
                    if r.document_id:
                        doc_ids.add(r.document_id)
                for nn in (r.norm_source, r.norm_target):
                    if nn not in visited:
                        visited.add(nn)
                        next_frontier.add(nn)
                if len(triples) >= MAX_TRIPLES:
                    break
            frontier = next_frontier

        if not triples:
            return None

        lines = [f"- {s} —{rel}→ {t}" for s, rel, t in triples[:MAX_TRIPLES]]
        content = (
            "Knowledge-graph relationships relevant to the question "
            "(extracted from approved documents):\n" + "\n".join(lines)
        )
        return {
            "episode_id": "graph_context",
            "content": content,
            "doc_id": next(iter(doc_ids)) if doc_ids else "",
            "score": 0.95,
            "is_graph": True,
        }

    try:
        if db is not None:
            return await _run(db)
        async with db_session_factory() as session:
            return await _run(session)
    except Exception as e:  # noqa: BLE001 — degrade to pure vector RAG
        logger.warning("graph_context failed: %s", e)
        return None
