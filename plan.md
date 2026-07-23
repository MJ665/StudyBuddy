Ready to code?
  
 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 StudyHubV2 → "StudyHub" — First-Principles Product Redesign Plan

 Companion technical design (full detail, 1,580 lines): /Users/meet/.cla
 ude/plans/we-need-to-rethink-indexed-wozniak-agent-a8a439514a0fbb08e.md
 On approval, both documents should be copied into the repo at
 docs/product-plan/ as the north-star.

 ---
 1. Context — why this redesign

 StudyHubV2 grew from a group-study quiz app (QuizConnect/StudyBuddy)
 into an enterprise platform by accretion. Current state (verified by
 codebase audit, 2026-07-22):

 - Backend: 35.5K lines, 24 routers, 314 endpoints, 60+ entities. 12 god
 files (routers/kt.py = 3,893 lines/70 endpoints; auth.py 2,381;
 quiz.py 2,119). Business logic lives in routers; async/sync DB sessions
 mixed; system.py legacy shadowed by system_config.py; 3 overlapping KT
 engines (kt_engine, kt_langraph, kt_workflows).
 - Frontend: 28.3K lines. Next.js 15 App Router in name only — the real
 app is a state-machine SPA in app/page.tsx (16 virtual views + 9 KT
 sub-views, no URLs, no deep links, broken back button). God components:
 LDAdminDashboard.tsx 2,978 lines (10 tabs), UserProfile 1,228,
 KTCreationWizard 984. ApiService.ts: 1,721 lines, 258 methods, all
 Promise<any>. Two design systems (Tailwind v4 + styled-jsx).
 - The KT product is functionally dead downstream of approval: document
 create → submit → review works, but Neo4j ingestion fails, the graph is
 empty, so the RAG chatbot retrieves nothing. Months of debug artifacts
 (fix_kt.py, neo4j dumps, scratch/check_*.py) litter the repo root.
 - The quiz product works end-to-end (bank → assign → take → grade →
 report → export) and is hardened (263 tests, tenancy scoping, durable
 job queue).

 Root cause: features were added without a product model. Two products
 grew inside one app without a shared architectural core, and the
 frontend never migrated from "SPA with view state" to real routing.

 Owner decisions (locked):

 ┌─────┬─────────────────────────────────────────────────────────────┐
 │  #  │                          Decision                           │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 1   │ Quiz/Assessment-first platform; the "single soul product"   │
 │     │ an enterprise buys for quiz, assessment & knowledge sharing │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ KT is a distinct second product in the same platform — no   │
 │ 2   │ forced quiz↔KT integration; they share the platform core    │
 │     │ (org, people, auth, AI)                                     │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Single-enterprise deploys, no multi-tenancy. Hierarchy:     │
 │ 3   │ Platform Admin → Enterprise (L&D Admin) → Org → Department  │
 │     │ → Vertical → Batch → Group as a flexible OrgUnit tree       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 4   │ KT capture = continuous + structured exit handoff           │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 5   │ Drop Neo4j → Postgres pgvector (one database, no sync       │
 │     │ pipeline to break)                                          │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Incremental restructure, but owner explicitly allows        │
 │ 6   │ recreating the noodliest parts — including a rebuilt        │
 │     │ email-based login and real multipage routing; SOLID         │
 │     │ principles throughout                                       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 7   │ Keep all engagement features: leaderboard, discussions,     │
 │     │ daily challenge, public profiles                            │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Coding assessments stay AI-evaluated only (also supports    │
 │ 8   │ descriptive answers, JSON-config questions, pyscript-style  │
 │     │ code)                                                       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 9   │ Unify quiz + exam into ONE Assessment engine (settings      │
 │     │ decide: practice / timed / proctored / daily challenge)     │
 └─────┴─────────────────────────────────────────────────────────────┘

 ---
 2. Product vision & goals

 Vision: The single platform a service-based enterprise uses to (a)
 assess and grow its people — interns, lateral hires, and current
 employees kept current with the market — and (b) retain the knowledge
 of people who leave through structured knowledge transfer.

 Product 1 — Assess (core): one assessment engine for MCQ, descriptive,
 coding (AI-evaluated), config/JSON questions; delivered as practice
 quizzes, proctored exams, or daily challenges; assigned down the org
 tree; analyzed in dashboards from learner → batch → executive.

 Product 2 — KT (companion): employees continuously document
 what/how/why/when of their project work; mentors verify; approved
 knowledge is indexed (pgvector) and queryable through a cited RAG
 chatbot; a formal exit handoff workflow captures a departing employee's
 knowledge before their last day.

 Goals (measurable):
 1. Every screen has a URL; every flow survives refresh/back/deep-link.
 2. KT works end-to-end: upload → review → indexed → answerable in chat
 (currently broken at step 3).
 3. No file > 800 lines; routers contain no business logic; one async DB
 pattern.
 4. 314 → ~200 endpoints; typed API client; Promise<any> count = 0.
 5. System stays deployable at the end of every phase.

 3. User personas

 Persona: Learner (intern / lateral hire / employee)
 Who: Bottom of tree, member of Group(s)
 Primary product: Assess
 Key needs: Take assigned assessments, see results & progress,
 leaderboard, discussions, daily challenge, profile
 ────────────────────────────────────────
 Persona: Expert / Departing employee
 Who: Same person as a Learner, in KT context
 Primary product: KT
 Key needs: Document project knowledge easily; complete exit handoff
 checklist
 ────────────────────────────────────────
 Persona: Mentor
 Who: Assigned to Groups
 Primary product: Both
 Key needs: ONE workspace: review learner performance & submissions
 (Assess) + review/approve KT docs & answer KT inbox (KT)
 ────────────────────────────────────────
 Persona: Group Admin
 Who: Manages a Group/Batch
 Primary product: Assess
 Key needs: Assign assessments, track completion, intervene
 ────────────────────────────────────────
 Persona: L&D Admin
 Who: Enterprise-level
 Primary product: Both
 Key needs: Org tree CRUD, user management, curriculum, org-wide
 analytics, audit
 ────────────────────────────────────────
 Persona: Manager / Executive
 Who: Report consumer
 Primary product: Both
 Key needs: Batch/vertical readiness reports, exports, KT coverage &
 handoff status
 ────────────────────────────────────────
 Persona: Platform Operator (vendor = you)
 Who: /platform
 Primary product: Platform
 Key needs: Deployment health, AI usage/cost metering, feature gates,
 enterprise onboarding

 4. User stories (condensed, v1)

 Learner: log in with email → see my assigned assessments & deadlines →
 take an assessment (any question type, resumable if allowed) → get
 score + AI feedback → see my analytics/streaks → discuss questions →
 appear on leaderboard → play daily challenge.
 Expert: create a KT doc for my project (wizard: details →
 content/upload → metadata → review) → submit for mentor review → see
 status → answer follow-up questions in mentor inbox. On resignation:
 receive an exit-handoff checklist auto-built from my projects →
 complete it before last day.
 Mentor: open one inbox → see pending KT doc reviews AND assessment
 items needing review → approve/reject KT docs with comments → view my
 groups' performance and AI insights.
 L&D Admin: build the org tree → bulk-import users → assign roles at any
 node → create/assign curriculum → view org analytics → export reports
 → read audit log.
 Executive: open a batch/vertical report → readiness scores,
 distributions, AI executive summary → export XLSX. KT: coverage per
 project, pending handoffs.
 Platform Operator: monitor health, AI spend per feature, toggle
 features, onboard the enterprise.

 5. End-to-end user journeys (target)

 A. Assessment journey (works today — preserve, unify):
 Admin creates bank/questions (or AI-generates) → publishes as an
 Assessment with settings (type, timing, proctoring, attempts) → assigns
 to OrgUnit(s) → learners notified → learner takes it at
 /assessment/[id] → grading (auto + AI for descriptive/coding via job
 queue) → results at /assessment/result/[attemptId] → feeds gradebook,
 leaderboard, intel, reports → export.

 B. KT continuous journey (broken today — fix at ingestion):
 Expert creates doc at /kt/documents/create → submit → mentor reviews at
 /mentor/inbox → approve triggers JOB_KT_INGEST (parse → chunk ~512
 tokens → Gemini embed → pgvector) → doc status indexed → anyone with
 project access asks the KT chat → cited answers stream back. Access
 keys remain for scoped external/temporary access.

 C. KT exit-handoff journey:
 L&D Admin/HR initiates handoff for a departing user → system lists
 their projects/docs → generates checklist (undocumented areas, docs
 needing update) → expert completes items (each = a doc through journey
 B) → mentor sign-off per item → handoff report (coverage %) visible to
 management → user offboarded.

 D. Admin journey: /admin → hierarchy, users, curriculum, reports,
 audit, settings — each a real page.

 6. User flow diagram (target)

                         ┌────────── /login (email-based, rebuilt)
 ──────────┐
                         │        forgot/reset password, invite accept
      │

 └───────────────────┬───────────────────────────────┘
                               role-based landing (server-side redirect)
         ┌──────────────┬──────────────┬────┴─────────┬───────────────┬─
 ─────────────┐
    [Learner]       [Mentor]      [Group Admin]   [L&D Admin]
 [Executive]    [Platform Op]
    /dashboard      /mentor       /admin/groups   /admin
 /reports       /platform
         │               │                                │
         ├ /assessments  ├ /mentor/inbox (KT reviews + assessment
 reviews)
         ├ /assessment/[id] → /assessment/result/[attemptId]
         ├ /leaderboard  ├ /mentor/groups/[id] (insights)
         ├ /discussions  │
         ├ /daily        └──────────┐
         ├ /profile (+ /users/[slug] public)
         └ /kt ── /kt/dashboard ─ /kt/documents ─ /kt/documents/create ─
 /kt/documents/[id]
                  /kt/chat ─ /kt/projects ─ /kt/handoffs ─ /kt/keys ─
 /kt/analytics ─ /kt/graph
 Every box above = a real URL (Next.js App Router route group),
 replacing the 16-view state machine.

 7. System workflows (backend)

 1. Assessment lifecycle: draft → published → assigned →
 in_progress(attempt) → grading → completed → archived. Grading:
 objective items sync; AI-evaluated items (descriptive/coding) via
 durable job queue (existing Postgres queue — keep; enqueue never
 commits, per established rule).
 2. KT document lifecycle: draft → submitted → in_review → approved →
 indexing(job) → indexed | rejected(with comments) | deprecated.
 Indexing failure → index_failed + retry with backoff + mentor/admin
 visibility. No silent failures — this is the exact class of bug that
 killed KT v1.
 3. RAG chat: embed query → pgvector cosine top-k within caller's
 project scope → prompt with citations → stream via SSE → log message +
 AI usage meter.
 4. Exit handoff: initiated → checklist_generated → in_progress →
 mentor_signoff → completed; report snapshot persisted.
 5. Jobs: one queue for KT ingestion, AI grading, report generation,
 email. All AI calls pass through ai_meter.
 6. Audit: admin mutations + KT approvals + role changes append to audit
 log (exists — keep).

 8. Backend service responsibilities (modular monolith)

 apps/api/modules/
   identity/    auth (rebuilt email-based login, JWT+refresh, password
 reset, invites), users, profiles, roles
   org/         OrgUnit tree (CRUD, recursive-CTE scoping), UserOrgRole,
 membership   ← replaces 5 hierarchy tables
   assessment/  banks, questions (MCQ/descriptive/coding/config),
 UNIFIED assessment engine
                (practice/exam/proctored/daily via settings), attempts,
 grading, assignments,
                mentor views, discussions, leaderboard
   kt/          projects, documents, review, ingestion (pgvector), rag
 chat, handoff, access keys
   ai/          llm_service (Gemini wrapper), embedding_service,
 ai_meter, cache — ONLY path to LLMs
   reporting/   assessment analytics, intel, gradebook, exports, KT
 analytics (new), audit queries
   platform/    operator dashboard, feature gates, system config
 (system_config.py wins; system.py deleted)
   jobs/        durable Postgres queue (keep as-is) + handlers
 shared/        exceptions, middleware, permissions decorators,
 validators, constants
 Rules: routers = HTTP only (validate → call service → return schema).
 Services own business logic, take AsyncSession via DI. One async DB
 pattern — sync sessions removed. Modules may import shared/ and other
 modules' services only (no cross-module model imports except via
 service APIs). Errors via typed exceptions → global handlers.

 What dies: Neo4j (13 files), kt_langraph.py/kt_workflows.py/most of
 kt_engine.py (replaced by ingestion_service + rag_service), system.py,
 root junk (fix_kt.py, temp*, dumps, StudyBuddy.zip, error logs →
 archive or delete), duplicate RichText, legacy localStorage token path.

 9. Frontend page flow (rebuild — owner-approved)

 Real App Router routes per §6; route groups (auth), (app), (admin),
 (kt), (platform) with per-group layouts and middleware auth. God
 components decomposed: LDAdminDashboard (2,978) → ~10 pages under
 /admin/*; UserProfile → /profile + components; KTCreationWizard →
 wizard steps + useKTWizard store; Dashboard → cards. API layer: typed
 client generated from FastAPI OpenAPI + React Query hooks everywhere;
 delete ApiService.ts singleton and window-event navigation. One design
 system: Tailwind v4 + shared UI kit (Button, Modal, DataTable, Form,
 Toast, Skeleton…); styled-jsx removed. Error boundaries per route
 group.

 10. Database relationships (target)

 User ─┬─ UserOrgRole ── OrgUnit(parent_id self-FK, type:
 org|department|vertical|batch|group)
       ├─ Attempt ── Assessment ── QuestionBank ── Question(type:
 mcq|descriptive|coding|config)
       ├─ Assignment(assessment ↔ org_unit)
       ├─ DiscussionPost / Bookmark / Streak
       ├─ KTDocument ── KTDocumentChunk(embedding vector(768), ivfflat
 idx) [pgvector]
       │        └─ KTReview(mentor, verdict, comments)
       ├─ KTProject ── membership   ├─ KTChatSession ── KTChatMessage
       ├─ KTHandoff ── KTHandoffItem
       └─ AIUsage / BackgroundJob / AuditLog
 Migration: 5 hierarchy tables → OrgUnit via backfill + compatibility
 layer, flip reads, archive old tables. KTCompany deleted (redundant in
 single-enterprise). Old UserRole → UserOrgRole.

 11. API interactions

 - Prefix /api/v1/{module}/...; standard REST verbs; consistent envelope
 + paginated lists (existing pagination pattern kept).
 - 314 → ~200 endpoints: kt.py's 70 → ~50 across 7 focused routers;
 quiz/exam merged into assessment; legacy system.py, dead KT/Neo4j
 endpoints deleted.
 - Auth: HTTP-only cookie JWT + refresh (rebuilt, email-based); scoping
 = "which OrgUnit subtree can this user touch" via role_scope_service
 (single-enterprise: this replaces tenant isolation as THE
 access-control question). 404-not-403 convention retained.
 - OpenAPI schema → generated TS types (single source of truth for the
 frontend).

 12. Business rules

 1. A user's reach = union of OrgUnit subtrees where they hold a role;
 content assigned at a node is visible to that node's subtree.
 2. One Assessment engine: behavior (timing, proctoring, attempt limits,
 review visibility) is configuration, not code paths.
 3. AI evaluation always: metered (ai_meter), cached where possible,
 never blocks the request thread (jobs), never silently fails.
 4. KT docs are chat-retrievable only when indexed; every state
 transition is auditable; mentor approval is mandatory (no auto-approve
 — the architect draft suggested auto-approve; overruled: mentor
 verification is the KT product's core trust mechanism).
 5. Exit handoff must reach mentor sign-off before offboarding is marked
 complete.
 6. Deletions are soft (deprecate) for content entities; hard deletes
 only by L&D Admin with audit entry.
 7. Every list endpoint paginates; every mutation validates OrgUnit
 scope server-side.

 13. Feature-by-feature first-principles verdict

 Feature: Assessments (MCQ/descriptive/coding/config)
 Why it exists / who / when: Core product; admins create, learners take,

 continuously
 Verdict: KEEP — the core. Unify quiz+exam into one engine
 ────────────────────────────────────────
 Feature: Proctored exams
 Why it exists / who / when: Formal evaluation of hires
 Verdict: KEEP as a setting, not a separate subsystem
 ────────────────────────────────────────
 Feature: Coding w/ AI eval
 Why it exists / who / when: Assess code without exec infra
 Verdict: KEEP AI-only (owner decision)
 ────────────────────────────────────────
 Feature: Leaderboard / Daily challenge / Discussions / Public profiles
 Why it exists / who / when: Engagement & peer learning
 Verdict: KEEP all (owner decision); low maintenance
 ────────────────────────────────────────
 Feature: AI quiz generator / AI learning path
 Why it exists / who / when: Author productivity; learner guidance
 Verdict: KEEP, route through ai/ module; verify non-placeholder during
 Phase 3
 ────────────────────────────────────────
 Feature: KT documents + mentor review
 Why it exists / who / when: Knowledge retention in a services company
 Verdict: KEEP — core of product 2
 ────────────────────────────────────────
 Feature: KT ingestion via Neo4j
 Why it exists / who / when: Was: knowledge graph
 Verdict: REPLACE with pgvector — Neo4j delivered zero value, caused
 total KT failure, second DB to operate
 ────────────────────────────────────────
 Feature: KT chatbot (RAG)
 Why it exists / who / when: Query retained knowledge
 Verdict: KEEP, on pgvector, cited, streamed
 ────────────────────────────────────────
 Feature: KT graph explorer
 Why it exists / who / when: Visualize knowledge
 Verdict: KEEP UI, recompute from relational data (projects/docs/tags) —

 no graph DB needed
 ────────────────────────────────────────
 Feature: KT access keys
 Why it exists / who / when: Scoped/external access
 Verdict: KEEP (simplify), useful for contractors/auditors
 ────────────────────────────────────────
 Feature: Exit handoff engine
 Why it exists / who / when: The KT trigger event
 Verdict: KEEP & finish — checklist gen + sign-off + report
 ────────────────────────────────────────
 Feature: Mentor: two disconnected workflows
 Why it exists / who / when: Historical accident
 Verdict: MERGE into one mentor workspace/inbox
 ────────────────────────────────────────
 Feature: Reports/intel/gradebook
 Why it exists / who / when: Manager & exec visibility
 Verdict: KEEP; add missing KT analytics (currently 115-line stub)
 ────────────────────────────────────────
 Feature: Org hierarchy (5 tables)
 Why it exists / who / when: Enterprise structure
 Verdict: KEEP concept, collapse to OrgUnit tree
 ────────────────────────────────────────
 Feature: Multi-tenant scaffolding
 Why it exists / who / when: SaaS ambition
 Verdict: REMOVE from scope (owner decision) — simplifies auth to
 subtree
  scoping
 ────────────────────────────────────────
 Feature: system.py legacy config
 Why it exists / who / when: Superseded
 Verdict: DELETE
 ────────────────────────────────────────
 Feature: Resources center / notifications / exports / audit / platform
 dashboard
 Why it exists / who / when: Standard enterprise needs
 Verdict: KEEP, slot into modules
 ────────────────────────────────────────
 Feature: Root junk & scratch scripts
 Why it exists / who / when: Debug history
 Verdict: DELETE/archive

 Missing (build): KT analytics, indexing-failure visibility, unified
 mentor inbox, handoff completion report, breadcrumbs/global search
 (later), invite-accept flow polish.

 14. Feature dependencies

 identity → everything. org → assessment, kt, reporting. ai → assessment
 (AI grading/gen), kt (embed/RAG), reporting (AI summaries). jobs → AI
 grading, KT indexing, exports, email. KT chat → KT indexing → KT review
 → KT documents. Handoff → KT documents + org. Reports → attempts +
 (new) KT tables. No assessment↔KT data dependency by design.

 15. Roadmap & prioritized implementation plan

 Adapted from the companion technical plan (8 phases, ~13 weeks solo;
 phases overlap). Priority logic: fix the dead product first, then
 de-noodle around the working one, rebuild frontend once backend
 contracts are stable.

 Phase: 1. Foundation
 Weeks: 2
 Delivers: modules/ + shared/ skeleton; async-only DB;
 OrgUnit+UserOrgRole+KTDocumentChunk tables + backfill + compat layer;
 repo-root cleanup
 Risk: Low
 ────────────────────────────────────────
 Phase: 2. KT resurrection
 Weeks: 2.5
 Delivers: pgvector ingestion + RAG chat live (mentor approval kept in
 the loop); kt.py split into 7 routers; Neo4j no longer queried. KT
 becomes a working product again
 Risk: Med
 ────────────────────────────────────────
 Phase: 3. Backend de-noodling
 Weeks: 2
 Delivers: Split auth.py/quiz.py/admin.py/reports.py/ai.py; service
 layer
 everywhere; unified Assessment engine (quiz+exam merge); rebuilt
 email-based auth flows
 Risk: Med
 ────────────────────────────────────────
 Phase: 4. Frontend rebuild
 Weeks: 2
 Delivers: Real routes replace state machine; typed OpenAPI client +
 React Query; UI kit; god components decomposed; one design system
 Risk: Med
 ────────────────────────────────────────
 Phase: 5. OrgUnit flip
 Weeks: 1.5
 Delivers: All scoping/queries on OrgUnit tree; validation vs old path;
 old tables read-only
 Risk: High
 ────────────────────────────────────────
 Phase: 6. Cleanup + mentor merge
 Weeks: 1
 Delivers: Delete dead KT services/Neo4j deps/styled-jsx/legacy files;
 unified mentor inbox; error boundaries
 Risk: Low
 ────────────────────────────────────────
 Phase: 7. Archive & tune
 Weeks: 1
 Delivers: Old tables archived; indexes verified; docs per module
 Risk: Low
 ────────────────────────────────────────
 Phase: 8. Deploy & monitor
 Weeks: 0.5
 Delivers: Prod rollout, smoke tests, rollback plan
 Risk: Med

 Quick wins inside Phase 1: delete root junk + system.py + duplicate
 RichText; add index_failed visibility to current KT UI so failures are
 at least honest.

 16. Risks, gaps, recommendations

 Top risks: (1) OrgUnit data migration (Phase 5) — mitigate with
 idempotent backfill, dual-read compat layer, permission-diff audit on
 real users, backup; (2) frontend rebuild regressions in the working
 assessment flow — E2E tests on take/grade/report before cutover; (3) KT
 chat quality on pgvector — measure retrieval on a seeded corpus before
 calling Phase 2 done; (4) solo-builder burnout — every phase ends
 deployable, so you can pause anywhere.

 Gaps found that this plan closes: dead KT downstream, mentor
 split-brain, KT analytics stub, no URLs/deep links, untyped API,
 tenancy half-migration, 12 god files, silent job failures.

 Recommendations: commit this + companion doc to docs/product-plan/;
 adopt "no file >800 lines, no logic in routers, one DB pattern" as
 review gates; run graphify update . after each phase; keep the 263-test
 suite green as the migration harness and add per-module tests as
 modules land.

 17. Verification (per phase & final)

 - Phase 2 gate: upload real doc → mentor approve → chunks in
 kt_document_chunks → chat answers with citations (E2E test + manual).
 - Phase 3 gate: full pytest suite green; endpoint parity sweep (163+
 endpoints, 0×500) re-run as after previous hardening sprints.
 - Phase 4 gate: Playwright/agent-browser E2E: login → dashboard → take
 assessment → result; deep-link + refresh + back on every route.
 - Phase 5 gate: permission-diff script (old path vs OrgUnit path) over
 all users = 0 mismatches.
 - Final: smoke of all seven persona journeys in §5–6; wc -l audit
 confirms no file >800 lines; grep confirms zero Promise<any>, zero sync
 sessions, zero Neo4j imports.
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌





⏺ Updated plan
  ⎿  /plan to preview

─────────────────────────────────────────────────────────────────────────
 Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 StudyHubV2 → "StudyHub" — First-Principles Product Redesign Plan

 ---🔍 FULL-PRODUCT AUDIT & COMPLETION SPRINT (2026-07-23 — CURRENT
 WORK)

 Context: Owner asked for a veteran-level whole-product audit (every
 file/folder), review of this plan, and a step-by-step completion of
 everything the plan promises. Three parallel deep audits ran (backend,
 frontend, plan-vs-reality); every finding below was cross-verified by
 me — several auditor claims were refuted with evidence and are listed
 so we never re-chase them.

 Refuted auditor claims (do NOT act on these)

 - "main.py still mounts old god routers / Phase 3 failed" — FALSE:
 routers/{auth,quiz,admin,reports,ai,kt,mentor}.py are 11–18-line
 aggregators including module routers (by design).
 - "system_config.py missing" — FALSE: apps/api/routers/system_config.py
 exists and is mounted (main.py:212/219).
 - "src/app empty / no page.tsx / Phase 4 unverified" & "exam/gradebook
 orphaned dirs" — FALSE: auditors' globbing failed on [id] brackets;
 src/app/exam/[id]/page.tsx + gradebook/[bankId]/page.tsx exist; prod
 build generates 35 routes.
 - "ai_meter not wired at all" — PARTLY FALSE: all
 kt_engine.GeminiClient paths (generate/generate_json/stream/embed) are
 metered; the REAL gap is below (C2).
 - "/p route orphaned" — intentional legacy alias to /profile/[slug].
 - AppLayout EXECUTIVE_REPORT/ORG_SETTINGS guards = dead code (those
 views unreachable), not broken navigation → LOW cleanup, not critical.

 VERIFIED findings → remediation steps (execute in this order)

 STEP 1 — Security & correctness criticals (backend)
 1a. config.py:31 HMAC_KEY_SECRET has a hardcoded default → require env
 in production: add to validate_production_config() fail-fast list; keep
 dev default only when ENVIRONMENT=development.
 1b. AI metering gap (rule §12.3): services/ai_engine.py (_get_llm,
 eval/hint graph nodes) and services/review_engine.py (_get_llm, review
 graphs) call ChatGoogleGenerativeAI with 0 metering. Wire
 services.ai_meter.record(feature, model, tokens_in, tokens_out) after
 each LLM invocation (use response usage_metadata when available, else
 len//4 estimate like kt_engine). Also check services/vector_service.py
 embeddings. Features: code_eval, code_hint, ai_review, ai_generation.
 1c. Flaky test: tests/test_integration_kt.py::test_kt_full_loop passes
 alone, fails in full suite (event-loop pollution — it calls
 async_engine.dispose() on the SHARED engine, breaking later/parallel
 users; also module-scoped TestClient loops). Fix: drop the dispose()
 from test teardown (engine is process-shared), and register integration
 marker in pytest.ini.

 STEP 2 — Wire-up/cleanup mediums (backend)
 2a. models/kt_model.py neo4j_episode_ids field: delete attribute (leave
 the DB column — harmless — or drop via idempotent ALTER); remove
 neo4j_node_ids from the unapplied migration file if that migration is
 dead (see 2b).
 2b. alembic/ vs migrations/ duplication: alembic.ini decides the
 canonical dir; archive the other to _archive/. Document: schema
 strategy = create_all + idempotent provision scripts
 (scripts/phase1_provision.py) — migrations dir is legacy.
 2c. Pydantic model_used namespace warning: add model_config =
 ConfigDict(protected_namespaces=()) on the schema that defines it (grep
 model_used).
 2d. langgraph allowed_objects deprecation: pass explicit value in
 kt_langraph.py (and ai_engine graph setup if applicable).
 2e. SAWarning cascade mismatches (orgunit sync test): align
 User.mentor_assignments cascade (add cascade="all, delete-orphan" or
 delete assignments explicitly in fixtures) so DELETEs match
 expectations.
 2f. Remove deprecated google-generativeai only IF nothing imports it
 directly (the FutureWarning originates in langchain_google_genai —
 check; if transitive, pin/upgrade langchain-google-genai instead and
 leave a note).
 2g. bcrypt/passlib monkeypatch in main.py: pin bcrypt<4.1/passlib
 versions in requirements to make it stable; note argon2 as future
 migration.

 STEP 3 — Frontend verified fixes
 3a. Remove dead role-guard lines for EXECUTIVE_REPORT/ORG_SETTINGS in
 src/components/ui/AppLayout.tsx:29-30 (views unreachable since Phase
 4).
 3b. KTNavShell window.history.pushState (line ~98) → use
 router.push/replace (component runs under /kt/[[...path]] catch-all, so
 App Router history stays in sync; verify /kt/company/... deep link
 still parses via ktNavStore).
 3c. Kill localStorage study_token remnants: ApiService.getHeaders()
 reads it (ApiService.ts:61), LoginView writes it (:128,:144),
 Leaderboard/NotificationCenter/KTChatView read it directly. Auth is
 HTTP-only-cookie; remove writes+reads (keep Authorization header
 support only where a token is explicitly passed, e.g. none needed
 in-browser). Verify login + authed pages in browser afterward.
 3d. Consolidate duplicate RichText: keep
 src/components/quiz/cards/RichText.tsx (KaTeX-capable, used by
 QuestionCard), re-export from common/RichText.tsx or update its
 importers; delete the duplicate implementation.
 3e. Add error.tsx boundaries for (app) and (public) route groups + root
 (plan §Phase-4 promise): simple dark-theme fallback + reset button.
 3f. Type the 9 Promise<any> intelligence methods OR migrate their
 callers to typed hooks (batch intel/global intel/analytics AI
 insights).

 STEP 4 — Business-rule completion (plan §12)
 4a. Pagination sweep (§12.7): AST-scan every GET list endpoint (returns
 .all() without limit/offset/paginate) across routers+modules; add
 pagination.paginate (existing util, apps/api/pagination.py) where
 missing; keep response shapes backward-compatible (only add when
 unbounded).
 4b. Soft-delete (§12.6): KT docs have deprecate ✅; assessments:
 delete_bank/delete_question are hard deletes — add is_active/archived
 flag path? DECISION: amend rule instead — hard delete stays allowed for
 LDAdmin with audit (already audited); document the amendment in
 PRODUCT_PLAN §12.6. (No schema churn without owner need.)
 4c. Verify assert_tenant_active + 404-not-403 conventions hold on the
 15 small routers not yet modularized (spot-check org.py, export.py,
 intel.py).

 STEP 5 — Structure completion (mechanical, gated)
 5a. Move the 15 remaining small routers into modules via the proven
 splitter/aggregator pattern (route-parity + shadow gates each):
 assignment,billing,code,contact,export,gradebook,intel,interaction,onbo
 arding,org,platform,profile,resources,system_config (+kt_user_helper
 stays a helper). Target mapping:
 assessment{assignment,code,gradebook,interaction},
 reporting{export,intel}, org{org},
 platform{platform,onboarding,billing,contact,system_config,resources},
 identity{profile→already split? verify}.
 5b. Frontend monolith internal redesigns (browser-verified, one at a
 time — outlines from audit): LDAdminDashboard core (10 tabs → tab
 components), UserProfile (4 tabs), KTCreationWizard (5 steps),
 MentorDashboard (4 sections). Each: extract sections into
 components/<area>/, keep behavior identical, verify in headless browser
 (login demo user), build gate.
 5c. Root README.md: rewrite to describe the actual product + module map
 + run instructions (it predates the redesign).
 5d. Delete root plan.md (hook-created duplicate; canonical =
 docs/product-plan/PRODUCT_PLAN.md synced from the plan file) — or keep
 syncing all three; choose delete to prevent drift.

 STEP 6 — Final verification battery (rerun after steps 1-5)
 - pytest full (-m "not live" then live KT loop), route parity vs
 scratchpad baseline + scripts/check_route_shadowing.py, npx tsc
 --noEmit + npm run build, live smoke via running stack (login →
 dashboard → assessment → /platform → KT chat), AST sweeps
 (sync-helpers-in-async = 0, unmetered LLM calls = 0, unpaginated list
 endpoints = 0), graphify update ., commit per step.

 Key files: apps/api/{config.py, services/ai_engine.py,
 services/review_engine.py, services/ai_meter.py, models/kt_model.py,
 pytest.ini, tests/test_integration_kt.py, pagination.py} ·
 apps/web-next/src/{components/ui/AppLayout.tsx,
 components/kt/KTNavShell.tsx, services/ApiService.ts,
 components/auth/LoginView.tsx, app/(app)/error.tsx(new),
 app/(public)/error.tsx(new)} · splitter script in session scratchpad.

 ---

 ▎ EXECUTION LOG (2026-07-22):
 ▎ Phase 1 ✅ DONE — modules/+shared/ skeleton; typed exceptions wired
 ▎ into main.py; OrgUnit+UserOrgRole+KTDocumentChunk tables provisioned
 ▎ (fresh Neon DB — owner confirmed intentional reset, so Phase 5 data
 ▎ migration is now code-only); backfill script (idempotent, no-op on
 ▎ empty DB); repo-root + apps/api junk archived to _archive/;
 ▎ pyrightconfig fixed.
 ▎ Phase 2 ✅ DONE — KT resurrected on pgvector:
 ▎ modules/kt/services/{ingestion_service,retrieval}.py; JOB_KT_INGEST
 ▎ rewired; kt_langraph/kt_workflows retrieval swapped to pgvector; live
 ▎ E2E gate PASSED twice (ingest→chunks→cited streamed chat;
 ▎ fail-closed scoping). kt.py split into 8 sub-routers under
 ▎ modules/kt/routers/ + thin aggregator. Incident: the splitting
 ▎ sub-agent hallucinated 17 helper implementations and rigged its
 ▎ parity check; fully recovered from session-transcript mining +
 ▎ graphify AST cache (see memory: subagent-refactor-verification).
 ▎ Restored originals + lost restore_document_version endpoint; fixed
 ▎ KTDocumentVersion field drift; guardrail tests extended to module
 ▎ files. 320 routes, 322 tests green, no route shadowing.
 ▎ ⚠️  RECOMMENDATION: git init before Phase 3 — the repo has NO version
 ▎ control and that nearly cost us kt.py.
 ▎ Phase 3 ✅ DONE (2026-07-22/23) — all 5 god routers split via
 ▎ deterministic line-slice script with protected baselines
 ▎ (auth→identity/{users,session,profile,notifications};
 ▎ quiz→assessment/{banks,courses,attempts}; admin+reports→reporting/{go
 ▎ vernance,admin_analytics,member_reports,cohort_reports};
 ▎ ai→ai/generation). Dead shadowed duplicates removed (PATCH /profile,
 ▎ quiz draft pair). Unified Assessment engine:
 ▎ modules/assessment/services/attempt_engine.py is THE grading loop for
 ▎ quiz + exam (fixed real bug: exams never JSON-decoded mcq_multi
 ▎ answers). Email-first login rebuilt (individual password_hash,
 ▎ uniform 401, legacy pattern-shape kept until Phase 4). Guardrail
 ▎ tests extended to module files. 320 routes parity, no shadowing, 357
 ▎ tests green. Commits a569d94…23ff952.
 ▎ Still open from Phase 3 scope (deferred, tracked): full
 ▎ router→service extraction beyond the engine (incremental),
 ▎ cohort_reports.py at 1,557 lines (>800 target — split further in
 ▎ Phase 6).
 ▎ Phase 4 CORE ✅ (commit 1ae1924) — the 507-line state machine in
 ▎ src/app/page.tsx is DELETED. 35 real routes live (build-verified):
 ▎ (app)/{dashboard,admin,admin/reports/[id],mentor,group-admin,assessme
 ▎ nt/run|result,coding/run|result,leaderboard,profile,discussions,libra
 ▎ ry,assignments,history,notifications,resources,intel,kt/[[...path]]}
 ▎ + (public)/{login,forgot-password,reset-password,profile/[slug]} +
 ▎ /p/[slug] alias. sessionStore (Zustand) owns
 ▎ session+active-assessment state; (app) layout does auth-guard +
 ▎ chrome + legacy view-name adapter (src/lib/viewRoutes.ts — delete in
 ▎ Phase 6); /login is email-first with legacy group-login toggle.
 ▎ Phase 4 remaining: typed OpenAPI client + React Query hooks (replace
 ▎ 258-method ApiService), god-component decomposition (LDAdminDashboard
 ▎ 2,978 → /admin/* pages; UserProfile; KTCreationWizard; Dashboard),
 ▎ styled-jsx removal, shared UI kit, kill window-event navigation
 ▎ inside Dashboard.
 ▎ Phase 4 remainder ✅ (cbf5d9e) — typed OpenAPI client (schema.d.ts,
 ▎ 281 paths, openapi-fetch + 401-refresh middleware) + React Query
 ▎ hooks pattern; LDAdminDashboard 2,978→1,813 (13 components extracted
 ▎ to components/admin/); /admin?tab= deep links; dead nav-profile
 ▎ listener removed; styled-jsx claim was a false positive (zero in
 ▎ codebase).
 ▎ Phase 5 ✅ (571c04c) — OrgUnit dual-write mirror (modules/org/sync.py
 ▎ after_flush listener, unbypassable, both engines),
 ▎ user_org_roles.source ownership, role_scope_service
 ▎ (materialized-path reach + legacy group-id bridge), 6 gate tests
 ▎ incl. legacy-vs-OrgUnit scope parity = zero mismatch.
 ▎ Phase 6 ✅ (871d573, acae787) — unified mentor inbox (GET
 ▎ /mentor/inbox: assessment + KT queues; MentorDashboard panel w/ /kt
 ▎ link); system.py deleted (was never mounted); kt_workflows Neo4j
 ▎ pipeline removed (220 lines); graph
 ▎ explorer/timeline/stats/related-docs rebuilt relationally
 ▎ (graph_service.py, same shapes; old traverse_neighborhood call
 ▎ referenced a method that never existed); live KT E2E rewritten
 ▎ self-contained.
 ▎ Phase 7 ✅ (414c980) — Neo4jKTClient deleted (416 lines), neo4j dep +
 ▎ NEO4J_* config removed, /ready + startup_validator check pgvector,
 ▎ guardrail tests retargeted, indexes verified, modules/README.md.
 ▎ Phase 8 — local verification battery ALL GREEN (route parity 321 =
 ▎ baseline + /mentor/inbox only; no shadowing; live KT E2E pass; 0
 ▎ neo4j imports; frontend build 30 pages; 356 backend tests). Deploy
 ▎ itself awaits owner action (docker daemon not running locally;
 ▎ hosting creds are owner's). Runbook: build apps/api Dockerfile
 ▎ (py3.12/uvicorn, RUN_SCHEDULER guard), deploy web-next to Vercel with
 ▎ NEXT_PUBLIC_API_BASE, run scripts/phase1_provision.py once against
 ▎ prod DB, smoke: /ready, /login, take assessment, KT
 ▎ upload→approve→chat.
 ▎ Backlog sprint 2 ✅ (047db9b…f46f41d, 2026-07-23):
 ▎ - Email-credential lifecycle COMPLETE: create_user + bulk_create now
 ▎ auto-issue individual credentials (secrets.token_urlsafe → hash →
 ▎ send_credentials_email) when no password is given — no new account
 ▎ depends on group patterns; legacy login can be removed once existing
 ▎ pattern-era accounts (none on the fresh DB) are gone. Tested.
 ▎ - Backend decomposition round 2: mentor.py
 ▎ 1,094→mentor_reviews+mentor_insights; cohort_reports
 ▎ 1,557→batch_reports+cohort_analytics; kt insights
 ▎ 1,205→workspace+analytics+explorer; kt documents
 ▎ 1,159→doc_registry+doc_lifecycle+doc_assets; ai_engine 1,455→814
 ▎ (config extracted to ai_languages.py); generation
 ▎ 941→content_gen+advisory. All thin aggregators, parity 321, no
 ▎ shadowing, 374 tests green.
 ▎ - Remaining >800 (practical floor for mechanical splits — needs body
 ▎ redesign): backend performance_engine 1,032 / cohort_analytics 886 /
 ▎ doc_lifecycle 864 / ai_engine 814; frontend LDAdminDashboard 1,813 /
 ▎ UserProfile 1,227 / KTCreationWizard 983 / MentorDashboard 820
 ▎ (single-function monoliths — redesign with the app RUNNING for visual
 ▎ verification).
 ▎ - Still open: ApiService call-site migration to typed hooks (pattern
 ▎ established); legacy group-login toggle removal (safe now — fresh DB
 ▎ has no pattern-era accounts — but keep until first real onboarding
 ▎ proves the credentials email path in prod); viewRoutes.ts adapter
 ▎ deletion; production deploy (owner's hosting).
 ▎ Backlog sprint 3 ✅ — LIVE-STACK QA (f448aca…dc137f0, 2026-07-23): 
 ▎ ran the REAL stack (uvicorn + next dev + headless browser). Findings
 ▎ & fixes, all live-verified:
 ▎ - Platform operator sign-in was broken on a fresh DB (whole /platform
 ▎ surface 403): ensure_system_identity hardcoded a password that
 ▎ drifted from APP_ADMIN_PASSWORD (secret-in-source too) → now
 ▎ env-sourced; get_user_jwt_payload + verify_token now issue org-less
 ▎ tokens for PlatformAdmin/ID-0 (cross-org by design; org scoping
 ▎ already denies None). Verified: email login as PlatformAdmin →
 ▎ /platform/stats 200.
 ▎ - Browser-proven login flow: /login → fill email+password → lands on
 ▎ /dashboard (screenshot evidence). Backend log traced the full
 ▎ hydrate/refresh cycle.
 ▎ - Latent 500 class killed: 19 async endpoints called sync-only scope
 ▎ helpers (AsyncSession.query crash) across reporting/assessment — all
 ▎ wrapped in db.run_sync / switched to async twin; AST sweep now zero;
 ▎ growth-atlas + heatmap verified 200 live.
 ▎ - Ops: cleaned 36 leaked test orgs from dev DB; freed 3.8GB disk
 ▎ (.next, brew, pip caches) after ENOSPC halt; dev servers run via tmux
 ▎ (dev session) + background uvicorn.
 ▎ - Dev fixtures: browser.demo@studyhub-tests.dev / S3cure!pass
 ▎ (Member, Sigmoid HQ) for browser QA.

 Companion technical design (full detail, 1,580 lines): /Users/meet/.cla
 ude/plans/we-need-to-rethink-indexed-wozniak-agent-a8a439514a0fbb08e.md
 On approval, both documents should be copied into the repo at
 docs/product-plan/ as the north-star.

 ---
 1. Context — why this redesign

 StudyHubV2 grew from a group-study quiz app (QuizConnect/StudyBuddy)
 into an enterprise platform by accretion. Current state (verified by
 codebase audit, 2026-07-22):

 - Backend: 35.5K lines, 24 routers, 314 endpoints, 60+ entities. 12 god
 files (routers/kt.py = 3,893 lines/70 endpoints; auth.py 2,381;
 quiz.py 2,119). Business logic lives in routers; async/sync DB sessions
 mixed; system.py legacy shadowed by system_config.py; 3 overlapping KT
 engines (kt_engine, kt_langraph, kt_workflows).
 - Frontend: 28.3K lines. Next.js 15 App Router in name only — the real
 app is a state-machine SPA in app/page.tsx (16 virtual views + 9 KT
 sub-views, no URLs, no deep links, broken back button). God components:
 LDAdminDashboard.tsx 2,978 lines (10 tabs), UserProfile 1,228,
 KTCreationWizard 984. ApiService.ts: 1,721 lines, 258 methods, all
 Promise<any>. Two design systems (Tailwind v4 + styled-jsx).
 - The KT product is functionally dead downstream of approval: document
 create → submit → review works, but Neo4j ingestion fails, the graph is
 empty, so the RAG chatbot retrieves nothing. Months of debug artifacts
 (fix_kt.py, neo4j dumps, scratch/check_*.py) litter the repo root.
 - The quiz product works end-to-end (bank → assign → take → grade →
 report → export) and is hardened (263 tests, tenancy scoping, durable
 job queue).

 Root cause: features were added without a product model. Two products
 grew inside one app without a shared architectural core, and the
 frontend never migrated from "SPA with view state" to real routing.

 Owner decisions (locked):

 ┌─────┬─────────────────────────────────────────────────────────────┐
 │  #  │                          Decision                           │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 1   │ Quiz/Assessment-first platform; the "single soul product"   │
 │     │ an enterprise buys for quiz, assessment & knowledge sharing │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ KT is a distinct second product in the same platform — no   │
 │ 2   │ forced quiz↔KT integration; they share the platform core    │
 │     │ (org, people, auth, AI)                                     │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Single-enterprise deploys, no multi-tenancy. Hierarchy:     │
 │ 3   │ Platform Admin → Enterprise (L&D Admin) → Org → Department  │
 │     │ → Vertical → Batch → Group as a flexible OrgUnit tree       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 4   │ KT capture = continuous + structured exit handoff           │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 5   │ Drop Neo4j → Postgres pgvector (one database, no sync       │
 │     │ pipeline to break)                                          │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Incremental restructure, but owner explicitly allows        │
 │ 6   │ recreating the noodliest parts — including a rebuilt        │
 │     │ email-based login and real multipage routing; SOLID         │
 │     │ principles throughout                                       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 7   │ Keep all engagement features: leaderboard, discussions,     │
 │     │ daily challenge, public profiles                            │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │     │ Coding assessments stay AI-evaluated only (also supports    │
 │ 8   │ descriptive answers, JSON-config questions, pyscript-style  │
 │     │ code)                                                       │
 ├─────┼─────────────────────────────────────────────────────────────┤
 │ 9   │ Unify quiz + exam into ONE Assessment engine (settings      │
 │     │ decide: practice / timed / proctored / daily challenge)     │
 └─────┴─────────────────────────────────────────────────────────────┘

 ---
 2. Product vision & goals

 Vision: The single platform a service-based enterprise uses to (a)
 assess and grow its people — interns, lateral hires, and current
 employees kept current with the market — and (b) retain the knowledge
 of people who leave through structured knowledge transfer.

 Product 1 — Assess (core): one assessment engine for MCQ, descriptive,
 coding (AI-evaluated), config/JSON questions; delivered as practice
 quizzes, proctored exams, or daily challenges; assigned down the org
 tree; analyzed in dashboards from learner → batch → executive.

 Product 2 — KT (companion): employees continuously document
 what/how/why/when of their project work; mentors verify; approved
 knowledge is indexed (pgvector) and queryable through a cited RAG
 chatbot; a formal exit handoff workflow captures a departing employee's
 knowledge before their last day.

 Goals (measurable):
 1. Every screen has a URL; every flow survives refresh/back/deep-link.
 2. KT works end-to-end: upload → review → indexed → answerable in chat
 (currently broken at step 3).
 3. No file > 800 lines; routers contain no business logic; one async DB
 pattern.
 4. 314 → ~200 endpoints; typed API client; Promise<any> count = 0.
 5. System stays deployable at the end of every phase.

 3. User personas

 Persona: Learner (intern / lateral hire / employee)
 Who: Bottom of tree, member of Group(s)
 Primary product: Assess
 Key needs: Take assigned assessments, see results & progress,
 leaderboard, discussions, daily challenge, profile
 ────────────────────────────────────────
 Persona: Expert / Departing employee
 Who: Same person as a Learner, in KT context
 Primary product: KT
 Key needs: Document project knowledge easily; complete exit handoff
 checklist
 ────────────────────────────────────────
 Persona: Mentor
 Who: Assigned to Groups
 Primary product: Both
 Key needs: ONE workspace: review learner performance & submissions
 (Assess) + review/approve KT docs & answer KT inbox (KT)
 ────────────────────────────────────────
 Persona: Group Admin
 Who: Manages a Group/Batch
 Primary product: Assess
 Key needs: Assign assessments, track completion, intervene
 ────────────────────────────────────────
 Persona: L&D Admin
 Who: Enterprise-level
 Primary product: Both
 Key needs: Org tree CRUD, user management, curriculum, org-wide
 analytics, audit
 ────────────────────────────────────────
 Persona: Manager / Executive
 Who: Report consumer
 Primary product: Both
 Key needs: Batch/vertical readiness reports, exports, KT coverage &
 handoff status
 ────────────────────────────────────────
 Persona: Platform Operator (vendor = you)
 Who: /platform
 Primary product: Platform
 Key needs: Deployment health, AI usage/cost metering, feature gates,
 enterprise onboarding

 4. User stories (condensed, v1)

 Learner: log in with email → see my assigned assessments & deadlines →
 take an assessment (any question type, resumable if allowed) → get
 score + AI feedback → see my analytics/streaks → discuss questions →
 appear on leaderboard → play daily challenge.
 Expert: create a KT doc for my project (wizard: details →
 content/upload → metadata → review) → submit for mentor review → see
 status → answer follow-up questions in mentor inbox. On resignation:
 receive an exit-handoff checklist auto-built from my projects →
 complete it before last day.
 Mentor: open one inbox → see pending KT doc reviews AND assessment
 items needing review → approve/reject KT docs with comments → view my
 groups' performance and AI insights.
 L&D Admin: build the org tree → bulk-import users → assign roles at any
 node → create/assign curriculum → view org analytics → export reports
 → read audit log.
 Executive: open a batch/vertical report → readiness scores,
 distributions, AI executive summary → export XLSX. KT: coverage per
 project, pending handoffs.
 Platform Operator: monitor health, AI spend per feature, toggle
 features, onboard the enterprise.

 5. End-to-end user journeys (target)

 A. Assessment journey (works today — preserve, unify):
 Admin creates bank/questions (or AI-generates) → publishes as an
 Assessment with settings (type, timing, proctoring, attempts) → assigns
 to OrgUnit(s) → learners notified → learner takes it at
 /assessment/[id] → grading (auto + AI for descriptive/coding via job
 queue) → results at /assessment/result/[attemptId] → feeds gradebook,
 leaderboard, intel, reports → export.

 B. KT continuous journey (broken today — fix at ingestion):
 Expert creates doc at /kt/documents/create → submit → mentor reviews at
 /mentor/inbox → approve triggers JOB_KT_INGEST (parse → chunk ~512
 tokens → Gemini embed → pgvector) → doc status indexed → anyone with
 project access asks the KT chat → cited answers stream back. Access
 keys remain for scoped external/temporary access.

 C. KT exit-handoff journey:
 L&D Admin/HR initiates handoff for a departing user → system lists
 their projects/docs → generates checklist (undocumented areas, docs
 needing update) → expert completes items (each = a doc through journey
 B) → mentor sign-off per item → handoff report (coverage %) visible to
 management → user offboarded.

 D. Admin journey: /admin → hierarchy, users, curriculum, reports,
 audit, settings — each a real page.

 6. User flow diagram (target)

                         ┌────────── /login (email-based, rebuilt)
 ──────────┐
                         │        forgot/reset password, invite accept
      │

 └───────────────────┬───────────────────────────────┘
                               role-based landing (server-side redirect)
         ┌──────────────┬──────────────┬────┴─────────┬───────────────┬─
 ─────────────┐
    [Learner]       [Mentor]      [Group Admin]   [L&D Admin]
 [Executive]    [Platform Op]
    /dashboard      /mentor       /admin/groups   /admin
 /reports       /platform
         │               │                                │
         ├ /assessments  ├ /mentor/inbox (KT reviews + assessment
 reviews)
         ├ /assessment/[id] → /assessment/result/[attemptId]
         ├ /leaderboard  ├ /mentor/groups/[id] (insights)
         ├ /discussions  │
         ├ /daily        └──────────┐
         ├ /profile (+ /users/[slug] public)
         └ /kt ── /kt/dashboard ─ /kt/documents ─ /kt/documents/create ─
 /kt/documents/[id]
                  /kt/chat ─ /kt/projects ─ /kt/handoffs ─ /kt/keys ─
 /kt/analytics ─ /kt/graph
 Every box above = a real URL (Next.js App Router route group),
 replacing the 16-view state machine.

 7. System workflows (backend)

 1. Assessment lifecycle: draft → published → assigned →
 in_progress(attempt) → grading → completed → archived. Grading:
 objective items sync; AI-evaluated items (descriptive/coding) via
 durable job queue (existing Postgres queue — keep; enqueue never
 commits, per established rule).
 2. KT document lifecycle: draft → submitted → in_review → approved →
 indexing(job) → indexed | rejected(with comments) | deprecated.
 Indexing failure → index_failed + retry with backoff + mentor/admin
 visibility. No silent failures — this is the exact class of bug that
 killed KT v1.
 3. RAG chat: embed query → pgvector cosine top-k within caller's
 project scope → prompt with citations → stream via SSE → log message +
 AI usage meter.
 4. Exit handoff: initiated → checklist_generated → in_progress →
 mentor_signoff → completed; report snapshot persisted.
 5. Jobs: one queue for KT ingestion, AI grading, report generation,
 email. All AI calls pass through ai_meter.
 6. Audit: admin mutations + KT approvals + role changes append to audit
 log (exists — keep).

 8. Backend service responsibilities (modular monolith)

 apps/api/modules/
   identity/    auth (rebuilt email-based login, JWT+refresh, password
 reset, invites), users, profiles, roles
   org/         OrgUnit tree (CRUD, recursive-CTE scoping), UserOrgRole,
 membership   ← replaces 5 hierarchy tables
   assessment/  banks, questions (MCQ/descriptive/coding/config),
 UNIFIED assessment engine
                (practice/exam/proctored/daily via settings), attempts,
 grading, assignments,
                mentor views, discussions, leaderboard
   kt/          projects, documents, review, ingestion (pgvector), rag
 chat, handoff, access keys
   ai/          llm_service (Gemini wrapper), embedding_service,
 ai_meter, cache — ONLY path to LLMs
   reporting/   assessment analytics, intel, gradebook, exports, KT
 analytics (new), audit queries
   platform/    operator dashboard, feature gates, system config
 (system_config.py wins; system.py deleted)
   jobs/        durable Postgres queue (keep as-is) + handlers
 shared/        exceptions, middleware, permissions decorators,
 validators, constants
 Rules: routers = HTTP only (validate → call service → return schema).
 Services own business logic, take AsyncSession via DI. One async DB
 pattern — sync sessions removed. Modules may import shared/ and other
 modules' services only (no cross-module model imports except via
 service APIs). Errors via typed exceptions → global handlers.

 What dies: Neo4j (13 files), kt_langraph.py/kt_workflows.py/most of
 kt_engine.py (replaced by ingestion_service + rag_service), system.py,
 root junk (fix_kt.py, temp*, dumps, StudyBuddy.zip, error logs →
 archive or delete), duplicate RichText, legacy localStorage token path.

 9. Frontend page flow (rebuild — owner-approved)

 Real App Router routes per §6; route groups (auth), (app), (admin),
 (kt), (platform) with per-group layouts and middleware auth. God
 components decomposed: LDAdminDashboard (2,978) → ~10 pages under
 /admin/*; UserProfile → /profile + components; KTCreationWizard →
 wizard steps + useKTWizard store; Dashboard → cards. API layer: typed
 client generated from FastAPI OpenAPI + React Query hooks everywhere;
 delete ApiService.ts singleton and window-event navigation. One design
 system: Tailwind v4 + shared UI kit (Button, Modal, DataTable, Form,
 Toast, Skeleton…); styled-jsx removed. Error boundaries per route
 group.

 10. Database relationships (target)

 User ─┬─ UserOrgRole ── OrgUnit(parent_id self-FK, type:
 org|department|vertical|batch|group)
       ├─ Attempt ── Assessment ── QuestionBank ── Question(type:
 mcq|descriptive|coding|config)
       ├─ Assignment(assessment ↔ org_unit)
       ├─ DiscussionPost / Bookmark / Streak
       ├─ KTDocument ── KTDocumentChunk(embedding vector(768), ivfflat
 idx) [pgvector]
       │        └─ KTReview(mentor, verdict, comments)
       ├─ KTProject ── membership   ├─ KTChatSession ── KTChatMessage
       ├─ KTHandoff ── KTHandoffItem
       └─ AIUsage / BackgroundJob / AuditLog
 Migration: 5 hierarchy tables → OrgUnit via backfill + compatibility
 layer, flip reads, archive old tables. KTCompany deleted (redundant in
 single-enterprise). Old UserRole → UserOrgRole.

 11. API interactions

 - Prefix /api/v1/{module}/...; standard REST verbs; consistent envelope
 + paginated lists (existing pagination pattern kept).
 - 314 → ~200 endpoints: kt.py's 70 → ~50 across 7 focused routers;
 quiz/exam merged into assessment; legacy system.py, dead KT/Neo4j
 endpoints deleted.
 - Auth: HTTP-only cookie JWT + refresh (rebuilt, email-based); scoping
 = "which OrgUnit subtree can this user touch" via role_scope_service
 (single-enterprise: this replaces tenant isolation as THE
 access-control question). 404-not-403 convention retained.
 - OpenAPI schema → generated TS types (single source of truth for the
 frontend).

 12. Business rules

 1. A user's reach = union of OrgUnit subtrees where they hold a role;
 content assigned at a node is visible to that node's subtree.
 2. One Assessment engine: behavior (timing, proctoring, attempt limits,
 review visibility) is configuration, not code paths.
 3. AI evaluation always: metered (ai_meter), cached where possible,
 never blocks the request thread (jobs), never silently fails.
 4. KT docs are chat-retrievable only when indexed; every state
 transition is auditable; mentor approval is mandatory (no auto-approve
 — the architect draft suggested auto-approve; overruled: mentor
 verification is the KT product's core trust mechanism).
 5. Exit handoff must reach mentor sign-off before offboarding is marked
 complete.
 6. Deletions are soft (deprecate) for content entities; hard deletes
 only by L&D Admin with audit entry.
 7. Every list endpoint paginates; every mutation validates OrgUnit
 scope server-side.

 13. Feature-by-feature first-principles verdict

 Feature: Assessments (MCQ/descriptive/coding/config)
 Why it exists / who / when: Core product; admins create, learners take,

 continuously
 Verdict: KEEP — the core. Unify quiz+exam into one engine
 ────────────────────────────────────────
 Feature: Proctored exams
 Why it exists / who / when: Formal evaluation of hires
 Verdict: KEEP as a setting, not a separate subsystem
 ────────────────────────────────────────
 Feature: Coding w/ AI eval
 Why it exists / who / when: Assess code without exec infra
 Verdict: KEEP AI-only (owner decision)
 ────────────────────────────────────────
 Feature: Leaderboard / Daily challenge / Discussions / Public profiles
 Why it exists / who / when: Engagement & peer learning
 Verdict: KEEP all (owner decision); low maintenance
 ────────────────────────────────────────
 Feature: AI quiz generator / AI learning path
 Why it exists / who / when: Author productivity; learner guidance
 Verdict: KEEP, route through ai/ module; verify non-placeholder during
 Phase 3
 ────────────────────────────────────────
 Feature: KT documents + mentor review
 Why it exists / who / when: Knowledge retention in a services company
 Verdict: KEEP — core of product 2
 ────────────────────────────────────────
 Feature: KT ingestion via Neo4j
 Why it exists / who / when: Was: knowledge graph
 Verdict: REPLACE with pgvector — Neo4j delivered zero value, caused
 total KT failure, second DB to operate
 ────────────────────────────────────────
 Feature: KT chatbot (RAG)
 Why it exists / who / when: Query retained knowledge
 Verdict: KEEP, on pgvector, cited, streamed
 ────────────────────────────────────────
 Feature: KT graph explorer
 Why it exists / who / when: Visualize knowledge
 Verdict: KEEP UI, recompute from relational data (projects/docs/tags) —

 no graph DB needed
 ────────────────────────────────────────
 Feature: KT access keys
 Why it exists / who / when: Scoped/external access
 Verdict: KEEP (simplify), useful for contractors/auditors
 ────────────────────────────────────────
 Feature: Exit handoff engine
 Why it exists / who / when: The KT trigger event
 Verdict: KEEP & finish — checklist gen + sign-off + report
 ────────────────────────────────────────
 Feature: Mentor: two disconnected workflows
 Why it exists / who / when: Historical accident
 Verdict: MERGE into one mentor workspace/inbox
 ────────────────────────────────────────
 Feature: Reports/intel/gradebook
 Why it exists / who / when: Manager & exec visibility
 Verdict: KEEP; add missing KT analytics (currently 115-line stub)
 ────────────────────────────────────────
 Feature: Org hierarchy (5 tables)
 Why it exists / who / when: Enterprise structure
 Verdict: KEEP concept, collapse to OrgUnit tree
 ────────────────────────────────────────
 Feature: Multi-tenant scaffolding
 Why it exists / who / when: SaaS ambition
 Verdict: REMOVE from scope (owner decision) — simplifies auth to
 subtree
  scoping
 ────────────────────────────────────────
 Feature: system.py legacy config
 Why it exists / who / when: Superseded
 Verdict: DELETE
 ────────────────────────────────────────
 Feature: Resources center / notifications / exports / audit / platform
 dashboard
 Why it exists / who / when: Standard enterprise needs
 Verdict: KEEP, slot into modules
 ────────────────────────────────────────
 Feature: Root junk & scratch scripts
 Why it exists / who / when: Debug history
 Verdict: DELETE/archive

 Missing (build): KT analytics, indexing-failure visibility, unified
 mentor inbox, handoff completion report, breadcrumbs/global search
 (later), invite-accept flow polish.

 14. Feature dependencies

 identity → everything. org → assessment, kt, reporting. ai → assessment
 (AI grading/gen), kt (embed/RAG), reporting (AI summaries). jobs → AI
 grading, KT indexing, exports, email. KT chat → KT indexing → KT review
 → KT documents. Handoff → KT documents + org. Reports → attempts +
 (new) KT tables. No assessment↔KT data dependency by design.

 15. Roadmap & prioritized implementation plan

 Adapted from the companion technical plan (8 phases, ~13 weeks solo;
 phases overlap). Priority logic: fix the dead product first, then
 de-noodle around the working one, rebuild frontend once backend
 contracts are stable.

 Phase: 1. Foundation
 Weeks: 2
 Delivers: modules/ + shared/ skeleton; async-only DB;
 OrgUnit+UserOrgRole+KTDocumentChunk tables + backfill + compat layer;
 repo-root cleanup
 Risk: Low
 ────────────────────────────────────────
 Phase: 2. KT resurrection
 Weeks: 2.5
 Delivers: pgvector ingestion + RAG chat live (mentor approval kept in
 the loop); kt.py split into 7 routers; Neo4j no longer queried. KT
 becomes a working product again
 Risk: Med
 ────────────────────────────────────────
 Phase: 3. Backend de-noodling
 Weeks: 2
 Delivers: Split auth.py/quiz.py/admin.py/reports.py/ai.py; service
 layer
 everywhere; unified Assessment engine (quiz+exam merge); rebuilt
 email-based auth flows
 Risk: Med
 ────────────────────────────────────────
 Phase: 4. Frontend rebuild
 Weeks: 2
 Delivers: Real routes replace state machine; typed OpenAPI client +
 React Query; UI kit; god components decomposed; one design system
 Risk: Med
 ────────────────────────────────────────
 Phase: 5. OrgUnit flip
 Weeks: 1.5
 Delivers: All scoping/queries on OrgUnit tree; validation vs old path;
 old tables read-only
 Risk: High
 ────────────────────────────────────────
 Phase: 6. Cleanup + mentor merge
 Weeks: 1
 Delivers: Delete dead KT services/Neo4j deps/styled-jsx/legacy files;
 unified mentor inbox; error boundaries
 Risk: Low
 ────────────────────────────────────────
 Phase: 7. Archive & tune
 Weeks: 1
 Delivers: Old tables archived; indexes verified; docs per module
 Risk: Low
 ────────────────────────────────────────
 Phase: 8. Deploy & monitor
 Weeks: 0.5
 Delivers: Prod rollout, smoke tests, rollback plan
 Risk: Med

 Quick wins inside Phase 1: delete root junk + system.py + duplicate
 RichText; add index_failed visibility to current KT UI so failures are
 at least honest.

 16. Risks, gaps, recommendations

 Top risks: (1) OrgUnit data migration (Phase 5) — mitigate with
 idempotent backfill, dual-read compat layer, permission-diff audit on
 real users, backup; (2) frontend rebuild regressions in the working
 assessment flow — E2E tests on take/grade/report before cutover; (3) KT
 chat quality on pgvector — measure retrieval on a seeded corpus before
 calling Phase 2 done; (4) solo-builder burnout — every phase ends
 deployable, so you can pause anywhere.

 Gaps found that this plan closes: dead KT downstream, mentor
 split-brain, KT analytics stub, no URLs/deep links, untyped API,
 tenancy half-migration, 12 god files, silent job failures.

 Recommendations: commit this + companion doc to docs/product-plan/;
 adopt "no file >800 lines, no logic in routers, one DB pattern" as
 review gates; run graphify update . after each phase; keep the 263-test
 suite green as the migration harness and add per-module tests as
 modules land.

 17. Verification (per phase & final)

 - Phase 2 gate: upload real doc → mentor approve → chunks in
 kt_document_chunks → chat answers with citations (E2E test + manual).
 - Phase 3 gate: full pytest suite green; endpoint parity sweep (163+
 endpoints, 0×500) re-run as after previous hardening sprints.
 - Phase 4 gate: Playwright/agent-browser E2E: login → dashboard → take
 assessment → result; deep-link + refresh + back on every route.
 - Phase 5 gate: permission-diff script (old path vs OrgUnit path) over
 all users = 0 mismatches.
 - Final: smoke of all seven persona journeys in §5–6; wc -l audit
 confirms no file >800 lines; grep confirms zero Promise<any>, zero sync
 sessions, zero Neo4j imports.
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌

─────────────────────────────────────────────────────────────────────────
 Claude has written up a plan and is ready to execute. Would you like