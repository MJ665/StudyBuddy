"""
Access keys and verification
"""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()


class RedeemKeyRequest(BaseModel):
    raw_key: str


@router.post("/keys/redeem")
async def redeem_key(
    body: RedeemKeyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Redeem an access key to gain PERSISTENT access to a company's project
    knowledge. Adds the caller as a KTProjectMember (DocumentContributor) for the
    key's projects, so they can then upload knowledge AND chat over it — even
    after this request (unlike the per-request X-KT-Key header path)."""
    uid = int(current_user["sub"])
    org_id = int(current_user["organization_id"])

    raw = (body.raw_key or "").strip()
    if not raw or not verify_access_key_signature(raw):
        raise HTTPException(401, "Invalid access key")
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    res = await db.execute(select(KTAccessKey).where(KTAccessKey.key_hash == key_hash))
    key = res.scalar_one_or_none()
    if not key or not key.is_active or key.revoked_at is not None:
        raise HTTPException(401, "Access key revoked or invalid")
    if key.expires_at and key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(401, "Access key expired")
    if key.organization_id != org_id:
        raise HTTPException(403, "This access key belongs to another organization.")
    if key.max_uses and key.use_count >= key.max_uses:
        raise HTTPException(401, "Access key exhausted (max uses reached).")

    project_ids = _normalize_grant_list(key.project_ids)
    if not project_ids:
        raise HTTPException(400, "This access key grants no project knowledge.")

    newly_added = []
    for pid in project_ids:
        exists = await db.execute(
            select(KTProjectMember).where(
                KTProjectMember.project_id == pid, KTProjectMember.user_id == uid
            )
        )
        if exists.scalar_one_or_none():
            continue
        db.add(
            KTProjectMember(
                project_id=pid, user_id=uid, role_in_project="DocumentContributor"
            )
        )
        newly_added.append(pid)

    key.use_count += 1
    key.last_used_at = datetime.now(timezone.utc)
    await _audit(
        db,
        org_id,
        AuditActionEnum.KEY_USED,
        company_id=key.company_id,
        user_id=uid,
        resource_type="access_key",
        resource_id=key.id,
        meta={"redeemed_projects": project_ids, "newly_added": newly_added},
    )
    await db.commit()
    return {
        "company_id": key.company_id,
        "granted_project_ids": project_ids,
        "newly_added": newly_added,
        "message": "Access granted. You can now contribute to and chat over this project's knowledge.",
    }


@router.get("/me/access")
async def my_access(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Companies + projects the caller can retrieve/contribute to (their grants)."""
    uid = int(current_user["sub"])
    rows = await db.execute(
        select(KTProjectMember.project_id).where(KTProjectMember.user_id == uid)
    )
    pids = [r[0] for r in rows.all()]
    if not pids:
        return {"companies": []}
    proj_rows = await db.execute(
        select(KTProject.id, KTProject.name, KTProject.company_id).where(
            KTProject.id.in_(pids)
        )
    )
    by_company: dict = {}
    company_ids = set()
    for pid, pname, cid in proj_rows.all():
        by_company.setdefault(cid, []).append({"id": pid, "name": pname})
        company_ids.add(cid)
    comp_rows = await db.execute(
        select(KTCompany.id, KTCompany.name).where(KTCompany.id.in_(company_ids))
    )
    names = {cid: cname for cid, cname in comp_rows.all()}
    return {
        "companies": [
            {"company_id": cid, "company_name": names.get(cid, "Company"), "projects": projs}
            for cid, projs in by_company.items()
        ]
    }


@router.get("/me/keys")
async def my_keys(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Access keys issued to the caller's email (metadata only — never the raw key)."""
    user = await db.get(User, int(current_user["sub"]))
    if not user or not user.email:
        return []
    res = await db.execute(
        select(KTAccessKey).where(
            func.lower(KTAccessKey.recipient_email) == user.email.strip().lower()
        )
    )
    keys = res.scalars().all()
    return [
        {
            "id": k.id,
            "key_prefix": k.key_prefix,
            "scope_label": k.scope_label,
            "company_id": k.company_id,
            "project_ids": _normalize_grant_list(k.project_ids),
            "expires_at": k.expires_at,
            "revoked": k.revoked_at is not None or not k.is_active,
        }
        for k in keys
    ]

@router.post("/keys/generate")
async def generate_key(
    body: GenerateKeyRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Only mentors+ can generate passkeys."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    # Auto-resolve company_id if not provided (same logic as project creation)
    if not body.company_id:
        res = await db.execute(
            select(KTCompany).where(
                KTCompany.organization_id == org_id, KTCompany.is_active == True
            )
        )
        company = res.scalars().first()
        if not company:
            res = await db.execute(
                select(KTCompany).where(KTCompany.organization_id == org_id)
            )
            company = res.scalars().first()
        if not company:
            raise HTTPException(
                400, "No company found for this organization. Create a company first."
            )
        body.company_id = company.id
    else:
        company = await db.get(KTCompany, body.company_id)
        if not company or company.organization_id != org_id:
            raise HTTPException(404, "Company not found")

    for pid in body.project_ids:
        p = await db.get(KTProject, pid)
        if not p or p.company_id != body.company_id:
            raise HTTPException(
                400, f"Project {pid} does not belong to company {body.company_id}"
            )

    expires_at = datetime.now(timezone.utc) + timedelta(days=body.ttl_days)
    key_id = str(uuid.uuid4())
    raw_key, key_hash, key_prefix = generate_access_key(
        body.company_id, body.project_ids
    )

    key_record = KTAccessKey(
        id=key_id,
        company_id=body.company_id,
        organization_id=org_id,
        issued_by_id=uid,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scope_label=body.scope_label,
        recipient_email=body.recipient_email,
        recipient_name=body.recipient_name,
        project_ids=body.project_ids,
        expires_at=expires_at,
        max_uses=body.max_uses,
        is_onboarding_key=body.is_onboarding_key,
        notes=body.notes,
    )
    db.add(key_record)
    await _audit(
        db,
        org_id,
        AuditActionEnum.KEY_GENERATED,
        company_id=body.company_id,
        user_id=uid,
        resource_type="access_key",
        resource_id=key_id,
        meta={"project_ids": body.project_ids, "scope": body.scope_label},
    )
    await db.commit()

    # Send key via email
    if body.send_email and body.recipient_email:
        proj_names = []
        for pid in body.project_ids:
            p = await db.get(KTProject, pid)
            if p:
                proj_names.append(p.name)
        await enqueue_job(
            db,
            JOB_EMAIL,
            {"method": "send_access_key", "args": [body.recipient_email, body.recipient_name or "Team Member", raw_key, body.scope_label or "Project Knowledge Base", proj_names, expires_at]},
        )

    return {
        "id": key_id,
        "raw_key": raw_key,  # ← returned ONCE only
        "key_prefix": key_prefix,
        "scope_label": body.scope_label,
        "project_ids": body.project_ids,
        "expires_at": expires_at,
        "message": "Save the raw_key — it will not be shown again.",
    }



@router.get("/me/documents")
async def my_documents(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Knowledge documents the caller authored or co-authored (their own uploads)."""
    uid = int(current_user["sub"])
    res = await db.execute(
        select(KTDocument)
        .where(
            or_(
                KTDocument.author_id == uid,
                KTDocument.co_author_ids.contains([uid]),
            )
        )
        .order_by(KTDocument.updated_at.desc().nullslast())
        .limit(200)
    )
    docs = res.scalars().all()
    return [
        {
            "id": d.id,
            "title": d.title,
            "status": d.status.value if hasattr(d.status, "value") else d.status,
            "project_id": d.project_id,
            "company_id": d.company_id,
            "updated_at": d.updated_at,
        }
        for d in docs
    ]


@router.get("/keys/scope")
async def get_key_scope(
    x_kt_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns what a key is allowed to access.
    Used by frontend to render scoped UI.
    """
    key_record = await _resolve_key(x_kt_key, db)

    projects = []
    for pid in _normalize_grant_list(key_record.project_ids):
        p = await db.get(KTProject, pid)
        if p:
            doc_count = await db.scalar(
                select(func.count(KTDocument.id)).where(
                    KTDocument.project_id == pid,
                    KTDocument.status.in_(
                        [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]
                    ),
                )
            )
            projects.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "doc_count": doc_count,
                }
            )

    return {
        "company_id": key_record.company_id,
        "project_ids": _normalize_grant_list(key_record.project_ids),
        "projects": projects,
        "scope_label": key_record.scope_label,
        "expires_at": key_record.expires_at,
        "is_onboarding_key": key_record.is_onboarding_key,
    }



@router.get("/keys/{key_id}/scope")
async def get_specific_key_scope(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    key_record = await db.get(KTAccessKey, key_id)
    if not key_record or key_record.organization_id != org_id:
        raise HTTPException(404, "Key not found")

    projects = []
    for pid in _normalize_grant_list(key_record.project_ids):
        p = await db.get(KTProject, pid)
        if p:
            doc_count = await db.scalar(
                select(func.count(KTDocument.id)).where(
                    KTDocument.project_id == pid,
                    KTDocument.status.in_(
                        [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]
                    ),
                )
            )
            projects.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "doc_count": doc_count,
                }
            )

    return {
        "company_id": key_record.company_id,
        "project_ids": _normalize_grant_list(key_record.project_ids),
        "projects": projects,
        "scope_label": key_record.scope_label,
        "expires_at": key_record.expires_at,
        "is_onboarding_key": key_record.is_onboarding_key,
    }



@router.get("/keys", response_model=List[KTKeyOut])
async def list_keys(
    company_id: Optional[str] = None,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")

    q = select(KTAccessKey).where(KTAccessKey.organization_id == org_id)

    # Mentors only see keys they issued
    if role == "Mentor":
        q = q.where(KTAccessKey.issued_by_id == uid)

    if company_id:
        q = q.where(KTAccessKey.company_id == company_id)
    if active_only:
        now = datetime.now(timezone.utc)
        q = q.where(
            KTAccessKey.revoked_at.is_(None),
            or_(KTAccessKey.expires_at.is_(None), KTAccessKey.expires_at > now),
        )

    result = await db.execute(q.order_by(KTAccessKey.created_at.desc()))
    keys = result.scalars().all()

    # Populate the computed UI fields (recipient_name is a real column;
    # is_active + uses_remaining are derived) so the registry shows real values
    # instead of 'System Account' / 'undefined/100' / everything 'Revoked'.
    now = datetime.now(timezone.utc)
    from kt_schemas import KTKeyOut

    out = []
    for k in keys:
        exp = k.expires_at
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        active = k.revoked_at is None and (exp is None or exp > now)
        remaining = (k.max_uses - (k.use_count or 0)) if k.max_uses else None
        dto = KTKeyOut.model_validate(k)
        dto.is_active = active
        dto.uses_remaining = remaining
        out.append(dto)
    return out



@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")

    key = await db.get(KTAccessKey, key_id)
    if not key or key.organization_id != org_id:
        raise HTTPException(404, "Key not found")
    # Mentor can only revoke own keys
    if role == "Mentor" and key.issued_by_id != uid:
        raise HTTPException(403, "You can only revoke keys you issued")

    key.revoked_at = datetime.now(timezone.utc)
    await _audit(
        db,
        org_id,
        AuditActionEnum.KEY_REVOKED,
        user_id=uid,
        resource_type="access_key",
        resource_id=key_id,
    )
    await db.commit()
    return {"message": "Key revoked"}



@router.post("/keys/verify")
async def verify_key_endpoint(
    x_kt_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
):
    """Check validity without consuming a use."""
    if not verify_access_key_signature(x_kt_key):
        return {"valid": False, "reason": "Invalid signature"}
    key_hash = hashlib.sha256(x_kt_key.encode()).hexdigest()
    result = await db.execute(
        select(KTAccessKey).where(KTAccessKey.key_hash == key_hash)
    )
    key = result.scalar_one_or_none()
    if not key:
        return {"valid": False, "reason": "Not found"}
    if key.revoked_at:
        return {"valid": False, "reason": "Revoked"}
    return {
        "valid": True,
        "scope_label": key.scope_label,
        "company_id": key.company_id,
        "project_ids": key.project_ids,
        "expires_at": key.expires_at,
    }



    # ════════════════════════════════════════════════════════════════════════════
    # GRAPH: Neighborhood exploration
    # ════════════════════════════════════════════════════════════════════════════


    @router.get("/neighborhood")
    async def explore_graph_neighborhood(
        node_id: str = Query(..., description="Document ID or concept node"),
        depth: int = Query(1, ge=1, le=3),
        db: AsyncSession = Depends(get_db),
        current_user: dict = Depends(get_current_user_with_db_role),
    ):
        """
        Traverse K-hops from a node in the knowledge graph.
        Returns connected documents, concepts, and relationships.
        """
        org_id = int(current_user["organization_id"])
        uid = int(current_user["sub"])

        # Try to load document node from primary DB first
        doc = await db.get(KTDocument, node_id)
        if not doc or doc.organization_id != org_id:
            raise HTTPException(404, "Document not found")

        # Company access check — RETRIEVAL path, so membership is required.
        # A global Mentor/LDAdmin role does not by itself grant read access to
        # another team's knowledge graph.
        if not await _user_can_retrieve_company(uid, doc.company_id, org_id, db):
            raise HTTPException(403, "Access denied")

        # Relational neighborhood (Phase 6): same project + shared tags.
        # (The old neo4j.traverse_neighborhood call referenced a method that
        # never existed — it always raised and returned [].)
        try:
            from modules.kt.services.graph_service import related_documents

            neighbors = await related_documents(db, doc)
        except Exception:
            # Fallback: return empty neighbor list on service errors
            neighbors = []

        return {
            "root_node": {"id": doc.id, "title": doc.title, "type": "document"},
            "neighbors": neighbors,
            "depth": depth,
        }


    # ════════════════════════════════════════════════════════════════════════════
    # CHAT (RAG)
    # ════════════════════════════════════════════════════════════════════════════



