"""Guards that write/admin handlers keyed on a resource id enforce a tenant check.

Earlier tenancy work covered read/list surfaces; the WRITE/admin side still relied
on role-only checks (`require_admin`/`require_ldadmin` gate the ROLE, not the org).
Spot-verified live gaps included: delete another org's question bank, impersonate
another org's group, read another org's attempt. All now enforce a tenant check.

This AST guard fails if one of these handlers is added/edited to drop the check.
"""

import ast
import pathlib

import pytest

ROUTERS = pathlib.Path(__file__).resolve().parent.parent / "routers"

# (file, handler) -> must call one of the scope checks
GUARDED = [
    ("quiz.py", "get_bank"), ("quiz.py", "update_bank_metadata"), ("quiz.py", "delete_bank"),
    ("quiz.py", "get_bank_questions"), ("quiz.py", "get_leaderboard"), ("quiz.py", "publish_bank"),
    ("quiz.py", "clone_bank"), ("quiz.py", "update_question"), ("quiz.py", "delete_question"),
    ("quiz.py", "get_courses"), ("quiz.py", "subscribe_group"),
    ("resources.py", "update_resource_metadata"), ("resources.py", "delete_resource"),
    ("resources.py", "mark_attempt_reviewed"), ("resources.py", "add_resource_comment"),
    ("resources.py", "get_resource_comments"),
    ("mentor.py", "get_attempt_comments"), ("mentor.py", "get_group_students"),
    ("mentor.py", "get_group_stats"), ("mentor.py", "get_group_activity_feed"),
    ("mentor.py", "get_group_ai_summary"),
    ("auth.py", "impersonate_group"), ("auth.py", "bulk_create_users"), ("auth.py", "discovery_users"),
    ("assignment.py", "get_group_assignments"),
]

SCOPE_CALLS = {
    "assert_same_org", "assert_same_super_org", "assert_group_in_org", "assert_batch_in_org",
    "scope_to_org", "scope_to_super_org",
}


def _calls_in(fname, handler):
    tree = ast.parse((ROUTERS / fname).read_text())
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == handler:
            return {
                c.func.id
                for c in ast.walk(n)
                if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
            }
    return None


@pytest.mark.parametrize("fname,handler", GUARDED, ids=lambda x: x if isinstance(x, str) else "")
def test_write_handler_has_a_tenant_check(fname, handler):
    calls = _calls_in(fname, handler)
    assert calls is not None, f"{fname}::{handler} not found — renamed?"
    assert calls & SCOPE_CALLS, (
        f"{fname}::{handler} takes a resource id but calls no tenant scope check "
        f"({', '.join(sorted(SCOPE_CALLS))}). This is the cross-tenant write class."
    )
