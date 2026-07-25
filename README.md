# StudyHub — Enterprise Assessment & Knowledge Transfer Platform

One platform, two products, single-enterprise deployment.

- **Assess** (core) — question banks (MCQ / true-false / multi-select / short-answer / essay / AI-evaluated coding), practice quizzes, proctored exams (one unified engine — behavior is configuration, not code paths), assignments, leaderboards, daily challenges, and analytics from learner → batch → executive.
- **KT — Knowledge Transfer** (companion) — senior/departing engineers document the what/how/why/when of their work; mentors review & approve; approved knowledge is chunked, embedded into **Postgres/pgvector**, and served through a cited RAG chatbot; plus a structured exit-handoff workflow.

Web-first. The Android app is a thin Expo WebView wrapper of the same web app, so web changes reflect there automatically.

**North-star docs:** [`docs/product-plan/PRODUCT_PLAN.md`](docs/product-plan/PRODUCT_PLAN.md) (plan + execution log) · [`docs/product-plan/TARGET_ARCHITECTURE.md`](docs/product-plan/TARGET_ARCHITECTURE.md) · [`DEPLOYMENT.md`](DEPLOYMENT.md) (go-live runbook).

---

## Monorepo layout

npm workspaces + [Turborepo](https://turbo.build). Three apps under `apps/*`:

```
apps/
  api/          FastAPI backend — Python 3.12 (venv at .venv)
    modules/    modular monolith: identity · org · assessment · kt · ai · reporting
    routers/    thin HTTP aggregators mounted by main.py
    services/   shared engines: grading, ai_meter, durable job queue, email, push
    models/     SQLAlchemy models (single Base; create_all + idempotent scripts)
    observability/  vendor-neutral telemetry facade (Sentry now, OTel-swappable)
    scripts/    provisioning + verification gates
  web-next/     Next.js 15 frontend (App Router; src/app is the root)
    src/app/(app)/     authenticated routes (dashboard, admin, mentor, kt, …)
    src/app/(public)/  login (email-first), recovery, public profiles
    src/services/api/  typed OpenAPI client (schema.d.ts generated from the backend)
  mobile/       Expo (React Native) WebView wrapper of the web app + FCM push
docs/product-plan/   the plan — single source of truth
```

**Tech stack:** FastAPI · SQLAlchemy 2 (sync + async) · Postgres/pgvector (Neon) · Upstash Redis · Google Gemini · Resend (email) · AWS S3 · Next.js 15 · React Query · Tailwind · Expo · Sentry.

---

## Quick start

Prereqs: **Node ≥ 18**, **Python 3.12**, and an `.env` (copy from [`.env.example`](.env.example)).

```bash
npm install                      # installs all workspaces
# one-time backend venv:
python3.12 -m venv apps/api/.venv && apps/api/.venv/bin/pip install -r apps/api/requirements.txt
```

### Run everything (Turbo)

```bash
npm run dev            # turbo dev — all apps
npm run dev:next       # web only  (http://localhost:3000, proxies /api → :8000)
npm run dev:api        # api only  (http://localhost:8000)
npm run build          # turbo build across workspaces
npm run lint           # turbo lint
npm run test           # turbo test
```

### Run an app directly

```bash
# Backend
cd apps/api
ENVIRONMENT=development DEBUG=True .venv/bin/python -m uvicorn main:app --port 8000

# Frontend
cd apps/web-next && npm run dev

# Mobile (against the local web dev server on the Android emulator)
cd apps/mobile && npm install && EXPO_PUBLIC_WEB_URL=http://10.0.2.2:3000 npx expo start
```

First backend boot provisions the schema (`create_all` + pgvector) and seeds the operator identities; `apps/api/scripts/phase1_provision.py` is the idempotent full provisioning/backfill for fresh databases.

---

## Tests & gates

```bash
cd apps/api
.venv/bin/python -m pytest -q -m "not live"          # fast suite (533 tests)
.venv/bin/python -m pytest -q -m live                # live KT loop (needs GEMINI_API_KEY)
ENVIRONMENT=development DEBUG=True .venv/bin/python scripts/phase2_kt_e2e.py   # KT E2E
.venv/bin/python scripts/check_route_shadowing.py    # route-shadow gate
cd ../web-next && npx tsc --noEmit && npm run build   # frontend gates
# everything in one shot (from the repo root):
bash scripts/verify_all.sh
```

---

## Auth model

- **Employees**: email + individual password (`POST /api/auth/login`); short-lived access token (Authorization header) bootstrapped/renewed via an HttpOnly refresh cookie. New accounts auto-receive credentials by email.
- **Platform operator** (vendor): org-less `PlatformAdmin` — email login or `/auth/superadmin/login` (env `APP_ADMIN_PASSWORD`); gates on role, not org.
- **Tenancy**: single enterprise; access = OrgUnit-subtree scoping (`modules/org`), **404-not-403** convention.
- Operator accounts are created/enforced on every startup from env by `ensure_system_identity.py` (`APP_ADMIN_*`, `LD_ADMIN_*`).

---

## Observability

Errors + traces + logs + metrics + Slack alerts across all three apps, via a vendor-neutral facade (`apps/api/observability/`). **Sentry** by default; flip `TELEMETRY_BACKEND=otel` (+ an OTLP endpoint, `pip install -r apps/api/requirements-otel.txt`) to switch to OpenTelemetry with no code changes. Everything is env-driven and no-ops when no DSN is set. See [`DEPLOYMENT.md`](DEPLOYMENT.md) Part D2.

---

## Deployment

Full runbook in [`DEPLOYMENT.md`](DEPLOYMENT.md). In short:

- **Backend → Railway** (Docker) — `apps/api/Dockerfile` + `railway.json`; long-running process (APScheduler cron + durable job worker), so not serverless. Set `RUN_SCHEDULER=true` on exactly one instance.
- **Frontend → Vercel** — Root Directory `apps/web-next`; the same-origin `/api/*` proxy (next.config.ts) forwards to the backend, keeping the auth cookie first-party (no CORS setup).
- **Mobile → EAS** — `eas build -p android --profile production`; set `EXPO_PUBLIC_WEB_URL` + drop in a Firebase `google-services.json`.

**Required production env** (validated at startup): `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ADMIN_PASSWORD`, `S3_BUCKET_NAME`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, `HMAC_KEY_SECRET` (must not be the dev default). All AI calls are metered into `ai_usage` (see the `/platform` dashboard).
