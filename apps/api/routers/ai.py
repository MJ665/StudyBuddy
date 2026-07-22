# ai.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/ai/routers/{generation}.py
from fastapi import APIRouter

from modules.ai.routers import generation


router = APIRouter(prefix="/ai", tags=["ai"])
router.include_router(generation.router)
