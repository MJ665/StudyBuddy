"""Shared helpers for AI evaluation and hint graphs.

Language/prompt configuration lives in services/ai_languages.py; this
module keeps common utilities used by both eval and hint pipelines.
"""
from __future__ import annotations

from services.ai_languages import *  # noqa: F401,F403


# ── LLM Factory ──────────────────────────────────────────────────────────────


def _get_llm(max_tokens: int = 1200, json_mode: bool = False):
    # Provider-agnostic: OpenRouter (free) for chat, Gemini fallback. Embeddings
    # stay on Gemini elsewhere. See services/llm_provider.py.
    from services.llm_provider import get_chat_llm

    return get_chat_llm(temperature=0.15, max_tokens=max_tokens, json_mode=json_mode)


# ── Helper: Get Language Entry ────────────────────────────────────────────────


def get_language_entry(language_id: str) -> Dict:
    """Find language entry from registry, fallback to generic."""
    lang_id = (language_id or "").lower()
    for lang in ENTERPRISE_LANGUAGES:
        if lang["id"] == lang_id:
            return lang
    return {
        "id": lang_id,
        "name": lang_id.upper(),
        "monaco_language": lang_id,
        "category": "General",
        "ai_context": f"General {lang_id} programming best practices",
    }


# ── Public Helper: Sanitize Input ────────────────────────────────────────────


def sanitize_input(text: str, max_length: int = 32000) -> str:
    if not text:
        return ""
    return str(text).strip()[:max_length]


def get_all_languages() -> List[Dict]:
    """Returns the full enterprise language registry for the frontend."""
    return ENTERPRISE_LANGUAGES


def get_languages_by_category() -> Dict[str, List[Dict]]:
    """Returns languages grouped by category for the frontend dropdown."""
    from collections import defaultdict

    grouped = defaultdict(list)
    for lang in ENTERPRISE_LANGUAGES:
        grouped[lang["category"]].append(
            {
                "id": lang["id"],
                "name": lang["name"],
                "monaco_language": lang["monaco_language"],
            }
        )
    return dict(grouped)
