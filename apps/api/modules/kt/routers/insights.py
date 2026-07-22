"""
Insights, analytics, explorer, and other KT endpoints
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

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
        org_id = int(current_user["organization_id"])
        stmt = stmt.where(KTCompany.organization_id == org_id)
    result = await db.execute(stmt)
    return result.scalars().all()


# ════════════════════════════════════════════════════════════════════════════
# PROJECT ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════



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


# ════════════════════════════════════════════════════════════════════════════
# DOCUMENT ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════



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



@router.get("/mentor/inbox")
async def mentor_inbox(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")

    q = select(KTDocument).where(
        KTDocument.organization_id == org_id,
        KTDocument.status.in_([DocStatusEnum.SUBMITTED, DocStatusEnum.UNDER_REVIEW]),
    )
    # Mentors only see docs assigned to them
    if role == "Mentor":
        q = q.where(or_(KTDocument.mentor_id == uid, KTDocument.mentor_id.is_(None)))
    # GroupAdmin sees their group's projects
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

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(KTDocument.submitted_at.asc().nullslast())
        .offset((page - 1) * size)
        .limit(size)
    )
    docs = result.scalars().all()
    return {
        "items": [KTDocumentOut.model_validate(d) for d in docs],
        "total": total,
        "page": page,
        "pages": math.ceil((total or 0) / size),
    }


# ════════════════════════════════════════════════════════════════════════════
# ACCESS KEYS (Passkeys)
# ════════════════════════════════════════════════════════════════════════════



@router.get("/insights/my-docs")
async def my_doc_traction(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Author sees traction/analytics for their own documents only."""
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    result = await db.execute(
        select(
            KTDocument.id,
            KTDocument.title,
            KTDocument.status,
            KTDocument.quality_score,
            KTDocument.endorsement_count,
            KTDocument.word_count,
            KTDocument.created_at,
            KTDocument.ingested_at,
        )
        .where(
            KTDocument.organization_id == org_id,
            or_(KTDocument.author_id == uid, KTDocument.co_author_ids.contains([uid])),
        )
        .order_by(KTDocument.created_at.desc())
    )
    docs = result.fetchall()

    # Chat queries referencing these doc_ids
    doc_ids = [d.id for d in docs]
    query_counts = {}
    if doc_ids:
        msgs = await db.execute(
            select(
                func.unnest(KTChatMessage.retrieved_doc_ids).label("doc_id"),
                func.count().label("cnt"),
            )
            .where(KTChatMessage.retrieved_doc_ids.overlap(doc_ids))
            .group_by(func.unnest(KTChatMessage.retrieved_doc_ids))
        )
        query_counts = {r.doc_id: r.cnt for r in msgs.fetchall()}

    return [
        {
            "doc_id": d.id,
            "title": d.title,
            "status": d.status,
            "quality_score": d.quality_score,
            "endorsement_count": d.endorsement_count,
            "word_count": d.word_count,
            "query_count": query_counts.get(d.id, 0),
            "created_at": d.created_at,
            "ingested_at": d.ingested_at,
        }
        for d in docs
    ]



@router.get("/insights/project/{project_id}")
async def project_insights(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Mentor+ sees project-level analytics."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    p = await _get_project_or_404(project_id, org_id, db)

    total = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(KTDocument.project_id == project_id)
        )
        or 0
    )
    ingested = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.project_id == project_id,
                KTDocument.status == DocStatusEnum.INGESTED,
            )
        )
        or 0
    )
    approved = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.project_id == project_id,
                KTDocument.status.in_([DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]),
            )
        )
        or 0
    )
    pending = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.project_id == project_id,
                KTDocument.status == DocStatusEnum.SUBMITTED,
            )
        )
        or 0
    )
    quality_avg = await db.scalar(
        select(func.avg(KTDocument.quality_score)).where(
            KTDocument.project_id == project_id
        )
    )
    contributors = (
        await db.scalar(
            select(func.count(distinct(KTDocument.author_id))).where(
                KTDocument.project_id == project_id
            )
        )
        or 0
    )

    # Knowledge gaps for this project
    gaps_result = await db.execute(
        select(KTUnansweredQuery.query_text, KTUnansweredQuery.occurrence_count)
        .where(
            KTUnansweredQuery.company_id == p.company_id,
            KTUnansweredQuery.project_ids.contains([project_id]),
            KTUnansweredQuery.resolved.is_(False),
        )
        .order_by(KTUnansweredQuery.occurrence_count.desc())
        .limit(10)
    )
    gaps = [
        {"query": r.query_text, "count": r.occurrence_count}
        for r in gaps_result.fetchall()
    ]

    return {
        "project_id": project_id,
        "project_name": p.name,
        "company_id": p.company_id,
        "total_docs": total,
        "approved_docs": approved,
        "ingested_docs": ingested,
        "pending_docs": pending,
        "quality_avg": round(float(quality_avg), 1) if quality_avg else None,
        "contributor_count": contributors,
        "top_queried_topics": gaps,
        "unanswered_count": len(gaps),
        "last_activity_at": p.last_doc_at,
    }



@router.get("/insights/group")
async def group_insights(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """GroupAdmin sees analytics for their group's memberTs' documents."""
    _require_group_admin_plus(current_user)
    org_id = int(current_user["organization_id"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
    group_id = current_user.get("group_id")

    if role == "GroupAdmin" and not group_id:
        raise HTTPException(400, "Group admin has no group assigned")

    # Get projects for this group
    proj_q = select(KTProject.id, KTProject.name, KTProject.company_id).where(
        KTProject.organization_id == org_id
    )
    if role == "GroupAdmin":
        proj_q = proj_q.where(KTProject.group_id == group_id)

    proj_result = await db.execute(proj_q)
    projects = proj_result.fetchall()
    proj_ids = [p.id for p in projects]

    if not proj_ids:
        return {"projects": [], "total_docs": 0, "contributors": 0}

    total_docs = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(KTDocument.project_id.in_(proj_ids))
        )
        or 0
    )
    ingested = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.project_id.in_(proj_ids),
                KTDocument.status == DocStatusEnum.INGESTED,
            )
        )
        or 0
    )
    contributors = (
        await db.scalar(
            select(func.count(distinct(KTDocument.author_id))).where(
                KTDocument.project_id.in_(proj_ids)
            )
        )
        or 0
    )

    # Per-project stats
    project_stats = []
    for proj in projects:
        pdocs = (
            await db.scalar(
                select(func.count(KTDocument.id)).where(
                    KTDocument.project_id == proj.id
                )
            )
            or 0
        )
        pingested = (
            await db.scalar(
                select(func.count(KTDocument.id)).where(
                    KTDocument.project_id == proj.id,
                    KTDocument.status == DocStatusEnum.INGESTED,
                )
            )
            or 0
        )
        project_stats.append(
            {
                "project_id": proj.id,
                "project_name": proj.name,
                "total_docs": pdocs,
                "ingested_docs": pingested,
                "coverage": "high"
                if pingested >= 5
                else "medium"
                if pingested >= 2
                else "low",
            }
        )

    # Top contributors
    contrib_result = await db.execute(
        select(KTDocument.author_id, func.count(KTDocument.id).label("cnt"))
        .where(KTDocument.project_id.in_(proj_ids))
        .group_by(KTDocument.author_id)
        .order_by(func.count(KTDocument.id).desc())
        .limit(10)
    )
    top_contributors = []
    for row in contrib_result.fetchall():
        u = await db.get(User, row.author_id) if row.author_id else None
        top_contributors.append(
            {
                "user_id": row.author_id,
                "name": u.full_name if u else "Unknown",
                "doc_count": row.cnt,
            }
        )

    return {
        "total_docs": total_docs,
        "ingested_docs": ingested,
        "contributors": contributors,
        "project_coverage": project_stats,
        "top_contributors": top_contributors,
    }



@router.get("/insights/company")
async def company_insights(
    company_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Mentor+ sees all companies' analytics in the org. GroupAdmin sees only their group's traction."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
    group_id_filter = current_user.get("group_id") if role == "GroupAdmin" else None

    q_comp = select(KTCompany).where(KTCompany.organization_id == org_id)
    if company_id:
        q_comp = q_comp.where(KTCompany.id == company_id)
    companies_result = await db.execute(q_comp)
    companies = companies_result.scalars().all()

    result = []
    for company in companies:
        proj_q = select(KTProject.id).where(
            KTProject.company_id == company.id,
            KTProject.organization_id == org_id,
        )
        if group_id_filter:
            proj_q = proj_q.where(KTProject.group_id == group_id_filter)

        proj_res = await db.execute(proj_q)
        proj_ids = [r[0] for r in proj_res.fetchall()]

        if not proj_ids and group_id_filter:
            continue  # Skip companies where group has no projects

        doc_filter = KTDocument.company_id == company.id
        if group_id_filter:
            doc_filter = and_(doc_filter, KTDocument.project_id.in_(proj_ids))

        total = (
            await db.scalar(select(func.count(KTDocument.id)).where(doc_filter)) or 0
        )
        ingested = (
            await db.scalar(
                select(func.count(KTDocument.id)).where(
                    doc_filter, KTDocument.status == DocStatusEnum.INGESTED
                )
            )
            or 0
        )

        gap_filter = KTUnansweredQuery.company_id == company.id
        if group_id_filter:
            gap_filter = and_(
                gap_filter, KTUnansweredQuery.project_ids.overlap(proj_ids)
            )

        gaps = (
            await db.scalar(
                select(func.count(KTUnansweredQuery.id)).where(
                    gap_filter,
                    KTUnansweredQuery.resolved.is_(False),
                )
            )
            or 0
        )
        contributors = (
            await db.scalar(
                select(func.count(distinct(KTDocument.author_id))).where(doc_filter)
            )
            or 0
        )

        result.append(
            {
                "company_id": company.id,
                "company_name": company.name,
                "total_projects": len(proj_ids),
                "total_docs": total,
                "ingested_docs": ingested,
                "knowledge_gaps": gaps,
                "contributors": contributors,
                "health_estimate": round(min(100, (ingested / max(total, 1)) * 100), 1),
            }
        )

    return result



@router.get("/insights/summary")
async def org_insights_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Aggregated organizational analytics for Admin/Mentor views."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])

    # 1. PostgreSQL Aggregations
    total_docs = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.organization_id == org_id
            )
        )
        or 0
    )
    ingested_docs = (
        await db.scalar(
            select(func.count(KTDocument.id)).where(
                KTDocument.organization_id == org_id,
                KTDocument.status == DocStatusEnum.INGESTED,
            )
        )
        or 0
    )
    total_projects = (
        await db.scalar(
            select(func.count(KTProject.id)).where(KTProject.organization_id == org_id)
        )
        or 0
    )
    total_users = (
        await db.scalar(
            select(func.count(distinct(KTDocument.author_id))).where(
                KTDocument.organization_id == org_id
            )
        )
        or 0
    )

    # 2. Activity (last 30 days)
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    activity_res = await db.execute(
        select(
            func.date(KTDocument.created_at).label("date"),
            func.count(KTDocument.id).label("count"),
        )
        .where(
            KTDocument.organization_id == org_id,
            KTDocument.created_at >= thirty_days_ago,
        )
        .group_by(func.date(KTDocument.created_at))
        .order_by(func.date(KTDocument.created_at))
    )
    activity = [
        {"date": str(r.date), "count": r.count} for r in activity_res.fetchall()
    ]

    # 3. Knowledge-store stats (relational, Phase 6 — was Neo4j)
    from modules.kt.services.graph_service import graph_counts

    _counts = await graph_counts(db, organization_id=org_id)
    total_episodes = _counts["total_episodes"]
    total_entities = _counts["total_entities"]

    # 4. Health Metrics (Calculated)
    coverage = (ingested_docs / max(total_docs, 1)) * 100

    # Knowledge Gaps (Unanswered)
    gaps_res = await db.execute(
        select(
            KTUnansweredQuery.query_text,
            KTUnansweredQuery.occurrence_count,
            KTUnansweredQuery.last_asked_at,
        )
        .where(KTUnansweredQuery.resolved.is_(False))
        .order_by(KTUnansweredQuery.occurrence_count.desc())
        .limit(10)
    )
    gaps = [
        {
            "query_text": r.query_text,
            "occurrence_count": r.occurrence_count,
            "last_seen": r.last_asked_at.isoformat(),
        }
        for r in gaps_res.fetchall()
    ]

    return {
        "doc_count": total_docs,
        "ingested_count": ingested_docs,
        "project_count": total_projects,
        "user_count": total_users,
        "overall_health": round(coverage, 1),
        "activity_last_30d": activity,
        "gaps": gaps,
        "graph": {"episodes": total_episodes, "entities": total_entities},
        "metrics": {
            "coverage_health": round(coverage, 1),
            "freshness_health": 85,
            "depth_health": min(100, (total_episodes / max(total_docs * 5, 1)) * 100),
            "engagement_health": min(100, (total_entities / 100) * 100),
            "collaboration_health": 90,
            "handoff_health": 65,
        },
    }



@router.get("/insights/gaps")
async def knowledge_gaps(
    company_id: Optional[str] = None,
    departing_user_id: Optional[int] = None,
    resolved: bool = False,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    # Allowed for all authenticated users to encourage contributions
    org_id = int(current_user["organization_id"])

    q = select(KTUnansweredQuery).where(
        KTUnansweredQuery.organization_id == org_id,
        KTUnansweredQuery.resolved == resolved,
    )
    if company_id:
        q = q.where(KTUnansweredQuery.company_id == company_id)
    if departing_user_id:
        # In this context, we just return general gaps for now
        # but we could filter by projects the user was in.
        pass

    total = await db.scalar(select(func.count()).select_from(q.subquery()))
    result = await db.execute(
        q.order_by(KTUnansweredQuery.occurrence_count.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    gaps = result.scalars().all()
    return {
        "items": [
            {
                "id": g.id,
                "query_text": g.query_text,
                "occurrence_count": g.occurrence_count,
                "project_ids": g.project_ids,
                "first_asked_at": g.first_asked_at,
                "last_asked_at": g.last_asked_at,
                "resolved": g.resolved,
            }
            for g in gaps
        ],
        "total": total,
        "page": page,
        "pages": math.ceil((total or 0) / size),
    }



@router.patch("/insights/gaps/{gap_id}/resolve")
async def resolve_gap(
    gap_id: str,
    doc_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    gap = await db.get(KTUnansweredQuery, gap_id)
    if not gap or gap.organization_id != org_id:
        raise HTTPException(404, "Gap not found")
    gap.resolved = True
    gap.resolved_by_doc_id = doc_id
    gap.resolved_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Resolved"}


# ════════════════════════════════════════════════════════════════════════════
# GRAPH EXPLORER
# ════════════════════════════════════════════════════════════════════════════



@router.get("/explorer/graph")
async def explore_graph(
    project_ids: List[str] = Query(..., alias="project_ids"),
    company_id: Optional[str] = None,
    x_kt_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token),
):
    """
    Explore the knowledge graph.
    Supports both JWT (internal) and Access Key (external).
    """
    # Scope comes from the caller's grants, never from the query string. The old
    # code set `resolved_project_ids = project_ids` and then "verified" project_ids
    # against itself, so the check always passed.
    resolved_company_id, resolved_project_ids, _, _ = await _resolve_retrieval_scope(
        db,
        current_user,
        x_kt_key,
        requested_project_ids=project_ids,
        requested_company_id=company_id,
    )

    import json

    # Sort project ids for deterministic cache key
    sorted_pids = sorted(project_ids) if project_ids else []
    redis_key = f"kt:graph:explore:{resolved_company_id}:{','.join(sorted_pids)}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    from modules.kt.services.graph_service import get_graph_explorer_data

    data = await get_graph_explorer_data(
        db, str(resolved_company_id) if resolved_company_id else "", project_ids
    )

    try:
        await redis_client.set(redis_key, json.dumps(data), ex=3600)
    except Exception:
        pass

    return data



@router.get("/explorer/graph/{node_id}/neighborhood")
async def explore_graph_neighborhood(
    node_id: str,
    x_kt_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token_optional),
):
    if not current_user and not x_kt_key:
        raise HTTPException(401, "Authentication required")

    import json

    redis_key = f"kt:graph:neighborhood:{node_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    try:
        from modules.kt.services.graph_service import get_graph_neighborhood

        data = await get_graph_neighborhood(db, node_id)
        try:
            await redis_client.set(redis_key, json.dumps(data), ex=3600)
        except Exception:
            pass
        return data
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(500, str(e))



@router.get("/explorer/timeline")
async def knowledge_timeline(
    project_ids: List[str] = Query(..., alias="project_ids"),
    company_id: Optional[str] = None,
    x_kt_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[dict] = Depends(verify_token),
):
    """
    Get a timeline of knowledge events.
    Supports both JWT (internal) and Access Key (external).
    """
    # Scope comes from the caller's grants, never from the query string (see
    # _resolve_retrieval_scope — this endpoint had the same self-referential check
    # as /explorer/graph).
    resolved_company_id, resolved_project_ids, _, _ = await _resolve_retrieval_scope(
        db,
        current_user,
        x_kt_key,
        requested_project_ids=project_ids,
        requested_company_id=company_id,
    )

    import json

    from cache_manager import redis_client

    pids_hash = "-".join(sorted(project_ids))
    redis_key = f"kt:timeline:{resolved_company_id}:{pids_hash}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    from modules.kt.services.graph_service import get_timeline

    data = await get_timeline(
        db, str(resolved_company_id) if resolved_company_id else "", project_ids
    )

    try:
        await redis_client.set(redis_key, json.dumps(data), ex=3600)
    except Exception:
        pass

    return data



@router.get("/explorer/stats")
async def graph_stats(
    company_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    if not company_id:
        res = await db.execute(
            select(KTCompany).where(KTCompany.organization_id == org_id)
        )
        c = res.scalars().first()
        if not c:
            raise HTTPException(404, "No company found")
        company_id = c.id

    company = await db.get(KTCompany, company_id)
    if not company or company.organization_id != org_id:
        raise HTTPException(404, "Company not found")

    import json

    redis_key = f"kt:graph:stats:{company_id}"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass

    from modules.kt.services.graph_service import graph_counts

    stats_res = await graph_counts(db, company_id=company_id)

    try:
        await redis_client.set(redis_key, json.dumps(stats_res), ex=3600)
    except Exception:
        pass

    return stats_res


# ════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ════════════════════════════════════════════════════════════════════════════



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


# ════════════════════════════════════════════════════════════════════════════
# HANDOFF
# ════════════════════════════════════════════════════════════════════════════

DEFAULT_CHECKLIST = [
    {"item": "Document active project architectures", "done": False, "required": True},
    {"item": "Document deployment + CI/CD runbooks", "done": False, "required": True},
    {"item": "Document all third-party integrations", "done": False, "required": True},
    {"item": "Document database schemas + migrations", "done": False, "required": True},
    {
        "item": "Document environment variables + secrets locations",
        "done": False,
        "required": True,
    },
    {"item": "Document known bugs + workarounds", "done": False, "required": False},
    {"item": "Introduce successor to stakeholders", "done": False, "required": True},
    {"item": "Transfer all credentials + access", "done": False, "required": True},
    {
        "item": "Review open tickets + handoff ownership",
        "done": False,
        "required": True,
    },
    {"item": "Mentor sign-off", "done": False, "required": True},
]



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


from services.redis_service import redis_client  # noqa: E402



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

