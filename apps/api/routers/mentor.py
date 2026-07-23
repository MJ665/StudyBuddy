# mentor.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/assessment/routers/{mentor_insights,mentor_reviews}.py
from fastapi import APIRouter

from modules.assessment.routers import mentor_insights
from modules.assessment.routers import mentor_reviews


router = APIRouter(prefix="/mentor", tags=["mentor"])
router.include_router(mentor_insights.router)
router.include_router(mentor_reviews.router)
