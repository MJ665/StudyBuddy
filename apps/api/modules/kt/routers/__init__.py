"""
KT sub-routers aggregation.
Each sub-router is imported and aggregated in routers/kt.py.
"""

from modules.kt.routers import (
    access,
    chat,
    documents,
    handoff,
    ingestion,
    insights,
    projects,
    review,
)

__all__ = [
    "access",
    "chat",
    "documents",
    "handoff",
    "ingestion",
    "insights",
    "projects",
    "review",
]
