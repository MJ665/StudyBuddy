"""Single source of truth for the chat/completion LLM.

Chat/completion runs on **OpenRouter** (free models, no Gemini credit needed)
when ``AI_CHAT_PROVIDER=openrouter`` and a key is set; otherwise it falls back to
**Gemini**. EMBEDDINGS are NOT handled here — they stay on Gemini in
``kt_engine`` (OpenRouter has no free embedding model).

All LangChain call sites (eval/hint/review/reporting graphs) get their model
from :func:`get_chat_llm` so the provider can be switched in one place.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from config import settings

logger = logging.getLogger("llm_provider")


def use_openrouter() -> bool:
    return (settings.AI_CHAT_PROVIDER or "").lower() == "openrouter" and bool(
        settings.OPENROUTER_API_KEY
    )


def get_chat_llm(
    temperature: float = 0.15,
    max_tokens: int = 1200,
    json_mode: bool = False,
):
    """Return a LangChain chat model for the active provider, or ``None`` when
    no provider is configured (callers already degrade to a safe fallback).

    ``json_mode`` is best-effort: free OpenRouter models may not honor a strict
    response_format, so callers must keep using the JSON-repair path.
    """
    if use_openrouter():
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=settings.OPENROUTER_MODEL,
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=60,
                max_retries=2,
                default_headers={
                    "HTTP-Referer": "https://studybuddy.mj665.in",
                    "X-Title": "StudyBuddy",
                },
            )
        except Exception as e:  # noqa: BLE001
            logger.error("OpenRouter LLM init failed (%s); falling back to Gemini", e)

    # Gemini fallback
    api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("No chat LLM configured (OpenRouter + Gemini both unset).")
        return None
    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
        HarmBlockThreshold,
        HarmCategory,
    )

    safety = {
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }
    model_kwargs = {}
    if json_mode:
        model_kwargs["response_mime_type"] = "application/json"
    return ChatGoogleGenerativeAI(
        model=settings.PRIMARY_AI_MODEL,
        temperature=temperature,
        max_output_tokens=max_tokens,
        safety_settings=safety,
        model_kwargs=model_kwargs,
        api_key=api_key,
    )


# ── Raw async chat (used by kt_engine.GeminiClient chat paths) ────────────────
def get_openrouter_async_client():
    """An AsyncOpenAI client pointed at OpenRouter, or None."""
    if not use_openrouter():
        return None
    try:
        from openai import AsyncOpenAI

        return AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://studybuddy.mj665.in",
                "X-Title": "StudyBuddy",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.error("OpenRouter async client init failed: %s", e)
        return None
