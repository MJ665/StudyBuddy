# Modular monolith — module map

North-star: `docs/product-plan/TARGET_ARCHITECTURE.md`. Rules that gate review:
**no file > 800 lines · routers are HTTP-only (validate → service → schema) ·
one async DB pattern for new code · errors via `shared/exceptions.py`.**

| Module | Owns | Key files |
|---|---|---|
| `identity/` | auth (email-first login), users, profiles, notifications | `routers/{session,users,profile,notifications}.py`, `routers/auth_shared.py` |
| `org/` | OrgUnit tree + role scoping; legacy-hierarchy mirror | `models.py` (OrgUnit, UserOrgRole), `sync.py` (dual-write after_flush mirror), `services/role_scope_service.py` |
| `assessment/` | banks, questions, courses, attempts, unified grading engine | `routers/{banks,courses,attempts}.py`, `services/attempt_engine.py` |
| `kt/` | knowledge transfer: documents, review, chat, keys, handoff, graph views | `routers/*` (8 files), `services/{ingestion_service,retrieval,graph_service}.py`, `models.py` (KTDocumentChunk, pgvector 3072-dim) |
| `ai/` | LLM generation endpoints | `routers/generation.py`, `routers/ai_shared.py` |
| `reporting/` | admin governance/analytics, member & cohort reports | `routers/{governance,admin_analytics,member_reports,cohort_reports}.py` |
| `platform/`, `jobs/` | reserved (operator surface; queue handlers still in `services/`) | — |

Legacy `routers/*.py` files are thin aggregators kept so `main.py` mounts are
stable; implementation lives here. The KT store is **Postgres/pgvector** —
Neo4j is fully retired (Phase 7). Legacy org tables are mirrored into
`org_units`/`user_org_roles` by `org/sync.py`; new reads use
`role_scope_service`.
