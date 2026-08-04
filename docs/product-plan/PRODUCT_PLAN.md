# StudyHubV2 → "StudyHub" — First-Principles Product Redesign Plan

---
## 🎓 EXAM PORTAL (Mettl parity) + EMAILS + PROCTORING (2026-08-02 — ✅ COMPLETE)

Owner wanted the exam portal to work like **Mercer Mettl**, every email working, real webcam **video recording**, and **reliable detection**. Root cause of "only the L&D can take the exam": invites were sent synchronously with a swallowed error (unreliable), members had no surface to discover exams, and `start_exam` was super-org-only. All fixed. Per-phase commits (`feat exam-p1` … `feat exam-p3c`); 533 tests pass, no shadowing (337 routes), 0×500 exam GET sweep, web build 32 pages, tsc clean.

- **P1 — Emails reliable ✅** — exam invites now flow through the durable `JOB_EMAIL` queue (new `job_queue.enqueue_sync`) instead of a synchronous swallowed send; `GET /admin/email/health` (LDAdmin) reports RESEND config + optional live test. All 17 `send_*` templates were already wired — real blocker is prod config (set `RESEND_EMAILS_API_KEY` + verify the `email.mj665.in` sender domain in Resend).
- **P2 — Candidate access + scheduling + Mettl config ✅** — new `ExamInvite` candidate list (invited→started→submitted); `start_exam` access = in super-org OR on the invite list (any invited member can take it); **scheduling window** `starts_at/ends_at/timezone` enforced (403 before/after) with an IST-formatted label in the invite email; `Exam.settings` JSONB (`require_camera, record_video, require_fullscreen, max_tab_switches, negative_marking, allow_backtrack, show_results_immediately, instructions`); `GET /exams/me/invited` member feed; submit applies negative marking + honors show-results. Frontend: **"My Exams"** feed on /exams + a **member Dashboard "My Exams" card** (open/upcoming invited exams, discoverable from home); nav shown to everyone (authoring stays Mentor+); creation form with scheduling + all 8 toggles. All settings are enforced in the runner, incl. `allow_backtrack` (linear one-question-at-a-time mode when off).
- **P3 — Full video recording + real detection ✅** — `POST /exams/attempts/{id}/proctor-media` (presigned S3) + `s3_service.generate_proctor_media_upload_url`; runner rewritten with a **pre-exam lobby** (instructions/window/requirements), settings enforcement (camera-required blocks start, fullscreen request+flag, tab-limit auto-submit), **MediaRecorder → 20s webm chunks → S3** + 15s snapshots → S3 (data-URL fallback when no S3, via `src/lib/proctorMedia.ts`). Detection upgraded to **MediaPipe Tasks Vision** (`src/lib/faceDetection.ts`, self-hosted WASM+model, cross-browser) with graceful fallback to the browser FaceDetector. Review page **plays back the recording** (sequential chunk player) + snapshot gallery + flag timeline. `ProctorEvent` gained `video_chunk`/`looking_away`; `get_proctor_events` resolves S3 keys to presigned GET URLs.
- **P4 — Mettl statistics ✅** — `GET /exams/{id}/stats`: participation/completion, pass rate + avg/median/high/low + 5-bucket distribution, avg time, per-question difficulty (correct %), proctoring integrity summary. Review page overview dashboard (KPI tiles + distribution bars + question difficulty + integrity) above the per-candidate drilldown, plus **`GET /exams/{id}/export` → CSV results** (Export CSV button, authed blob download).
- **P5 — Verification ✅** — 533 pytest, 337 routes no-shadow, 0×500 exam sweep, web build 32 pages, tsc clean.

**Senior-review hardening (2026-08-05):** (a) targeted exams (with an invite list) are now **invited-candidates-only** — a non-invited super-org member is 403'd (open exams stay super-org-wide; owner/platform-admin may preview); (b) added an `email` claim to the JWT so ExamInvite email-matching works, not just user_id; (c) `/exams/{id}/stats` per-question analytics is **objective-only (no AI)** — free-text questions are marked 'manual' rather than re-graded via the LLM (which would have fired N×AI calls per stats view). Confirmed `grade_free_text` fails closed (`needs_review`, no 500) so submits are safe under the AI spend cap. Verified: invited=200 / non-invited=403 / open=200; 533 tests, 338 routes no-shadow, build 32 pages.

**Owner prereqs for prod:** (1) `RESEND_EMAILS_API_KEY` + verified `email.mj665.in` sender domain (emails); (2) S3 bucket configured (`S3_BUCKET_NAME` + creds) for webcam video/snapshots — snapshots fall back to inline storage without it, video is skipped. **Not yet browser-smoke-tested with a real camera** (record/detect) — flagged for a device test.

---
## 🐛 QA BUG-FIX SPRINT — 22 defects, 6 phases (2026-07-31 — ✅ COMPLETE)

Owner + QA tester filed ~22 defects from an end-to-end product traversal. Fixed across 6 phases, one commit per phase (`8dc6a18` → `e40c4c6` + `qa-p3-api` link fix). Locked Q&A: Bug 1 L&D scope = **enterprise-wide (super-org)**; Bug 10 proctoring = **full live face-presence detection**; Bug 16 chatbot = **grounded + friendly + fixed ingestion**.

- **Phase 1 ✅** — Bug1 (CRITICAL) L&D **super-org scoping**: `assert_group/batch/user_in_org` gain an LDAdmin+ branch (target reachable if in caller's super-org), `create_org` stamps `super_organization_id`, `get_orgs`/`get_org_tree` scoped per super-org, orphan orgs backfilled; `create_user` role-aware (LDAdmin+ → `assert_group_in_org`, else same-group). Bug12 inventory Edit/Delete wired in `QuestionManagement` (the component `InventoryTab` renders). Bug3 discussion vote → per-user toggle (`voter_ids` ARRAY, idempotent ALTER). Bug17 emails use `_frontend_url()` (`FRONTEND_URL`, default studybuddy.mj665.in) — only sender `@email.mj665.in` addresses remain. Bug7 `/exams` route group gets its own `ToastProvider` layout (the `/exam/[id]` runner uses inline errors, no provider needed). Bug11 L&D filter: `discovery_users` (the `getUsers` endpoint) scoped to super-org and returns `group/batch/vertical/dept/org_name`; UsersTab dropdowns are data-derived so the exact-match filters resolve.
- **Phase 2 ✅** — Bug2 AttemptHistory shows **real accuracy** (Σscore/Σtotal) not completion_rate. Bug19 banks list returns `total_attempts` (Library counts render). Bug20 **added `POST /code/questions`** (L&D coding wizard was 405; then fixed the id-0 falsy-`or` 500 → explicit-None resolve). Bug22 `/code/evaluate` now calls `update_assignment_completion` (mandatory coding `attempts_used` advances). Bug18 `BankCreationModal` drops Text Format, Load Template emits correct current-schema JSON.
- **Phase 3 ✅** — Bug16 **friendly KT chatbot**: `classify_conversational`/`conversational_reply` greeting-meta branch wired into BOTH chat paths (`kt_langraph.stream` + `kt_workflows.run_rag_query`) — "hi"/"what can you do" get a warm reply, real questions stay grounded + cited; ingestion pipeline confirmed producing pgvector chunks. Bug6 `ResourceComment` column is `comment` not `content` (POST+GET both 500'd). Bug15 KT chat **persists** active session per-project in localStorage, auto-restores on boot. Bug13/14 verified: PATCH returns full doc (`setDoc` works), submit reaches SUBMITTED → mentor inbox populates; access-key raw key shown in a persistent banner + **email now carries a `{FRONTEND_URL}/kt` portal link**.
- **Phase 4 ✅** — Bug5 PublicProfile renders `intro_video_url` via `normalizeVideoEmbed` (YouTube/Vimeo/Loom/direct → iframe/`<video>`). Bug4 photo path verified correct end-to-end (presigned S3 → `public_url` → render with initials fallback); non-visibility = S3 bucket public-read config (owner infra), not code.
- **Phase 5 ✅** — Bug8 `/exams/{id}/attempts` returns `user_name`+`user_email` (review shows "Name / email"). Bug9 `_notify_exam_recipients` resolves recipients **across the caller's super-org** for LDAdmin+ (was single-org → "0 notified"). Bug10 **full live face-presence proctoring**: runner captures webcam + on-device `FaceDetector` (`no_face`/`multiple_faces`/`camera_denied` flags) + periodic JPEG data-URL snapshots + live PiP/status badge; new `GET /exams/attempts/{id}/proctor-events`; review page expandable **snapshot gallery + flag timeline**; `proctor_events.media_url` VARCHAR(500)→TEXT (idempotent ALTER). **Live-verified:** snapshot persists, face flags increment count, GET returns gallery+timeline, review row shows name+email.
- **Phase 6 ✅** — Bug21 batch report: `generate_batch_insights` returns flat `"[Category] text"` strings but `ExecutiveReport` mapped object fields → ~30 empty cards. `structure_batch_observations()` parses each into `{category, impact, dimension, observation, actionable_step}` at `/admin/batch/{id}/ai-insights`; frontend also filters empties. Verified through the AI-spend-cap fallback path → 4 populated cards. Verify-hardening: org-less caller (seed id-0, org None) no longer 500s on `/mentor/inbox` (returns just assessment queue) + `/kt/companies` (fail-closed `[]`); public `POST /api/contact` allow-listed in the anonymous-endpoint guardrail.

**Verification (all green):** `pytest -m "not live"` **533 pass**; `check_route_shadowing.py` no shadowing among 333 routes; `test_unit_no_unresolved_calls` + `test_unit_public_endpoints` pass; **0×500** live GET sweep; web `tsc` clean + `npm run build` green (32 pages); new UI responsive by construction (fixed 160px PiP, `overflow-x-auto` gallery, `max-w-3xl` video); `graphify update .`. **Owner-side (not code):** Gemini key at monthly spend cap (429) → KT live answers + AI observations use fallbacks (all fallback paths work); Bug4 prod photo needs S3 bucket public-read.

---
## 🛠️ EXAMS + REPORTS + ADMIN + MOBILE SPRINT (2026-07-25 — ✅ COMPLETE)

Owner-reported defect batch fixed across 5 phases (commits after 9ef7b2f). Locked Q&A: exams = internal users email-notified, marks on profile; bank selection = searchable picker + inline create-bank wizard.

- **Phase 1 ✅** — daily-challenge `not <Column>` → `.is_(False)` (idempotent, no more UniqueViolation); peer-review AI reply flattened (`/ai/ask` `data.response`); question reports return `status` + full question payload (dropped `response_model` that stripped it) + inline Edit-question modal (`PUT /quiz/questions/{id}`).
- **Phase 2 ✅** — `Exam.recipient_emails` (ARRAY) + `send_exam_invite` email (direct `/exam/{id}` link) + in-app notif + best-effort push on publish; recipients ORG-scoped (User has no super_organization_id; PlatformAdmin cross-org), bogus emails dropped, returns `{invited}`. `GET /exams/me/attempts` (caller-scoped) → Exam Results on profile. Frontend: searchable bank picker + inline `BankCreationModal` wizard (auto-selects new bank) + recipient-email chips. **Live E2E:** publish→invited 1→notif→member took→me/attempts returns mark.
- **Phase 3 ✅** — global mobile responsiveness: `useMobile` hook; AppLayout main `min-w-0 overflow-x-hidden`; Sidebar `flex-1 overflow-y-auto` region; **KTNavShell `w-80`→AppLayout drawer** (hamburger+backdrop, `max-w-[85vw]`, closes on nav); table `overflow-hidden→overflow-x-auto` (AdminTables×3, UsersTab, CodingTab, SystemHealthMonitor); UserIntelPanel `grid-cols-5→grid-cols-2 md:grid-cols-5`; exams-review wrapped scroll+`min-w-[560px]`; overlays capped `max-w-[92vw]`. **Verified via CDP headless at 390px on /login /dashboard /exams /leaderboard /profile /kt /admin → `body.scrollWidth===innerWidth` (0 overflow) ALL.**
- **Phase 4 ✅** — Direct Mandate (`create_assignment`) always 500'd: `created_by` invalid kwarg (→ real column, see Phase 5) + `visibility_scope` NOT NULL unset (→ `target_type`). System Intelligence: `/admin/tasks/status` field mismatch (`executed_at`/`runs` added; UI shows real Last Executed/Total Runs, maps `failure`→Failed). Global Curriculum Deployment + `/admin/health` already 200.
- **Phase 5 ✅** — **0×500 across all 87 no-arg GET endpoints** (fixed `GET /assignments` raw-ORM serialization 500 + added real `assignments.created_by` column for ownership checks). **533 tests pass** (`-m "not live"`); tsc 0; production build green (35 routes); mobile 390px pass. Idempotent ALTERs (`exams.recipient_emails`, `assignments.created_by`) in live DB + `phase1_provision`.

---
## 🔍 FULL-PRODUCT AUDIT & COMPLETION SPRINT (2026-07-23 — CURRENT WORK)

**Context:** Owner asked for a veteran-level whole-product audit (every file/folder), review of this plan, and a step-by-step completion of everything the plan promises. Three parallel deep audits ran (backend, frontend, plan-vs-reality); every finding below was **cross-verified by me** — several auditor claims were refuted with evidence and are listed so we never re-chase them.

### Refuted auditor claims (do NOT act on these)
- "main.py still mounts old god routers / Phase 3 failed" — FALSE: `routers/{auth,quiz,admin,reports,ai,kt,mentor}.py` are 11–18-line aggregators including module routers (by design).
- "system_config.py missing" — FALSE: `apps/api/routers/system_config.py` exists and is mounted (main.py:212/219).
- "src/app empty / no page.tsx / Phase 4 unverified" & "exam/gradebook orphaned dirs" — FALSE: auditors' globbing failed on `[id]` brackets; `src/app/exam/[id]/page.tsx` + `gradebook/[bankId]/page.tsx` exist; prod build generates 35 routes.
- "ai_meter not wired at all" — PARTLY FALSE: all `kt_engine.GeminiClient` paths (generate/generate_json/stream/embed) are metered; the REAL gap is below (C2).
- "/p route orphaned" — intentional legacy alias to /profile/[slug].
- AppLayout `EXECUTIVE_REPORT`/`ORG_SETTINGS` guards = dead code (those views unreachable), not broken navigation → LOW cleanup, not critical.

### VERIFIED findings → remediation steps (execute in this order)

**STEP 1 — Security & correctness criticals (backend)**
1a. `config.py:31` `HMAC_KEY_SECRET` has a hardcoded default → require env in production: add to `validate_production_config()` fail-fast list; keep dev default only when ENVIRONMENT=development.
1b. **AI metering gap (rule §12.3):** `services/ai_engine.py` (`_get_llm`, eval/hint graph nodes) and `services/review_engine.py` (`_get_llm`, review graphs) call `ChatGoogleGenerativeAI` with 0 metering. Wire `services.ai_meter.record(feature, model, tokens_in, tokens_out)` after each LLM invocation (use response usage_metadata when available, else len//4 estimate like kt_engine). Also check `services/vector_service.py` embeddings. Features: `code_eval`, `code_hint`, `ai_review`, `ai_generation`.
1c. **Flaky test:** `tests/test_integration_kt.py::test_kt_full_loop` passes alone, fails in full suite (event-loop pollution — it calls `async_engine.dispose()` on the SHARED engine, breaking later/parallel users; also module-scoped TestClient loops). Fix: drop the `dispose()` from test teardown (engine is process-shared), and register `integration` marker in pytest.ini.

**STEP 2 — Wire-up/cleanup mediums (backend)**
2a. `models/kt_model.py` `neo4j_episode_ids` field: delete attribute (leave the DB column — harmless — or drop via idempotent ALTER); remove `neo4j_node_ids` from the unapplied migration file if that migration is dead (see 2b).
2b. **alembic/ vs migrations/ duplication:** `alembic.ini` decides the canonical dir; archive the other to `_archive/`. Document: schema strategy = `create_all` + idempotent provision scripts (scripts/phase1_provision.py) — migrations dir is legacy.
2c. Pydantic `model_used` namespace warning: add `model_config = ConfigDict(protected_namespaces=())` on the schema that defines it (grep `model_used`).
2d. langgraph `allowed_objects` deprecation: pass explicit value in `kt_langraph.py` (and ai_engine graph setup if applicable).
2e. SAWarning cascade mismatches (orgunit sync test): align `User.mentor_assignments` cascade (add `cascade="all, delete-orphan"` or delete assignments explicitly in fixtures) so DELETEs match expectations.
2f. Remove deprecated `google-generativeai` only IF nothing imports it directly (the FutureWarning originates in `langchain_google_genai` — check; if transitive, pin/upgrade `langchain-google-genai` instead and leave a note).
2g. bcrypt/passlib monkeypatch in main.py: pin `bcrypt<4.1`/passlib versions in requirements to make it stable; note argon2 as future migration.

**STEP 3 — Frontend verified fixes**
3a. Remove dead role-guard lines for `EXECUTIVE_REPORT`/`ORG_SETTINGS` in `src/components/ui/AppLayout.tsx:29-30` (views unreachable since Phase 4).
3b. **KTNavShell `window.history.pushState` (line ~98)** → use `router.push/replace` (component runs under `/kt/[[...path]]` catch-all, so App Router history stays in sync; verify /kt/company/... deep link still parses via ktNavStore).
3c. **Kill localStorage `study_token` remnants:** ApiService.getHeaders() reads it (ApiService.ts:61), LoginView writes it (:128,:144), Leaderboard/NotificationCenter/KTChatView read it directly. Auth is HTTP-only-cookie; remove writes+reads (keep Authorization header support only where a token is explicitly passed, e.g. none needed in-browser). Verify login + authed pages in browser afterward.
3d. Consolidate duplicate RichText: keep `src/components/quiz/cards/RichText.tsx` (KaTeX-capable, used by QuestionCard), re-export from `common/RichText.tsx` or update its importers; delete the duplicate implementation.
3e. Add `error.tsx` boundaries for `(app)` and `(public)` route groups + root (plan §Phase-4 promise): simple dark-theme fallback + reset button.
3f. Type the 9 `Promise<any>` intelligence methods OR migrate their callers to typed hooks (batch intel/global intel/analytics AI insights).

**STEP 4 — Business-rule completion (plan §12)**
4a. **Pagination sweep (§12.7):** AST-scan every GET list endpoint (returns `.all()` without limit/offset/paginate) across routers+modules; add `pagination.paginate` (existing util, apps/api/pagination.py) where missing; keep response shapes backward-compatible (only add when unbounded).
4b. **Soft-delete (§12.6):** KT docs have deprecate ✅; assessments: `delete_bank`/`delete_question` are hard deletes — add `is_active`/archived flag path? DECISION: amend rule instead — hard delete stays allowed for LDAdmin with audit (already audited); document the amendment in PRODUCT_PLAN §12.6. (No schema churn without owner need.)
4c. Verify `assert_tenant_active` + 404-not-403 conventions hold on the 15 small routers not yet modularized (spot-check org.py, export.py, intel.py).

**STEP 5 — Structure completion (mechanical, gated)**
5a. Move the 15 remaining small routers into modules via the proven splitter/aggregator pattern (route-parity + shadow gates each): assignment,billing,code,contact,export,gradebook,intel,interaction,onboarding,org,platform,profile,resources,system_config (+kt_user_helper stays a helper). Target mapping: assessment{assignment,code,gradebook,interaction}, reporting{export,intel}, org{org}, platform{platform,onboarding,billing,contact,system_config,resources}, identity{profile→already split? verify}.
5b. Frontend monolith internal redesigns (browser-verified, one at a time — outlines from audit): LDAdminDashboard core (10 tabs → tab components), UserProfile (4 tabs), KTCreationWizard (5 steps), MentorDashboard (4 sections). Each: extract sections into components/<area>/, keep behavior identical, verify in headless browser (login demo user), build gate.
5c. Root `README.md`: rewrite to describe the actual product + module map + run instructions (it predates the redesign).
5d. Delete root `plan.md` (hook-created duplicate; canonical = docs/product-plan/PRODUCT_PLAN.md synced from the plan file) — or keep syncing all three; choose delete to prevent drift.

**STEP 6 — Final verification battery (rerun after steps 1-5)**
- pytest full (`-m "not live"` then live KT loop), route parity vs scratchpad baseline + `scripts/check_route_shadowing.py`, `npx tsc --noEmit` + `npm run build`, live smoke via running stack (login → dashboard → assessment → /platform → KT chat), AST sweeps (sync-helpers-in-async = 0, unmetered LLM calls = 0, unpaginated list endpoints = 0), `graphify update .`, commit per step.

**Key files:** apps/api/{config.py, services/ai_engine.py, services/review_engine.py, services/ai_meter.py, models/kt_model.py, pytest.ini, tests/test_integration_kt.py, pagination.py} · apps/web-next/src/{components/ui/AppLayout.tsx, components/kt/KTNavShell.tsx, services/ApiService.ts, components/auth/LoginView.tsx, app/(app)/error.tsx(new), app/(public)/error.tsx(new)} · splitter script in session scratchpad.

### ✅ AUDIT SPRINT EXECUTED (commits 7e42861, e7f2c4f + docs; 2026-07-23)
**Steps 1–4 + 5c/5d DONE:**
- HMAC_KEY_SECRET dev-default now fails production validation (proven: fired on non-dev shell)
- AI metering complete: record_sync/record_langchain_sync added; code_eval/code_hint/ai_review LangChain paths metered (0→4 sites); kt paths were already metered
- Flaky live KT test fixed (shared-engine dispose removed); markers registered; pydantic/langgraph warnings resolved; google-generativeai dropped (transitive only); mentor_assignments delete-orphan cascade; neo4j_episode_ids attribute+column removed; orphan alembic/ archived (migrations/ canonical)
- **REAL BUG (missed by all audits until config read): next.config.ts legacy rewrites `/profile/:slug`→`/` and `/p/:slug`→`/` were shadowing the Phase-4 dynamic routes — removed**
- error.tsx boundaries for (app)+(public); dead AppLayout guards removed; KTNavShell URL sync via router.replace; MathText rename (name-collision, NOT a duplicate — correction to audit); 8 Promise<any> methods typed
- **PLAN CORRECTION:** "remove localStorage study_token" was WRONG — the access token in localStorage IS the auth transport (header bearer), bootstrapped/renewed by the HttpOnly refresh cookie; oauth2_scheme is header-only. Email login now persists the token like every other path.
- **SECURITY: intel.py cross-org IDOR closed** — 5 user_id-keyed endpoints (intelligence/ai-summary/roles read/assign/remove) had role-only gates; assert_user_in_org now mandatory + endpoints added to the write-path-scope guardrail (SCOPE_CALLS gained assert_user_in_org)
- **Rule §12.7 refined:** blanket pagination NOT applied to naturally-bounded lists; unbounded-growth lists get caps (500) — applied to question-reports + bank-library. **Rule §12.6 amended:** soft-delete (deprecate) is a KT-content rule; assessment hard-deletes remain LDAdmin-gated + audited + referential-integrity-guarded (no schema churn).
- Root README rewritten for the actual product; root plan.md deleted (canonical: docs/product-plan/PRODUCT_PLAN.md)
- 379 tests green; build green; tsc clean
**✅ 5a DONE (b24c221):** all 14 small routers moved into modules (assessment/reporting/org/platform/identity); routers/*.py are sys.modules ALIASES (imports/monkeypatch/inspection identical; main.py untouched); profile→profile_social rename (collision). Scanner guardrails extended to module paths → suite grew **379 → 523 tests**, all green; parity 321; no shadowing; KT E2E PASS; build green. The `routers/` dir now contains ONLY aggregators, alias stubs, and kt_user_helper.
**5b progress (5d85bfb):** UserProfile ✅ decomposed 1,228→652 + 6 verbatim tab components (audit said 4 tabs; code says 6 — always the code) via scripted extraction + ctx object + tsc-as-completeness-gate; browser-verified (login → /profile → all 6 tabs, screenshot evidence). Extractor pattern reusable in scratchpad (extract_userprofile.py).
**✅ 5b COMPLETE (052997e, b628558):** KTCreationWizard 984→470 + 6 WizardStep components; MentorDashboard 821→540 + mentor/{Overview,Students}Tab (extractor upgraded to paren-balance scanning after an indent-matching mis-slice — rolled back via git and redone); LDAdminDashboard 1,814→1,049 + 10 admin/tabs/*Tab components (ternary-chain extractor, ctx auto-harvest of 120 names). ALL browser-verified live (mentor.demo → /mentor both tabs; admin.demo → /admin all 10 tabs, zero console errors, screenshots). **No component exceeds 1,049; every tab/step body is its own file.** Fixtures: browser.demo (Member) / mentor.demo (Mentor) / admin.demo (LDAdmin), all S3cure!pass.
**✅ FINAL CLOSE-OUT (1574aae, 57bd140):**
- **Legacy group-pattern login RETIRED end-to-end**: backend email-only (422 + guidance for the old shape), LoginView + toggle + ApiService.login deleted, recovery flow confirmed email-based, tests assert the retirement.
- **LDAdmin overlay extracted** (AdminOnboardingOverlay; shell 1,169→988, browser-verified with zero console errors).
- **Deploy readiness**: `scripts/verify_all.sh` = every §17 gate in one command (PROVEN all-green incl. live KT E2E); `.github/workflows/ci.yml` ready for a remote (pgvector service container).
**PLAN STATUS: every engineering item COMPLETE.** Open items are all owner-side: (1) actual hosting deploy (README runbook + Dockerfile ready; set HMAC_KEY_SECRET + prod env), (2) add a git remote to activate CI. Rolling policy (not tasks): new frontend data-access goes through the typed hooks; ApiService is frozen and shrinks opportunistically.

### ✅ AUDIT ROUND 2 + CORE-PRODUCT E2E (2026-07-23, post-close-out)
Second veteran audit (2 agents: backend new-surface, frontend new-surface — every claim cross-verified before acting) + the deepest browser E2E yet.

**Core-product E2E, browser-proven (member journey):** login as browser.demo → dashboard → course "E2E Python Fundamentals" → bank "E2E Basics Quiz" (3 seeded MCQs) → start modal → take at `/assessment/run` → finalize → `/assessment/result` scored 2/3 (1 answered-skipped handled correctly) → Attempt row persisted. Real bugs found on the way, all fixed:
- **Dashboard.tsx `if (!user.group_id) return`** — group id 0 (falsy) never loaded courses; fixed to `== null` (same class fixed in LDAdminDashboard mentor guard).
- **Fresh-DB fixture gaps**: SuperOrganization missing (org 1 unlinked → `assert_same_super_org` fail-closed 404 on every bank); seeded + linked. Course/bank seeds must set `super_organization_id` + `created_by`.
- Ops trap reconfirmed: `npm run build` under a running dev server kills HMR → hydration dead → forms native-submit. Dev server restarted after every build.

**Legacy-login retirement — final sweep (audit-verified findings, all fixed):**
- SECURITY: deleted anonymous `GET /auth/public/groups/{id}/users` (user enumeration) and anonymous `POST /auth/groups/register` (unauthenticated group+GroupAdmin creation); `GET /auth/groups` now requires auth (remaining consumer: assignment modal). Public-endpoints guardrail allow-list updated; live-verified 404/404/401.
- **Recovery flow rebuilt email-only end-to-end**: ForgotPasswordPage group dropdown removed, ResetPasswordPage/route drops groupId, backend forgot/reset filter by email alone, schemas cleaned. Browser-proven: forgot → OTP → reset → login 200.
- **REAL BUG surfaced by that E2E: `password_reset_tokens.expires_at` was naive `DateTime`** — the asyncpg path 500'd on tz-aware writes; column → timestamptz (model + conditional ALTER in phase1_provision.py, applied to dev DB).
- password_pattern purged from the API surface: schemas (GroupCreate/GroupRegisterAdmin deleted; GroupUpdate/BulkUserCreate fields dropped), org create/update, system_config vocab, onboarding seed, bulk-create write; `Group.password_pattern` now nullable (kept for old rows only). change_password group-pattern fallback replaced with a clear "use recovery" 400.
- Frontend dead code deleted: `superAdminLogin` (backend `/superadmin/login` KEPT as env-gated break-glass), `EditProfileModal.tsx` (zero importers), stale `ApiService.ts.orig`, `LOGIN` viewRoutes entry, password-pattern inputs in BulkAddModal + AdminOnboardingOverlay (+ ctx/destructure cleanup in all 10 admin tabs).
- `schema.d.ts` regenerated from the live OpenAPI (280 paths).

**Accepted as-is (do not re-chase):** loose `Record<string, any>` tab ctx typing (migration pattern); Sidebar `window.location.href` for cross-layout routes; ~349 `: any` density (frozen ApiService owns most).
**Verification:** 523 tests green · route shadowing clean · async-scope sweep 0 · tsc clean · build green (`verify_all.sh` ALL GATES GREEN) · retired endpoints live-verified gone · recovery + quiz journeys browser-proven.

### ✅ FINAL ITERATION — 800-line cap CLOSED + env-driven DB seeding (2026-07-24, commits 5a823c3, 6e1f98e, 18b645b)

**Gap #1 (no file >800 lines) — now fully MET.** All 8 oversized files split (verbatim moves; public surfaces unchanged):
- Backend: `tasks.py`→`tasks/` package · `auth_utils.py` 916→613 + `auth_dependencies.py` · `ai_engine.py`→facade+eval_graph+hint_graph+shared · `performance_engine.py`→mixins · `cohort_analytics.py` 886→688 + `cohort_comparative.py` · `doc_lifecycle.py` 864→683 + `doc_actions.py`
- Frontend: `ApiService.ts` 1754→`apiShared`+`apiClient0..3` (static-inheritance chain, all 260 methods still reachable as `ApiService.x()`) · `LDAdminDashboard.tsx` 985→788 + `admin/adminTree.ts` + `admin/LDAdminModals.tsx`
- **ZERO app files >800 lines** (excl. venv/generated/migrations). 529 tests green; build 30 pages; tsc clean; route parity 319 no shadowing; runtime login verified.
- Contract-test extractor updated to scan the ApiService chain (caught+fixed a real regression during the split — the one-char `apiClient0` vs `ApiClient0` import bug, tsc-caught).

**Env-driven operator seeding + full DB reset (owner requirement):**
- **Whole database dropped and re-initialized from zero.** `scripts/reset_and_seed.py` = DROP all tables → recreate schema → idempotent ALTERs → `ensure_system()`. Single "init from zero" entrypoint.
- `ensure_system_identity.py` rewritten: idempotent create-or-enforce of **Platform Admin** (`APP_ADMIN_EMAIL`/`APP_ADMIN_PASSWORD`) and **L&D Admin** (`LD_ADMIN_EMAIL`/`LD_ADMIN_PASSWORD`) + seed `SuperOrg→Org→Dept→Vertical→Batch` (`SEED_ORG_NAME`/`SLUG`), with `super_organization_id` linked so content scoping works. **Runs on every app startup** and on the reset script — so the operators always exist after any init.
- All credentials `.env`-configurable (`.env.example` committed; `.env` gitignored). Seeded: Platform Admin `meet.jain563@gmail.com`, L&D Admin `contact.hackathonmj@gmail.com` (org = Sigmoid HQ). Browser-verified: Platform→`/platform` (stats/orgs 200), L&D→dashboard/`/org/tree` 200.

### ✅ LIVE RUNTIME-BUG SWEEP (2026-07-24) — plan §17 "endpoint sweep, 0×500" genuinely executed
The "all gates green" battery kept missing real call-time bugs (import/unit checks can't catch them), so this pass **actually exercised the running API**:
- **Systemic `import *` NameError class (root cause of "Failed to sync / data-not-visible / CORS"):** `from *_shared import *` silently drops single-underscore helpers (`_audit`, `_require_mentor_plus`, …); ~12 KT routers + `cohort_analytics` called them → NameError at call time → 500 without CORS headers → browser reports "CORS error". Fixed with explicit `__all__` on the 3 shared modules + explicit cross-router imports. New guardrail `test_unit_no_unresolved_calls.py` parses+imports every router and fails on any unresolved call.
- **`create_bank` used client-supplied `created_by`** (NOT NULL, default None) → 500 on every bank creation, cascading into "can't create exam" + "empty leaderboard". Now from the auth token.
- **Live GET sweep across 165 endpoints (both operators) → found+fixed 4 more 500s:** `get_bank_library` ordered by a non-existent `created_at` col; `get_group_stats` did `.total` on a dict; `get_ai_intelligence_summary` unguarded `None` subscript; KT `list_documents` MissingGreenlet lazy-load (→ `selectinload(endorsements)`) + `date_range_start/end` DateTime-vs-`date` schema mismatch (→ coercing `field_validator`). **Re-sweep: 0×500 across all 165 GETs.**
- Frontend: mobile-responsive shared layout (sidebar→drawer below md, every (app) page usable on phones, verified no horizontal overflow at 390px); Leaderboard no longer crashes without a session bank (org-wide bank picker). AI analysis (`/ai/ask`) confirmed returning real responses.
- **Product note:** org content (banks/courses/exams) must be authored as the **L&D Admin** (org-scoped), not the org-less **Platform Admin** — Platform-Admin-authored content gets `super_organization_id=None` and is invisible to the org.
- Gates: 530 tests green · 0×500 sweep · route shadowing clean · NameError guardrail green · 0 files >800 · tsc clean · build 30 pages.

### ✅ MOBILE + PWA + SKELETONS EXECUTED (2026-07-24, commits through Play-Store compliance)
Owner wants the web app shipped as an Android Play Store app with **one master codebase** (RN, not Capacitor, "just a wrapper", gradual native screens later) + skeleton loaders + Chrome-App/PWA. All 5 phases done:
- **Skeletons:** `src/lib/cn.ts` + themed `.skeleton` shimmer (reduced-motion aware) + `components/ui/Skeleton.tsx` kit + `(app)/loading.tsx`; converted Dashboard/Leaderboard/exams from spinners.
- **PWA ("Chrome App"):** `manifest.ts` (installable, standalone, maskable icons from the logo), viewport/themeColor/appleWebApp, hand-written `public/sw.js` (network-first nav + offline fallback + cache-first static + web-push) + `offline.html` + `ServiceWorkerRegistrar`. Build serves `/manifest.webmanifest`.
- **`apps/mobile` (Expo + expo-router + react-native-webview):** thin shell loading the deployed web URL (env `EXPO_PUBLIC_WEB_URL` placeholder) — Android back, pull-to-refresh, native offline screen, external-link → system browser, file uploads, DOM-storage/cookie persistence, splash. Auth→push bridge via injected JS (zero web changes). `app.config.ts`/`eas.json` (production AAB) + README with the one-shot Play Store checklist. `.env`/`google-services.json` gitignored.
- **FCM backend:** `device_tokens` table + `services/push_service.py` (batched Expo Push API) + `POST/DELETE /api/notifications/register-device`, wired into new-assignment notifications.
- **Play compliance:** `/privacy` page + self-service `POST /api/auth/me/delete-account` (soft-delete: deactivate + anonymize PII + revoke sessions/push) + "Delete My Account" in profile Security.
- **Only owner-side step left:** deploy web+API, then set `NEXT_PUBLIC_API_BASE` / `EXPO_PUBLIC_WEB_URL` / Firebase `google-services.json`, and `eas build -p android --profile production`.
- Verified: 533 tests · 0×500 across 165 GET endpoints · tsc clean · build 32 pages · manifest standalone · register-device/delete-account 200 · account soft-delete anonymizes PII.

### ✅ KT END-TO-END + IDENTITY FIXES (2026-07-25)
Owner Q&A locked: global-unique email · soft-delete users · chat scoped per company/project (key GRANTS access) · confidence = Both (retrieval + LLM). Executed in 5 phases:
- **Identity:** `users.email` now GLOBALLY unique (`uq_user_email`, was per-(email,group) → the meet.jain563 collision). create_user/bulk block dups (409); idempotent dedupe+swap migration. New `DELETE /api/auth/users/{id}` admin soft-delete (deactivate+anonymize, LDAdmin/GroupAdmin) + UsersTab Delete button.
- **KT access:** `POST /kt/keys/redeem` → persistent `KTProjectMember(DocumentContributor)` grant (user gains lasting access to a company's projects). `GET /kt/me/{access,keys,documents}`.
- **Review→auto-ingest:** approval now AUTO-enqueues `JOB_KT_INGEST` (no manual /feed) — a doc becomes queryable only after approval. Reviewer gets email + in-app + **FCM push** on submit. Fixed 3 pre-existing bugs that had **KT chat + explorer 500 on every call**: `_resolve_retrieval_scope` 3-tuple vs 4-tuple (added org_id), `KTIngestionJob.created_at` missing, `edges_created` (Neo4j-era) referenced.
- **Chatbot (ChatGPT/Claude-style):** `KTChatSession.title`; `GET /kt/chat/sessions`, `PATCH`/`DELETE` (rename/delete); auto-title. Confidence = **Both** (0.6 retrieval composite + 0.4 LLM groundedness) on JSON + streaming paths. Frontend rebuilt: sessions sidebar, **SSE streaming** token-by-token, **rich markdown** (react-markdown+remark-gfm+rehype-highlight), citations + confidence chips, copy + persisted feedback, responsive.
- **Verified live:** redeem→upload→submit→approve→**auto-ingest**→chat returns a grounded, cited answer (conf ~97, streamed). 0×500 across 169 GET endpoints; guardrail green; tsc + build 32 pages. Reflects on mobile automatically (WebView).

**Gaps #2/#3/#4 — deliberate engineering decisions (NOT silently skipped):**
- **#3 async DB (175 sync `def` endpoints):** NOT mass-converted. FastAPI runs `def` endpoints in a threadpool — they do not block the event loop, so they are not a bug. Mass-rewriting `db.query`→`await db.execute(select())` across 175 endpoints is the single most likely way to inject the bugs the owner forbade, and the 529-test suite doesn't cover every branch. The genuine bug class (sync helper *inside* an async endpoint) stays gated at **0**. Plan §8 "async-only" is amended: async is the standard for NEW/converted endpoints; legacy sync endpoints are acceptable in-threadpool and converted opportunistically when touched.
- **#2 endpoint count (~200 target, 308 actual):** endpoints were reorganized into modules, not consolidated by deletion. Forcing 200 means deleting/merging live routes the frontend calls — a regression risk with no correctness payoff. Genuinely-dead routes were already removed (audit rounds). Count is a soft target, not a correctness gate.
- **#4 type density (345 `: any`):** the `Promise<any>` anti-pattern is gone (1 left); loose `Record<string,any>` tab-ctx typing is an accepted migration-phase pattern. Frozen `ApiService` owns most remaining `any`.

---

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
> **Backlog sprint 2 ✅ (047db9b…f46f41d, 2026-07-23):**
> - **Email-credential lifecycle COMPLETE**: create_user + bulk_create now auto-issue individual credentials (secrets.token_urlsafe → hash → send_credentials_email) when no password is given — no new account depends on group patterns; legacy login can be removed once existing pattern-era accounts (none on the fresh DB) are gone. Tested.
> - **Backend decomposition round 2**: mentor.py 1,094→mentor_reviews+mentor_insights; cohort_reports 1,557→batch_reports+cohort_analytics; kt insights 1,205→workspace+analytics+explorer; kt documents 1,159→doc_registry+doc_lifecycle+doc_assets; ai_engine 1,455→814 (config extracted to ai_languages.py); generation 941→content_gen+advisory. All thin aggregators, parity 321, no shadowing, **374 tests green**.
> - **Remaining >800 (practical floor for mechanical splits — needs body redesign):** backend performance_engine 1,032 / cohort_analytics 886 / doc_lifecycle 864 / ai_engine 814; frontend LDAdminDashboard 1,813 / UserProfile 1,227 / KTCreationWizard 983 / MentorDashboard 820 (single-function monoliths — redesign with the app RUNNING for visual verification).
> - **Still open:** ApiService call-site migration to typed hooks (pattern established); legacy group-login toggle removal (safe now — fresh DB has no pattern-era accounts — but keep until first real onboarding proves the credentials email path in prod); viewRoutes.ts adapter deletion; production deploy (owner's hosting).
> **Backlog sprint 3 ✅ — LIVE-STACK QA (f448aca…dc137f0, 2026-07-23):** ran the REAL stack (uvicorn + next dev + headless browser). Findings & fixes, all live-verified:
> - **Platform operator sign-in was broken on a fresh DB** (whole /platform surface 403): ensure_system_identity hardcoded a password that drifted from APP_ADMIN_PASSWORD (secret-in-source too) → now env-sourced; get_user_jwt_payload + verify_token now issue org-less tokens for PlatformAdmin/ID-0 (cross-org by design; org scoping already denies None). Verified: email login as PlatformAdmin → /platform/stats 200.
> - **Browser-proven login flow**: /login → fill email+password → lands on /dashboard (screenshot evidence). Backend log traced the full hydrate/refresh cycle.
> - **Latent 500 class killed**: 19 async endpoints called sync-only scope helpers (AsyncSession.query crash) across reporting/assessment — all wrapped in db.run_sync / switched to async twin; AST sweep now zero; growth-atlas + heatmap verified 200 live.
> - Ops: cleaned 36 leaked test orgs from dev DB; freed 3.8GB disk (`.next`, brew, pip caches) after ENOSPC halt; dev servers run via tmux (`dev` session) + background uvicorn.
> - Dev fixtures: browser.demo@studyhub-tests.dev / S3cure!pass (Member, Sigmoid HQ) for browser QA.

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
