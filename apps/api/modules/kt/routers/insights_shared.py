"""
Insights, analytics, explorer, and other KT endpoints
"""

"""Shared imports/helpers/schemas for the split kt_insights router (moved verbatim from modules/kt/routers/insights.py — do not re-type)."""

from fastapi import APIRouter

from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

DEFAULT_CHECKLIST = [
    {"item": "Document active project architectures", "done": False, "required": True},
    {"item": "Document deployment + CI/CD runbooks", "done": False, "required": True},
    {"item": "Document all third-party integrations", "done": False, "required": True},
    {"item": "Document database schemas + migrations", "done": False, "required": True},
    {
        "item": "Document environment variables + secrets locations",
        "done": False,
        "required": True,
    },
    {"item": "Document known bugs + workarounds", "done": False, "required": False},
    {"item": "Introduce successor to stakeholders", "done": False, "required": True},
    {"item": "Transfer all credentials + access", "done": False, "required": True},
    {
        "item": "Review open tickets + handoff ownership",
        "done": False,
        "required": True,
    },
    {"item": "Mentor sign-off", "done": False, "required": True},
]

from services.redis_service import redis_client  # noqa: E402
