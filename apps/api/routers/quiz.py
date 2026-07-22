# quiz.py — thin aggregator (Phase 3 split). Implementation lives in
# modules/assessment/routers/{banks,courses,attempts}.py
from fastapi import APIRouter

from modules.assessment.routers import banks
from modules.assessment.routers import courses
from modules.assessment.routers import attempts

from modules.assessment.routers.quiz_shared import resolve_answer  # noqa: F401
from modules.assessment.routers.quiz_shared import check_attempt_eligibility  # noqa: F401

router = APIRouter(prefix="/quiz", tags=["quiz"])
router.include_router(banks.router)
router.include_router(courses.router)
router.include_router(attempts.router)
