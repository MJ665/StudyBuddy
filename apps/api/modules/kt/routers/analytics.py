"""analytics endpoints (moved verbatim from modules/kt/routers/insights.py)."""
from fastapi import APIRouter

from modules.kt.routers.insights_shared import *  # noqa: F401,F403

router = APIRouter()

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
