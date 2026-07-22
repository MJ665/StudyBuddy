# admin.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/reporting/routers/{governance,admin_analytics}.py
from fastapi import APIRouter

from modules.reporting.routers import governance
from modules.reporting.routers import admin_analytics


router = APIRouter(prefix="/admin", tags=["admin_governance"])
router.include_router(governance.router)
router.include_router(admin_analytics.router)
