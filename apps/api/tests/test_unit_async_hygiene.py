"""Catches half-migrated async handlers.

The dangerous state during the sync→async migration is a handler whose signature
says `AsyncSession` but whose body still calls `db.query(...)` / `db.commit()`.
That compiles, imports, and passes any test that doesn't execute the endpoint —
then raises `MissingGreenlet` or silently fails to persist at runtime.

This scans the AST of every router and fails on that mismatch.
"""

import ast
import pathlib

import pytest

# routers/ aggregators+stubs plus the modular router files (Phase 3/5a moves).
_API = pathlib.Path(__file__).resolve().parent.parent
ROUTERS = sorted((_API / "routers").glob("*.py")) + sorted(
    (_API / "modules").glob("*/routers/*.py")
)

# `db.add()` is a plain synchronous method on AsyncSession — legitimate.
SYNC_ONLY_SESSION_CALLS = {"query", "commit", "refresh", "delete", "flush", "rollback"}


def _annotation_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _async_session_handlers(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        anns = {_annotation_name(a.annotation) for a in node.args.args}
        if "AsyncSession" in anns:
            yield node


def _sync_db_calls(func):
    """`db.query(...)` etc. called directly on the session inside `func`."""
    for node in ast.walk(func):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in SYNC_ONLY_SESSION_CALLS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "db"
        ):
            # `await db.commit()` is correct; only bare calls are a problem.
            yield node


def _awaited_line_numbers(tree):
    return {
        node.value.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Await) and hasattr(node.value, "lineno")
    }


@pytest.mark.parametrize("router", ROUTERS, ids=lambda p: p.name)
def test_async_handlers_do_not_use_sync_session_calls(router):
    tree = ast.parse(router.read_text())
    awaited = _awaited_line_numbers(tree)

    offenders = []
    for func in _async_session_handlers(tree):
        for call in _sync_db_calls(func):
            if call.lineno in awaited:
                continue  # `await db.commit()` — fine
            offenders.append(f"{router.name}:{call.lineno} db.{call.func.attr}() in {func.name}()")

    assert not offenders, (
        "AsyncSession handler still using synchronous session calls "
        "(raises MissingGreenlet at runtime):\n  " + "\n  ".join(offenders)
    )


def test_scan_actually_finds_async_handlers():
    """Guards the guard — a broken matcher would make every case vacuously pass."""
    total = sum(len(list(_async_session_handlers(ast.parse(r.read_text())))) for r in ROUTERS)
    assert total > 20, f"expected many AsyncSession handlers, found {total}"


def test_cache_decorator_supports_sync_and_async_handlers():
    """`@cache_manager.cached` wraps BOTH `def` and `async def` endpoints.

    It used to do a bare `await func(...)`, so every SYNC handler it decorated
    raised "object dict can't be used in 'await' expression" and returned 500.
    Five endpoints were affected (admin audit/email-logs/security-stats,
    intel hierarchy, quiz leaderboard) and no test caught it, because none of
    them executed the endpoint.
    """
    import inspect

    import cache_manager

    src = inspect.getsource(cache_manager.CacheManager.cached)
    assert "iscoroutinefunction" in src, "cache decorator must detect sync handlers"
    assert "run_in_threadpool" in src, "sync handlers must not run on the event loop"


@pytest.mark.parametrize("router", ROUTERS, ids=lambda p: p.name)
def test_sync_handlers_are_not_awaited_by_decorators(router):
    """A sync `def` endpoint may only carry decorators that tolerate sync functions."""
    tree = ast.parse(router.read_text())
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):  # sync only
            continue
        for dec in node.decorator_list:
            text = ast.unparse(dec)
            if "cache_manager.cached" in text:
                # allowed now that the decorator handles sync — assert it still does
                import inspect

                import cache_manager

                if "iscoroutinefunction" not in inspect.getsource(
                    cache_manager.CacheManager.cached
                ):
                    offenders.append(f"{router.name}:{node.lineno} {node.name}")
    assert not offenders, "sync handlers awaited by a decorator: " + ", ".join(offenders)
