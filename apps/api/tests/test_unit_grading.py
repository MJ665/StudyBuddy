"""Unit tests for the multi-type grading dispatch (objective types — no network)."""
import pytest

from services.grading import grade_objective, grade_question


def _q(**kw):
    base = {"question_type": "mcq_single", "options": [], "answer": None,
            "correct_options": None, "points": 1, "question": "q"}
    base.update(kw)
    return base


def test_mcq_single_correct():
    q = _q(question_type="mcq_single", options=["A", "B", "C"], answer="B")
    r = grade_objective(q, "B")
    assert r.is_correct and r.fraction == 1.0 and r.points_earned == 1.0


def test_mcq_single_incorrect_and_case_insensitive():
    q = _q(options=["MySQL", "Postgres"], answer="MySQL")
    assert grade_objective(q, "Postgres").is_correct is False
    assert grade_objective(q, "mysql").is_correct is True  # case-insensitive


def test_true_false():
    q = _q(question_type="true_false", options=["True", "False"], answer="True")
    assert grade_objective(q, "true").is_correct is True
    assert grade_objective(q, "False").is_correct is False


def test_mcq_multi_exact_set():
    q = _q(question_type="mcq_multi", options=["A", "B", "C", "D"], correct_options=[0, 2])
    assert grade_objective(q, [0, 2]).is_correct is True
    assert grade_objective(q, ["A", "C"]).is_correct is True  # by text
    assert grade_objective(q, [0]).is_correct is False        # incomplete
    assert grade_objective(q, [0, 1, 2]).is_correct is False  # extra


def test_mcq_multi_without_correct_set_defers_to_mentor():
    q = _q(question_type="mcq_multi", options=["A", "B"], correct_options=None)
    r = grade_objective(q, [0])
    assert r.method == "pending" and r.needs_review is True


def test_points_weighting():
    q = _q(options=["A", "B"], answer="A", points=5)
    r = grade_objective(q, "A")
    assert r.max_points == 5.0 and r.points_earned == 5.0


@pytest.mark.asyncio
async def test_grade_question_dispatches_objective():
    q = _q(question_type="true_false", answer="False")
    r = await grade_question(q, "False")
    assert r.method == "objective" and r.is_correct is True


@pytest.mark.asyncio
async def test_free_text_empty_answer_scores_zero_without_ai():
    from services.grading import grade_free_text

    q = _q(question_type="short_answer", model_answer="Paris", points=10)
    r = await grade_free_text(q, "")
    assert r.points_earned == 0.0 and r.method == "ai"
