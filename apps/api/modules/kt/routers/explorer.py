"""explorer endpoints (moved verbatim from modules/kt/routers/insights.py)."""
from fastapi import APIRouter

from modules.kt.routers.insights_shared import *  # noqa: F401,F403

router = APIRouter()

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
