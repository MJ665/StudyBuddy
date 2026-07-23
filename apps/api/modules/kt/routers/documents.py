# documents.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/kt/routers/{doc_registry,doc_lifecycle,doc_assets}.py
from fastapi import APIRouter

from modules.kt.routers import doc_registry
from modules.kt.routers import doc_lifecycle
from modules.kt.routers import doc_assets


router = APIRouter()
router.include_router(doc_registry.router)
router.include_router(doc_lifecycle.router)
router.include_router(doc_assets.router)
