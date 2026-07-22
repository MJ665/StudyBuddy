"""Guards that interaction.py endpoints keyed on a non-user id are tenant-checked.

10 endpoints take a question_id / bank_id / discussion_id straight from the URL.
Earlier these were ASSERTED to be "inherently tenant-safe because they scope by
user_id" — but that was wrong: a caller could read or act on another customer's
question/bank/discussion by id (the same IDOR class fixed on the quiz and coding
portals). Live cross-tenant probe now returns 404 for a foreign caller.

This AST guard fails if such a handler is added or edited to skip the scope check.
"""

import ast
import pathlib

import pytest

INTERACTION = pathlib.Path(__file__).resolve().parent.parent / "routers" / "interaction.py"

# handler -> the tenant-key parameter it must validate
GUARDED = {
    "report_question": "question_id",
    "get_discussions": "question_id",
    "get_global_discussions": "bank_id",
    "add_discussion": "question_id",
    "vote_discussion": "discussion_id",
    "delete_discussion": "discussion_id",
    "toggle_bookmark": "question_id",
    "get_bookmark_status": "question_id",
}

SCOPE_CALLS = {
    "_require_question_scope",
    "_require_question_scope_async",
    "_require_discussion_scope",
    "assert_same_super_org",
    "assert_same_super_org_async",
}


def _handler_nodes():
    tree = ast.parse(INTERACTION.read_text())
    return {
        n.name: n
        for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in GUARDED
    }


HANDLERS = _handler_nodes()


@pytest.mark.parametrize("name", sorted(GUARDED))
def test_handler_exists(name):
    assert name in HANDLERS, f"{name} not found — did it get renamed?"


@pytest.mark.parametrize("name", sorted(GUARDED))
def test_handler_calls_a_scope_check(name):
    node = HANDLERS[name]
    called = {
        c.func.id
        for c in ast.walk(node)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
    }
    assert called & SCOPE_CALLS, (
        f"{name} takes {GUARDED[name]} from the URL but calls no tenant scope check "
        f"({', '.join(sorted(SCOPE_CALLS))}). This is the IDOR class fixed elsewhere."
    )


def test_scope_helpers_use_super_org_for_content():
    """Questions/banks are shared CONTENT, so they scope by SUPER-org (a sibling
    business unit may legitimately share the bank), not organization."""
    src = INTERACTION.read_text()
    assert "assert_same_super_org" in src
