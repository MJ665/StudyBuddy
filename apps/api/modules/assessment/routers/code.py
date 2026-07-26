import json
import logging
from typing import List, Optional

from cache_manager import cache_manager
from database import get_async_db, get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models.attempt import CodingAttempt, CodingHint
from models.coding import CodingQuestion, CodingTestCase
from auth_utils import (
    assert_same_org,
    assert_same_super_org,
    caller_org_id,
    caller_super_org_id,
    scope_to_org,
    scope_to_super_org,
)
from routers.auth import get_current_user
from schemas import (
    AIResponseEnvelope,
    CodingAttemptCreate,
    CodingAttemptResponse,
    CodingHintRequest,
    CodingQuestionResponse,
)
from services.ai_engine import (
    get_all_languages,
    get_languages_by_category,
    run_evaluation_graph,
    run_hint_graph,
)
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

router = APIRouter(prefix="/code", tags=["coding"])
logger = logging.getLogger(__name__)


@router.get("/languages", response_model=AIResponseEnvelope)
async def list_languages():
    """
    Returns the supported languages for the code editor.
    This drives the Monaco editor configuration and language selection.
    """
    import json

    from cache_manager import redis_client

    redis_key = "code:languages"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    langs = get_all_languages()
    res = {
        "ai_generated": False,
        "data": {"languages": langs, "categories": get_languages_by_category()},
    }

    try:
        await redis_client.set(redis_key, json.dumps(res))
    except Exception:
        pass

    return res


@router.get("/questions", response_model=List[CodingQuestionResponse])
def get_coding_questions(
    course_id: Optional[int] = None,
    difficulty: Optional[str] = None,
    topic: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Was UNAUTHENTICATED and unscoped: any anonymous caller could enumerate every
    customer's coding questions. Questions are authored content, so they are shared
    across the customer's business units (super-org scope)."""
    query = scope_to_super_org(
        db.query(CodingQuestion).filter(CodingQuestion.is_active == True),  # noqa: E712
        CodingQuestion,
        current_user,
        db,
    )

    if course_id:
        query = query.filter(CodingQuestion.course_id == course_id)
    if difficulty:
        query = query.filter(CodingQuestion.difficulty == difficulty)
    if topic:
        # Use any() or ilike search within the concept_tags array
        query = query.filter(CodingQuestion.concept_tags.contains([topic]))

    query.count()
    questions = (
        query.order_by(CodingQuestion.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return questions


@router.get("/questions/{question_id}", response_model=CodingQuestionResponse)
def get_coding_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Was UNAUTHENTICATED — anyone could read any customer's question by id."""
    question = db.query(CodingQuestion).filter(CodingQuestion.id == question_id).first()
    return assert_same_super_org(question, current_user, db, "Question")


@router.post("/evaluate", response_model=AIResponseEnvelope)
async def evaluate_code(
    request: CodingAttemptCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Pure AI evaluation endpoint.
    1. Fetches question details.
    2. Runs LangGraph-based AI evaluation (No Sandbox).
    3. Persists the attempt to database.
    4. Returns comprehensive AI feedback.
    """
    question = await db.get(CodingQuestion, request.coding_question_id)
    assert_same_super_org(question, current_user, db, "Question")

    # ── AI EVALUATION PIPELINE ──────────────────────────────────────────────
    try:
        eval_result_envelope = run_evaluation_graph(
            question_title=question.title,
            question_description=question.description,
            language=request.language,
            code_submitted=request.submitted_code,
            evaluation_criteria=question.evaluation_criteria,
            sample_solution=question.sample_solution,
            topic=question.concept_tags[0] if question.concept_tags else "General",
            mentor_evaluation_criteria=question.expected_approach,
        )

        ai_data = eval_result_envelope["data"]["evaluation"]
        is_correct = ai_data.get("is_correct", False)
        score = ai_data.get("score", 0)

        # ── HONESTY: AI review, NOT sandboxed execution ──────────────────────
        # This platform does not run submissions against test cases (no sandbox).
        # `is_correct`/`score` are an AI judgment. We therefore NEVER present a
        # "N/N tests passed" count, and we label the result clearly so learners and
        # mentors are not misled. (The old guardrail checked a `test_cases_passed`
        # field the AI never returns — it was dead code and is removed.)
        _tc_rows = await db.execute(
            select(CodingTestCase).where(
                CodingTestCase.coding_question_id == question.id
            )
        )
        actual_test_cases = _tc_rows.scalars().all()
        ai_data["ai_assessed"] = True
        ai_data["test_cases_total"] = len(actual_test_cases)
        ai_data["feedback"] = (ai_data.get("feedback") or "") + (
            "\n\n[AI-assessed: your code was reviewed by AI, not executed against "
            "test cases. Treat this result as guidance, not a verified test run.]"
        )

        # ── PERSISTENCE ───────────────────────────────────────────────────────
        _hint_rows = await db.execute(
            select(func.count())
            .select_from(CodingHint)
            .where(
                CodingHint.coding_question_id == question.id,
                CodingHint.user_id == current_user["id"],
            )
        )
        hints_used = _hint_rows.scalar_one()

        attempt = CodingAttempt(
            organization_id=caller_org_id(current_user),
            coding_question_id=question.id,
            user_id=current_user["id"],
            submitted_code=request.submitted_code,
            language=request.language,
            is_correct=is_correct,
            score=score,
            ai_feedback=ai_data.get("feedback"),
            ai_suggestions=json.dumps(ai_data.get("suggestions", [])),
            rubric_json=json.dumps(ai_data.get("rubric", {})),
            time_spent_seconds=request.time_spent_seconds or 0,
            execution_time_ms=eval_result_envelope.get("execution_time_ms", 0),
            hints_used=hints_used,
            overall_result="correct" if is_correct else "wrong",
            leaderboard_eligible=True,
            is_verified=False,
        )
        db.add(attempt)
        await db.commit()
        await db.refresh(attempt)

        # Bug 22: record this attempt against any mandatory coding assignment so
        # attempts_used advances (previously only quizzes updated completion).
        try:
            from services.assignment_service import update_assignment_completion

            await db.run_sync(
                lambda sync_db: update_assignment_completion(
                    db=sync_db,
                    user_id=current_user["id"],
                    coding_question_id=question.id,
                    score=int(score),
                    total=100,
                )
            )
        except Exception as e:
            logger.warning(f"Coding assignment completion update failed: {e}")

        # Proactive Intelligence Cache Invalidation (STRAT-CACHE-SYNC)
        try:
            user_id = current_user.get("id") or current_user.get("sub")
            if user_id:
                await cache_manager.invalidate(f"user_vectors:{user_id}")
                await cache_manager.invalidate(f"user_intel:{user_id}")
                await cache_manager.invalidate(f"user_atlas:{user_id}")
                logger.info(f"Sync: Intelligence cache purged for user {user_id}")
        except Exception as e:
            logger.warning(f"Sync: Cache purge failed: {e}")

        # Append database ID to response
        eval_result_envelope["data"]["attempt_id"] = attempt.id
        return eval_result_envelope

    except Exception as e:
        logger.error(f"Evaluation pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


@router.post("/hint", response_model=AIResponseEnvelope)
def get_coding_hint(
    request: CodingHintRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    AI-powered progressive hint generation.
    Checks for existing hints first to provide progression (Level 1 -> 2 -> 3).
    """
    question = (
        db.query(CodingQuestion)
        .filter(CodingQuestion.id == request.coding_question_id)
        .first()
    )
    assert_same_super_org(question, current_user, db, "Question")

    # Determine next hint level
    previous_hints_count = (
        db.query(CodingHint)
        .filter(
            CodingHint.coding_question_id == question.id,
            CodingHint.user_id == current_user["id"],
        )
        .count()
    )

    requested_level = min(3, previous_hints_count + 1)

    # ── AI HINT PIPELINE ────────────────────────────────────────────────────
    try:
        hint_envelope = run_hint_graph(
            question_title=question.title,
            question_description=question.description,
            hint_level=requested_level,
            user_code=request.user_code or "",
            language=request.language or "python",
            topic=question.concept_tags[0] if question.concept_tags else "General",
        )

        hint_data = hint_envelope["data"]

        # Persist hint request
        hint_record = CodingHint(
            coding_question_id=question.id,
            user_id=current_user["id"],
            hint_text=hint_data["hint_text"],
            hint_level=hint_data["hint_level"],
        )
        db.add(hint_record)
        db.commit()

        return hint_envelope

    except Exception as e:
        logger.error(f"Hint pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate hint")


@router.get("/attempts/my", response_model=List[CodingAttemptResponse])
def get_my_attempts(
    question_id: Optional[int] = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    query = scope_to_org(
        db.query(CodingAttempt).filter(CodingAttempt.user_id == current_user["id"]),
        CodingAttempt,
        current_user,
    )
    if question_id:
        query = query.filter(CodingAttempt.coding_question_id == question_id)

    return query.order_by(desc(CodingAttempt.attempted_at)).limit(limit).all()


@router.get("/attempts/{attempt_id}", response_model=CodingAttemptResponse)
def get_attempt_detail(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    attempt = db.query(CodingAttempt).filter(CodingAttempt.id == attempt_id).first()
    # Tenant check FIRST: the role check below grants Mentor/LDAdmin access to "all"
    # attempts, which without this meant all attempts in EVERY organization —
    # the same IDOR already fixed on the quiz side.
    assert_same_org(attempt, current_user, "Attempt")

    if attempt.user_id != current_user["id"] and current_user["role"] not in [
        "LDAdmin",
        "Mentor",
    ]:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this attempt"
        )

    return attempt


@router.post("/attempts/{attempt_id}/verify")
def verify_coding_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Verify a coding attempt. restricted to LDAdmin or Mentor roles.
    """
    if current_user.get("role") not in ["LDAdmin", "Mentor"]:
        raise HTTPException(status_code=403, detail="Not authorized to verify attempts")

    attempt = db.query(CodingAttempt).filter(CodingAttempt.id == attempt_id).first()
    assert_same_org(attempt, current_user, "Attempt")

    attempt.is_verified = True
    db.commit()
    return {"message": "Attempt verified successfully", "attempt_id": attempt_id}


from pydantic import BaseModel, Field  # noqa: E402


class _TestCaseIn(BaseModel):
    input_data: str = ""
    expected_output: str = ""
    is_public: bool = True
    weight: int = 1


class CodingQuestionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    language: str = "python"
    sample_solution: str = ""
    expected_approach: Optional[str] = None
    evaluation_criteria: List[str] = Field(default_factory=list)
    difficulty: str = "Medium"
    course_id: Optional[int] = None
    is_public: bool = True
    concept_tags: Optional[List[str]] = None
    test_cases: List[_TestCaseIn] = Field(default_factory=list)


@router.post("/questions")
def create_coding_question(
    body: CodingQuestionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a coding question (was missing → the L&D wizard 405'd)."""
    if current_user.get("role") not in ["LDAdmin", "Mentor", "GroupAdmin"]:
        raise HTTPException(403, "Not authorized to create coding questions")

    author_id = current_user.get("id")
    if author_id is None:
        author_id = current_user.get("sub")
    if author_id is None:
        raise HTTPException(401, "Unable to resolve the authoring user.")

    q = CodingQuestion(
        title=body.title,
        description=body.description or body.title,
        language=body.language or "python",
        sample_solution=body.sample_solution or "",
        expected_approach=body.expected_approach,
        evaluation_criteria=body.evaluation_criteria
        or ["Functionality", "Logic", "Clean Code"],
        difficulty=body.difficulty or "Medium",
        concept_tags=body.concept_tags,
        course_id=body.course_id,
        created_by=int(author_id),
        organization_id=caller_org_id(current_user),
        super_organization_id=caller_super_org_id(current_user, db),
    )
    db.add(q)
    db.flush()  # get q.id for the test cases
    for tc in body.test_cases:
        if tc.input_data or tc.expected_output:
            db.add(
                CodingTestCase(
                    coding_question_id=q.id,
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    is_public=tc.is_public,
                    weight=tc.weight or 1,
                )
            )
    db.commit()
    db.refresh(q)
    return {"id": q.id, "title": q.title, "success": True}


@router.delete("/questions/{question_id}")
def delete_coding_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Hard delete a coding question and its related attempts/hints.
    """
    if current_user.get("role") not in ["LDAdmin", "Mentor"]:
        raise HTTPException(
            status_code=403, detail="Not authorized to delete coding questions"
        )

    question = db.query(CodingQuestion).filter(CodingQuestion.id == question_id).first()
    assert_same_super_org(question, current_user, db, "Question")

    # Clean up associated attempts and hints first to satisfy constraints
    db.query(CodingAttempt).filter(
        CodingAttempt.coding_question_id == question_id
    ).delete()
    db.query(CodingHint).filter(CodingHint.coding_question_id == question_id).delete()

    db.delete(question)
    db.commit()
    return {"message": "Coding question deleted successfully", "id": question_id}
