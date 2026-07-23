"""generation endpoints (moved verbatim from routers/ai.py)."""

"""Shared imports/helpers/schemas for the split ai_generation router (moved verbatim from modules/ai/routers/generation.py — do not re-type)."""

from fastapi import APIRouter

from modules.ai.routers.ai_shared import *  # noqa: F401,F403

from modules.ai.routers.ai_shared import (  # noqa: F401
    _check_rate_limit,
    _get_llm,
    _repair_json,
    _strip_fences,
)
