"""
AI Feature Router — StudyHub Enterprise
Exposes AI-powered endpoints:
  - POST /ai/review         → Answer review with Gemini (existing)
  - POST /ai/smart-quiz     → Generate quiz questions from topic with Gemini
  - POST /ai/explain        → Explain a question/answer in depth
  - POST /ai/learning-path  → Generate personalised learning path
  - POST /ai/summarize      → Summarize resource/topic into study notes
  - GET  /ai/next-topic     → Recommend next topic based on performance
"""

"""Shared imports/helpers/schemas for the split ai router (moved verbatim from routers/ai.py — do not re-type)."""

import datetime

import hashlib

import json

import logging

import os

import re

import traceback

from collections import defaultdict

from typing import List, Optional, Any

import models

from auth_utils import caller_org_id, caller_super_org_id  # noqa: F401

from auth_utils import verify_token

from config import settings

from database import get_async_db, get_db

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from services.ai_reporting import ai_executive

from services.redis_service import redis_client

from services.review_engine import run_review_graph

from sqlalchemy.orm import Session

from utils.json_repair import repair_json

from utils.security import is_injection

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = 60

RATE_LIMIT_MAX_CALLS = 10

async def _check_rate_limit(user_id: str, key_suffix: str = "ai"):
    """Redis sliding-window rate limiter. Falls back gracefully if Redis is down."""
    key = f"rate_limit:{key_suffix}:{user_id}"
    try:
        count_result = await redis_client.get(key)
        current_count = int(count_result) if count_result else 0
        if current_count >= RATE_LIMIT_MAX_CALLS:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Max {RATE_LIMIT_MAX_CALLS} AI requests per minute.",
            )
        await redis_client.set(key, current_count + 1, ex=RATE_LIMIT_WINDOW)
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down → allow request

def _get_llm(temperature: float = 0.3, max_tokens: int = 800, json_mode: bool = False):
    """Create a Gemini LLM instance via LangChain."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
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
        kwargs = {}
        if json_mode:
            kwargs["model_kwargs"] = {"response_mime_type": "application/json"}
        return ChatGoogleGenerativeAI(
            model=settings.PRIMARY_AI_MODEL,
            temperature=temperature,
            max_output_tokens=max_tokens,
            safety_settings=safety,
            api_key=api_key,
            **kwargs,
        )
    except Exception as e:
        logger.error(f"LLM init error: {e}")
        return None

def _strip_fences(raw: str) -> str:
    """Strip markdown code fences (```json ... ```) from LLM output."""
    # Remove ```json\n...\n``` or ```...\n...\n```
    stripped = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    stripped = re.sub(r"\s*```$", "", stripped.strip())
    return stripped.strip()

def _repair_json(raw: str) -> str:
    # STRAT-FIX: Delegating to shared utility
    return repair_json(raw)

class AIQuery(BaseModel):
    attempt_id: int
    question_id: int
    user_query: str

class SmartQuizRequest(BaseModel):
    topic: str
    difficulty: str = "Medium"  # Easy | Medium | Hard
    num_questions: int = 5
    language: str = "English"
    save_as_draft: bool = False
    group_id: Optional[int] = None
    # mcq_single | true_false | short_answer | essay
    question_type: str = "mcq_single"

class ExplainRequest(BaseModel):
    question_text: str
    correct_answer: str
    user_answer: Optional[str] = None
    context: Optional[str] = None

class LearningPathRequest(BaseModel):
    goal: str  # e.g. "Master Python OOP"
    current_level: str = "Beginner"  # Beginner | Intermediate | Advanced
    available_hours_per_week: int = 5

class SummarizeRequest(BaseModel):
    content: str  # raw text from PDF / resource
    summary_type: str = "study_notes"  # "study_notes" | "flashcards" | "quiz_questions"

class NextTopicRequest(BaseModel):
    group_id: Optional[int] = None

class AIAskRequest(BaseModel):
    attempt_id: Optional[int] = None
    question_id: Optional[int] = None
    user_query: str

class LeaderboardSummaryRequest(BaseModel):
    leaderboard_data: List[dict]
    group_name: Optional[str] = "Global"
