"""Guardrail: no router calls a name that isn't resolvable at runtime.

`from X import *` silently DROPS single-underscore names (_audit,
_require_mentor_plus, ...). When the KT routers were split into
`_shared`/`documents_shared`/`insights_shared`, every leaf router that
star-imported those modules lost the underscore helpers — so endpoints like
deprecate/endorse/ai-suggest raised NameError *at call time* (invisible to
import checks and to tests that don't hit that exact route). A later split also
moved `get_comparative_analytics` out from under `get_lnd_stats`.

This test parses every router, imports it, and asserts that every bare function
call resolves to a local name, an import, the module's runtime namespace (which
includes star-imports), or a builtin. It fails loudly on the whole class of
latent call-time NameErrors.
"""

import ast
import builtins
import importlib
import pathlib

import pytest

API_ROOT = pathlib.Path(__file__).resolve().parent.parent
BUILTINS = set(dir(builtins)) | {"self", "cls"}


def _router_modules():
    for base in ("modules", "routers"):
        root = API_ROOT / base
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if base == "modules" and path.parent.name != "routers":
                continue
            rel = path.relative_to(API_ROOT)
            yield path, ".".join(rel.with_suffix("").parts)


def _unresolved(path: pathlib.Path, modname: str):
    tree = ast.parse(path.read_text())
    local = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            local.add(n.name)
            local.update(a.arg for a in n.args.args + n.args.kwonlyargs)
            if n.args.vararg:
                local.add(n.args.vararg.arg)
            if n.args.kwarg:
                local.add(n.args.kwarg.arg)
        elif isinstance(n, ast.ImportFrom):
            local.update(a.asname or a.name for a in n.names)
        elif isinstance(n, ast.Import):
            local.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, ast.Assign):
            local.update(t.id for t in n.targets if isinstance(t, ast.Name))
    mod = importlib.import_module(modname)
    ns = set(dir(mod))
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    return sorted(c for c in called if c not in local and c not in ns and c not in BUILTINS)


@pytest.mark.integration
def test_no_router_calls_an_unresolvable_name():
    offenders = {}
    for path, modname in _router_modules():
        bad = _unresolved(path, modname)
        if bad:
            offenders[str(path.relative_to(API_ROOT))] = bad
    assert not offenders, "Call-time NameError risk (star-import dropped names?):\n" + "\n".join(
        f"  {f}: {', '.join(names)}" for f, names in sorted(offenders.items())
    )
