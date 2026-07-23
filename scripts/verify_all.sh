#!/usr/bin/env bash
# StudyHub — full verification battery (plan §17). One command, all gates.
# Usage: ./scripts/verify_all.sh   (from repo root; needs apps/api/.venv + npm deps)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
API="$ROOT/apps/api"
WEB="$ROOT/apps/web-next"
PY="$API/.venv/bin/python"
ENVV="ENVIRONMENT=development DEBUG=True GEMINI_API_KEY=${GEMINI_API_KEY:-dummy} SECRET_KEY=dummysecret"
FAIL=0

step() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
gate() { if [ "$1" -ne 0 ]; then FAIL=1; printf '\033[31m✘ %s FAILED\033[0m\n' "$2"; else printf '\033[32m✔ %s\033[0m\n' "$2"; fi; }

step "backend: fast test suite"
(cd "$API" && "$PY" -m pytest -q -m "not live"); gate $? "pytest (not live)"

step "backend: app assembles + route shadowing"
(cd "$API" && env $ENVV "$PY" scripts/check_route_shadowing.py); gate $? "route shadowing"

step "backend: sync-helper-in-async sweep (must be 0)"
(cd "$API" && python3 - <<'EOF'
import ast, glob, sys
SYNC = {'assert_user_in_org','assert_same_org','assert_group_in_org','assert_batch_in_org','scope_to_org','scope_to_super_org','check_scoped_role','log_admin_action'}
hits = []
for f in glob.glob('routers/*.py') + glob.glob('modules/*/routers/*.py'):
    t = ast.parse(open(f).read())
    for fn in ast.walk(t):
        if not isinstance(fn, ast.AsyncFunctionDef): continue
        if 'AsyncSession' not in ast.dump(fn.args) and 'get_async_db' not in ast.dump(fn.args): continue
        for n in ast.walk(fn):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in SYNC:
                if any(isinstance(a, ast.Name) and a.id == 'db' for a in n.args):
                    hits.append((f, fn.name, n.func.id, n.lineno))
for h in hits: print('  OFFENDER:', h)
sys.exit(1 if hits else 0)
EOF
); gate $? "async-scope sweep"

step "backend: forbidden imports (neo4j must be gone)"
N=$(grep -rl "from neo4j\|import neo4j" --include="*.py" "$API" 2>/dev/null | grep -v ".venv\|venv\|__pycache__\|_archive" | wc -l | tr -d ' ')
[ "$N" = "0" ]; gate $? "neo4j imports = 0 (found $N)"

step "frontend: type-check"
(cd "$WEB" && npx tsc --noEmit); gate $? "tsc"

step "frontend: production build"
(cd "$WEB" && npm run build >/dev/null 2>&1); gate $? "next build"

if [ -n "${GEMINI_API_KEY:-}" ] && [ "${GEMINI_API_KEY}" != "dummy" ]; then
  step "live: KT E2E gate (real Gemini + DB)"
  (cd "$API" && ENVIRONMENT=development DEBUG=True "$PY" scripts/phase2_kt_e2e.py | grep -q "GATE: PASS"); gate $? "KT live E2E"
else
  printf '\n(skipping live KT E2E — set GEMINI_API_KEY to include it)\n'
fi

step "result"
if [ "$FAIL" -ne 0 ]; then echo "❌ VERIFICATION FAILED"; exit 1; fi
echo "✅ ALL GATES GREEN"
