# cohort_reports.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/reporting/routers/{batch_reports,cohort_analytics}.py
from fastapi import APIRouter

from modules.reporting.routers import batch_reports
from modules.reporting.routers import cohort_analytics

from modules.reporting.routers.cohort_analytics import get_group_leaderboard  # noqa: F401

router = APIRouter()
router.include_router(batch_reports.router)
router.include_router(cohort_analytics.router)
