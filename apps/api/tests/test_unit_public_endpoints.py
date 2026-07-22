"""Guards which endpoints may be reached WITHOUT authentication.

Five endpoints (`/org/organizations`, `/org/departments`, `/org/verticals`,
`/org/batches`, plus the coding portal's question routes) had no `current_user`
dependency, so any anonymous caller received every customer's name and internal
hierarchy — a customer-list disclosure in a multi-tenant product.

Anonymous access is now an explicit allow-list. Adding a new public endpoint is a
deliberate act that must be recorded here, with a reason.
"""

import ast
import pathlib

import pytest

ROUTERS = pathlib.Path(__file__).resolve().parent.parent / "routers"

# path-suffix -> why it is intentionally public
ALLOWED_ANONYMOUS = {
    # auth flows must work before a token exists
    "/login", "/refresh", "/logout", "/forgot-password", "/reset-password",
    "/superadmin/login", "/sso/login", "/sso/callback",
    # the login form is a group dropdown, then a name dropdown
    "/groups", "/groups/register", "/public/groups/{group_id}/users",
    # public onboarding for prospective customers
    "/signup", "/verify", "/complete",
    # public profile pages
    "/{slug}", "/profile/{slug}",
    # static vocabularies / config — no tenant data
    "/registry/doc-types", "/registry/complexities", "/registry/access-levels",
    "/registry/sensitivities", "/config", "/config/languages", "/languages",
    "/topics",
    # signature-verified webhook (see routers/billing.py)
    "/webhook",
    # signed, expiring link — the browser cannot send a bearer token via window.open
    "/attempts/{attempt_id}/certificate/download",
    # SSE stream authenticates via query token
    "/notifications/stream",
}


def _anonymous_endpoints():
    out = []
    # routers/ (monoliths + aggregators) plus the Phase-3 modular router files.
    paths = sorted(ROUTERS.glob("*.py")) + sorted(
        (ROUTERS.parent / "modules").glob("*/routers/*.py")
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decs = [
                d for d in node.decorator_list
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
                and isinstance(d.func.value, ast.Name) and d.func.value.id == "router"
            ]
            if not decs:
                continue
            params = {a.arg for a in node.args.args}
            if {"current_user", "x_kt_key"} & params:
                continue
            route = decs[0].args[0].value if decs[0].args else "?"
            out.append((path.name, node.name, route))
    return out


def test_no_unapproved_anonymous_endpoints():
    unexpected = [
        f"{f}::{fn} -> {route}"
        for f, fn, route in _anonymous_endpoints()
        if route not in ALLOWED_ANONYMOUS
    ]
    assert not unexpected, (
        "Endpoint(s) reachable WITHOUT authentication and not on the allow-list:\n  "
        + "\n  ".join(unexpected)
        + "\n\nIf this is intentional, add the route to ALLOWED_ANONYMOUS with a reason."
    )


def test_scan_finds_the_known_public_endpoints():
    """Guards the guard — a broken matcher would make this vacuously pass."""
    assert len(_anonymous_endpoints()) > 10


@pytest.mark.parametrize("route", ["/organizations", "/departments", "/verticals", "/batches"])
def test_org_hierarchy_is_not_anonymous(route):
    """These leaked every customer's structure to anonymous callers."""
    anon = {r for _, _, r in _anonymous_endpoints()}
    assert route not in anon


def test_coding_portal_questions_require_auth():
    anon = {r for _, _, r in _anonymous_endpoints()}
    assert "/questions" not in anon
    assert "/questions/{question_id}" not in anon
