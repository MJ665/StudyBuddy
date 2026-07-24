"""
Shared helpers, common imports, and utilities for KT routers.
Used by all KT sub-routers to avoid circular imports.
"""

import asyncio
import hashlib
import json
import logging
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

logger = logging.getLogger("kt.router")

from auth_utils import verify_token, verify_token_optional
from database import db_session_factory
from database import get_async_db as get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import StreamingResponse
from kt_schemas import (
    GenerateKeyRequest,
    KTAttachmentOut,
    KTAttachmentPresignRequest,
    KTAttachmentRegisterRequest,
    KTChatFeedbackRequest,
    KTChatMessageRequest,
    KTChatStartRequest,
    KTCompanyCreate,
    KTCompanyOut,
    KTDocumentCreate,
    KTDocumentOut,
    KTDocumentUpdate,
    KTHandoffInitiateRequest,
    KTKeyOut,
    KTOnboardingBundleRequest,
    KTProjectCreate,
    KTProjectOut,
    KTProjectUpdate,
    ReviewRequest,
    SubmitDocumentRequest,
)
from models import (
    AuditActionEnum,
    DocStatusEnum,
    IngestionStatusEnum,
    KTAccessKey,
    KTAuditLog,
    KTChatMessage,
    KTChatSession,
    KTCompany,
    KTDocument,
    KTDocumentAttachment,
    KTDocumentReview,
    KTDocumentVersion,
    KTEndorsement,
    KTHandoff,
    KTIngestionJob,
    KTNotification,
    KTProject,
    KTProjectMember,
    KTUnansweredQuery,
    ReviewActionEnum,
    User,
)
from routers.kt_user_helper import get_current_user_with_db_role
from services import s3_service
from services.kt_engine import (
    RAG_SYSTEM_PROMPT,
    build_rag_prompt,
    extract_temporal_range,
    gemini,
    generate_access_key,
    is_injection,
    rerank,
    sanitize_output,
    verify_access_key_signature,
)
from services import email_service as email_svc
from services.job_handlers import (
    JOB_EMAIL,
    JOB_KT_ENRICH,
    JOB_KT_INGEST,
)
from services.job_queue import enqueue as enqueue_job
from services.kt_workflows import KTIngestionService, run_rag_query
from sqlalchemy import and_, distinct, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from services.kt_langraph import stream_kt_chatbot_response

# ── Helper: role check ────────────────────────────────────────────────────
# NOTE: these helpers were recovered verbatim from the original routers/kt.py
# (session-transcript evidence) after a refactoring agent replaced them with
# invented implementations. Do not "simplify" them — the docstrings encode
# security decisions (least-privilege retrieval, fail-closed grants).


def _require_role(user: dict, *allowed_roles: str):
    if user.get("role") not in allowed_roles:
        raise HTTPException(403, "Insufficient role")


def _require_mentor_plus(user: dict):
    _require_role(user, "Mentor", "GroupAdmin", "LDAdmin", "Owner")


def _require_group_admin_plus(user: dict):
    _require_role(user, "GroupAdmin", "LDAdmin", "Owner")


def _require_ld_admin_plus(user: dict):
    _require_role(user, "LDAdmin", "Owner")


async def _require_project_access(
    user_id: int, project_id: str, allowed_roles: list[str], db: AsyncSession
):
    """
    Verify user has one of the allowed roles for a specific project.
    Uses the real auth schema: global `User.role` plus project membership.
    """
    from models.auth import User
    from models.kt_model import KTProjectMember

    # First, check the user's global role.
    user = await db.get(User, user_id)
    if user and user.role in allowed_roles:
        return

    # Fallback: check if user is a project member
    is_member = await db.scalar(
        select(KTProjectMember).where(
            KTProjectMember.user_id == user_id,
            KTProjectMember.project_id == project_id,
            KTProjectMember.role_in_project.in_(allowed_roles),
        )
    )

    if is_member:
        return

    raise HTTPException(403, f"User lacks required project role: {allowed_roles}")


def _normalize_grant_list(value) -> list[str]:
    """Grant lists must fail CLOSED. A NULL/absent list means 'no grants', never
    'all'; it is also unsafe to pass None into a SQL IN (...) clause."""
    if not value:
        return []
    return [str(v) for v in value]


async def _resolve_granted_project_ids(
    user_id: int,
    org_id: int,
    db: AsyncSession,
    requested: list[str] | None = None,
) -> list[str]:
    """The single source of truth for which projects a user may RETRIEVE knowledge from.

    Least privilege: membership in `kt_project_members` is the only grant. A global
    role never confers knowledge access on its own — an LDAdmin who is not a member
    of a project cannot query that project's knowledge. Project creators are
    auto-enrolled as "lead" at creation, so this does not lock anyone out of their
    own projects.

    `requested` NARROWS the result and can never widen it. Ids outside the grant set
    are dropped silently rather than raising, so a caller cannot use the error to
    probe which project ids exist; the caller raises 403 when the result is empty.
    """
    rows = await db.execute(
        select(KTProject.id)
        .join(KTProjectMember, KTProjectMember.project_id == KTProject.id)
        .where(
            KTProjectMember.user_id == user_id,
            KTProject.organization_id == org_id,
        )
    )
    granted = set(rows.scalars().all())
    if requested:
        granted &= set(_normalize_grant_list(requested))
    return sorted(granted)


async def _resolve_retrieval_scope(
    db: AsyncSession,
    current_user: Optional[dict],
    x_kt_key: Optional[str],
    requested_project_ids: Optional[list[str]] = None,
    requested_company_id: Optional[str] = None,
) -> tuple[str, list[str], Optional[str]]:
    """THE enforcement point for every KT retrieval path.

    Returns `(company_id, project_ids, access_key_id)` derived from the caller's
    GRANTS. Chat, graph exploration and the knowledge timeline all route through
    here so the rule cannot drift between them — each previously resolved scope
    from client input (`resolved_project_ids = body.project_ids` /
    `= project_ids`), letting any authenticated user read any project in their org.

    Requested ids only ever NARROW the grant set.
    """
    if x_kt_key:
        key_record = await _resolve_key(x_kt_key, db)
        granted = set(_normalize_grant_list(key_record.project_ids))
        if requested_project_ids:
            granted &= set(_normalize_grant_list(requested_project_ids))
        if not granted:
            raise HTTPException(403, "This access key grants no project knowledge.")
        # 4-tuple: (company_id, project_ids, access_key_id, org_id). org_id comes
        # from the key for anonymous (X-KT-Key) callers who have no JWT. Callers
        # (chat.py, explorer.py) unpack all four.
        return key_record.company_id, sorted(granted), key_record.id, key_record.organization_id

    if not current_user:
        raise HTTPException(401, "Authentication required (JWT or X-KT-Key)")

    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    granted = await _resolve_granted_project_ids(
        uid, org_id, db, requested=requested_project_ids
    )
    if not granted:
        raise HTTPException(
            403, "You have no knowledge access grants for the requested projects."
        )

    rows = await db.execute(
        select(KTProject.id, KTProject.company_id).where(KTProject.id.in_(granted))
    )
    project_company = {pid: cid for pid, cid in rows.all()}

    if requested_company_id:
        granted = [p for p in granted if project_company.get(p) == requested_company_id]
        if not granted:
            raise HTTPException(
                403, "You have no knowledge access grants in that company."
            )
        company_id = requested_company_id
    else:
        companies = set(project_company.values())
        if len(companies) > 1:
            raise HTTPException(
                400, "Your grants span multiple companies; specify company_id."
            )
        company_id = companies.pop()

    # Defence in depth: the company must still belong to the caller's org.
    company = await db.get(KTCompany, company_id)
    if not company or company.organization_id != org_id:
        raise HTTPException(404, "Company not found")

    return company_id, granted, None, org_id


async def _sensitivities_for_session(session, db: AsyncSession) -> list[str]:
    """Which document sensitivities may this chat session retrieve?

    `high` sensitivity means credentials/PII are present, so it is limited to
    callers who LEAD one of the session's granted projects. External access-key
    callers are never project members and therefore never see `high`.
    Resolved per request so a revoked role applies immediately.
    """
    from services.kt_engine import DEFAULT_SENSITIVITIES, sensitivities_for

    project_ids = _normalize_grant_list(session.resolved_project_ids)
    if not session.user_id or not project_ids:
        return list(DEFAULT_SENSITIVITIES)

    rows = await db.execute(
        select(KTProjectMember.role_in_project).where(
            KTProjectMember.user_id == session.user_id,
            KTProjectMember.project_id.in_(project_ids),
        )
    )
    return sensitivities_for(list(rows.scalars().all()))


async def _user_can_retrieve_company(
    user_id: int, company_id: str, org_id: int, db: AsyncSession
) -> bool:
    """Strict, membership-only company check for RETRIEVAL paths.

    Deliberately distinct from `_user_can_access_company` below, which governs
    AUTHORING and intentionally lets Mentor+ create documents in projects they do
    not belong to. Reading someone else's knowledge is not the same permission as
    contributing to it, and conflating the two is what allowed org-wide reads.
    """
    row = await db.execute(
        select(KTProject.id)
        .join(KTProjectMember, KTProjectMember.project_id == KTProject.id)
        .where(
            KTProjectMember.user_id == user_id,
            KTProject.company_id == company_id,
            KTProject.organization_id == org_id,
        )
        .limit(1)
    )
    return row.scalar_one_or_none() is not None


async def _user_can_access_company(
    user_id: int, company_id: str, org_id: int, db: AsyncSession, user_role: dict = None
) -> bool:
    """
    AUTHORING-side check: may this user create/contribute in this company?

    NOTE: this is intentionally broader than retrieval. For read/query paths use
    `_user_can_retrieve_company` instead.
    Rules:
    - LDAdmin/Owner: all companies in their org
    - Mentor: any company in their org (they curate knowledge)
    - Others: only via project membership
    """
    # Global admins can access all companies
    if user_role and user_role.get("role") in ["LDAdmin", "Owner"]:
        return True

    if user_role and user_role.get("role") == "Mentor":
        return True  # Mentors can access any company in their org

    # For other roles: check if user is member of any project in this company
    has_project = await db.scalar(
        select(KTProjectMember).where(
            KTProjectMember.user_id == user_id,
        ).join(KTProject).where(
            KTProject.company_id == company_id,
            KTProject.organization_id == org_id,
        )
    )

    return bool(has_project)


# ── Helper: get company from project (validated) ──────────────────────────


async def _get_project_or_404(
    project_id: str, org_id: int, db: AsyncSession
) -> KTProject:
    if not project_id or project_id == "":
        raise HTTPException(400, "A project must be selected.")
    try:
        uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(400, "Invalid project selection.")

    p = (
        await db.execute(
            select(KTProject)
            .where(KTProject.id == project_id)
            .options(selectinload(KTProject.members).selectinload(KTProjectMember.user))
        )
    ).scalar_one_or_none()

    if not p or p.organization_id != org_id:
        raise HTTPException(404, "Project not found")
    return p


async def _get_doc_or_404(doc_id: str, org_id: int, db: AsyncSession) -> KTDocument:
    if not doc_id or doc_id == "":
        raise HTTPException(400, "Document ID is required.")
    try:
        uuid.UUID(doc_id)
    except ValueError:
        raise HTTPException(400, "Invalid Document ID format.")

    res = await db.execute(
        select(KTDocument)
        .options(selectinload(KTDocument.endorsements))
        .where(KTDocument.id == doc_id, KTDocument.organization_id == org_id)
    )
    d = res.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "Document not found")
    return d


async def _can_edit_doc(doc: KTDocument, user: dict | None) -> bool:
    """Author OR co-author (by user_id) OR mentor+ role."""
    if not user:
        return False
    uid = int(user.get("sub", 0))
    role = user.get("role", "")
    if role in ["Mentor", "GroupAdmin", "LDAdmin", "Owner"]:
        return True
    if doc.author_id == uid:
        return True
    if uid in (doc.co_author_ids or []):
        return True
    return False


# ── Helper: audit log ─────────────────────────────────────────────────────


async def _audit(
    db: AsyncSession,
    org_id: int,
    action: AuditActionEnum,
    company_id: Optional[str] = None,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    meta: Optional[dict] = None,
    request: Optional[Request] = None,
):
    log = KTAuditLog(
        organization_id=org_id,
        company_id=company_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
        metadata_json=meta or {},
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(log)


# ── Helper: create notification ───────────────────────────────────────────


async def _notify(
    db: AsyncSession,
    user_id: int,
    org_id: int,
    company_id: str,
    ntype: str,
    title: str,
    body: str,
    resource_type: str | None = None,
    resource_id: str | None = None,
):
    n = KTNotification(
        user_id=user_id,
        organization_id=org_id,
        company_id=company_id,
        type=ntype,
        title=title,
        body=body,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id else None,
    )
    db.add(n)


# ── Helper: resolve access key (for external/chatbot endpoints) ───────────


async def _resolve_key(raw_key: str, db: AsyncSession) -> KTAccessKey:
    """Validate a raw `sh_kt_…` access key and return its active record.

    (Reconstructed against KTAccessKey's schema + the original call sites:
    format check → hash lookup → active/expiry/quota gates → usage stamp.)
    """
    if not raw_key or not verify_access_key_signature(raw_key):
        raise HTTPException(401, "Invalid access key")

    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    res = await db.execute(
        select(KTAccessKey).where(KTAccessKey.key_hash == key_hash)
    )
    key = res.scalar_one_or_none()
    if not key or not key.is_active or key.revoked_at is not None:
        raise HTTPException(401, "Access key revoked or invalid")
    if key.expires_at and key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "Access key expired")
    if key.max_uses and key.use_count >= key.max_uses:
        raise HTTPException(401, "Access key exhausted (max uses reached)")

    key.use_count += 1
    key.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    return key


# Export EVERY module-level name — including the single-underscore
# helpers (_audit, _require_mentor_plus, ...) that `import *` skips by
# default. Without this, every leaf router that star-imports this module
# raised NameError at call time on those helpers.
__all__ = [name for name in dir() if not name.startswith("__")]
