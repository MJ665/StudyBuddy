# reports.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/reporting/routers/{member_reports,cohort_reports}.py
from fastapi import APIRouter

from modules.reporting.routers import member_reports
from modules.reporting.routers import cohort_reports

from modules.reporting.routers.cohort_reports import get_group_leaderboard  # noqa: F401

router = APIRouter(prefix="/reports", tags=["reports"])
router.include_router(member_reports.router)
router.include_router(cohort_reports.router)
