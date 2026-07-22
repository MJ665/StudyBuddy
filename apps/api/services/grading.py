"""Multi-type question grading dispatch.

Objective types (mcq_single, true_false, mcq_multi) are graded deterministically.
Free-text types (short_answer, essay) are graded by AI against a model answer +
optional rubric; a mentor override is applied by the caller. Every grader returns
a normalized GradeResult so attempt persistence stays consistent across types.

Questions are passed as plain dicts (use `question_to_dict` for ORM rows) so this
module has no DB/ORM dependency and is trivially unit-testable.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("grading")

OBJECTIVE_TYPES = {"mcq_single", "true_false", "mcq_multi"}
FREE_TEXT_TYPES = {"short_answer", "essay"}
PASS_FRACTION = 0.7


@dataclass
class GradeResult:
    is_correct: bool
    fraction: float          # 0..1 of the question's points earned
    points_earned: float
    max_points: float
    method: str              # "objective" | "ai" | "pending"
    rationale: str = ""
    needs_review: bool = False


def question_to_dict(q: Any) -> dict:
    """Build a grader-friendly dict from an ORM Question (or pass a dict through)."""
    if isinstance(q, dict):
        return q
    return {
        "question": getattr(q, "question", ""),
        "question_type": getattr(q, "question_type", "mcq_single") or "mcq_single",
        "options": getattr(q, "options", None) or [],
        "answer": getattr(q, "answer", None),
        "correct_options": getattr(q, "correct_options", None),
        "model_answer": getattr(q, "model_answer", None),
        "rubric": getattr(q, "rubric", None),
        "points": getattr(q, "points", 1) or 1,
    }


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _idx_of(value: Any, options: list) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    for i, o in enumerate(options):
        if _norm(o) == _norm(value):
            return i
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def grade_objective(question: dict, user_answer: Any) -> GradeResult:
    qtype = question.get("question_type", "mcq_single")
    max_points = float(question.get("points", 1) or 1)
    options = question.get("options") or []

    if qtype == "mcq_multi":
        correct = set(question.get("correct_options") or [])
        selected = user_answer if isinstance(user_answer, list) else [user_answer]
        sel_idx = {_idx_of(v, options) for v in selected}
        sel_idx.discard(None)
        if not correct:
            # No defined correct set — cannot grade objectively; defer to mentor.
            return GradeResult(False, 0.0, 0.0, max_points, "pending", needs_review=True)
        is_correct = sel_idx == correct
        frac = 1.0 if is_correct else 0.0
        return GradeResult(is_correct, frac, frac * max_points, max_points, "objective")

    # true_false and mcq_single both compare against the single `answer`.
    is_correct = _norm(user_answer) == _norm(question.get("answer"))
    frac = 1.0 if is_correct else 0.0
    return GradeResult(is_correct, frac, frac * max_points, max_points, "objective")


async def grade_free_text(question: dict, user_answer: Any) -> GradeResult:
    from services.kt_engine import gemini

    max_points = float(question.get("points", 1) or 1)
    ans = str(user_answer or "").strip()
    if not ans:
        return GradeResult(False, 0.0, 0.0, max_points, "ai", rationale="No answer provided.")

    model_answer = question.get("model_answer") or ""
    rubric = question.get("rubric")
    prompt = (
        "Grade the student's answer on a 0-100 scale using the model answer and rubric. "
        "Be fair and rigorous; reward correct, complete, clear answers.\n"
        f"QUESTION: {question.get('question', '')}\n"
        f"MODEL ANSWER: {model_answer or '(none provided — grade on general correctness)'}\n"
        f"RUBRIC: {json.dumps(rubric) if rubric else '(none — accuracy, completeness, clarity)'}\n"
        f"STUDENT ANSWER: {ans}\n"
        'Return ONLY JSON: {"score": <0-100 integer>, "rationale": "<one short paragraph>"}'
    )
    try:
        data = await gemini.generate_json(
            prompt, system="You are a fair, rigorous exam grader. Return ONLY JSON."
        )
        score = max(0.0, min(100.0, float(data.get("score", 0))))
        frac = score / 100.0
        return GradeResult(
            frac >= PASS_FRACTION,
            frac,
            round(frac * max_points, 3),
            max_points,
            "ai",
            rationale=str(data.get("rationale", ""))[:1000],
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("free-text grading failed: %s", e)
        return GradeResult(
            False, 0.0, 0.0, max_points, "ai",
            rationale="Auto-grading unavailable; needs mentor review.",
            needs_review=True,
        )


async def grade_question(question: dict, user_answer: Any) -> GradeResult:
    """Dispatch to the right grader based on question_type."""
    if question.get("question_type", "mcq_single") in FREE_TEXT_TYPES:
        return await grade_free_text(question, user_answer)
    return grade_objective(question, user_answer)
