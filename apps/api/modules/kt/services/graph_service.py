"""Relational knowledge-graph views (Phase 6) — replaces the last Neo4j reads.

The explorer/timeline UI consumes {nodes, edges} / timeline rows that the old
Neo4jKTClient produced from the (empty, unreachable) graph. The same shapes
are now COMPUTED from Postgres:

    project  ← kt_projects
    document ← kt_documents            (edge document -BELONGS_TO-> project)
    episode  ← kt_document_chunks      (edge episode -PART_OF-> document)
    entity   ← document tags/auto_tags (edge document -MENTIONS-> entity)

Episode ids use the retrieval convention "{doc_id}_ep_{chunk_index}".
"""

from typing import Dict, List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.kt_model import DocStatusEnum, KTDocument, KTProject
from modules.kt.models import KTDocumentChunk, KTGraphEdge, KTGraphNode

VISIBLE_STATUSES = (DocStatusEnum.APPROVED, DocStatusEnum.INGESTED)


def _doc_tags(doc: KTDocument) -> List[str]:
    tags = list(doc.tags or []) + list(doc.auto_tags or [])
    return sorted({t.strip() for t in tags if t and t.strip()})


async def get_timeline(
    db: AsyncSession, company_id: str, project_ids: List[str]
) -> List[Dict]:
    """[{id, content, time, doc_title}] — newest first, capped at 50."""
    if not project_ids:
        return []
    rows = await db.execute(
        select(
            KTDocumentChunk.document_id,
            KTDocumentChunk.chunk_index,
            KTDocumentChunk.text,
            KTDocumentChunk.reference_time,
            KTDocument.title,
        )
        .join(KTDocument, KTDocument.id == KTDocumentChunk.document_id)
        .where(
            KTDocument.company_id == company_id,
            KTDocumentChunk.project_id.in_(project_ids),
        )
        .order_by(KTDocumentChunk.reference_time.desc().nullslast())
        .limit(50)
    )
    return [
        {
            "id": f"{r.document_id}_ep_{r.chunk_index}",
            "content": r.text,
            "time": r.reference_time,
            "doc_title": r.title,
        }
        for r in rows.fetchall()
    ]


async def get_graph_explorer_data(
    db: AsyncSession, company_id: str, project_ids: List[str]
) -> Dict[str, List]:
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen: set = set()
    if not project_ids:
        return {"nodes": nodes, "edges": edges}

    projects = (
        (
            await db.execute(
                select(KTProject).where(
                    KTProject.company_id == company_id,
                    KTProject.id.in_(project_ids),
                )
            )
        )
        .scalars()
        .all()
    )
    for p in projects:
        if p.id not in seen:
            nodes.append({"id": p.id, "label": p.name or "Project", "type": "project"})
            seen.add(p.id)

    docs = (
        (
            await db.execute(
                select(KTDocument).where(
                    KTDocument.company_id == company_id,
                    KTDocument.project_id.in_(project_ids),
                    KTDocument.status.in_(VISIBLE_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    doc_ids = [d.id for d in docs]
    for d in docs:
        if d.id not in seen:
            nodes.append({"id": d.id, "label": d.title or "Document", "type": "document"})
            seen.add(d.id)
            edges.append({"source": d.id, "target": d.project_id, "type": "BELONGS_TO"})

    # Real knowledge graph (GraphRAG, Phase 6): entities + relationships
    # extracted at ingest. Documents with an extracted graph use it; documents
    # without one fall back to their tags so nothing regresses.
    docs_with_graph: set = set()
    if doc_ids:
        gnodes = (
            (
                await db.execute(
                    select(KTGraphNode).where(KTGraphNode.document_id.in_(doc_ids))
                )
            )
            .scalars()
            .all()
        )
        gedges = (
            (
                await db.execute(
                    select(KTGraphEdge).where(KTGraphEdge.document_id.in_(doc_ids))
                )
            )
            .scalars()
            .all()
        )
        # One entity node per distinct norm_name (cross-document grouping).
        entity_label: Dict[str, str] = {}
        entity_type: Dict[str, str] = {}
        for n in gnodes:
            docs_with_graph.add(n.document_id)
            entity_label.setdefault(n.norm_name, n.name)
            entity_type.setdefault(n.norm_name, (n.node_type or "entity").lower())
        for e in gedges:
            docs_with_graph.add(e.document_id)
            entity_label.setdefault(e.norm_source, e.source_name)
            entity_label.setdefault(e.norm_target, e.target_name)

        def _ent_id(norm: str) -> str:
            return f"entity:{norm}"

        for norm, label in entity_label.items():
            eid = _ent_id(norm)
            if eid not in seen:
                nodes.append({"id": eid, "label": label, "type": entity_type.get(norm, "entity")})
                seen.add(eid)
        # document -MENTIONS-> entity, and entity -relation-> entity
        mention_seen: set = set()
        for n in gnodes:
            key = (n.document_id, n.norm_name)
            if key not in mention_seen:
                mention_seen.add(key)
                edges.append({"source": n.document_id, "target": _ent_id(n.norm_name), "type": "MENTIONS"})
        for e in gedges:
            edges.append(
                {"source": _ent_id(e.norm_source), "target": _ent_id(e.norm_target), "type": e.relation}
            )

    # Tag fallback for documents that have no extracted graph yet.
    for d in docs:
        if d.id in docs_with_graph:
            continue
        for tag in _doc_tags(d):
            if tag not in seen:
                nodes.append({"id": tag, "label": tag, "type": "entity"})
                seen.add(tag)
            edges.append({"source": d.id, "target": tag, "type": "MENTIONS"})

    if doc_ids:
        chunks = await db.execute(
            select(
                KTDocumentChunk.document_id,
                KTDocumentChunk.chunk_index,
                KTDocumentChunk.reference_time,
            ).where(KTDocumentChunk.document_id.in_(doc_ids))
        )
        for r in chunks.fetchall():
            eid = f"{r.document_id}_ep_{r.chunk_index}"
            if eid not in seen:
                nodes.append(
                    {
                        "id": eid,
                        "label": "Knowledge Item",
                        "type": "episode",
                        "metadata": {"time": r.reference_time or ""},
                    }
                )
                seen.add(eid)
                edges.append({"source": eid, "target": r.document_id, "type": "PART_OF"})

    return {"nodes": nodes, "edges": edges}


async def get_graph_neighborhood(db: AsyncSession, node_id: str) -> Dict[str, List]:
    """1-hop neighborhood for a project / document / episode / entity node."""
    nodes: List[Dict] = []
    edges: List[Dict] = []
    seen: set = set()

    def add_node(nid: str, label: str, ntype: str):
        if nid not in seen:
            nodes.append({"id": nid, "label": label, "type": ntype})
            seen.add(nid)

    def add_edge(s: str, t: str, etype: str):
        edges.append({"source": s, "target": t, "type": etype})

    # Extracted entity node? ("entity:{norm_name}")
    if node_id.startswith("entity:"):
        norm = node_id.split("entity:", 1)[1]
        add_node(node_id, norm, "entity")
        rel_rows = (
            await db.execute(
                select(KTGraphEdge)
                .where(or_(KTGraphEdge.norm_source == norm, KTGraphEdge.norm_target == norm))
                .limit(50)
            )
        ).scalars().all()
        for e in rel_rows:
            if e.norm_source == norm:
                add_node(f"entity:{e.norm_target}", e.target_name, "entity")
            else:
                add_node(f"entity:{e.norm_source}", e.source_name, "entity")
            add_edge(f"entity:{e.norm_source}", f"entity:{e.norm_target}", e.relation)
        doc_rows = (
            await db.execute(
                select(KTGraphNode.document_id).where(KTGraphNode.norm_name == norm).limit(50)
            )
        ).fetchall()
        for r in doc_rows:
            d = await db.get(KTDocument, r.document_id)
            if d:
                add_node(d.id, d.title or "Document", "document")
                add_edge(d.id, node_id, "MENTIONS")
        return {"nodes": nodes, "edges": edges}

    # Episode id? ("{uuid}_ep_{i}")
    if "_ep_" in node_id:
        doc_id = node_id.rsplit("_ep_", 1)[0]
        doc = await db.get(KTDocument, doc_id)
        if doc:
            add_node(node_id, "Knowledge Item", "episode")
            add_node(doc.id, doc.title or "Document", "document")
            add_edge(node_id, doc.id, "PART_OF")
        return {"nodes": nodes, "edges": edges}

    # Project?
    proj = await db.get(KTProject, node_id)
    if proj:
        add_node(proj.id, proj.name or "Project", "project")
        docs = (
            (
                await db.execute(
                    select(KTDocument).where(
                        KTDocument.project_id == proj.id,
                        KTDocument.status.in_(VISIBLE_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )
        for d in docs:
            add_node(d.id, d.title or "Document", "document")
            add_edge(d.id, proj.id, "BELONGS_TO")
        return {"nodes": nodes, "edges": edges}

    # Document?
    doc = await db.get(KTDocument, node_id)
    if doc:
        add_node(doc.id, doc.title or "Document", "document")
        add_node(doc.project_id, "Project", "project")
        add_edge(doc.id, doc.project_id, "BELONGS_TO")
        chunk_rows = await db.execute(
            select(KTDocumentChunk.chunk_index, KTDocumentChunk.reference_time).where(
                KTDocumentChunk.document_id == doc.id
            )
        )
        for r in chunk_rows.fetchall():
            eid = f"{doc.id}_ep_{r.chunk_index}"
            add_node(eid, "Knowledge Item", "episode")
            add_edge(eid, doc.id, "PART_OF")
        for tag in _doc_tags(doc):
            add_node(tag, tag, "entity")
            add_edge(doc.id, tag, "MENTIONS")
        return {"nodes": nodes, "edges": edges}

    # Entity (tag name): documents mentioning it.
    tag_docs = (
        (
            await db.execute(
                select(KTDocument).where(
                    KTDocument.status.in_(VISIBLE_STATUSES),
                    (KTDocument.tags.contains([node_id]))
                    | (KTDocument.auto_tags.contains([node_id])),
                )
            )
        )
        .scalars()
        .all()
    )
    if tag_docs:
        add_node(node_id, node_id, "entity")
        for d in tag_docs:
            add_node(d.id, d.title or "Document", "document")
            add_edge(d.id, node_id, "MENTIONS")
    return {"nodes": nodes, "edges": edges}


async def graph_counts(
    db: AsyncSession,
    *,
    organization_id: Optional[int] = None,
    company_id: Optional[str] = None,
) -> Dict[str, int]:
    """{total_episodes, total_entities} — chunk and distinct-tag counts."""
    doc_filter = []
    if organization_id is not None:
        doc_filter.append(KTDocument.organization_id == organization_id)
    if company_id is not None:
        doc_filter.append(KTDocument.company_id == company_id)

    episodes = await db.scalar(
        select(func.count(KTDocumentChunk.id))
        .join(KTDocument, KTDocument.id == KTDocumentChunk.document_id)
        .where(*doc_filter)
    )
    docs = (
        (await db.execute(select(KTDocument.tags, KTDocument.auto_tags).where(*doc_filter)))
        .fetchall()
    )
    entities: set = set()
    for r in docs:
        entities.update((t or "").strip().lower() for t in (r.tags or []) if t)
        entities.update((t or "").strip().lower() for t in (r.auto_tags or []) if t)

    # Union in the distinct extracted graph entities (GraphRAG, Phase 6).
    node_filter = []
    if organization_id is not None:
        node_filter.append(KTGraphNode.organization_id == organization_id)
    if company_id is not None:
        node_filter.append(KTGraphNode.company_id == company_id)
    norm_rows = (
        await db.execute(select(KTGraphNode.norm_name).where(*node_filter))
    ).fetchall()
    entities.update(r.norm_name for r in norm_rows if r.norm_name)

    return {"total_episodes": int(episodes or 0), "total_entities": len(entities)}


async def related_documents(db: AsyncSession, doc: KTDocument, limit: int = 10) -> List[Dict]:
    """Neighbors for the access-key document view: same project + shared tags.
    (Replaces neo4j.traverse_neighborhood, which never existed — the old call
    always raised and returned [].)"""
    tags = set(_doc_tags(doc))
    rows = (
        (
            await db.execute(
                select(KTDocument).where(
                    KTDocument.company_id == doc.company_id,
                    KTDocument.id != doc.id,
                    KTDocument.status.in_(VISIBLE_STATUSES),
                )
            )
        )
        .scalars()
        .all()
    )
    scored = []
    for d in rows:
        shared = tags & set(_doc_tags(d))
        same_project = d.project_id == doc.project_id
        if not shared and not same_project:
            continue
        scored.append(
            {
                "id": d.id,
                "title": d.title,
                "type": "document",
                "relation": "same_project" if same_project else "shared_tags",
                "shared_tags": sorted(shared),
                "score": (2 if same_project else 0) + len(shared),
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
