"""Unit tests for gradebook + item analysis (pure, no network)."""
from services.analytics import compute_gradebook, compute_item_analysis


def test_gradebook_best_score_per_user():
    rows = [
        {"user_id": 1, "user_name": "A", "score": 6, "total": 10},
        {"user_id": 1, "user_name": "A", "score": 9, "total": 10},  # best
        {"user_id": 2, "user_name": "B", "score": 5, "total": 10},
    ]
    gb = compute_gradebook(rows)
    a = next(g for g in gb if g["user_id"] == 1)
    assert a["best_pct"] == 90.0 and a["attempts"] == 2
    # sorted best first
    assert gb[0]["user_id"] == 1


def test_item_analysis_difficulty_and_discrimination():
    # 4 attempts; q1 everyone right (too easy), q2 only high scorers right (good discrimination)
    attempts = [
        {"total": 2, "items": {1: True, 2: True}},   # top
        {"total": 2, "items": {1: True, 2: True}},    # top
        {"total": 1, "items": {1: True, 2: False}},   # bottom
        {"total": 0, "items": {1: True, 2: False}},   # bottom
    ]
    res = {r["question_id"]: r for r in compute_item_analysis(attempts)}
    assert res[1]["difficulty"] == 1.0 and res[1]["flag"] == "too_easy"
    assert res[2]["difficulty"] == 0.5
    assert res[2]["discrimination"] > 0.5  # top get it, bottom don't


def test_item_analysis_empty():
    assert compute_item_analysis([]) == []
