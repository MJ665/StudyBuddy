"""
LangGraph-based Knowledge Transfer Chatbot with Citations & Streaming.

Architecture:
1. Retrieve: Query Neo4j (vector search) for relevant Episodes, scoped to
   company_id + project_ids, then enrich with document titles from Postgres.
2. Rerank: Order chunks by relevance for the LLM context window.
3. Generate: Gemini generation grounded strictly in the retrieved context,
   emitting inline [citation: Document Title] tags which we parse into sources.

Both a non-streaming (`invoke_kt_chatbot`) and a real token-streaming
(`stream_kt_chatbot_response`) entrypoint are exposed. They share the same
retrieval/guardrail logic so the two chat endpoints behave identically.
"""

import json
import logging
import re
from typing import AsyncIterator

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from typing_extensions import TypedDict

from database import db_session_factory
from models.kt_model import KTDocument, KTProject

from modules.kt.services.retrieval import vector_search as pg_vector_search

from .kt_engine import (
    build_rag_prompt,
    gemini,
    is_injection,
    rerank_llm,
)

logger = logging.getLogger("kt.langraph")

KT_CHAT_SYSTEM_PROMPT = (
    "You are the Knowledge Transfer assistant for an engineering organization. "
    "Answer the user's question using ONLY the information in the provided sources. "
    "Each source is labelled like '[Source N — Document Title]'. When you use "
    "information from a source, cite it inline using the EXACT format "
    "[citation: Document Title] with the document's exact title. Cite every claim "
    "you draw from the sources. If the sources do not contain the answer, say you "
    "do not have that information in the project's knowledge base — never invent "
    "facts or cite sources that were not provided."
)

REFUSAL_NO_CONTEXT = (
    "I don't have enough knowledge in the documents I can access for this "
    "project to answer that. Try rephrasing, or ask a mentor to feed a "
    "relevant document into the knowledge graph."
)
REFUSAL_INJECTION = (
    "I can only answer questions about this project's knowledge base."
)

# How many candidates to pull from vector search before reranking, and how many
# reranked chunks to hand to the LLM.
RETRIEVE_TOP_K = 25
CONTEXT_TOP_N = 8
CITATION_PATTERN = re.compile(r"\[citation:\s*([^\]]+)\]", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph State
# ─────────────────────────────────────────────────────────────────────────────


class KTChatState(TypedDict, total=False):
    # Input
    query: str
    company_id: str
    project_ids: list[str]
    user_id: int
    session_id: str

    # Retrieval
    candidate_chunks: list[dict]
    reranked_chunks: list[dict]

    # Generation
    full_response: str
    cited_sources: list[dict]
    tokens_generated: int
    generation_complete: bool
    refused: bool


# ─────────────────────────────────────────────────────────────────────────────
# Retrieval helpers (real Gemini + Neo4j + Postgres)
# ─────────────────────────────────────────────────────────────────────────────


async def _enrich_with_titles(chunks: list[dict], company_id: str) -> list[dict]:
    """Attach doc_title / project_name to vector-search chunks via Postgres.

    vector_search returns Neo4j Episodes carrying only doc_id; the human-facing
    title lives in Postgres. Without this, citations can never resolve.
    """
    doc_ids = list({c.get("doc_id") for c in chunks if c.get("doc_id")})
    if not doc_ids:
        return chunks

    async with db_session_factory() as db:
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
                "doc_type": str(r.doc_type) if r.doc_type else "DOC",
                "project_name": r.project_name,
            }
            for r in rows.fetchall()
        }

    enriched = []
    for c in chunks:
        meta = doc_map.get(c.get("doc_id", ""), {})
        # Drop chunks whose document is not visible to this company (defence in depth).
        if not meta:
            continue
        enriched.append(
            {
                **c,
                "doc_title": meta.get("title", "Untitled Document"),
                "doc_type": meta.get("doc_type", "DOC"),
                "project_name": meta.get("project_name", "Unknown Project"),
                "relevance": float(c.get("score", 0.0)),
            }
        )
    return enriched


async def _retrieve_and_rerank(
    query: str, company_id: str, project_ids: list[str]
) -> list[dict]:
    """Embed → vector search (scoped) → enrich with titles → rerank."""
    query_embedding = await gemini.embed_query(query)
    if not query_embedding:
        return []

    # pgvector (Phase 2) — replaced neo4j.vector_search; same chunk contract.
    candidates = await pg_vector_search(
        query_embedding=query_embedding,
        company_id=company_id,
        project_ids=project_ids,
        top_k=RETRIEVE_TOP_K,
    )
    enriched = await _enrich_with_titles(candidates, company_id)
    return await rerank_llm(query, enriched, top_n=CONTEXT_TOP_N)


def _build_context(chunks: list[dict]) -> str:
    """Numbered, title-tagged source blocks for the LLM to cite."""
    blocks = []
    for i, c in enumerate(chunks, 1):
        title = c.get("doc_title", f"Document {i}")
        content = c.get("content", "")
        blocks.append(f"[Source {i} — {title}]\n{content}")
    return "\n\n".join(blocks)


def _extract_citations(response: str, chunks: list[dict]) -> list[dict]:
    """Map inline [citation: Title] tags back to source chunks (deduped)."""
    titles = CITATION_PATTERN.findall(response)
    sources: list[dict] = []
    seen: set[str] = set()
    for raw in titles:
        name = raw.strip().lower()
        for c in chunks:
            if c.get("doc_title", "").lower() == name and c.get("doc_id") not in seen:
                seen.add(c.get("doc_id"))
                sources.append(
                    {
                        "doc_id": c.get("doc_id", ""),
                        "doc_title": c.get("doc_title", ""),
                        "project_name": c.get("project_name", ""),
                        "excerpt": c.get("content", "")[:200],
                        "relevance_score": c.get("relevance", 0.0),
                    }
                )
                break
    return sources


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph nodes (non-streaming path)
# ─────────────────────────────────────────────────────────────────────────────


async def node_retrieve(state: KTChatState) -> KTChatState:
    logger.info(
        "🔍 Retrieve: q=%r company=%s projects=%s",
        state["query"][:60],
        state["company_id"],
        state["project_ids"],
    )
    try:
        state["reranked_chunks"] = await _retrieve_and_rerank(
            state["query"], state["company_id"], state["project_ids"]
        )
    except Exception as e:  # noqa: BLE001 - log and degrade to refusal
        logger.error("Retrieval failed: %s", e)
        state["reranked_chunks"] = []
    return state


async def node_generate(state: KTChatState) -> KTChatState:
    chunks = state.get("reranked_chunks", [])
    if not chunks:
        state["full_response"] = REFUSAL_NO_CONTEXT
        state["cited_sources"] = []
        state["refused"] = True
        state["generation_complete"] = True
        return state

    context = _build_context(chunks)
    prompt = build_rag_prompt(state["query"], context)
    try:
        response = await gemini.generate(prompt, system=KT_CHAT_SYSTEM_PROMPT)
    except Exception as e:  # noqa: BLE001
        logger.error("Generation failed: %s", e)
        response = REFUSAL_NO_CONTEXT

    state["full_response"] = response
    state["cited_sources"] = _extract_citations(response, chunks)
    state["tokens_generated"] = len(response.split())
    state["generation_complete"] = True
    return state


def build_kt_chatbot_graph() -> StateGraph:
    workflow = StateGraph(KTChatState)
    workflow.add_node("retrieve", node_retrieve)
    workflow.add_node("generate", node_generate)
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)
    return workflow


kt_langraph_app = build_kt_chatbot_graph().compile()


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


async def invoke_kt_chatbot(
    query: str, company_id: str, project_ids: list[str], user_id: int, session_id: str
) -> KTChatState:
    """Non-streaming: run the graph and return the final state."""
    if is_injection(query):
        return {
            "query": query,
            "full_response": REFUSAL_INJECTION,
            "cited_sources": [],
            "tokens_generated": 0,
            "generation_complete": True,
            "refused": True,
        }
    initial: KTChatState = {
        "query": query,
        "company_id": company_id,
        "project_ids": project_ids,
        "user_id": user_id,
        "session_id": session_id,
        "reranked_chunks": [],
        "full_response": "",
        "cited_sources": [],
        "tokens_generated": 0,
        "generation_complete": False,
        "refused": False,
    }
    return await kt_langraph_app.ainvoke(initial)


async def stream_kt_chatbot_response(
    query: str, company_id: str, project_ids: list[str], user_id: int, session_id: str
) -> AsyncIterator[str]:
    """Real SSE streaming.

    Retrieval + reranking run first, then Gemini tokens are streamed live as
    they arrive. Each line is a JSON object:
      {"token": str, "done": false}                       (incremental)
      {"token": "", "done": true, "sources": [...],       (terminal)
       "full_response": str}
    """
    # Guardrail: prompt-injection.
    if is_injection(query):
        yield json.dumps({"token": REFUSAL_INJECTION, "done": False}) + "\n"
        yield json.dumps(
            {"token": "", "done": True, "sources": [], "full_response": REFUSAL_INJECTION}
        ) + "\n"
        return

    try:
        chunks = await _retrieve_and_rerank(query, company_id, project_ids)
    except Exception as e:  # noqa: BLE001
        logger.error("Stream retrieval failed: %s", e)
        chunks = []

    # Guardrail: refuse when there is no grounding context.
    if not chunks:
        yield json.dumps({"token": REFUSAL_NO_CONTEXT, "done": False}) + "\n"
        yield json.dumps(
            {"token": "", "done": True, "sources": [], "full_response": REFUSAL_NO_CONTEXT}
        ) + "\n"
        return

    context = _build_context(chunks)
    prompt = build_rag_prompt(query, context)

    full_response = ""
    async for token in gemini.stream(prompt, system=KT_CHAT_SYSTEM_PROMPT):
        if not token:
            continue
        full_response += token
        yield json.dumps({"token": token, "done": False}) + "\n"

    sources = _extract_citations(full_response, chunks)
    yield json.dumps(
        {"token": "", "done": True, "sources": sources, "full_response": full_response}
    ) + "\n"
