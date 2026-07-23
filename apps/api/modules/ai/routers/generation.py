# generation.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/ai/routers/{content_gen,advisory}.py
from fastapi import APIRouter

from modules.ai.routers import content_gen
from modules.ai.routers import advisory


router = APIRouter()
router.include_router(content_gen.router)
router.include_router(advisory.router)
