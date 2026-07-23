"""
Document CRUD, versions, attachments, registry endpoints
"""

"""Shared imports/helpers/schemas for the split kt_documents router (moved verbatim from modules/kt/routers/documents.py — do not re-type)."""

from fastapi import APIRouter

from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403
