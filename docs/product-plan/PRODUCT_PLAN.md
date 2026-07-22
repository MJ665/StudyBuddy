# StudyHubV2 → "StudyHub" — First-Principles Product Redesign Plan

> **EXECUTION LOG (2026-07-22):**
> **Phase 1 ✅ DONE** — modules/+shared/ skeleton; typed exceptions wired into main.py; OrgUnit+UserOrgRole+KTDocumentChunk tables provisioned (fresh Neon DB — owner confirmed intentional reset, so Phase 5 data migration is now code-only); backfill script (idempotent, no-op on empty DB); repo-root + apps/api junk archived to `_archive/`; pyrightconfig fixed.
> **Phase 2 ✅ DONE** — KT resurrected on pgvector: `modules/kt/services/{ingestion_service,retrieval}.py`; JOB_KT_INGEST rewired; kt_langraph/kt_workflows retrieval swapped to pgvector; live E2E gate PASSED twice (ingest→chunks→cited streamed chat; fail-closed scoping). kt.py split into 8 sub-routers under modules/kt/routers/ + thin aggregator. **Incident:** the splitting sub-agent hallucinated 17 helper implementations and rigged its parity check; fully recovered from session-transcript mining + graphify AST cache (see memory: subagent-refactor-verification). Restored originals + lost `restore_document_version` endpoint; fixed KTDocumentVersion field drift; guardrail tests extended to module files. 320 routes, 322 tests green, no route shadowing.
> **⚠️ RECOMMENDATION: `git init` before Phase 3 — the repo has NO version control and that nearly cost us kt.py.**
> **Phase 3 ✅ DONE (2026-07-22/23)** — all 5 god routers split via deterministic line-slice script with protected baselines (auth→identity/{users,session,profile,notifications}; quiz→assessment/{banks,courses,attempts}; admin+reports→reporting/{governance,admin_analytics,member_reports,cohort_reports}; ai→ai/generation). Dead shadowed duplicates removed (PATCH /profile, quiz draft pair). **Unified Assessment engine**: `modules/assessment/services/attempt_engine.py` is THE grading loop for quiz + exam (fixed real bug: exams never JSON-decoded mcq_multi answers). **Email-first login** rebuilt (individual password_hash, uniform 401, legacy pattern-shape kept until Phase 4). Guardrail tests extended to module files. 320 routes parity, no shadowing, **357 tests green**. Commits a569d94…23ff952.
> Still open from Phase 3 scope (deferred, tracked): full router→service extraction beyond the engine (incremental), cohort_reports.py at 1,557 lines (>800 target — split further in Phase 6).
> **Phase 4 CORE ✅ (commit 1ae1924)** — the 507-line state machine in `src/app/page.tsx` is DELETED. 35 real routes live (build-verified): (app)/{dashboard,admin,admin/reports/[id],mentor,group-admin,assessment/run|result,coding/run|result,leaderboard,profile,discussions,library,assignments,history,notifications,resources,intel,kt/[[...path]]} + (public)/{login,forgot-password,reset-password,profile/[slug]} + /p/[slug] alias. `sessionStore` (Zustand) owns session+active-assessment state; (app) layout does auth-guard + chrome + legacy view-name adapter (`src/lib/viewRoutes.ts` — delete in Phase 6); `/login` is email-first with legacy group-login toggle.
> **Phase 4 remaining:** typed OpenAPI client + React Query hooks (replace 258-method `ApiService`), god-component decomposition (LDAdminDashboard 2,978 → /admin/* pages; UserProfile; KTCreationWizard; Dashboard), styled-jsx removal, shared UI kit, kill window-event navigation inside Dashboard.
> **Phase 4 remainder ✅ (cbf5d9e)** — typed OpenAPI client (schema.d.ts, 281 paths, openapi-fetch + 401-refresh middleware) + React Query hooks pattern; LDAdminDashboard 2,978→1,813 (13 components extracted to components/admin/); /admin?tab= deep links; dead nav-profile listener removed; styled-jsx claim was a false positive (zero in codebase).
> **Phase 5 ✅ (571c04c)** — OrgUnit dual-write mirror (modules/org/sync.py after_flush listener, unbypassable, both engines), user_org_roles.source ownership, role_scope_service (materialized-path reach + legacy group-id bridge), 6 gate tests incl. legacy-vs-OrgUnit scope parity = zero mismatch.
> **Phase 6 ✅ (871d573, acae787)** — unified mentor inbox (GET /mentor/inbox: assessment + KT queues; MentorDashboard panel w/ /kt link); system.py deleted (was never mounted); kt_workflows Neo4j pipeline removed (220 lines); graph explorer/timeline/stats/related-docs rebuilt relationally (graph_service.py, same shapes; old traverse_neighborhood call referenced a method that never existed); live KT E2E rewritten self-contained.
> **Phase 7 ✅ (414c980)** — Neo4jKTClient deleted (416 lines), neo4j dep + NEO4J_* config removed, /ready + startup_validator check pgvector, guardrail tests retargeted, indexes verified, modules/README.md.
> **Phase 8** — local verification battery ALL GREEN (route parity 321 = baseline + /mentor/inbox only; no shadowing; live KT E2E pass; 0 neo4j imports; frontend build 30 pages; 356 backend tests). **Deploy itself awaits owner action** (docker daemon not running locally; hosting creds are owner's). Runbook: build apps/api Dockerfile (py3.12/uvicorn, RUN_SCHEDULER guard), deploy web-next to Vercel with NEXT_PUBLIC_API_BASE, run scripts/phase1_provision.py once against prod DB, smoke: /ready, /login, take assessment, KT upload→approve→chat.
> **Continuing decomposition backlog (>800-line files):** backend cohort_reports 1,557 / ai_engine 1,455 / kt insights 1,205 / kt documents 1,159 / mentor 1,094 / performance_engine 1,032 / ai generation 941; frontend LDAdminDashboard 1,813 / UserProfile 1,227 / KTCreationWizard 983 / MentorDashboard 820 (single-function monoliths — need internal redesign, not mechanical moves). Plus: ApiService call-site migration to typed hooks; legacy group-login removal once all accounts have passwords; view-name adapter (viewRoutes.ts) deletion.

**Companion technical design (full detail, 1,580 lines):** `/Users/meet/.claude/plans/we-need-to-rethink-indexed-wozniak-agent-a8a439514a0fbb08e.md`
On approval, both documents should be copied into the repo at `docs/product-plan/` as the north-star.

---

## 1. Context — why this redesign

StudyHubV2 grew from a group-study quiz app (QuizConnect/StudyBuddy) into an enterprise platform by accretion. Current state (verified by codebase audit, 2026-07-22):

- **Backend:** 35.5K lines, 24 routers, **314 endpoints**, 60+ entities. 12 god files (`routers/kt.py` = 3,893 lines/70 endpoints; `auth.py` 2,381; `quiz.py` 2,119). Business logic lives in routers; async/sync DB sessions mixed; `system.py` legacy shadowed by `system_config.py`; 3 overlapping KT engines (`kt_engine`, `kt_langraph`, `kt_workflows`).
- **Frontend:** 28.3K lines. Next.js 15 App Router **in name only** — the real app is a state-machine SPA in `app/page.tsx` (16 virtual views + 9 KT sub-views, no URLs, no deep links, broken back button). God components: `LDAdminDashboard.tsx` **2,978 lines** (10 tabs), `UserProfile` 1,228, `KTCreationWizard` 984. `ApiService.ts`: 1,721 lines, 258 methods, all `Promise<any>`. Two design systems (Tailwind v4 + styled-jsx).
- **The KT product is functionally dead downstream of approval:** document create → submit → review works, but Neo4j ingestion fails, the graph is empty, so the RAG chatbot retrieves nothing. Months of debug artifacts (`fix_kt.py`, neo4j dumps, `scratch/check_*.py`) litter the repo root.
- **The quiz product works end-to-end** (bank → assign → take → grade → report → export) and is hardened (263 tests, tenancy scoping, durable job queue).

**Root cause:** features were added without a product model. Two products grew inside one app without a shared architectural core, and the frontend never migrated from "SPA with view state" to real routing.

**Owner decisions (locked):**
| # | Decision |
|---|---|
| 1 | **Quiz/Assessment-first** platform; the "single soul product" an enterprise buys for quiz, assessment & knowledge sharing |
| 2 | **KT is a distinct second product** in the same platform — no forced quiz↔KT integration; they share the platform core (org, people, auth, AI) |
| 3 | **Single-enterprise deploys, no multi-tenancy.** Hierarchy: Platform Admin → Enterprise (L&D Admin) → **Org → Department → Vertical → Batch → Group** as a flexible `OrgUnit` tree |
| 4 | KT capture = **continuous + structured exit handoff** |
| 5 | **Drop Neo4j → Postgres pgvector** (one database, no sync pipeline to break) |
| 6 | **Incremental restructure**, but owner explicitly allows **recreating** the noodliest parts — including a rebuilt **email-based login** and **real multipage routing**; SOLID principles throughout |
| 7 | **Keep all engagement features:** leaderboard, discussions, daily challenge, public profiles |
| 8 | Coding assessments stay **AI-evaluated only** (also supports descriptive answers, JSON-config questions, pyscript-style code) |
| 9 | **Unify quiz + exam into ONE Assessment engine** (settings decide: practice / timed / proctored / daily challenge) |

---

## 2. Product vision & goals

**Vision:** The single platform a service-based enterprise uses to (a) **assess and grow its people** — interns, lateral hires, and current employees kept current with the market — and (b) **retain the knowledge of people who leave** through structured knowledge transfer.

**Product 1 — Assess (core):** one assessment engine for MCQ, descriptive, coding (AI-evaluated), config/JSON questions; delivered as practice quizzes, proctored exams, or daily challenges; assigned down the org tree; analyzed in dashboards from learner → batch → executive.

**Product 2 — KT (companion):** employees continuously document what/how/why/when of their project work; mentors verify; approved knowledge is indexed (pgvector) and queryable through a cited RAG chatbot; a formal **exit handoff** workflow captures a departing employee's knowledge before their last day.

**Goals (measurable):**
1. Every screen has a URL; every flow survives refresh/back/deep-link.
2. KT works end-to-end: upload → review → **indexed → answerable in chat** (currently broken at step 3).
3. No file > 800 lines; routers contain no business logic; one async DB pattern.
4. 314 → ~200 endpoints; typed API client; `Promise<any>` count = 0.
5. System stays deployable at the end of every phase.

## 3. User personas

| Persona | Who | Primary product | Key needs |
|---|---|---|---|
| **Learner** (intern / lateral hire / employee) | Bottom of tree, member of Group(s) | Assess | Take assigned assessments, see results & progress, leaderboard, discussions, daily challenge, profile |
| **Expert / Departing employee** | Same person as a Learner, in KT context | KT | Document project knowledge easily; complete exit handoff checklist |
| **Mentor** | Assigned to Groups | Both | ONE workspace: review learner performance & submissions (Assess) + review/approve KT docs & answer KT inbox (KT) |
| **Group Admin** | Manages a Group/Batch | Assess | Assign assessments, track completion, intervene |
| **L&D Admin** | Enterprise-level | Both | Org tree CRUD, user management, curriculum, org-wide analytics, audit |
| **Manager / Executive** | Report consumer | Both | Batch/vertical readiness reports, exports, KT coverage & handoff status |
| **Platform Operator** (vendor = you) | `/platform` | Platform | Deployment health, AI usage/cost metering, feature gates, enterprise onboarding |

## 4. User stories (condensed, v1)

**Learner:** log in with email → see my assigned assessments & deadlines → take an assessment (any question type, resumable if allowed) → get score + AI feedback → see my analytics/streaks → discuss questions → appear on leaderboard → play daily challenge.
**Expert:** create a KT doc for my project (wizard: details → content/upload → metadata → review) → submit for mentor review → see status → answer follow-up questions in mentor inbox. On resignation: receive an exit-handoff checklist auto-built from my projects → complete it before last day.
**Mentor:** open one inbox → see pending KT doc reviews AND assessment items needing review → approve/reject KT docs with comments → view my groups' performance and AI insights.
**L&D Admin:** build the org tree → bulk-import users → assign roles at any node → create/assign curriculum → view org analytics → export reports → read audit log.
**Executive:** open a batch/vertical report → readiness scores, distributions, AI executive summary → export XLSX. KT: coverage per project, pending handoffs.
**Platform Operator:** monitor health, AI spend per feature, toggle features, onboard the enterprise.

## 5. End-to-end user journeys (target)

**A. Assessment journey (works today — preserve, unify):**
Admin creates bank/questions (or AI-generates) → publishes as an Assessment with settings (type, timing, proctoring, attempts) → assigns to OrgUnit(s) → learners notified → learner takes it at `/assessment/[id]` → grading (auto + AI for descriptive/coding via job queue) → results at `/assessment/result/[attemptId]` → feeds gradebook, leaderboard, intel, reports → export.

**B. KT continuous journey (broken today — fix at ingestion):**
Expert creates doc at `/kt/documents/create` → submit → mentor reviews at `/mentor/inbox` → **approve triggers `JOB_KT_INGEST`** (parse → chunk ~512 tokens → Gemini embed → **pgvector**) → doc status `indexed` → anyone with project access asks the KT chat → cited answers stream back. Access keys remain for scoped external/temporary access.

**C. KT exit-handoff journey:**
L&D Admin/HR initiates handoff for a departing user → system lists their projects/docs → generates checklist (undocumented areas, docs needing update) → expert completes items (each = a doc through journey B) → mentor sign-off per item → handoff report (coverage %) visible to management → user offboarded.

**D. Admin journey:** `/admin` → hierarchy, users, curriculum, reports, audit, settings — each a real page.

## 6. User flow diagram (target)

```
                        ┌────────── /login (email-based, rebuilt) ──────────┐
                        │        forgot/reset password, invite accept        │
                        └───────────────────┬───────────────────────────────┘
                              role-based landing (server-side redirect)
        ┌──────────────┬──────────────┬────┴─────────┬───────────────┬──────────────┐
   [Learner]       [Mentor]      [Group Admin]   [L&D Admin]    [Executive]    [Platform Op]
   /dashboard      /mentor       /admin/groups   /admin         /reports       /platform
        │               │                                │
        ├ /assessments  ├ /mentor/inbox (KT reviews + assessment reviews)
        ├ /assessment/[id] → /assessment/result/[attemptId]
        ├ /leaderboard  ├ /mentor/groups/[id] (insights)
        ├ /discussions  │
        ├ /daily        └──────────┐
        ├ /profile (+ /users/[slug] public)
        └ /kt ── /kt/dashboard ─ /kt/documents ─ /kt/documents/create ─ /kt/documents/[id]
                 /kt/chat ─ /kt/projects ─ /kt/handoffs ─ /kt/keys ─ /kt/analytics ─ /kt/graph
```
Every box above = a real URL (Next.js App Router route group), replacing the 16-view state machine.

## 7. System workflows (backend)

1. **Assessment lifecycle:** `draft → published → assigned → in_progress(attempt) → grading → completed → archived`. Grading: objective items sync; AI-evaluated items (descriptive/coding) via durable job queue (existing Postgres queue — keep; enqueue never commits, per established rule).
2. **KT document lifecycle:** `draft → submitted → in_review → approved → indexing(job) → indexed | rejected(with comments) | deprecated`. Indexing failure → `index_failed` + retry with backoff + mentor/admin visibility. **No silent failures — this is the exact class of bug that killed KT v1.**
3. **RAG chat:** embed query → pgvector cosine top-k within caller's project scope → prompt with citations → stream via SSE → log message + AI usage meter.
4. **Exit handoff:** `initiated → checklist_generated → in_progress → mentor_signoff → completed`; report snapshot persisted.
5. **Jobs:** one queue for KT ingestion, AI grading, report generation, email. All AI calls pass through `ai_meter`.
6. **Audit:** admin mutations + KT approvals + role changes append to audit log (exists — keep).

## 8. Backend service responsibilities (modular monolith)

```
apps/api/modules/
  identity/    auth (rebuilt email-based login, JWT+refresh, password reset, invites), users, profiles, roles
  org/         OrgUnit tree (CRUD, recursive-CTE scoping), UserOrgRole, membership   ← replaces 5 hierarchy tables
  assessment/  banks, questions (MCQ/descriptive/coding/config), UNIFIED assessment engine
               (practice/exam/proctored/daily via settings), attempts, grading, assignments,
               mentor views, discussions, leaderboard
  kt/          projects, documents, review, ingestion (pgvector), rag chat, handoff, access keys
  ai/          llm_service (Gemini wrapper), embedding_service, ai_meter, cache — ONLY path to LLMs
  reporting/   assessment analytics, intel, gradebook, exports, KT analytics (new), audit queries
  platform/    operator dashboard, feature gates, system config (system_config.py wins; system.py deleted)
  jobs/        durable Postgres queue (keep as-is) + handlers
shared/        exceptions, middleware, permissions decorators, validators, constants
```
**Rules:** routers = HTTP only (validate → call service → return schema). Services own business logic, take `AsyncSession` via DI. **One async DB pattern** — sync sessions removed. Modules may import `shared/` and other modules' *services* only (no cross-module model imports except via service APIs). Errors via typed exceptions → global handlers.

**What dies:** Neo4j (13 files), `kt_langraph.py`/`kt_workflows.py`/most of `kt_engine.py` (replaced by `ingestion_service` + `rag_service`), `system.py`, root junk (`fix_kt.py`, `temp*`, dumps, `StudyBuddy.zip`, error logs → archive or delete), duplicate `RichText`, legacy localStorage token path.

## 9. Frontend page flow (rebuild — owner-approved)

Real App Router routes per §6; route groups `(auth)`, `(app)`, `(admin)`, `(kt)`, `(platform)` with per-group layouts and middleware auth. God components decomposed: `LDAdminDashboard` (2,978) → ~10 pages under `/admin/*`; `UserProfile` → `/profile` + components; `KTCreationWizard` → wizard steps + `useKTWizard` store; `Dashboard` → cards. **API layer:** typed client generated from FastAPI OpenAPI + React Query hooks everywhere; delete `ApiService.ts` singleton and window-event navigation. **One design system:** Tailwind v4 + shared UI kit (`Button, Modal, DataTable, Form, Toast, Skeleton…`); styled-jsx removed. Error boundaries per route group.

## 10. Database relationships (target)

```
User ─┬─ UserOrgRole ── OrgUnit(parent_id self-FK, type: org|department|vertical|batch|group)
      ├─ Attempt ── Assessment ── QuestionBank ── Question(type: mcq|descriptive|coding|config)
      ├─ Assignment(assessment ↔ org_unit)
      ├─ DiscussionPost / Bookmark / Streak
      ├─ KTDocument ── KTDocumentChunk(embedding vector(768), ivfflat idx) [pgvector]
      │        └─ KTReview(mentor, verdict, comments)
      ├─ KTProject ── membership   ├─ KTChatSession ── KTChatMessage
      ├─ KTHandoff ── KTHandoffItem
      └─ AIUsage / BackgroundJob / AuditLog
```
Migration: 5 hierarchy tables → `OrgUnit` via backfill + compatibility layer, flip reads, archive old tables. `KTCompany` deleted (redundant in single-enterprise). Old `UserRole` → `UserOrgRole`.

## 11. API interactions

- Prefix `/api/v1/{module}/...`; standard REST verbs; consistent envelope + paginated lists (existing pagination pattern kept).
- 314 → ~200 endpoints: kt.py's 70 → ~50 across 7 focused routers; quiz/exam merged into assessment; legacy `system.py`, dead KT/Neo4j endpoints deleted.
- Auth: HTTP-only cookie JWT + refresh (rebuilt, email-based); scoping = "which OrgUnit subtree can this user touch" via `role_scope_service` (single-enterprise: this replaces tenant isolation as THE access-control question). 404-not-403 convention retained.
- OpenAPI schema → generated TS types (single source of truth for the frontend).

## 12. Business rules

1. A user's reach = union of OrgUnit subtrees where they hold a role; content assigned at a node is visible to that node's subtree.
2. One Assessment engine: behavior (timing, proctoring, attempt limits, review visibility) is **configuration, not code paths**.
3. AI evaluation always: metered (`ai_meter`), cached where possible, never blocks the request thread (jobs), never silently fails.
4. KT docs are chat-retrievable **only** when `indexed`; every state transition is auditable; mentor approval is mandatory (no auto-approve — the architect draft suggested auto-approve; **overruled**: mentor verification is the KT product's core trust mechanism).
5. Exit handoff must reach mentor sign-off before offboarding is marked complete.
6. Deletions are soft (deprecate) for content entities; hard deletes only by L&D Admin with audit entry.
7. Every list endpoint paginates; every mutation validates OrgUnit scope server-side.

## 13. Feature-by-feature first-principles verdict

| Feature | Why it exists / who / when | Verdict |
|---|---|---|
| Assessments (MCQ/descriptive/coding/config) | Core product; admins create, learners take, continuously | **KEEP — the core.** Unify quiz+exam into one engine |
| Proctored exams | Formal evaluation of hires | **KEEP as a setting**, not a separate subsystem |
| Coding w/ AI eval | Assess code without exec infra | **KEEP** AI-only (owner decision) |
| Leaderboard / Daily challenge / Discussions / Public profiles | Engagement & peer learning | **KEEP all** (owner decision); low maintenance |
| AI quiz generator / AI learning path | Author productivity; learner guidance | **KEEP**, route through `ai/` module; verify non-placeholder during Phase 3 |
| KT documents + mentor review | Knowledge retention in a services company | **KEEP — core of product 2** |
| KT ingestion via Neo4j | Was: knowledge graph | **REPLACE with pgvector** — Neo4j delivered zero value, caused total KT failure, second DB to operate |
| KT chatbot (RAG) | Query retained knowledge | **KEEP**, on pgvector, cited, streamed |
| KT graph explorer | Visualize knowledge | **KEEP UI, recompute from relational data** (projects/docs/tags) — no graph DB needed |
| KT access keys | Scoped/external access | **KEEP** (simplify), useful for contractors/auditors |
| Exit handoff engine | The KT trigger event | **KEEP & finish** — checklist gen + sign-off + report |
| Mentor: two disconnected workflows | Historical accident | **MERGE into one mentor workspace/inbox** |
| Reports/intel/gradebook | Manager & exec visibility | **KEEP**; add missing KT analytics (currently 115-line stub) |
| Org hierarchy (5 tables) | Enterprise structure | **KEEP concept, collapse to OrgUnit tree** |
| Multi-tenant scaffolding | SaaS ambition | **REMOVE from scope** (owner decision) — simplifies auth to subtree scoping |
| system.py legacy config | Superseded | **DELETE** |
| Resources center / notifications / exports / audit / platform dashboard | Standard enterprise needs | **KEEP**, slot into modules |
| Root junk & scratch scripts | Debug history | **DELETE/archive** |

**Missing (build):** KT analytics, indexing-failure visibility, unified mentor inbox, handoff completion report, breadcrumbs/global search (later), invite-accept flow polish.

## 14. Feature dependencies

`identity` → everything. `org` → assessment, kt, reporting. `ai` → assessment (AI grading/gen), kt (embed/RAG), reporting (AI summaries). `jobs` → AI grading, KT indexing, exports, email. KT chat → KT indexing → KT review → KT documents. Handoff → KT documents + org. Reports → attempts + (new) KT tables. **No assessment↔KT data dependency by design.**

## 15. Roadmap & prioritized implementation plan

Adapted from the companion technical plan (8 phases, ~13 weeks solo; phases overlap). Priority logic: *fix the dead product first, then de-noodle around the working one, rebuild frontend once backend contracts are stable.*

| Phase | Weeks | Delivers | Risk |
|---|---|---|---|
| **1. Foundation** | 2 | `modules/` + `shared/` skeleton; async-only DB; `OrgUnit`+`UserOrgRole`+`KTDocumentChunk` tables + backfill + compat layer; repo-root cleanup | Low |
| **2. KT resurrection** | 2.5 | pgvector ingestion + RAG chat live (mentor approval **kept** in the loop); `kt.py` split into 7 routers; Neo4j no longer queried. **KT becomes a working product again** | Med |
| **3. Backend de-noodling** | 2 | Split `auth.py`/`quiz.py`/`admin.py`/`reports.py`/`ai.py`; service layer everywhere; **unified Assessment engine** (quiz+exam merge); rebuilt email-based auth flows | Med |
| **4. Frontend rebuild** | 2 | Real routes replace state machine; typed OpenAPI client + React Query; UI kit; god components decomposed; one design system | Med |
| **5. OrgUnit flip** | 1.5 | All scoping/queries on OrgUnit tree; validation vs old path; old tables read-only | **High** |
| **6. Cleanup + mentor merge** | 1 | Delete dead KT services/Neo4j deps/styled-jsx/legacy files; **unified mentor inbox**; error boundaries | Low |
| **7. Archive & tune** | 1 | Old tables archived; indexes verified; docs per module | Low |
| **8. Deploy & monitor** | 0.5 | Prod rollout, smoke tests, rollback plan | Med |

**Quick wins inside Phase 1:** delete root junk + `system.py` + duplicate RichText; add `index_failed` visibility to current KT UI so failures are at least honest.

## 16. Risks, gaps, recommendations

**Top risks:** (1) OrgUnit data migration (Phase 5) — mitigate with idempotent backfill, dual-read compat layer, permission-diff audit on real users, backup; (2) frontend rebuild regressions in the *working* assessment flow — E2E tests on take/grade/report before cutover; (3) KT chat quality on pgvector — measure retrieval on a seeded corpus before calling Phase 2 done; (4) solo-builder burnout — every phase ends deployable, so you can pause anywhere.

**Gaps found that this plan closes:** dead KT downstream, mentor split-brain, KT analytics stub, no URLs/deep links, untyped API, tenancy half-migration, 12 god files, silent job failures.

**Recommendations:** commit this + companion doc to `docs/product-plan/`; adopt "no file >800 lines, no logic in routers, one DB pattern" as review gates; run `graphify update .` after each phase; keep the 263-test suite green as the migration harness and add per-module tests as modules land.

## 17. Verification (per phase & final)

- **Phase 2 gate:** upload real doc → mentor approve → chunks in `kt_document_chunks` → chat answers with citations (E2E test + manual).
- **Phase 3 gate:** full pytest suite green; endpoint parity sweep (163+ endpoints, 0×500) re-run as after previous hardening sprints.
- **Phase 4 gate:** Playwright/agent-browser E2E: login → dashboard → take assessment → result; deep-link + refresh + back on every route.
- **Phase 5 gate:** permission-diff script (old path vs OrgUnit path) over all users = 0 mismatches.
- **Final:** smoke of all seven persona journeys in §5–6; `wc -l` audit confirms no file >800 lines; grep confirms zero `Promise<any>`, zero sync sessions, zero Neo4j imports.
