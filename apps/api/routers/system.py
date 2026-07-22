from config import settings
from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/config")
def get_system_config():
    """
    Exposes platform-wide enum constants and configurations.
    Used by the frontend to replace hardcoded dropdown values (STRAT-102).
    """
    return {
        "supported_languages": settings.SUPPORTED_LANGUAGES,
        "difficulty_levels": settings.DIFFICULTY_LEVELS,
        "resource_categories": settings.RESOURCE_CATEGORIES,
        "ai_languages": settings.AI_LANGUAGES,
        "learner_levels": settings.LEARNER_LEVELS,
        "password_patterns": settings.PASSWORD_PATTERNS,
        "notification_types": settings.NOTIFICATION_TYPES,
    }
