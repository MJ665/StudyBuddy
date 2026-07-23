"""
System Configuration Router — StudyHub Enterprise
Serves dynamic configuration to the frontend.
Replaces all hardcoded arrays in React components.
"""

from fastapi import APIRouter
from services.ai_engine import get_all_languages, get_languages_by_category

router = APIRouter(prefix="/system", tags=["system"])


SYSTEM_CONFIG = {
    "difficulty_levels": ["Easy", "Medium", "Hard", "Expert", "Mixed"],
    "learner_levels": ["Beginner", "Intermediate", "Advanced", "Expert"],
    "resource_categories": [
        "General",
        "Lecture Notes",
        "Reference",
        "Cheat Sheet",
        "Assessment",
        "Architecture Diagrams",
        "Runbooks",
        "Compliance Docs",
        "Security Guidelines",
        "Other",
    ],
    "ai_languages": [
        "English",
        "Hindi",
        "Spanish",
        "French",
        "German",
        "Japanese",
        "Mandarin",
    ],
    "password_patterns": [
        "<name>sigmoid@123",
        "<name>@2026",
        "sigmoid@<year>",
        "<name>@learn2026",
        "train@<name>123",
    ],
    "promotable_roles": {
        "LDAdmin": ["Mentor", "GroupAdmin", "LDAdmin"],
        "GroupAdmin": ["Mentor"],
        "Mentor": [],
    },
    "grade_thresholds": {"A+": 90, "A": 80, "B": 70, "C": 60, "D": 50, "F": 0},
    "passing_threshold_default": 70,
}


@router.get("/config")
async def get_system_config():
    """
    Returns complete system configuration for the frontend.
    Used to replace all hardcoded dropdowns, enums, and thresholds.
    No auth required — this is static/semi-static config data.
    """
    import json

    from cache_manager import redis_client

    redis_key = "system:config:full"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    langs = get_all_languages()
    res = {
        **SYSTEM_CONFIG,
        "supported_languages": langs,
        "languages_by_category": get_languages_by_category(),
    }

    try:
        await redis_client.set(redis_key, json.dumps(res))
    except Exception:
        pass

    return res


@router.get("/config/languages")
async def get_language_config():
    """Returns only the language registry. Lightweight endpoint for CodeEditor."""
    import json

    from cache_manager import redis_client

    redis_key = "system:config:languages"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    res = {
        "supported_languages": get_all_languages(),
        "by_category": get_languages_by_category(),
    }

    try:
        await redis_client.set(redis_key, json.dumps(res))
    except Exception:
        pass

    return res
