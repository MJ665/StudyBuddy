"""Detect route shadowing: an earlier-registered dynamic route (/x/{id})
swallowing a later static sibling (/x/analytics). FastAPI matches in
registration order, so after any router split this must stay clean.

Run: ENVIRONMENT=development DEBUG=True GEMINI_API_KEY=dummy SECRET_KEY=dummy \
     .venv/bin/python scripts/check_route_shadowing.py
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main  # noqa: E402

PARAM = re.compile(r"\{[^}]+\}")


def to_regex(path: str) -> re.Pattern:
    return re.compile("^" + PARAM.sub(r"[^/]+", re.escape(path).replace(r"\{", "{").replace(r"\}", "}")) + "$")


routes = []
for r in main.app.routes:
    if hasattr(r, "methods") and getattr(r, "path", None):
        for m in r.methods or []:
            routes.append((m, r.path))

shadowed = []
for i, (m1, p1) in enumerate(routes):
    if "{" not in p1:
        continue
    rx = to_regex(p1)
    for m2, p2 in routes[i + 1:]:
        if m2 == m1 and "{" not in p2 and rx.match(p2):
            shadowed.append((f"{m1} {p2}", f"shadowed by earlier {m1} {p1}"))

if shadowed:
    print("SHADOWING DETECTED:")
    for s in shadowed:
        print("  ", *s)
    sys.exit(1)
print(f"no shadowing among {len(routes)} routes")
