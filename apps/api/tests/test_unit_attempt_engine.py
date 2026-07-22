"""Unit tests for the unified assessment engine (Phase 3).

The engine is the ONE grading loop shared by practice quizzes and proctored
exams; these tests pin the contract both delivery modes rely on.
"""

import asyncio

from modules.assessment.services.attempt_engine import (
    decode_answer,
    grade_answer_set,
)


class Q:
    """Minimal Question stand-in (objective types grade deterministically)."""

    def __init__(self, id, answer, qtype="mcq_single", options=None,
                 difficulty="Medium", points=1):
        self.id = id
        self.question = f"Q{id}?"
        self.question_type = qtype
        self.answer = answer
        self.options = options or ["Paris", "Berlin", "Rome", "Madrid"]
        self.correct_options = [answer] if qtype == "mcq_multi" else None
        self.model_answer = None
        self.rubric = None
        self.points = points
        self.difficulty = difficulty


class TestDecodeAnswer:
    def test_json_array_string_becomes_list(self):
        assert decode_answer('["a", "b"]') == ["a", "b"]

    def test_plain_string_passes_through(self):
        assert decode_answer("Paris") == "Paris"

    def test_malformed_json_passes_through(self):
        assert decode_answer("[not json") == "[not json"


class TestGradeAnswerSet:
    def test_positional_answers_quiz_style(self):
        qs = {1: Q(1, "Paris"), 2: Q(2, "Berlin")}
        graded = asyncio.run(
            grade_answer_set(qs, [1, 2], ["Paris", "Rome"],
                             difficulty_weights={"Medium": 1.0})
        )
        assert [i.grade.is_correct for i in graded.items] == [True, False]
        assert graded.points_list == [1.0, 0.0]
        assert graded.weights_list == [1.0, 1.0]
        assert len(graded.detailed_answers) == 2

    def test_dict_answers_exam_style(self):
        qs = {1: Q(1, "Paris"), 2: Q(2, "Berlin")}
        graded = asyncio.run(
            grade_answer_set(qs, [1, 2], {"1": "Paris", "2": "Berlin"},
                             collect_details=False)
        )
        assert graded.earned_points == 2.0
        assert graded.max_points == 2.0
        assert graded.detailed_answers == []

    def test_difficulty_weighting_only_affects_weighted_totals(self):
        qs = {1: Q(1, "Paris", difficulty="Hard")}
        graded = asyncio.run(
            grade_answer_set(qs, [1], ["Paris"],
                             difficulty_weights={"Hard": 2.0, "Medium": 1.0})
        )
        assert graded.points_list == [2.0]
        assert graded.earned_points == 1.0  # raw points unaffected

    def test_unknown_question_ids_are_skipped(self):
        graded = asyncio.run(grade_answer_set({}, [99], ["x"]))
        assert graded.items == []
        assert graded.max_points == 0.0

    def test_missing_positional_answer_counts_wrong_not_crash(self):
        qs = {1: Q(1, "Paris")}
        graded = asyncio.run(grade_answer_set(qs, [1], []))
        assert graded.items[0].grade.is_correct is False

    def test_exam_multi_select_json_decode_regression(self):
        """The old exam path passed the raw '["A","B"]' string to the grader —
        the shared engine must decode it exactly like the quiz path."""
        q = Q(1, "Paris", qtype="mcq_multi")
        q.correct_options = [0, 1]  # indices of Paris, Berlin
        graded = asyncio.run(
            grade_answer_set({1: q}, [1], {"1": '["Paris", "Berlin"]'},
                             collect_details=False)
        )
        assert graded.items[0].grade.fraction > 0.0