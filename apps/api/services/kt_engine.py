# apps/api/services/kt_engine.py

import datetime
import hashlib
import hmac
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from fastapi import HTTPException
from google import genai
from google.genai import types
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

# Constants
GEMINI_MODEL = settings.PRIMARY_AI_MODEL  # "gemini-2.5-flash"
# Verified working embedding model via ListModels API (text-embedding-004 returns 404 on v1beta)
GEMINI_EMBED_MODEL = "gemini-embedding-001"  # 3072 dims, supports RETRIEVAL_DOCUMENT/QUERY
HMAC_SECRET = settings.HMAC_KEY_SECRET

RAG_SYSTEM_PROMPT = """You are a highly capable AI assistant for an enterprise study hub.
Your goal is to provide accurate, concise, and helpful answers based strictly on the provided context.
If the answer cannot be found in the context, politely state that you don't know."""

# ── Knowledge access policy ──────────────────────────────────────────────────
# Sensitivity vocabulary (see /kt/registry/sensitivities): low | medium | high.
# `high` means credentials/PII are present, so it is withheld unless the caller
# leads the project. Retrieval is additionally constrained to the caller's granted
# projects, which is what enforces access_level (public/company_wide/project_only).
SENSITIVITY_LOW = "low"
SENSITIVITY_MEDIUM = "medium"
SENSITIVITY_HIGH = "high"

DEFAULT_SENSITIVITIES = [SENSITIVITY_LOW, SENSITIVITY_MEDIUM]
ALL_SENSITIVITIES = [SENSITIVITY_LOW, SENSITIVITY_MEDIUM, SENSITIVITY_HIGH]
# Project roles trusted with high-sensitivity content.
PRIVILEGED_PROJECT_ROLES = {"lead", "owner"}

# The vector index is global, so queryNodes returns the top-k across ALL tenants
# and the tenant/scope filter is applied afterwards. Over-fetch so a caller with a
# narrow grant still gets usable recall instead of an empty result set.
OVERFETCH_FACTOR = 8


def sensitivities_for(project_roles: List[str] | None) -> List[str]:
    """Map a caller's project membership roles to the sensitivities they may read."""
    roles = {str(r).lower() for r in (project_roles or [])}
    if roles & PRIVILEGED_PROJECT_ROLES:
        return list(ALL_SENSITIVITIES)
    return list(DEFAULT_SENSITIVITIES)


def build_rag_prompt(query: str, context: Any, doc_map: Any = None, history: Any = None) -> str:
    """Builds a formatted RAG prompt from the query and context."""
    return f"Context:\n{context}\n\nQuery: {query}"

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "for", "on",
    "with", "how", "what", "why", "when", "we", "do", "does", "did", "was",
    "were", "be", "are", "this", "that", "our", "us", "i", "you",
}


def _terms(text: str) -> set:
    return {w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOPWORDS and len(w) > 2}


def rerank(query: str, chunks: List[Dict], top_n: int = 5) -> List[Dict]:
    """Lexical reranker — the always-available fallback.

    Previously this returned `chunks[:top_n]`, i.e. it did no reranking at all and
    simply trusted raw vector order. Here the vector score is blended with term
    overlap against the chunk body and its document title, which materially
    reorders results when the embedding is topically close but lexically off.
    """
    q_terms = _terms(query)
    if not q_terms:
        return chunks[:top_n]

    scored = []
    for c in chunks:
        body_terms = _terms(c.get("content", ""))
        title_terms = _terms(c.get("doc_title", "") or c.get("title", ""))
        body_overlap = len(q_terms & body_terms) / len(q_terms)
        title_overlap = len(q_terms & title_terms) / len(q_terms)
        vector = float(c.get("score") or 0.0)
        combined = (0.60 * vector) + (0.30 * body_overlap) + (0.10 * title_overlap)
        scored.append((combined, c))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    out = []
    for combined, c in scored[:top_n]:
        c = dict(c)
        c["rerank_score"] = round(combined, 4)
        out.append(c)
    return out


async def rerank_llm(query: str, chunks: List[Dict], top_n: int = 5) -> List[Dict]:
    """Relevance-judge reranker: ask the model to score each candidate.

    Falls back to the lexical reranker on any failure, so retrieval never depends
    on the judge being available. Metered like every other AI call.
    """
    if not chunks:
        return []
    if len(chunks) <= 1:
        return rerank(query, chunks, top_n=top_n)

    listing = "\n".join(
        f"[{i}] {(c.get('doc_title') or 'Untitled')}: {(c.get('content') or '')[:500]}"
        for i, c in enumerate(chunks)
    )
    prompt = (
        f"Question: {query}\n\n"
        f"Candidate passages:\n{listing}\n\n"
        "Score how well each passage helps answer the question, from 0 (irrelevant) "
        "to 10 (directly answers it). Judge only the passage text; do not use outside "
        'knowledge. Return JSON: {"scores": [{"index": 0, "score": 7}, ...]} '
        "with one entry per passage."
    )

    try:
        result = await gemini.generate_json(
            prompt,
            system="You rank retrieved passages by relevance. Return ONLY the JSON object.",
        )
        raw = result.get("scores", result) if isinstance(result, dict) else result
        judged = {}
        for item in raw or []:
            if isinstance(item, dict) and "index" in item:
                idx = int(item["index"])
                if 0 <= idx < len(chunks):
                    judged[idx] = max(0.0, min(10.0, float(item.get("score", 0)))) / 10.0
        if not judged:
            raise ValueError("judge returned no usable scores")

        scored = []
        for i, c in enumerate(chunks):
            c = dict(c)
            # Blend with the vector score so a judge miss cannot bury an obviously
            # similar chunk entirely.
            llm = judged.get(i, 0.0)
            c["llm_score"] = round(llm, 3)
            c["rerank_score"] = round(0.75 * llm + 0.25 * float(c.get("score") or 0.0), 4)
            scored.append(c)
        scored.sort(key=lambda x: x["rerank_score"], reverse=True)
        return scored[:top_n]
    except Exception as e:
        logger.warning(f"LLM rerank failed, falling back to lexical: {e}")
        return rerank(query, chunks, top_n=top_n)


def compute_confidence(chunks: List[Dict], answer: str = "", citations: Optional[List] = None) -> float:
    """Calibrated 0-100 confidence for a grounded answer.

    The old value was `top_cosine * 100` (+5 for >3 chunks), which reported high
    confidence whenever the nearest vector happened to be close — even if the
    passages disagreed or the answer cited nothing. This combines three signals:

      * strength   — how relevant the best passages actually are
      * corroboration — whether several INDEPENDENT documents support the answer
      * grounding  — whether the answer cited the retrieved sources at all
    """
    if not chunks:
        return 0.0

    scores = [float(c.get("rerank_score", c.get("score") or 0.0)) for c in chunks]
    top = max(scores)
    strength = min(1.0, max(0.0, top))

    distinct_docs = len({c.get("doc_id") for c in chunks if c.get("doc_id")})
    corroboration = min(1.0, distinct_docs / 3.0)

    if citations:
        grounding = min(1.0, len(citations) / 2.0)
    elif answer:
        grounding = 0.35  # an answer with no resolvable citation is weakly grounded
    else:
        grounding = 0.0

    confidence = 100.0 * (0.55 * strength + 0.25 * corroboration + 0.20 * grounding)
    return round(min(99.0, max(1.0, confidence)), 1)


def extract_temporal_range(message: str) -> Tuple[Optional[str], Optional[str]]:
    """Extracts date ranges from the message. Stubbed for now."""
    return None, None


# Prompt-injection patterns. Each requires an imperative AND an instruction-shaped
# target, so ordinary prose ("act as a mentor to your team") does not trip it —
# this guard also runs over learner-submitted quiz answers via routers/ai.py, where
# false positives would block legitimate work.
_INJECTION_PATTERNS = [
    re.compile(r"\b(ignore|disregard|forget|override)\b[^.]{0,40}\b(previous|prior|above|earlier|all)\b[^.]{0,20}\b(instruction|prompt|rule|direction|context)", re.I),
    re.compile(r"\b(reveal|show|print|repeat|output|leak)\b[^.]{0,30}\b(system|initial|original|hidden)\b[^.]{0,20}\b(prompt|instruction|message)", re.I),
    re.compile(r"\byou are now\b[^.]{0,40}\b(unrestricted|unfiltered|jailbroken|dan|developer mode)", re.I),
    re.compile(r"\b(enable|enter|activate)\b[^.]{0,20}\b(developer|god|jailbreak|dan)\s*mode", re.I),
    re.compile(r"<\|?(im_start|im_end|system|endoftext)\|?>", re.I),
    re.compile(r"^\s*#{2,}\s*(system|instruction)\b", re.I | re.M),
    re.compile(r"\bpretend\b[^.]{0,30}\b(you have no|there are no)\b[^.]{0,20}\b(rule|restriction|guideline)", re.I),
]


def is_injection(message: str) -> bool:
    """Detect prompt-injection attempts in untrusted text.

    Previously `return False`, so the guard at every call site was inert.
    """
    if not message or len(message) < 8:
        return False
    return any(p.search(message) for p in _INJECTION_PATTERNS)

def sanitize_output(output: str) -> str:
    """Sanitizes AI output to remove dangerous tags."""
    return output.replace("<script>", "").replace("</script>", "")

# ════════════════════════════════════════════════════════════════════════════
# GEMINI CLIENT (Modern google-genai SDK)
# ════════════════════════════════════════════════════════════════════════════


class GeminiClient:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            logger.warning("GEMINI_API_KEY not configured. AI services disabled.")

    async def generate(
        self, prompt: str, system: Optional[str] = None, feature: str = "gemini_generate"
    ) -> str:
        if not self.client:
            raise HTTPException(503, "Gemini service unavailable")
        try:
            resp = await self.client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system, temperature=0.1, max_output_tokens=8192
                ),
            )
            from services import ai_meter

            await ai_meter.record_response(feature, GEMINI_MODEL, resp)
            return resp.text or ""
        except Exception as e:
            logger.error(f"Gemini generate error: {e}")
            raise HTTPException(500, f"AI generation failed: {e}")

    async def stream(self, prompt: str, system: Optional[str] = None):
        if not self.client:
            raise HTTPException(503, "Gemini service unavailable")
        try:
            # google-genai: generate_content_stream() is a coroutine returning an
            # async iterator — it MUST be awaited before `async for`.
            stream = await self.client.aio.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                ),
            )
            last = None
            async for chunk in stream:
                last = chunk
                if chunk.text:
                    yield chunk.text
            if last is not None:
                from services import ai_meter

                await ai_meter.record_response("kt_chat_stream", GEMINI_MODEL, last)
        except Exception as e:
            logger.error(f"Gemini stream error: {e}")
            yield f"Error: {e}"

    async def generate_json(self, prompt: str, system: Optional[str] = None) -> Any:
        if not self.client:
            raise HTTPException(503, "Gemini service unavailable")
        try:
            resp = await self.client.aio.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.1,
                    response_mime_type="application/json",
                ),
            )
            from services import ai_meter

            await ai_meter.record_response("gemini_json", GEMINI_MODEL, resp)
            return json.loads(resp.text or "{}")
        except Exception as e:
            logger.error(f"Gemini generate_json error: {e}")
            # Fallback
            text = await self.generate(prompt, system)
            try:
                clean = re.sub(r"```json\n?|\n?```", "", text).strip()
                return json.loads(clean)
            except Exception:
                raise HTTPException(500, "AI failed to return valid JSON")

    async def embed(self, text: str, is_query: bool = False) -> List[float]:
        if not self.client:
            return []
        try:
            task_type = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
            resp = await self.client.aio.models.embed_content(
                model=GEMINI_EMBED_MODEL,
                contents=text[:8000],
                config=types.EmbedContentConfig(task_type=task_type),
            )
            if resp.embeddings and resp.embeddings[0].values:
                from services import ai_meter

                await ai_meter.record(
                    "kt_embedding", GEMINI_EMBED_MODEL, len(text) // 4, 0
                )
                return resp.embeddings[0].values
        except Exception as e:
            # No cross-model fallback: a different embedding model would return a
            # different dimensionality and corrupt the 3072-dim kt_vector_index.
            logger.error(f"Gemini embedding error [{GEMINI_EMBED_MODEL}]: {e}")
        return []

    async def embed_query(self, text: str) -> List[float]:
        return await self.embed(text, is_query=True)


gemini = GeminiClient()

# ════════════════════════════════════════════════════════════════════════════
# NEO4J CLIENT
# ════════════════════════════════════════════════════════════════════════════


class Neo4jKTClient:
    def __init__(self):
        self.uri = settings.NEO4J_URI
        self.user = settings.NEO4J_USERNAME
        self.password = settings.NEO4J_PASSWORD
        self.instance = settings.NEO4J_INSTANCE

        # Fallback for Aura instances if URI is missing
        if not self.uri and self.instance:
            self.uri = f"neo4j+s://{self.instance}.databases.neo4j.io"

        self.driver = None

    async def connect(self):
        """Connect to Neo4j. Returns True if successful, False if not configured."""
        if not self.driver:
            if not self.uri:
                return False
            self.driver = AsyncGraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
        return True

    async def close(self):
        if self.driver:
            await self.driver.close()

    async def setup_constraints(self):
        """Initialize indexes and constraints for KT graph."""
        if not await self.connect():
            logger.warning("Neo4j not configured. Skipping graph initialization.")
            return
        queries = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (o:Organization) REQUIRE o.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Project) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Sprint) REQUIRE s.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Episode) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (ent:Entity) REQUIRE ent.name IS UNIQUE",
            "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.company_id)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Episode) ON (e.reference_time)",
            # Neo4j Vector Index — 3072 dims for gemini-embedding-001
            """
            CREATE VECTOR INDEX kt_vector_index IF NOT EXISTS
            FOR (e:Episode) ON (e.embedding)
            OPTIONS {indexConfig: {
                `vector.dimensions`: 3072,
                `vector.similarity_function`: 'cosine'
            }}
            """,
        ]
        assert self.driver is not None
        async with self.driver.session() as session:
            for q in queries:
                try:
                    await session.run(q)
                except Exception as e:
                    logger.warning(f"Neo4j Setup Warning: {e}")

            # Drop and recreate vector index if dimensions changed (768 -> 3072)
            # IF NOT EXISTS won't update an existing index's config
            try:
                info = await session.run(
                    "SHOW VECTOR INDEXES WHERE name = 'kt_vector_index'"
                )
                rows = await info.data()
                if rows and rows[0].get("options", {}).get("vector.dimensions") != 3072:
                    logger.info(
                        "kt_vector_index has wrong dimensions — dropping and recreating with 3072 dims"
                    )
                    await session.run("DROP INDEX kt_vector_index IF EXISTS")
                    await session.run("""
                        CREATE VECTOR INDEX kt_vector_index
                        FOR (e:Episode) ON (e.embedding)
                        OPTIONS {indexConfig: {
                            `vector.dimensions`: 3072,
                            `vector.similarity_function`: 'cosine'
                        }}
                    """)
            except Exception as e:
                logger.warning(f"Vector index migration check: {e}")

    async def vector_search(
        self,
        query_embedding: List[float],
        company_id: str,
        project_ids: List[str],
        top_k: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
        allowed_sensitivities: List[str] | None = None,
    ) -> List[Dict]:
        # Fail closed BEFORE doing any work: an empty grant list must retrieve
        # nothing, never everything.
        if not project_ids:
            return []
        if not await self.connect():
            return []
        sensitivities = allowed_sensitivities or DEFAULT_SENSITIVITIES
        cypher = """
        CALL db.index.vector.queryNodes('kt_vector_index', $k, $embedding)
        YIELD node, score
        MATCH (node)-[:PART_OF]->(d:Document)-[:BELONGS_TO]->(p:Project)-[:OWNED_BY]->(c:Company)
        WHERE c.id = $cid AND p.id IN $pids
          AND coalesce(d.sensitivity, 'low') IN $sens
        """
        params = {
            "embedding": query_embedding,
            "k": top_k * OVERFETCH_FACTOR,
            "cid": company_id,
            "pids": project_ids,
            "sens": sensitivities,
        }

        if date_from:
            cypher += " AND node.reference_time >= $dfrom"
            params["dfrom"] = date_from
        if date_to:
            cypher += " AND node.reference_time <= $dto"
            params["dto"] = date_to

        cypher += " RETURN node.id as episode_id, node.content as content, d.id as doc_id, score LIMIT $limit"
        params["limit"] = top_k

        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            # neo4j AsyncResult: use .data() not .all()
            return await result.data()

    async def delete_doc_episodes(self, doc_id: str, company_id: str, project_id: str):
        """Purge episodes and relationships for a specific document."""
        if not await self.connect():
            return
        cypher = "MATCH (e:Episode {doc_id: $did}) DETACH DELETE e"
        assert self.driver is not None
        async with self.driver.session() as session:
            await session.run(cypher, {"did": doc_id})

    async def graph_hop(
        self,
        seed_episode_ids: List[str],
        company_id: str,
        project_ids: List[str],
        allowed_sensitivities: List[str] | None = None,
    ) -> List[Dict]:
        """Expand retrieval via entity relationships (Multi-hop RAG).

        This carries the SAME scope + sensitivity filter as `vector_search`. A
        filtered seed query feeding an unfiltered hop would leak restricted
        content one relationship away from an allowed chunk.
        """
        if not project_ids:
            return []
        if not await self.connect():
            return []
        cypher = """
        MATCH (e:Episode) WHERE e.id IN $seeds
        MATCH (e)-[:MENTIONS]->(ent:Entity)<-[:MENTIONS]-(hop:Episode)
        MATCH (hop)-[:PART_OF]->(d:Document)-[:BELONGS_TO]->(p:Project)-[:OWNED_BY]->(c:Company)
        WHERE c.id = $cid AND p.id IN $pids AND NOT hop.id IN $seeds
          AND coalesce(d.sensitivity, 'low') IN $sens
        RETURN hop.id as episode_id, hop.content as content, d.id as doc_id, 1.0 as score
        LIMIT 5
        """
        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(
                cypher,
                {
                    "seeds": seed_episode_ids,
                    "cid": company_id,
                    "pids": project_ids,
                    "sens": allowed_sensitivities or DEFAULT_SENSITIVITIES,
                },
            )
            return await result.data()

    async def run_query(self, query: str, parameters: dict | None = None) -> List[dict]:
        """Execute a custom Cypher query."""
        if not await self.connect():
            return []
        assert self.driver is not None
        async with self.driver.session() as session:
            try:
                result = await session.run(query, parameters or {})
                return await result.data()
            except Exception as e:
                logger.error(f"Neo4j query error: {e}")
                return []

    async def get_hierarchy_graph(self, company_id: str) -> dict:
        """Returns the D3-compatible nodes and links for a given company hierarchy."""
        import json

        from cache_manager import redis_client

        redis_key = f"kt:hierarchy:{company_id}"
        try:
            cached = await redis_client.get(redis_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        if not await self.connect():
            return {"nodes": [], "links": []}

        query = """
        MATCH path = (c:Company {id: $cid})<-[:OWNED_BY|WITHIN|BELONGS_TO|PART_OF|MENTIONS*1..4]-(m)
        WITH nodes(path) AS ns, relationships(path) AS rs
        UNWIND ns AS n
        UNWIND rs AS r
        RETURN collect(distinct {
                 id: coalesce(n.id, n.name, elementId(n)), 
                 label: labels(n)[0], 
                 name: coalesce(n.title, n.name, n.id)
               }) as nodes,
               collect(distinct {
                 source: coalesce(startNode(r).id, startNode(r).name, elementId(startNode(r))), 
                 target: coalesce(endNode(r).id, endNode(r).name, elementId(endNode(r))), 
                 type: type(r)
               }) as links
        """
        assert self.driver is not None
        async with self.driver.session() as session:
            try:
                result = await session.run(query, {"cid": company_id})
                record = await result.single()
                if record:
                    data = {"nodes": record["nodes"], "links": record["links"]}
                    try:
                        await redis_client.set(redis_key, json.dumps(data), ex=86400)
                    except Exception:
                        pass
                    return data
                return {"nodes": [], "links": []}
            except Exception as e:
                logger.error(f"Failed to get hierarchy graph: {e}")
                return {"nodes": [], "links": []}

    async def run_one(self, query: str, **params) -> Optional[Dict]:
        """Execute a query and return a single record."""
        if not await self.connect():
            return None
        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(query, params)
            record = await result.single()
            return record.data() if record else None

    async def get_timeline(self, company_id: str, project_ids: List[str]) -> List[Dict]:
        """Get a timeline of knowledge events."""
        if not await self.connect():
            return []
        # Correct direction: Episode-[:PART_OF]->Document-[:BELONGS_TO]->Project-[:OWNED_BY]->Company
        cypher = """
        MATCH (c:Company {id: $cid})<-[:OWNED_BY]-(p:Project)<-[:BELONGS_TO]-(d:Document)<-[:PART_OF]-(e:Episode)
        WHERE p.id IN $pids
        RETURN e.id as id, e.content as content, e.reference_time as time, d.title as doc_title
        ORDER BY e.reference_time DESC
        LIMIT 50
        """
        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(cypher, {"cid": company_id, "pids": project_ids})
            return await result.data()

    async def get_graph_explorer_data(
        self, company_id: str, project_ids: List[str]
    ) -> Dict[str, List]:
        """Fetch all nodes and relationships for the graph explorer."""
        if not await self.connect():
            return {"nodes": [], "edges": []}
        cypher = """
        MATCH (c:Company {id: $cid})<-[:OWNED_BY]-(p:Project)
        WHERE p.id IN $pids
        OPTIONAL MATCH (d:Document)-[:BELONGS_TO]->(p)
        OPTIONAL MATCH (e:Episode)-[:PART_OF]->(d)
        OPTIONAL MATCH (e)-[:MENTIONS]->(ent:Entity)
        RETURN p, d, e, ent
        """
        nodes = []
        edges = []
        seen_nodes = set()

        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(cypher, {"cid": company_id, "pids": project_ids})
            async for record in result:
                p = record.get("p")
                d = record.get("d")
                e = record.get("e")
                ent = record.get("ent")

                # 1. Add Project
                if p and p["id"] not in seen_nodes:
                    nodes.append(
                        {
                            "id": p["id"],
                            "label": p.get("name", "Project"),
                            "type": "project",
                        }
                    )
                    seen_nodes.add(p["id"])

                # 2. Add Document
                if d and d["id"] not in seen_nodes:
                    nodes.append(
                        {
                            "id": d["id"],
                            "label": d.get("title", "Document"),
                            "type": "document",
                        }
                    )
                    seen_nodes.add(d["id"])
                    if p:
                        edges.append(
                            {"source": d["id"], "target": p["id"], "type": "BELONGS_TO"}
                        )

                # 3. Add Episode
                if e and e["id"] not in seen_nodes:
                    nodes.append(
                        {
                            "id": e["id"],
                            "label": "Knowledge Item",
                            "type": "episode",
                            "metadata": {"time": e.get("reference_time", "")},
                        }
                    )
                    seen_nodes.add(e["id"])
                    if d:
                        edges.append(
                            {"source": e["id"], "target": d["id"], "type": "PART_OF"}
                        )

                # 4. Add Entity
                if ent and ent["name"] not in seen_nodes:
                    nodes.append(
                        {"id": ent["name"], "label": ent["name"], "type": "entity"}
                    )
                    seen_nodes.add(ent["name"])
                    if e:
                        edges.append(
                            {
                                "source": e["id"],
                                "target": ent["name"],
                                "type": "MENTIONS",
                            }
                        )

        return {"nodes": nodes, "edges": edges}

    async def get_graph_neighborhood(self, node_id: str) -> Dict[str, List]:
        """Fetch 1-hop neighborhood for a specific node."""
        if not await self.connect():
            return {"nodes": [], "edges": []}
        cypher = """
        MATCH (n)-[r]-(m)
        WHERE n.id = $nid OR n.name = $nid
        RETURN n, r, m
        """
        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()

        assert self.driver is not None
        async with self.driver.session() as session:
            result = await session.run(cypher, {"nid": node_id})
            async for record in result:
                n = record.get("n")
                r = record.get("r")
                m = record.get("m")

                for node in [n, m]:
                    if not node:
                        continue
                    nid = node.get("id") or node.get("name")
                    if nid and nid not in seen_nodes:
                        label_list = list(node.labels)
                        node_type = label_list[0].lower() if label_list else "unknown"
                        nodes.append(
                            {
                                "id": nid,
                                "label": node.get("title")
                                or node.get("name")
                                or node.get("id", "Node"),
                                "type": node_type,
                            }
                        )
                        seen_nodes.add(nid)

                if r:
                    # Create edge ID
                    start_node = r.nodes[0]
                    end_node = r.nodes[1]
                    sid = start_node.get("id") or start_node.get("name")
                    tid = end_node.get("id") or end_node.get("name")
                    edge_id = f"{sid}-{r.type}-{tid}"
                    if edge_id not in seen_edges:
                        edges.append({"source": sid, "target": tid, "type": r.type})
                        seen_edges.add(edge_id)

        return {"nodes": nodes, "edges": edges}


neo4j = Neo4jKTClient()

# ════════════════════════════════════════════════════════════════════════════
# KT SECURITY: ACCESS KEYS & HMAC
# ════════════════════════════════════════════════════════════════════════════


def generate_access_key(
    company_id: str,
    project_ids: List[str],
    key_id: str | None = None,
    expires_at: datetime.datetime | None = None,
) -> Tuple[str, str, str]:
    """Create a high-entropy key: sh_kt_<random>_<hmac>"""
    raw = os.urandom(24).hex()
    payload = f"{company_id}:{','.join(sorted(project_ids))}:{raw}"
    sig = hmac.new(HMAC_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()[
        :16
    ]
    raw_key = f"sh_kt_{raw}_{sig}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = f"sh_kt_{raw[:8]}"
    return raw_key, key_hash, key_prefix


def verify_access_key_signature(
    key: str, company_id: Optional[str] = None, project_ids: Optional[List[str]] = None
) -> bool:
    if not key or not key.startswith("sh_kt_"):
        return False
    parts = key.split("_")

    # FIX: Handle keys with underscores in raw (24 hex chars = no underscores)
    # Format: sh_kt_{24-hex}_{16-hex-sig}
    if len(parts) != 4:
        return False

    prefix1, prefix2, raw, sig_provided = parts
    if prefix1 != "sh" or prefix2 != "kt":
        return False
    if len(raw) != 48:
        return False  # 24 bytes = 48 hex chars
    if len(sig_provided) != 16:
        return False

    if company_id and project_ids:
        payload = f"{company_id}:{','.join(sorted(project_ids))}:{raw}"
        sig_expected = hmac.new(
            HMAC_SECRET.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(sig_provided, sig_expected)

    # Without scope, can only verify format (not semantic correctness)
    # This should only be used for format pre-check; DB verification is authoritative
    return True

    # ════════════════════════════════════════════════════════════════════════════
    # TEMPORAL INGESTION PIPELINE
    # ════════════════════════════════════════════════════════════════════════════
