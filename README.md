# StudyHub — Enterprise Assessment & Knowledge Transfer Platform

One platform, two products, single-enterprise deployment:

- **Assess** — the core: question banks (MCQ / true-false / multi-select / short-answer / essay / AI-evaluated coding), practice quizzes, proctored exams (one unified engine — behavior is configuration), assignments, leaderboards, daily challenges, analytics from learner → batch → executive.
- **KT (Knowledge Transfer)** — departing/senior engineers document what/how/why/when of their project work; mentors review & approve; approved knowledge is chunked + embedded into **Postgres/pgvector** and served through a cited RAG chatbot; structured exit-handoff workflow.

North-star docs: [`docs/product-plan/PRODUCT_PLAN.md`](docs/product-plan/PRODUCT_PLAN.md) (product plan + execution log) and [`docs/product-plan/TARGET_ARCHITECTURE.md`](docs/product-plan/TARGET_ARCHITECTURE.md).

## Layout

```
apps/api        FastAPI backend (Python 3.12, venv at .venv)
  modules/      modular monolith: identity, org, assessment, kt, ai, reporting (see modules/README.md)
  routers/      thin aggregators (main.py mounts these) + a few small legacy routers
  services/     shared engines (grading, ai_meter, job queue, email, …)
  models/       SQLAlchemy models (single Base; create_all + idempotent scripts)
  scripts/      provisioning + verification gates
apps/web-next   Next.js 15 frontend (src/app is the router root)
  src/app/(app)/     authenticated routes (dashboard, admin, mentor, kt, …)
  src/app/(public)/  login (email-first), recovery, public profiles
  src/services/api/  typed OpenAPI client (schema.d.ts generated from backend)
docs/product-plan/   the plan — single source of truth
```

## Run locally

```bash
# Backend (needs .env at repo root: DATABASE_URL, GEMINI_API_KEY, JWT_SECRET_KEY, …)
cd apps/api
ENVIRONMENT=development DEBUG=True .venv/bin/python -m uvicorn main:app --port 8000

# Frontend (proxies /api → :8000)
cd apps/web-next && npm run dev     # http://localhost:3000

# Tests & gates
cd apps/api && .venv/bin/python -m pytest -q -m "not live"   # fast suite
.venv/bin/python -m pytest -q -m live                        # live KT loop (needs GEMINI_API_KEY)
ENVIRONMENT=development DEBUG=True .venv/bin/python scripts/phase2_kt_e2e.py   # KT E2E gate
.venv/bin/python scripts/check_route_shadowing.py            # route-shadow gate
cd apps/web-next && npm run build                            # frontend gate
```

First boot provisions the schema (`create_all` + pgvector extension) and seeds the system identity; `scripts/phase1_provision.py` is the idempotent full provisioning/backfill script for fresh databases.

## Auth model

- Employees: **email + individual password** (`POST /api/auth/login`), short-lived access token (Authorization header) bootstrapped/renewed via HttpOnly refresh cookie. New accounts auto-receive credentials by email.
- Platform operator (vendor): org-less `PlatformAdmin` identity — email login or `/auth/superadmin/login` (env `APP_ADMIN_PASSWORD`); gates on role, not org.
- Tenancy: single enterprise; access = OrgUnit-subtree scoping (`modules/org`), 404-not-403 convention, mirrored from the legacy hierarchy by `modules/org/sync.py`.

## Production notes

- Required env (validated at startup in production): `JWT_SECRET_KEY`, `APP_ADMIN_PASSWORD`, `DATABASE_URL`, `S3_BUCKET_NAME`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, `HMAC_KEY_SECRET` (must not be the dev default).
- Backend container: `apps/api/Dockerfile` (uvicorn; set `RUN_SCHEDULER=false` on all but one instance).
- Frontend: deploy `apps/web-next` (set `NEXT_PUBLIC_API_BASE`).
- All AI calls are metered into `ai_usage` (see `/platform` dashboard).
