"""doc_lifecycle endpoints (moved verbatim from modules/kt/routers/documents.py)."""
from fastapi import APIRouter

from modules.kt.routers.documents_shared import *  # noqa: F401,F403

router = APIRouter()

@router.post("/documents", response_model=KTDocumentOut)
async def create_document(
    body: KTDocumentCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    user_role = current_user.get("role", "Member")

    # Validate project belongs to org
    project = await _get_project_or_404(body.project_id, org_id, db)

    # RBAC: Verify user can create documents in this project
    # DocumentContributor or ProjectOwner roles can upload
    try:
        await _require_project_access(
            uid, body.project_id, 
            ["DocumentContributor", "ProjectOwner", "Mentor", "LDAdmin", "Owner"], 
            db
        )
    except HTTPException:
        # If no scoped role, allow Mentor+ at global level to create in any project
        if user_role not in ["Mentor", "GroupAdmin", "LDAdmin", "Owner"]:
            raise

    # Verify user can access the company this project belongs to
    can_access = await _user_can_access_company(
        uid, project.company_id, org_id, db, current_user
    )
    if not can_access:
        raise HTTPException(403, "Access denied to this company's projects")

    # Validate co-authors exist in DB + collect their info
    co_names, co_emails, valid_co_ids = [], [], []
    from models import Department, Group

    for co_uid in body.co_author_ids or []:
        u_row = await db.execute(
            select(User.id, User.full_name, User.email, Department.organization_id)
            .outerjoin(Group, User.group_id == Group.id)
            .outerjoin(
                Department,
                or_(
                    User.department_id == Department.id,
                    Group.department_id == Department.id,
                ),
            )
            .where(User.id == co_uid)
        )
        u = u_row.one_or_none()
        if not u:
            raise HTTPException(400, f"Co-author user_id={co_uid} not found")
        # u.organization_id might be None if user has no dept/group-dept
        if u.organization_id and u.organization_id != org_id:
            raise HTTPException(
                400, f"Co-author user_id={co_uid} belongs to a different organization"
            )

        co_names.append(u.full_name)
        co_emails.append(u.email)
        valid_co_ids.append(u.id)

    wc = len(body.body_markdown.split())
    doc = KTDocument(
        project_id=body.project_id,
        company_id=project.company_id,
        organization_id=org_id,
        author_id=uid,
        title=body.title,
        doc_type=body.doc_type,
        knowledge_domain=body.knowledge_domain,
        tech_stack=body.tech_stack or [],
        tags=body.tags or [],
        complexity=body.complexity,
        is_evergreen=body.is_evergreen,
        access_level=body.access_level,
        sensitivity=body.sensitivity,
        language=body.language,
        co_author_ids=valid_co_ids,
        co_author_names=co_names,
        co_author_emails=co_emails,
        client_name=body.client_name,
        date_range_start=body.date_range_start,
        date_range_end=body.date_range_end,
        sprint=body.sprint,
        milestone=body.milestone,
        related_project_ids=body.related_project_ids or [],
        related_doc_ids=body.related_doc_ids or [],
        jira_tickets=body.jira_tickets or [],
        github_prs=body.github_prs or [],
        problem_statement=body.problem_statement,
        decisions_made=body.decisions_made or [],
        outcome=body.outcome,
        conclusion=body.conclusion,
        open_questions=body.open_questions or [],
        lessons_learned=body.lessons_learned or [],
        body_markdown=body.body_markdown,
        mentor_id=body.mentor_id,
        word_count=wc,
        read_time_minutes=max(1, wc // 200),
    )
    db.add(doc)
    await db.execute(
        update(KTProject)
        .where(KTProject.id == body.project_id)
        .values(doc_count=KTProject.doc_count + 1)
    )
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_CREATED,
        company_id=project.company_id,
        user_id=uid,
        resource_type="document",
        request=request,
    )
    await db.commit()
    await db.refresh(doc)

    # Version 1
    db.add(
        KTDocumentVersion(
            document_id=doc.id,
            version=1,
            body_markdown=body.body_markdown,
            author_id=uid,
            change_summary="Initial draft",
        )
    )
    await db.commit()

    # Background: auto-tag + quality score (NOT ingestion — that fires after mentor FEED).
    # Durable: an in-process task left the document permanently untagged if the
    # process restarted, with nothing to retry it.
    await enqueue_job(
        db,
        JOB_KT_ENRICH,
        {
            "document_id": str(doc.id),
            "body_markdown": body.body_markdown,
            "title": body.title,
        },
    )

    # Notify co-authors
    for i, co_uid in enumerate(valid_co_ids):
        await enqueue_job(
            db,
            JOB_EMAIL,
            {"method": "send_coauthor_invite", "args": [co_emails[i], co_names[i], doc.title, doc.id, current_user.get("name", "A colleague")]},
        )
        await _notify(
            db,
            co_uid,
            org_id,
            project.company_id,
            "coauthor_added",
            "Added as co-author",
            f'You\'ve been added as co-author on "{doc.title}"',
            "document",
            doc.id,
        )

    await db.commit()

    # Reload with `endorsements` eagerly loaded. KTDocumentOut serializes both
    # server-default columns (created_at) and the endorsements relationship;
    # on a freshly inserted row neither is populated, and an AsyncSession cannot
    # satisfy them via an implicit lazy load (MissingGreenlet).
    doc = await _get_doc_or_404(doc.id, org_id, db)
    doc_out = KTDocumentOut.model_validate(doc)
    doc_out.can_edit = True
    return doc_out

@router.get("/documents", response_model=List[KTDocumentOut])
async def list_documents(
    project_id: Optional[str] = None,
    company_id: Optional[str] = None,
    status: Optional[str] = None,
    doc_type: Optional[str] = None,
    knowledge_domain: Optional[str] = None,
    sprint: Optional[str] = None,
    search: Optional[str] = None,
    author_id: Optional[int] = None,
    is_evergreen: Optional[bool] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    if not current_user and not x_kt_key:
        raise HTTPException(401, "Authentication required (JWT or X-KT-Key)")

    if x_kt_key:
        key_record = await _resolve_key(x_kt_key, db)
        q = select(KTDocument).where(
            KTDocument.organization_id == key_record.organization_id,
            KTDocument.project_id.in_(_normalize_grant_list(key_record.project_ids)),
            KTDocument.status.in_([DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]),
        )
        if project_id and project_id not in _normalize_grant_list(key_record.project_ids):
            return []
    else:
        assert current_user is not None
        org_id = int(current_user["organization_id"])
        uid = int(current_user["sub"])
        _db_user_res = await db.execute(
            select(User.role).where(User.id == int(current_user["sub"]))
        )
        role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")

        q = select(KTDocument).where(KTDocument.organization_id == org_id)

        # ── RBAC visibility ──────────────────────────────────────────────────
        if role == "author" or role not in ["Mentor", "GroupAdmin", "LDAdmin", "Owner"]:
            # Authors: see their own docs (any status) OR any approved/ingested docs (Discovery)
            q = q.where(
                or_(
                    KTDocument.author_id == uid,
                    KTDocument.co_author_ids.contains([uid]),
                    KTDocument.status.in_(
                        [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]
                    ),
                )
            )
        elif role == "Mentor":
            pass
        elif role == "GroupAdmin":
            group_id = current_user.get("group_id")
            if group_id:
                proj_res = await db.execute(
                    select(KTProject.id).where(
                        KTProject.organization_id == org_id,
                        KTProject.group_id == group_id,
                    )
                )
                proj_ids = [r[0] for r in proj_res.fetchall()]
                q = q.where(KTDocument.project_id.in_(proj_ids))
        # LDAdmin + Owner: see everything in org

    # ── Filters ──────────────────────────────────────────────────────────
    if project_id:
        q = q.where(KTDocument.project_id == project_id)
    if company_id:
        q = q.where(KTDocument.company_id == company_id)
    if status:
        q = q.where(KTDocument.status == status)
    if doc_type:
        q = q.where(KTDocument.doc_type == doc_type)
    if knowledge_domain:
        q = q.where(KTDocument.knowledge_domain == knowledge_domain)
    if sprint:
        q = q.where(KTDocument.sprint == sprint)
    if author_id:
        q = q.where(KTDocument.author_id == author_id)
    if is_evergreen is not None:
        q = q.where(KTDocument.is_evergreen == is_evergreen)
    if search:
        q = q.where(
            or_(
                KTDocument.title.ilike(f"%{search}%"),
                KTDocument.problem_statement.ilike(f"%{search}%"),
            )
        )

    await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(KTDocument.updated_at.desc().nullslast())
        .offset((page - 1) * size)
        .limit(size)
    )
    docs = result.scalars().all()

    out = []
    for d in docs:
        doc_out = KTDocumentOut.model_validate(d)
        doc_out.can_edit = await _can_edit_doc(d, current_user)
        out.append(doc_out)

    return out

@router.get("/documents/{doc_id}", response_model=KTDocumentOut)
async def get_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
    x_kt_key: Optional[str] = Header(None),
):
    if not current_user and not x_kt_key:
        raise HTTPException(401, "Authentication required (JWT or X-KT-Key)")

    if x_kt_key:
        key_record = await _resolve_key(x_kt_key, db)
        res = await db.execute(
            select(KTDocument)
            .options(selectinload(KTDocument.endorsements))
            .where(
                KTDocument.id == doc_id,
                KTDocument.organization_id == key_record.organization_id,
            )
        )
        doc = res.scalar_one_or_none()
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.project_id not in _normalize_grant_list(key_record.project_ids):
            raise HTTPException(403, "Access denied by gateway scope")
        if doc.status not in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]:
            raise HTTPException(403, "Access denied: Document not public")
        doc_out = KTDocumentOut.model_validate(doc)
        doc_out.can_edit = False
        return doc_out
    else:
        assert current_user is not None
        org_id = int(current_user["organization_id"])
        uid = int(current_user["sub"])
        _db_user_res = await db.execute(
            select(User.role).where(User.id == int(current_user["sub"]))
        )
        role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
        doc = await _get_doc_or_404(doc_id, org_id, db)

        # Access check for authors
        if role not in ["Mentor", "GroupAdmin", "LDAdmin", "Owner"]:
            is_author = doc.author_id == uid
            is_coauthor = uid in (doc.co_author_ids or [])
            is_public = doc.status in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]
            if not (is_author or is_coauthor or is_public):
                raise HTTPException(403, "Access denied")

        doc_out = KTDocumentOut.model_validate(doc)
        doc_out.can_edit = await _can_edit_doc(doc, current_user)
        return doc_out

@router.patch("/documents/{doc_id}", response_model=KTDocumentOut)
async def update_document(
    doc_id: str,
    body: KTDocumentUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    if not await _can_edit_doc(doc, current_user):
        raise HTTPException(403, "Not authorized to edit this document")

    # Re-validate co_author_ids if changed
    if body.co_author_ids is not None:
        from models import Department, Group

        co_names, co_emails, valid_ids = [], [], []
        for co_uid in body.co_author_ids:
            row = await db.execute(
                select(User.id, User.full_name, User.email)
                .outerjoin(Group, User.group_id == Group.id)
                .outerjoin(
                    Department,
                    or_(
                        User.department_id == Department.id,
                        Group.department_id == Department.id,
                    ),
                )
                .where(User.id == co_uid, Department.organization_id == org_id)
            )
            u = row.one_or_none()
            if not u:
                raise HTTPException(400, f"Co-author user_id={co_uid} not found")
            co_names.append(u.full_name)
            co_emails.append(u.email)
            valid_ids.append(u.id)

        # Notify newly added co-authors
        old_ids = set(doc.co_author_ids or [])
        set(valid_ids)
        for i, co_uid in enumerate(valid_ids):
            if co_uid not in old_ids:
                await db.get(KTProject, doc.project_id)
                await enqueue_job(
                    db,
                    JOB_EMAIL,
                    {"method": "send_coauthor_invite", "args": [co_emails[i], co_names[i], doc.title, doc.id, current_user.get("full_name", "A colleague")]},
                )

        doc.co_author_ids = valid_ids
        doc.co_author_names = co_names
        doc.co_author_emails = co_emails

    # Save version if body changed
    if body.body_markdown and body.body_markdown != doc.body_markdown:
        doc.version = (doc.version or 0) + 1
        db.add(
            KTDocumentVersion(
                document_id=doc.id,
                version=doc.version,
                body_markdown=body.body_markdown,
                author_id=uid,
                change_summary=body.change_summary,
            )
        )

    updates = body.model_dump(
        exclude_none=True, exclude={"change_summary", "co_author_ids"}
    )
    for k, v in updates.items():
        setattr(doc, k, v)

    if body.body_markdown:
        wc = len(body.body_markdown.split())
        doc.word_count = wc
        doc.read_time_minutes = max(1, wc // 200)

    quality, completeness = await KTIngestionService.compute_quality(doc)
    doc.quality_score = quality
    doc.header_completeness = completeness

    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_UPDATED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.commit()
    doc_out = KTDocumentOut.model_validate(doc)
    doc_out.can_edit = True
    return doc_out

@router.post("/documents/{doc_id}/submit")
async def submit_document(
    doc_id: str,
    body: SubmitDocumentRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    if doc.author_id != uid and uid not in (doc.co_author_ids or []):
        raise HTTPException(403, "Only author or co-author can submit")
    if doc.status not in [DocStatusEnum.DRAFT, DocStatusEnum.REJECTED]:
        raise HTTPException(400, f"Cannot submit from status: {doc.status}")
    if not doc.body_markdown.strip():
        raise HTTPException(400, "Document body cannot be empty")

    doc.status = DocStatusEnum.SUBMITTED
    doc.submitted_at = datetime.now(timezone.utc)
    if body.mentor_id:
        doc.mentor_id = body.mentor_id

    logger.info(
        f"📄 Doc {doc.id} submitted for review by user {uid} to mentor {doc.mentor_id}"
    )

    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_SUBMITTED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.commit()

    # Notify mentor
    if doc.mentor_id:
        mentor = await db.get(User, doc.mentor_id)
        if mentor:
            logger.info(
                f"📧 Triggering submission email to mentor {mentor.email} (UID: {doc.mentor_id})"
            )
            await enqueue_job(
                db,
                JOB_EMAIL,
                {"method": "send_doc_submitted", "args": [mentor.email, mentor.full_name, doc.title, doc_id]},
            )
            await _notify(
                db,
                doc.mentor_id,
                org_id,
                doc.company_id,
                "doc_submitted",
                "Document awaiting review",
                f'"{doc.title}" needs your approval',
                "document",
                doc_id,
            )
            await db.commit()
        else:
            logger.warning(
                f"⚠️ Mentor with ID {doc.mentor_id} not found in DB - skipping notification"
            )

    return {"message": "Submitted for review", "status": "submitted"}

@router.post("/documents/{doc_id}/feed")
async def feed_document(
    doc_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Mentor clicks FEED → triggers temporal graph ingestion pipeline."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    result = await db.execute(
        select(KTDocument, KTProject.name.label("project_name"))
        .join(KTProject, KTDocument.project_id == KTProject.id)
        .where(KTDocument.id == doc_id, KTDocument.organization_id == org_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(404, "Document not found")
    doc, project_name = row.KTDocument, row.project_name

    if doc.status not in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]:
        raise HTTPException(400, "Document must be approved first")

    is_re = doc.status == DocStatusEnum.INGESTED
    if is_re:
        # Re-ingestion: purge previous pgvector chunks (the pipeline also
        # replaces them atomically; this keeps the store clean if the new
        # ingestion fails midway).
        from modules.kt.services.ingestion_service import purge_chunks

        await purge_chunks(db, doc_id)

    job = KTIngestionJob(
        document_id=doc_id,
        triggered_by_id=uid,
        is_re_ingestion=is_re,
        status=IngestionStatusEnum.PENDING,
    )
    db.add(job)
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_FED,
        company_id=doc.company_id,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
        meta={"project_name": project_name, "re_ingestion": is_re},
        request=request,
    )
    # Durable enqueue INSIDE this transaction: if the commit below rolls back, no
    # orphan job survives; if the process dies after it, the worker still picks it
    # up. Previously this was a FastAPI BackgroundTask, so a deploy mid-ingestion
    # silently discarded the contribution.
    await enqueue_job(db, JOB_KT_INGEST, {"document_id": str(doc.id)})
    await db.commit()
    await db.refresh(job)

    return {
        "message": "Ingestion started",
        "job_id": job.id,
        "re_ingestion": is_re,
    }

@router.get("/documents/{doc_id}/ingestion-status")
async def ingestion_status(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    await _get_doc_or_404(doc_id, org_id, db)

    import json

    from cache_manager import redis_client

    redis_key = f"kt:ingestion:{doc_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    result = await db.execute(
        select(KTIngestionJob)
        .where(KTIngestionJob.document_id == doc_id)
        .order_by(KTIngestionJob.created_at.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return {"status": None}

    res = {
        "job_id": job.id,
        "status": job.status,
        "chunks_created": job.chunks_created,
        "nodes_created": job.nodes_created,
        "edges_created": job.edges_created,
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "duration_seconds": job.duration_seconds,
    }

    if job.status in [IngestionStatusEnum.COMPLETE, IngestionStatusEnum.FAILED]:
        try:
            await redis_client.set(redis_key, json.dumps(res), ex=86400)  # 24 hours
        except Exception:
            pass

    return res

@router.get("/documents/{doc_id}/ingestion-status/stream")
async def ingestion_status_stream(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    await _get_doc_or_404(doc_id, org_id, db)

    import json

    from cache_manager import redis_client

    async def event_generator():
        while True:
            redis_key = f"kt:ingestion:{doc_id}"
            try:
                cached = await redis_client.get(redis_key)
                if cached:
                    yield f"data: {cached}\n\n"
                    break
            except Exception:
                pass

            await db.rollback()  # Ensure fresh read
            result = await db.execute(
                select(KTIngestionJob)
                .where(KTIngestionJob.document_id == doc_id)
                .order_by(KTIngestionJob.created_at.desc())
                .limit(1)
            )
            job = result.scalar_one_or_none()
            if not job:
                yield f"data: {json.dumps({'status': None})}\n\n"
            else:
                data = {
                    "job_id": job.id,
                    "status": job.status,
                    "chunks_created": job.chunks_created,
                    "nodes_created": job.nodes_created,
                    "edges_created": job.edges_created,
                    "error_message": job.error_message,
                }
                yield f"data: {json.dumps(data)}\n\n"
                if job.status in [
                    IngestionStatusEnum.COMPLETE,
                    IngestionStatusEnum.FAILED,
                ]:
                    break
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/documents/{doc_id}/deprecate")
async def deprecate_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)
    doc.status = DocStatusEnum.DEPRECATED
    doc.deprecated_at = datetime.now(timezone.utc)
    # Remove from the vector store (retrieval also filters status==INGESTED).
    from modules.kt.services.ingestion_service import purge_chunks

    await purge_chunks(db, doc_id)
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_DEPRECATED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.commit()
    return {"message": "Deprecated and removed from knowledge graph"}

@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
    doc = await _get_doc_or_404(doc_id, org_id, db)

    if doc.author_id != uid and role not in [
        "Mentor",
        "GroupAdmin",
        "LDAdmin",
        "Owner",
    ]:
        raise HTTPException(403, "Not authorized to delete")

    from models.assignment import Assignment
    from models.learning_path import UserLearningPath

    # Referential Integrity Check Guardrail
    is_in_assignment = await db.execute(
        select(Assignment).where(Assignment.instructions.like(f"%{doc_id}%"))
    )
    if is_in_assignment.first():
        raise HTTPException(
            status_code=400,
            detail="Document is actively referenced in an Assignment and cannot be deleted.",
        )

    is_in_path = await db.execute(
        select(UserLearningPath).where(
            UserLearningPath.roadmap_json.like(f"%{doc_id}%")
        )
    )
    if is_in_path.first():
        raise HTTPException(
            status_code=400,
            detail="Document is actively referenced in a Learning Path and cannot be deleted.",
        )

    # Chunks cascade with the document row (FK ondelete=CASCADE); explicit
    # purge keeps behavior obvious and covers any orphaned rows.
    from modules.kt.services.ingestion_service import purge_chunks

    await purge_chunks(db, doc_id)

    await db.execute(
        update(KTProject)
        .where(KTProject.id == doc.project_id)
        .values(doc_count=KTProject.doc_count - 1)
    )
    await _audit(
        db,
        org_id,
        AuditActionEnum.DOC_DELETED,
        user_id=uid,
        resource_type="document",
        resource_id=doc_id,
    )
    await db.delete(doc)
    await db.commit()
    return {"message": "Document deleted"}

@router.post("/documents/{doc_id}/endorse")
async def endorse_document(
    doc_id: str,
    comment: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    doc = await _get_doc_or_404(doc_id, org_id, db)
    if doc.status not in [DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]:
        raise HTTPException(400, "Can only endorse approved documents")
    # Check if already endorsed
    existing = await db.execute(
        select(KTEndorsement).where(
            KTEndorsement.document_id == doc_id, KTEndorsement.user_id == uid
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Already endorsed this document")

    try:
        e = KTEndorsement(document_id=doc_id, user_id=uid, comment=comment)
        db.add(e)
        doc.endorsement_count = (doc.endorsement_count or 0) + 1
        await db.commit()
    except Exception as err:
        await db.rollback()
        from sqlalchemy.exc import IntegrityError

        if isinstance(err, IntegrityError) or "unique" in str(err).lower():
            raise HTTPException(400, "Already endorsed this document")
        raise
    return {"message": "Endorsed"}

@router.post("/documents/{doc_id}/ai-suggest")
async def ai_suggest_improvements(
    doc_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    doc = await _get_doc_or_404(doc_id, org_id, db)

    date_log_pattern = r"###\s+\d{4}-\d{2}-\d{2}"
    has_date_log = bool(re.search(date_log_pattern, doc.body_markdown))
    prompt = f"""Analyze this KT document and give specific improvement suggestions.

Title: {doc.title}
Type: {doc.doc_type}
Quality Score: {doc.quality_score}/100
Header Completeness: {doc.header_completeness}%
Word Count: {doc.word_count}
Has date-log sections: {has_date_log}

Return JSON:
{{
  "missing_fields": ["empty header fields"],
  "content_gaps": ["missing sections"],
  "temporal_log_suggestion": "specific date-log entries to add",
  "quality_tips": ["concrete tips"],
  "estimated_new_score": 85
}}
"""
    import hashlib
    import json

    # STRAT-AI-CACHE: Hash doc body to avoid redundant LLM calls for same exact doc state
    cache_hash = hashlib.sha256(f"{doc_id}|{doc.body_markdown}".encode()).hexdigest()
    redis_key = f"ai:suggest_kt:{cache_hash}"
    try:
        cached_str = await redis_client.get(redis_key)
        if cached_str:
            return json.loads(cached_str)
    except Exception:
        pass

    result = await gemini.generate_json(prompt)

    try:
        await redis_client.set(redis_key, json.dumps(result), ex=86400)  # 24h
    except Exception:
        pass

    return result
