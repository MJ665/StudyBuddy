"""Frontend↔backend contract check.

Every path `ApiService.ts` calls must exist in the FastAPI route table. Nine calls
were pointing at routes that did not exist — segments swapped
(`/kt/explorer/graph/neighborhood/{id}` vs `/kt/explorer/graph/{id}/neighborhood`),
renamed (`/code/my-attempts` vs `/code/attempts/my`), or never implemented. They
failed silently at runtime as 404s.

This test compares the two sides directly, so the drift becomes a build failure.
"""


import pathlib
import re

import pytest

API_ROOT = pathlib.Path(__file__).resolve().parent.parent
API_SERVICE = API_ROOT.parent / "web-next" / "src" / "services" / "ApiService.ts"


def _backend_routes() -> set[str]:
    import main

    return {
        re.sub(r"\{[^}]+\}", "{x}", p).rstrip("/")
        for p in (getattr(r, "path", "") for r in main.app.routes)
        if p
    }


def _frontend_paths() -> set[str]:
    src = API_SERVICE.read_text()
    found: set[str] = set()
    # backtick template literals may contain quotes inside ${...}
    for m in re.finditer(r"(?:this\.request|this\.getEventSource)\(\s*`(/[^`]*)`", src):
        found.add(m.group(1))
    for m in re.finditer(r"(?:this\.request|this\.getEventSource)\(\s*'(/[^']*)'", src):
        found.add(m.group(1))
    return found


def _normalize(path: str) -> str:
    """A `${...}` right after '/' is a path parameter; one glued onto a segment
    (`/kt/projects${params}`) is a query-string suffix."""
    path = re.sub(r"(?<=/)\$\{[^}]*\}", "{x}", path)
    path = re.sub(r"(?<!/)\$\{[^}]*\}.*$", "", path)
    path = path.split("?")[0]
    if not path.startswith("/api"):
        path = "/api" + path
    return path.rstrip("/") or "/"


@pytest.mark.skipif(not API_SERVICE.exists(), reason="frontend not present")
def test_every_frontend_call_hits_a_real_backend_route():
    backend = _backend_routes()
    unmatched = sorted(
        (raw, _normalize(raw))
        for raw in _frontend_paths()
        if _normalize(raw) not in backend
    )
    assert not unmatched, "ApiService calls with no matching backend route:\n" + "\n".join(
        f"  {raw}  ->  {norm}" for raw, norm in unmatched
    )


@pytest.mark.skipif(not API_SERVICE.exists(), reason="frontend not present")
def test_contract_check_actually_sees_both_sides():
    """Guards the guard: a broken extractor would make the test vacuously pass."""
    assert len(_backend_routes()) > 100
    assert len(_frontend_paths()) > 100
