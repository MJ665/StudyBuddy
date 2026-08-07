"""GraphRAG entity/relationship extraction (Phase 6, Postgres).

At KT ingest, an LLM (OpenRouter free model via kt_engine.generate_json, which
falls back to Gemini) reads an approved document and emits the entities and the
relationships between them. These become rows in ``kt_graph_nodes`` /
``kt_graph_edges`` scoped by company/project, so retrieval can traverse the
graph and the explorer can render a real knowledge graph — not just tags.

Extraction is BEST-EFFORT: any failure is logged and swallowed by the caller so
the vector pipeline (the retrieval floor) is never blocked. Re-ingest replaces a
document's nodes/edges atomically.
"""

import logging
import re
from typing import Dict, List, Tuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from models.kt_model import KTDocument
from modules.kt.models import KTGraphEdge, KTGraphNode

logger = logging.getLogger("kt.graph_extraction")

MAX_ENTITIES = 40
MAX_RELATIONSHIPS = 60
MAX_INPUT_CHARS = 6000

_SYSTEM = (
    "You are a precise knowledge-graph extractor. From the given engineering / "
    "handover document, extract the key entities (people, systems, services, "
    "technologies, concepts, decisions, teams) and the directed relationships "
    "between them. Use short canonical names (e.g. 'PostgreSQL', not 'the "
    "Postgres database we use'). Only extract what the text supports."
)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip()).lower()


def _clean(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())[:255]


def _doc_text(doc: KTDocument) -> str:
    parts: List[str] = [f"Title: {doc.title or ''}"]
    if doc.problem_statement:
        parts.append(f"Problem: {doc.problem_statement}")
    if doc.decisions_made:
        parts.append(f"Decisions: {doc.decisions_made}")
    if doc.outcome:
        parts.append(f"Outcome: {doc.outcome}")
    if doc.conclusion:
        parts.append(f"Conclusion: {doc.conclusion}")
    if doc.lessons_learned:
        parts.append("Lessons: " + "; ".join(doc.lessons_learned))
    if doc.body_markdown:
        parts.append(doc.body_markdown)
    return "\n".join(parts)[:MAX_INPUT_CHARS]


def _build_prompt(text: str) -> str:
    return (
        "Extract entities and relationships from the document below.\n"
        'Return ONLY JSON of this exact shape:\n'
        '{"entities":[{"name":"...","type":"PERSON|SYSTEM|SERVICE|TECHNOLOGY|'
        'CONCEPT|DECISION|TEAM|OTHER"}],'
        '"relationships":[{"source":"...","relation":"short verb phrase",'
        '"target":"..."}]}\n'
        f"Extract at most {MAX_ENTITIES} entities and {MAX_RELATIONSHIPS} "
        "relationships. Source and target of every relationship MUST be an "
        "entity name you listed.\n\n"
        f"--- DOCUMENT ---\n{text}"
    )


def _parse(raw) -> Tuple[Dict[str, Tuple[str, str]], List[Dict[str, str]]]:
    """Return ({norm_name: (display_name, type)}, [relationships])."""
    entities: Dict[str, Tuple[str, str]] = {}
    rels: List[Dict[str, str]] = []
    if not isinstance(raw, dict):
        return {}, []

    for e in (raw.get("entities") or [])[:MAX_ENTITIES]:
        if not isinstance(e, dict):
            continue
        name = _clean(e.get("name", ""))
        if not name:
            continue
        etype = (_clean(e.get("type", "")) or "CONCEPT").upper()[:50]
        entities[_norm(name)] = (name, etype)

    for r in (raw.get("relationships") or [])[:MAX_RELATIONSHIPS]:
        if not isinstance(r, dict):
            continue
        s, t = _clean(r.get("source", "")), _clean(r.get("target", ""))
        rel = _clean(r.get("relation", "")) or "related to"
        if not s or not t or _norm(s) == _norm(t):
            continue
        # Ensure endpoints exist as nodes even if the model forgot to list them.
        entities.setdefault(_norm(s), (s, "CONCEPT"))
        entities.setdefault(_norm(t), (t, "CONCEPT"))
        rels.append({"source": s, "target": t, "relation": rel[:120]})

    return entities, rels


async def extract_and_store(db: AsyncSession, doc: KTDocument) -> Dict[str, int]:
    """Extract → persist nodes/edges for ``doc``. Replaces prior graph rows for
    the document. Caller owns nothing — this commits its own transaction and
    never raises (returns zero counts on failure)."""
    from services.kt_engine import gemini

    try:
        text = _doc_text(doc)
        if not text.strip():
            return {"nodes": 0, "edges": 0}

        raw = await gemini.generate_json(_build_prompt(text), system=_SYSTEM)
        entities, rels = _parse(raw)
        if not entities:
            # Nothing extracted — still clear stale rows so the graph is honest.
            await _replace(db, doc, [], [])
            return {"nodes": 0, "edges": 0}

        node_rows = [
            KTGraphNode(
                document_id=doc.id,
                project_id=str(doc.project_id),
                company_id=doc.company_id,
                organization_id=doc.organization_id,
                name=name,
                norm_name=norm,
                node_type=etype,
            )
            for norm, (name, etype) in entities.items()
        ]
        edge_rows = [
            KTGraphEdge(
                document_id=doc.id,
                project_id=str(doc.project_id),
                company_id=doc.company_id,
                organization_id=doc.organization_id,
                source_name=r["source"],
                target_name=r["target"],
                norm_source=_norm(r["source"]),
                norm_target=_norm(r["target"]),
                relation=r["relation"],
            )
            for r in rels
        ]
        await _replace(db, doc, node_rows, edge_rows)
        logger.info(
            "graph extraction for doc %s: %d nodes, %d edges",
            doc.id, len(node_rows), len(edge_rows),
        )
        return {"nodes": len(node_rows), "edges": len(edge_rows)}
    except Exception as e:  # noqa: BLE001 — best-effort, never block ingest
        logger.warning("graph extraction failed for doc %s: %s", doc.id, e)
        try:
            await db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {"nodes": 0, "edges": 0}


async def _replace(
    db: AsyncSession, doc: KTDocument, nodes: List[KTGraphNode], edges: List[KTGraphEdge]
) -> None:
    await db.execute(delete(KTGraphEdge).where(KTGraphEdge.document_id == doc.id))
    await db.execute(delete(KTGraphNode).where(KTGraphNode.document_id == doc.id))
    if nodes:
        db.add_all(nodes)
    if edges:
        db.add_all(edges)
    await db.commit()
