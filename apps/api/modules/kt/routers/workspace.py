"""workspace endpoints (moved verbatim from modules/kt/routers/insights.py)."""
from fastapi import APIRouter

from modules.kt.routers.insights_shared import *  # noqa: F401,F403
# Cross-router delegations (defined in sibling routers, not the shared module):
from modules.kt.routers.analytics import knowledge_gaps  # noqa: E402
from modules.kt.routers.chat import send_message  # noqa: E402

router = APIRouter()

@router.post("/companies", response_model=KTCompanyOut)
async def create_company(
    body: KTCompanyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_ld_admin_plus(current_user)
    org_id = int(current_user["organization_id"])
    company = KTCompany(name=body.name, domain=body.domain, organization_id=org_id)
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company

@router.get("/companies", response_model=List[KTCompanyOut])
async def list_companies(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    from auth_utils import is_platform_admin

    stmt = select(KTCompany).where(KTCompany.is_active == True)  # noqa: E712
    # PlatformAdmin administers every customer, so it is not org-filtered here.
    # NOTE: this is the ADMIN LISTING only — it does NOT widen knowledge
    # RETRIEVAL, which stays least-privilege via _resolve_retrieval_scope().
    if not is_platform_admin(current_user):
        raw_org = current_user.get("organization_id")
        if raw_org is None:
            # Org-less, non-platform-admin caller has no company scope — fail
            # closed with an empty list rather than crashing on int(None).
            return []
        stmt = stmt.where(KTCompany.organization_id == int(raw_org))
    result = await db.execute(stmt)
    return result.scalars().all()

@router.get("/coauthor-search")
async def search_coauthors(
    q: str = Query(..., min_length=2),
    group_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """
    Search for users within the org to pick as co-authors.
    Returns list of {user_id, name, email, group_name}.
    Frontend shows this in a picker — NOT free text entry.
    """
    uid = int(current_user["sub"])
    org_id = int(current_user["organization_id"])

    from models import Department, Group

    # Multi-tenant scoping: find users belonging to departments in this org
    query = (
        select(User.id, User.full_name, User.email, Group.name.label("group_name"))
        .outerjoin(Group, User.group_id == Group.id)
        .outerjoin(
            Department,
            or_(
                User.department_id == Department.id,
                Group.department_id == Department.id,
            ),
        )
        .where(
            Department.organization_id == org_id,
            User.is_active == True,
            User.id != uid,
            or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")),
        )
    )
    if group_id:
        query = query.where(User.group_id == group_id)

    result = await db.execute(query.limit(20))
    rows = result.fetchall()
    return [
        {
            "user_id": r.id,
            "name": r.full_name,
            "email": r.email,
            "group_name": r.group_name,
        }
        for r in rows
    ]

@router.delete("/attachments/{attachment_id}")
async def delete_attachment(
    attachment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    att = await db.get(KTDocumentAttachment, attachment_id)
    if not att:
        raise HTTPException(404, "Attachment not found")

    # Security check: must have access to the document
    doc = await db.get(KTDocument, att.document_id)
    if not doc or doc.organization_id != org_id:
        raise HTTPException(404, "Document not found")

    uid = int(current_user["sub"])
    if att.uploaded_by_id != uid and current_user.get("role") not in [
        "GroupAdmin",
        "LDAdmin",
    ]:
        raise HTTPException(403, "Not authorized to delete this attachment")

    # Delete from S3
    s3_service.delete_s3_object(att.s3_key)

    # Delete from DB
    await db.delete(att)
    await db.commit()
    return {"message": "Attachment deleted"}

@router.get("/notifications")
async def get_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    uid = int(current_user["sub"])
    q = select(KTNotification).where(KTNotification.user_id == uid)
    if unread_only:
        q = q.where(KTNotification.is_read.is_(False))
    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(KTNotification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    notifs = result.scalars().all()
    return {
        "items": [
            {
                "id": n.id,
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "resource_type": n.resource_type,
                "resource_id": n.resource_id,
                "is_read": n.is_read,
                "created_at": n.created_at,
            }
            for n in notifs
        ],
        "total": total,
    }

@router.patch("/notifications/{notif_id}/read")
async def mark_read(
    notif_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    uid = int(current_user["sub"])
    n = await db.get(KTNotification, notif_id)
    if not n or n.user_id != uid:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    n.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Marked as read"}

@router.patch("/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    uid = int(current_user["sub"])
    await db.execute(
        update(KTNotification)
        .where(KTNotification.user_id == uid, KTNotification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"message": "All marked as read"}

@router.get("/users/{user_id}/info")
async def get_user_info_for_kt(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    int(current_user["organization_id"])
    u = await db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")

    return {
        "id": u.id,
        "user_id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "role": u.role,
        "group_id": u.group_id,
    }

@router.post("/onboarding/bundle")
async def generate_onboarding_bundle(
    body: KTOnboardingBundleRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    p = await _get_project_or_404(body.project_id, org_id, db)

    # Priority docs
    priority_types = [
        "onboarding_guide",
        "architecture_decision",
        "runbook",
        "deployment_guide",
    ]
    result = await db.execute(
        select(KTDocument)
        .where(
            KTDocument.project_id == body.project_id,
            KTDocument.status == DocStatusEnum.INGESTED,
            KTDocument.doc_type.in_(priority_types),
        )
        .limit(15)
    )
    docs = result.scalars().all()

    # Generate access key
    key_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=body.ttl_days)
    raw_key, key_hash, key_prefix = generate_access_key(
        p.company_id, [body.project_id], key_id, expires_at
    )
    key_record = KTAccessKey(
        id=key_id,
        company_id=p.company_id,
        organization_id=org_id,
        issued_by_id=uid,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scope_label=f"Onboarding — {p.name}",
        project_ids=[body.project_id],
        expires_at=expires_at,
        is_onboarding_key=True,
    )
    db.add(key_record)
    await db.commit()

    # AI starter questions
    titles = ", ".join(d.title for d in docs[:8])
    prompt = f"""Generate 8 starter questions a new engineer should ask on day 1 
for project '{p.name}'. Knowledge base covers: {titles}.
Return as JSON array of strings."""
    starter_q = []
    try:
        text = await gemini.generate(prompt)
        clean = re.sub(r"```json\n?|\n?```", "", text).strip()
        starter_q = json.loads(clean)
    except Exception:
        starter_q = [
            "What is the overall system architecture?",
            "How do I set up the development environment?",
            "What are the key APIs and endpoints?",
            "How do I deploy this project?",
            "What are the known bugs or issues?",
            "Who are the key stakeholders?",
        ]

    # Notify new user
    if body.new_user_id:
        new_user = await db.get(User, body.new_user_id)
        if new_user:
            await enqueue_job(
                db,
                JOB_EMAIL,
                {"method": "send_access_key", "args": [new_user.email, new_user.full_name, raw_key, f"Onboarding — {p.name}", [p.name], expires_at]},
            )

    return {
        "project_name": p.name,
        "documents": [
            {"id": d.id, "title": d.title, "doc_type": d.doc_type} for d in docs
        ],
        "access_key": raw_key,
        "expires_at": expires_at,
        "starter_questions": starter_q,
    }

@router.post("/ask")
async def ask_kt_question(
    body: KTChatMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    """
    Direct ask KT question endpoint. Alias of /chat/message for frontend parity.
    """
    return await send_message(
        body=body, request=request, db=db, current_user=current_user, x_kt_key=x_kt_key
    )

@router.get("/suggestions")
async def get_kt_suggestions(
    company_id: Optional[str] = None,
    resolved: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """
    Direct endpoint for KT discovery suggestions. Parity with frontend expectations.
    """
    return await knowledge_gaps(
        company_id=company_id,
        resolved=resolved,
        page=page,
        size=size,
        db=db,
        current_user=current_user,
    )

@router.post("/draft")
async def save_kt_draft(
    payload: dict, current_user: dict = Depends(get_current_user_with_db_role)
):
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    await redis_client.set(f"kt_draft_{user_id}", payload, ex=86400 * 7)
    return {"success": True, "message": "KT draft saved successfully"}

@router.get("/draft")
async def get_kt_draft(current_user: dict = Depends(get_current_user_with_db_role)):
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    draft = await redis_client.get(f"kt_draft_{user_id}")
    return {"draft": draft}
