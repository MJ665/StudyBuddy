# insights.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/kt/routers/{workspace,analytics,explorer}.py
from fastapi import APIRouter

from modules.kt.routers import workspace
from modules.kt.routers import analytics
from modules.kt.routers import explorer


router = APIRouter()
router.include_router(workspace.router)
router.include_router(analytics.router)
router.include_router(explorer.router)
