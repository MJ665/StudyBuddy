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

logger = logging.getLogger(__name__)

# Constants
GEMINI_MODEL = settings.PRIMARY_AI_MODEL  # "gemini-2.5-flash"
# Verified working embedding model via ListModels API (text-embedding-004 returns 404 on v1beta)
GEMINI_EMBED_MODEL = "gemini-embedding-001"  # 3072 dims, supports RETRIEVAL_DOCUMENT/QUERY
HMAC_SECRET = settings.HMAC_KEY_SECRET

RAG_SYSTEM_PROMPT = """You are a highly capable AI assistant for an enterprise study hub.
Your goal is to provide accurate, concise, and helpful answers based strictly on the provided context.
If the answer cannot be found in the context, politely state that you don't know."""

# ── Conversational (greeting / meta) handling ────────────────────────────────
# The KT chatbot is grounded (it answers from approved documents) but must also
# be *friendly*: greetings and "what can you do" should get a warm, conversational
# reply instead of the "I don't have enough knowledge" refusal. Only genuine
# knowledge questions fall through to retrieval + grounded generation.
_GREETING_RE = re.compile(
    r"^\s*(hi+|hey+|hello+|yo|hiya|hii+|howdy|sup|greetings|good\s*(morning|afternoon|evening|day)|"
    r"thanks?|thank\s*you|thx|ty|ok(ay)?|cool|nice|great|awesome|got\s*it|bye|goodbye)"
    r"(\s+(there|team|bot|assistant|everyone|folks|all|buddy|mate))?"
    r"[\s!.,?😊👋🙏]*$",
    re.IGNORECASE,
)
_META_RE = re.compile(
    r"\b(who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|what\s+do\s+you\s+do|"
    r"how\s+do\s+you\s+work|how\s+can\s+you\s+help|help\s+me|what\s+is\s+this|"
    r"your\s+(capabilities|purpose)|what\s+should\s+i\s+ask|how\s+to\s+use)\b",
    re.IGNORECASE,
)


def classify_conversational(query: str) -> Optional[str]:
    """Return 'greeting' or 'meta' for small-talk/meta queries that should be
    answered conversationally (no RAG grounding needed); None for real questions."""
    q = (query or "").strip()
    if not q:
        return None
    if _GREETING_RE.match(q):
        return "greeting"
    # Keep meta detection tight so real knowledge questions are never intercepted.
    if _META_RE.search(q) and len(q.split()) <= 14:
        return "meta"
    return None


def conversational_reply(kind: str) -> str:
    """Friendly, non-refusal reply for greeting/meta queries."""
    if kind == "greeting":
        return (
            "Hi! 👋 I'm your Knowledge Transfer assistant. I answer questions grounded "
            "in the approved knowledge documents for the projects you have access to — "
            "how a system works, why a decision was made, or how to do a task — and I "
            "cite my sources. What would you like to know?"
        )
    return (
        "I'm your Knowledge Transfer assistant. I draw on the approved knowledge "
        "documents in the projects you can access, and I always cite my sources. Ask me "
        "about a specific system, process, or decision — for example, "
        '"How does the auth migration work?" (If a project has no approved documents yet, '
        "I won't have anything to draw from there.)"
    )

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
# (Phase 7) Neo4jKTClient removed — the KT knowledge store is Postgres/pgvector
# (modules/kt/services/{retrieval,ingestion_service,graph_service}.py).
# ════════════════════════════════════════════════════════════════════════════

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
