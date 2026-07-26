<div align="center">

<img src="apps/web-next/public/images/logo.png" alt="StudyBuddy" width="96" height="96" />

# StudyBuddy

### Assess your people. Keep the knowledge they carry.

**The single enterprise platform to assess & grow every employee — and to retain the knowledge of the people who leave.**

Assessment (quizzes · coding · proctored exams) **+** AI-powered, cited Knowledge Transfer — sharing one org, identity, and AI core.

`FastAPI` · `Next.js 15` · `Expo` · `PostgreSQL + pgvector` · `Google Gemini` · `Turborepo`

<sub>_Formerly "StudyHub / QuizConnect". Live: web on Vercel, API on Railway, Android via Expo._</sub>

</div>

---

## Table of contents

- [What is StudyBuddy](#what-is-studybuddy)
- [The problem](#the-problem)
- [The solution](#the-solution)
- [Two products](#two-products)
- [Key features](#key-features)
- [Who it's for](#who-its-for)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Testing & quality gates](#testing--quality-gates)
- [API reference](#api-reference)
- [Deployment](#deployment)
- [Observability](#observability)
- [Security & auth](#security--auth)
- [Web, PWA & the mobile app](#web-pwa--the-mobile-app)
- [Documentation index](#documentation-index)

---

## What is StudyBuddy

StudyBuddy is a **single-enterprise** platform that a services company runs to do two hard things well:

1. **Assess and grow its people** — interns, lateral hires, and existing employees kept current with the market — with one assessment engine for MCQ, descriptive, coding (AI-evaluated) and config questions, delivered as practice quizzes, proctored exams, or daily challenges, and analyzed from the individual learner all the way up to the executive.
2. **Retain the knowledge of people who leave** — through continuous, structured **Knowledge Transfer (KT)**: experts document their work, mentors approve it, and it becomes an **AI chatbot that answers with citations**, grounded only in your approved knowledge. A formal **exit-handoff** workflow captures a departing employee's knowledge before their last day.

Both products share one platform core — org tree, people, RBAC, AI, jobs — but have **no forced data dependency** on each other.

> It is **not** multi-tenant SaaS. Each deployment serves **one enterprise**; access control is "which part of the org tree can this person touch," not tenant isolation. Accounts are provisioned by L&D admins (email + individual credentials), not self-serve signup.

---

## The problem

Every services/consulting company loses money to the same two gaps:

| Gap | What it looks like | Cost |
|---|---|---|
| **Knowledge walks out the door** | A senior engineer resigns. The *why* behind years of architectural decisions leaves with them. Wikis are stale; nobody documented in time. | Re-learning, repeated mistakes, slow onboarding. |
| **Assessment is fragmented** | Quizzes in one tool, coding tests in another, exams in a third. No single answer to "is this cohort ready?" | No line of sight on readiness; manual spreadsheet stitching. |

Traditional LMS/assessment tools cover the first gap partially and ignore the second entirely. Knowledge-base tools capture documents but don't verify them or make them reliably answerable.

---

## The solution

StudyBuddy puts **assessment** and **knowledge retention** on one platform so the same org structure, identities, permissions and AI power both:

- **One unified assessment engine.** Practice, timed, proctored and daily-challenge modes are *configuration*, not separate codebases. MCQ, descriptive, coding (LLM-evaluated — no execution infra), and JSON/config questions all flow through the same grading loop and durable job queue.
- **KT that's actually trustworthy.** Documents are **mentor-approved before they're indexed**, chunked and embedded into **Postgres/pgvector**, then served through a streamed, markdown-rich RAG chatbot that cites its sources and reports a confidence score — grounded *only* in approved knowledge.
- **Line of sight, end to end.** Analytics roll up learner → batch → vertical → executive, with AI executive summaries and exports. KT gives coverage-per-project and handoff status.
- **Enterprise-ready by default.** A flexible **OrgUnit tree** (org → department → vertical → batch → group) scopes every action (404-not-403), all AI spend is metered per tenant/feature, and everything is observable (Sentry/OpenTelemetry) with Slack alerts.

---

## Two products

### 🎯 Assess — the core
- Question banks: **MCQ · multi-select · true/false · descriptive/essay · AI-evaluated coding · config/JSON**.
- **One engine** for practice quizzes, **proctored exams** (server-side timing, deterministic shuffling, tab/copy/focus flags, optional webcam) and **daily challenges**.
- **Assignments** pushed down the org tree; grading is automatic for objective items and **AI-graded** for descriptive/coding via a durable Postgres-backed job queue.
- **AI authoring**: generate banks and learning paths with Gemini.
- **Engagement**: leaderboards, streaks, daily challenges, discussions.
- **Analytics**: learner → batch → executive dashboards, item analysis, gradebooks, XLSX exports.

### 🧠 Knowledge Transfer — the companion
- Experts document the **what / how / why / when** of their project work in a guided wizard.
- **Mentor review & approval** — approval **auto-indexes** the doc (chunk → embed → pgvector). Nothing is answerable until it's approved.
- **Cited RAG chatbot** — ChatGPT-style, streamed, markdown/code/math-rich, scoped per company/project, with **sources + blended confidence**.
- **Exit handoff** — auto-built checklists capture a departing employee's knowledge with mentor sign-off and a coverage report.
- **Access keys** for scoped/temporary external access; a relational **graph explorer** over projects/docs/tags.

---

## Key features

**Assessment** — unified engine · AI coding & descriptive grading · proctored exams · assignments · daily challenges · AI bank/path generation · gradebooks & item analysis · exports.

**Knowledge Transfer** — approval-gated indexing · pgvector RAG · streamed cited chatbot · exit handoff · access keys · graph explorer · mentor inbox.

**Platform** — email-first auth (JWT + refresh cookie) · **OrgUnit RBAC** (subtree scoping, 404-not-403) · durable background jobs + APScheduler crons · **AI cost metering** per feature/tenant · Resend email · AWS S3 uploads · Upstash Redis cache · rate limiting · **observability** (Sentry → OpenTelemetry-swappable) with Slack alerts.

**Clients** — responsive web (Next.js 15) · installable **PWA** · **Android app** (Expo WebView of the same web app + FCM push) — one codebase, three surfaces.

---

## Who it's for

| Persona | Uses | Gets |
|---|---|---|
| **Learner** (intern / hire / employee) | Assess | Assigned assessments, progress & streaks, leaderboard, discussions, KT chatbot. |
| **Expert / departing employee** | KT | An easy way to document project knowledge; an auto-built exit-handoff checklist. |
| **Mentor** | Both | **One inbox** — review learner performance *and* approve KT docs. |
| **L&D Admin** | Both | Org-tree CRUD, bulk user import, curriculum, org-wide analytics, audit. |
| **Executive** | Reporting | Readiness reports, AI summaries, KT coverage — exportable. |
| **Platform Operator** (vendor) | `/platform` | Health, AI spend, feature gates, enterprise onboarding. |

---

## How it works

```
ASSESS   author/AI-generate bank → publish & assign down the org tree
         → learner takes (any type) → auto + AI grading (job queue) → analytics/reports

KT       expert documents work → mentor reviews & approves → auto chunk+embed→pgvector
         → anyone with access asks the chatbot → streamed, cited, confidence-scored answer
```

---

## Architecture

```
                 ┌──────────────────────────────────────────────────────────┐
   Browser  ───► │  studybuddy.mj665.in  (Next.js 15 · Vercel)              │
   Android  ───► │  Expo WebView → /dashboard   ── same-origin /api proxy ──┐│
                 └──────────────────────────────────────────────────────────┼┘
                                                                             ▼
                 ┌──────────────────────────────────────────────────────────┐
                 │  studybuddy-api.mj665.in  (FastAPI · Railway/Docker)      │
                 │  modular monolith: identity · org · assessment · kt · ai  │
                 │  · reporting · platform   +  durable job queue + crons    │
                 └──┬───────────┬───────────┬───────────┬───────────┬────────┘
                    ▼           ▼           ▼           ▼           ▼
              Postgres     Upstash       AWS S3     Google       Sentry /
              + pgvector    Redis      (uploads)    Gemini        OTLP
              (Neon)       (cache)                  (LLM)      (observability)
```

- **Modular monolith** backend — routers are thin HTTP aggregators; business logic lives in `modules/*/services`; one async DB pattern; typed exceptions → consistent JSON.
- **Same-origin API proxy** — the browser only calls `/api/*` on the web domain; Next rewrites to the backend, so the auth refresh cookie stays first-party (no CORS gymnastics).
- **KT on pgvector** — no separate graph database; approval → chunk → embed → `pgvector` → cited RAG.

See [`docs/product-plan/TARGET_ARCHITECTURE.md`](docs/product-plan/TARGET_ARCHITECTURE.md) for the deep design.

---

## Repository layout

npm workspaces + [Turborepo](https://turbo.build). Three apps under `apps/*`, each with its own README:

```
apps/
  api/          FastAPI backend (Python 3.12)          → apps/api/README.md
  web-next/     Next.js 15 frontend + PWA + landing    → apps/web-next/README.md
  mobile/       Expo (React Native) WebView + FCM      → apps/mobile/README.md
docs/
  openapi.yaml / openapi.json     published API contract
  product-plan/                   PRODUCT_PLAN.md · TARGET_ARCHITECTURE.md
DEPLOYMENT.md                     go-live runbook (Vercel + Railway + DNS + Sentry)
```

---

## Tech stack

| Layer | Choices |
|---|---|
| **Backend** | FastAPI 0.111 · SQLAlchemy 2 (sync + async) · Pydantic 2 · Uvicorn |
| **Data** | PostgreSQL + **pgvector** (Neon) · Alembic + idempotent provisioning · Upstash Redis |
| **AI** | Google Gemini via `langchain-google-genai` · per-feature cost metering |
| **Infra services** | AWS S3 (boto3) · Resend (email) · APScheduler crons + durable DB job queue · slowapi rate limiting |
| **Frontend** | Next.js 15 (App Router) · React Query · Tailwind v4 · `motion/react` · typed OpenAPI client |
| **Mobile** | Expo SDK 52 · `react-native-webview` · `expo-notifications` (FCM) · EAS |
| **Observability** | Sentry (errors/traces/logs/metrics) → OpenTelemetry-swappable · Slack alerts |
| **Monorepo** | npm 11 workspaces · Turborepo · Node ≥ 18 · Python 3.12 |

---

## Quick start

**Prereqs:** Node ≥ 18, Python 3.12, and a repo-root `.env` (copy from [`.env.example`](.env.example) — you need at least `DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`).

```bash
npm install                       # all workspaces
python3.12 -m venv apps/api/.venv
apps/api/.venv/bin/pip install -r apps/api/requirements.txt
```

### Run (Turbo)

```bash
npm run dev            # all apps
npm run dev:next       # web only  → http://localhost:3000  (proxies /api → :8000)
npm run dev:api        # api only  → http://localhost:8000  (Swagger at /docs)
npm run build          # turbo build across workspaces
npm run lint | npm run test
```

### Run an app directly

```bash
# Backend
cd apps/api && ENVIRONMENT=development DEBUG=True .venv/bin/python -m uvicorn main:app --port 8000
# Frontend
cd apps/web-next && npm run dev
# Mobile (emulator against local web dev)
cd apps/mobile && npm install && EXPO_PUBLIC_WEB_URL=http://10.0.2.2:3000 npx expo start
```

First backend boot provisions the schema (`create_all` + pgvector) and seeds the operator accounts from env. Details per app: [`apps/api/README.md`](apps/api/README.md), [`apps/web-next/README.md`](apps/web-next/README.md), [`apps/mobile/README.md`](apps/mobile/README.md).

---

## Testing & quality gates

```bash
cd apps/api
.venv/bin/python -m pytest -q -m "not live"          # fast suite (533 tests)
.venv/bin/python -m pytest -q -m live                # live KT loop (needs GEMINI_API_KEY)
.venv/bin/python scripts/check_route_shadowing.py    # route-shadow gate
cd ../web-next && npx tsc --noEmit && npm run build   # frontend gates
bash scripts/verify_all.sh                            # everything, from repo root
```

---

## API reference

- **Live, always-current:** Swagger UI at `/docs`, ReDoc at `/redoc`, raw schema at `/openapi.json` (on the running API).
- **Published contract (committed):** [`docs/openapi.yaml`](docs/openapi.yaml) — 289 paths across identity, assessment, KT, reporting, platform.
- **Regenerate:** `cd apps/api && ENVIRONMENT=development .venv/bin/python scripts/export_openapi.py`.
- The frontend's typed client (`apps/web-next/src/services/api/schema.d.ts`) is generated from this schema.

---

## Deployment

Full runbook: **[`DEPLOYMENT.md`](DEPLOYMENT.md)**. In short:

- **Backend → Railway** (Docker): `apps/api/Dockerfile` + `railway.json`; long-running (APScheduler + job worker), so not serverless. `RUN_SCHEDULER=true` on exactly one instance. Root Directory = `apps/api`.
- **Frontend → Vercel**: Root Directory = `apps/web-next`; the same-origin `/api/*` proxy forwards to the backend.
- **Mobile → EAS**: `eas build -p android --profile production`; set `EXPO_PUBLIC_WEB_URL`, drop in a Firebase `google-services.json`.

**Required production env** (validated at startup): `DATABASE_URL`, `JWT_SECRET_KEY`, `APP_ADMIN_PASSWORD`, `S3_BUCKET_NAME`, `GEMINI_API_KEY`, `ALLOWED_ORIGINS`, `HMAC_KEY_SECRET` (not the dev default).

---

## Observability

Errors + traces + logs + metrics + Slack alerts across **all three apps**, via a vendor-neutral facade (`apps/api/observability/`). **Sentry** by default; flip `TELEMETRY_BACKEND=otel` (+ an OTLP endpoint, `pip install -r apps/api/requirements-otel.txt`) to switch to OpenTelemetry with **no code changes**. Everything is env-driven and no-ops when no DSN is set. See [`DEPLOYMENT.md`](DEPLOYMENT.md) Part D2.

---

## Security & auth

- **Employees**: email + individual password → short-lived access token (Authorization header) bootstrapped/renewed via an **HttpOnly refresh cookie**. New accounts auto-receive credentials by email.
- **Platform operator**: org-less `PlatformAdmin` — gates on role, not org.
- **Tenancy**: single enterprise; access = **OrgUnit-subtree scoping** (`modules/org`), **404-not-403** so existence never leaks across the tree.
- **Operator seeding**: `APP_ADMIN_*` / `LD_ADMIN_*` env vars create/enforce the two operator accounts on every startup (`ensure_system_identity.py`).
- All AI calls are metered into `ai_usage`; secrets are env-only (validated at boot).

---

## Web, PWA & the mobile app

One web codebase powers three surfaces — with a deliberate split so the **app** is a focused product client, not a marketing brochure:

| Surface | Entry point | Sees the marketing home? |
|---|---|---|
| **Web browser** / shared link / SEO | `/` (marketing landing) | ✅ yes |
| Logged-in user visiting `/` | client island → their dashboard | no (bounced to app) |
| **PWA** ("Add to Home Screen") | `start_url = /dashboard` | no |
| **Android app** (Expo WebView) | `EXPO_PUBLIC_ENTRY_PATH = /dashboard` (auth-gated) | no |

So `/` is the public front door; the installed app opens **straight into the product** (and avoids Play Store "just a website" rejections). See [`apps/mobile/README.md`](apps/mobile/README.md).

---

## Documentation index

| Doc | What |
|---|---|
| [`apps/api/README.md`](apps/api/README.md) | Backend: modules, running, env, jobs, OpenAPI, deploy |
| [`apps/web-next/README.md`](apps/web-next/README.md) | Frontend: routes, API proxy, design system, landing, PWA |
| [`apps/mobile/README.md`](apps/mobile/README.md) | Mobile: WebView architecture, entry-path, EAS, FCM, Play Store |
| [`apps/api/modules/README.md`](apps/api/modules/README.md) | Backend module map + service patterns |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Go-live runbook (Vercel + Railway + DNS + Sentry/Slack) |
| [`docs/product-plan/PRODUCT_PLAN.md`](docs/product-plan/PRODUCT_PLAN.md) | Product vision, personas, journeys, roadmap + execution log |
| [`docs/product-plan/TARGET_ARCHITECTURE.md`](docs/product-plan/TARGET_ARCHITECTURE.md) | Backend/frontend architecture & migration design |
| [`docs/openapi.yaml`](docs/openapi.yaml) | Published API contract (289 paths) |

---

<div align="center">
<sub>StudyBuddy · Assess. Retain. Grow. · single-enterprise assessment & AI knowledge transfer.</sub>
</div>
