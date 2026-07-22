# kt.py — thin aggregator for the KT module (Phase 2 router split).
"""
All KT API routes, now organized under modules/kt/routers/*:

    documents.py   document CRUD, versions, attachments, registry, feed
    review.py      mentor review workflow
    ingestion.py   ingestion status + chat feedback
    chat.py        chat sessions + RAG messages (stream + non-stream)
    access.py      access keys + external session gate
    projects.py    KT projects + membership + companies
    handoff.py     exit-handoff engine
    insights.py    analytics, gaps, graph explorer, timeline, notifications

RBAC is enforced at the router level — not in the engine; shared helpers live
in modules/kt/routers/_shared.py. main.py mounts `router` unchanged.
"""

from fastapi import APIRouter

from modules.kt.routers import (
    access,
    chat,
    documents,
    handoff,
    ingestion,
    insights,
    projects,
    review,
)

# Re-exported for tests and any legacy callers importing from routers.kt.
# (`import *` skips underscore names, so these are explicit.)
from modules.kt.routers._shared import (  # noqa: F401
    _audit,
    _can_edit_doc,
    _get_doc_or_404,
    _get_project_or_404,
    _normalize_grant_list,
    _notify,
    _require_group_admin_plus,
    _require_ld_admin_plus,
    _require_mentor_plus,
    _require_project_access,
    _require_role,
    _resolve_granted_project_ids,
    _resolve_key,
    _resolve_retrieval_scope,
    _sensitivities_for_session,
    _user_can_access_company,
    _user_can_retrieve_company,
)

router = APIRouter(prefix="/kt", tags=["Knowledge Transfer"])

# Registration order matters for path matching: static paths (e.g.
# /documents/registry) must not fall after a dynamic sibling registered by an
# earlier include. Each sub-router keeps its original internal order; cross-file
# shadowing is checked by scripts/check_route_shadowing.py.
router.include_router(documents.router)
router.include_router(review.router)
router.include_router(ingestion.router)
router.include_router(chat.router)
router.include_router(access.router)
router.include_router(projects.router)
router.include_router(handoff.router)
router.include_router(insights.router)
