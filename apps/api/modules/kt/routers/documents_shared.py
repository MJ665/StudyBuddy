"""
Document CRUD, versions, attachments, registry endpoints
"""

"""Shared imports/helpers/schemas for the split kt_documents router (moved verbatim from modules/kt/routers/documents.py — do not re-type)."""

from fastapi import APIRouter

from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403


# Export EVERY module-level name — including the single-underscore
# helpers (_audit, _require_mentor_plus, ...) that `import *` skips by
# default. Without this, every leaf router that star-imports this module
# raised NameError at call time on those helpers.
__all__ = [name for name in dir() if not name.startswith("__")]
