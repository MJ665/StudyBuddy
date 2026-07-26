# StudyBuddy API

FastAPI backend for StudyBuddy — a **modular monolith** powering the assessment engine, the KT (Knowledge Transfer) RAG platform, identity/RBAC, reporting, and the platform-operator surface.

> Part of the [StudyBuddy monorepo](../../README.md). Frontend: [`apps/web-next`](../web-next/README.md) · Mobile: [`apps/mobile`](../mobile/README.md).

- **Python** 3.12 · **FastAPI** 0.111 · **SQLAlchemy** 2 (sync + async) · **Pydantic** 2
- **Data:** PostgreSQL + **pgvector** (Neon) · Upstash Redis · AWS S3
- **AI:** Google Gemini (`langchain-google-genai`), metered per feature/tenant
- **Jobs:** APScheduler crons + a durable Postgres-backed queue (`FOR UPDATE SKIP LOCKED`)
- **Observability:** Sentry → OpenTelemetry-swappable (`observability/`)

---

## Architecture

Routers are **thin HTTP aggregators** — validate → call a service → return a schema. Business logic lives in `modules/*/services`. One async DB pattern; typed exceptions (`shared/exceptions.py`) → one consistent `{"detail": ...}` JSON shape.

```
apps/api/
  main.py               app factory, middleware, CORS, telemetry init, scheduler, job worker
  config.py             pydantic-settings (all env), production validation (fail-fast)
  database.py           sync + async engines/sessions (lazy; slow-query telemetry)
  auth_utils.py         JWT, RBAC helpers, OrgUnit subtree scoping (scope_to_org/_super_org)
  ensure_system_identity.py   seeds/enforces operator accounts from env on every boot
  models/               SQLAlchemy models (single Base)
  modules/              the monolith — see modules/README.md
    identity/           auth (email-first), users, profiles, notifications, devices (push)
    org/                OrgUnit tree, UserOrgRole, role scoping, legacy-hierarchy mirror
    assessment/         banks, questions, courses, attempts, grading (attempt_engine), assignments, exams
    kt/                 documents, review, chat (RAG), handoff, access keys, ingestion→pgvector
    ai/                 LLM generation endpoints (Gemini)
    reporting/          governance, admin analytics, member/cohort reports, exports
    platform/           operator surface, system config
  services/             shared engines: ai_meter, job_queue, email_service, push_service, s3, redis
  observability/        vendor-neutral telemetry facade (telemetry/tracing/metrics/slack/logging)
  tasks/                scheduled jobs (daily challenges, reminders, streaks, cleanup, …)
  scripts/              provisioning, verification gates, OpenAPI export
  requirements.txt      + requirements-otel.txt (optional, only for TELEMETRY_BACKEND=otel)
  Dockerfile · railway.json    deployment
```

Module map & service patterns: [`modules/README.md`](modules/README.md).

---

## Run locally

```bash
# 1. venv + deps (from apps/api)
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. env — the app reads .env (repo root) or apps/api/.env
#    minimum for dev: DATABASE_URL, JWT_SECRET_KEY, GEMINI_API_KEY
#    (see .env.production.example for the full list)

# 3. run (dev skips production config validation)
ENVIRONMENT=development DEBUG=True .venv/bin/python -m uvicorn main:app --port 8000 --reload
```

- Swagger UI → `http://localhost:8000/docs` · ReDoc → `/redoc` · schema → `/openapi.json`
- Health → `/health` · readiness (DB/Redis/pgvector) → `/ready`

First boot runs `ensure_system()` (idempotent): creates the system identity, the seed org hierarchy, and the two operator accounts from env.

---

## Configuration

All settings are in `config.py` (`pydantic-settings`); template in [`.env.production.example`](.env.production.example). `validate_production_config()` **fails fast** in production if any of these are missing: `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ADMIN_PASSWORD`, `S3_BUCKET_NAME`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, `HMAC_KEY_SECRET` (must not be the dev default).

**Operator accounts** are created/enforced on **every startup** from env — change them here, redeploy, done:

```
APP_ADMIN_EMAIL / APP_ADMIN_PASSWORD    # Platform Admin (owns /platform)
LD_ADMIN_EMAIL  / LD_ADMIN_PASSWORD     # L&D Admin (owns the seed org)
SEED_ORG_NAME   / SEED_ORG_SLUG
```

**Provisioning a fresh database:** `ENVIRONMENT=development .venv/bin/python scripts/phase1_provision.py` (idempotent full provisioning/backfill; `create_all` + pgvector extension + schema ALTERs).

---

## Background work

- **APScheduler crons** (`main.py::start_scheduler`, guarded by `RUN_SCHEDULER`) — daily challenges, notifications, deadline reminders, streaks, weekly digest, cleanup, S3 sync. Run the scheduler on **exactly one** instance.
- **Durable job queue** (`services/job_queue.py`) — DB-backed, at-least-once, stale-claim recovery; handlers in `services/job_handlers.py` (KT ingest/enrich, email send). Used for AI grading, KT indexing, and email so requests never block.

Telemetry is wired into both (job duration/failure metrics, Sentry capture, Slack on terminal failure).

---

## OpenAPI

- Live schema: `/openapi.json` (+ `/docs`, `/redoc`) on the running server.
- Published contract: [`../../docs/openapi.yaml`](../../docs/openapi.yaml) (289 paths) + `openapi.json`.
- Regenerate (no server/DB needed):
  ```bash
  ENVIRONMENT=development .venv/bin/python scripts/export_openapi.py
  ```

---

## Testing & gates

```bash
.venv/bin/python -m pytest -q -m "not live"          # fast suite (533 tests)
.venv/bin/python -m pytest -q -m live                # live KT loop (needs GEMINI_API_KEY)
.venv/bin/python tests/test_unit_no_unresolved_calls.py   # router-wiring guardrail
.venv/bin/python scripts/check_route_shadowing.py    # route-parity / no-shadow gate
ENVIRONMENT=development .venv/bin/python scripts/phase2_kt_e2e.py   # KT E2E
bash ../../scripts/verify_all.sh                     # everything (from repo root)
```

---

## Deployment

Long-running container (**not** serverless — it hosts the scheduler + job worker). See [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md).

- **Docker**: [`Dockerfile`](Dockerfile) — `python:3.12-slim`, uvicorn, non-root, binds `$PORT`.
- **Railway**: [`railway.json`](railway.json) — Dockerfile builder, `/health` healthcheck. Set **Root Directory = `apps/api`**, paste the env, `RUN_SCHEDULER=true` on one instance.

---

## Observability

The app imports **only** `observability/` — never `sentry_sdk`/`opentelemetry` directly — so `TELEMETRY_BACKEND=sentry|otel|none` swaps the whole stack via env. Structured JSON logs (`LOG_FORMAT=json`), request/DB/HTTP spans, AI-cost/job/latency metrics, 5xx capture, and Slack alerts (`SLACK_WEBHOOK_URL`). OTel deps are optional (`requirements-otel.txt`). See [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md) Part D2.
