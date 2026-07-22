"""Assessment analytics — gradebook aggregation + classical item analysis.

Pure functions (no DB/ORM) so they are trivially unit-testable; routers feed them
structured attempt data pulled from the DB.
"""
from __future__ import annotations


def compute_item_analysis(attempts: list[dict]) -> list[dict]:
    """Classical item analysis.

    `attempts`: [{"total": float, "items": {question_id: is_correct_bool}}].
    Returns per-question: difficulty (p-value = fraction correct), discrimination
    (upper-lower index = correct-rate in top third minus bottom third by total
    score), and a quality flag.
    """
    if not attempts:
        return []

    ordered = sorted(attempts, key=lambda a: a.get("total", 0) or 0)
    n = len(ordered)
    cut = max(1, n // 3)
    lower, upper = ordered[:cut], ordered[-cut:]

    qids: set = set()
    for a in attempts:
        qids.update((a.get("items") or {}).keys())

    def _rate(group, qid):
        vals = [g["items"][qid] for g in group if qid in (g.get("items") or {})]
        return (sum(1 for v in vals if v) / len(vals)) if vals else 0.0

    out = []
    for qid in qids:
        vals = [a["items"][qid] for a in attempts if qid in (a.get("items") or {})]
        if not vals:
            continue
        difficulty = sum(1 for v in vals if v) / len(vals)
        discrimination = _rate(upper, qid) - _rate(lower, qid)
        if difficulty > 0.95:
            flag = "too_easy"
        elif difficulty < 0.20:
            flag = "too_hard"
        elif discrimination < 0.10:
            flag = "poor_discrimination"
        else:
            flag = "ok"
        out.append(
            {
                "question_id": qid,
                "responses": len(vals),
                "difficulty": round(difficulty, 3),
                "discrimination": round(discrimination, 3),
                "flag": flag,
            }
        )
    # worst discrimination first — those are the questions to review.
    return sorted(out, key=lambda x: x["discrimination"])


def compute_gradebook(rows: list[dict]) -> list[dict]:
    """Per-user best score from raw attempt rows.

    `rows`: [{"user_id", "user_name", "score", "total", "attempted_at"}].
    Returns one row per user with best score, best %, and attempt count.
    """
    by_user: dict = {}
    for r in rows:
        uid = r.get("user_id")
        pct = (r["score"] / r["total"] * 100.0) if r.get("total") else 0.0
        cur = by_user.get(uid)
        entry = {
            "user_id": uid,
            "user_name": r.get("user_name"),
            "best_score": r.get("score", 0),
            "best_total": r.get("total", 0),
            "best_pct": round(pct, 1),
            "attempts": 1,
        }
        if not cur:
            by_user[uid] = entry
        else:
            cur["attempts"] += 1
            if pct > cur["best_pct"]:
                cur["best_score"] = r.get("score", 0)
                cur["best_total"] = r.get("total", 0)
                cur["best_pct"] = round(pct, 1)
    return sorted(by_user.values(), key=lambda x: -x["best_pct"])
