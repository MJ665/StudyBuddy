import json
import logging

import models
import schemas
from auth_utils import (
    caller_org_id,
    is_platform_admin,
    require_ldadmin,
    scope_to_org,
    verify_token,
)
from cache_manager import cache_manager, redis_client
from database import get_async_db
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from services.audit_service import log_admin_action_async
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

router = APIRouter(prefix="/org", tags=["organization"])
logger = logging.getLogger(__name__)


# --- Schemas ---
class OrgCreate(BaseModel):
    name: str
    slug: str


class DeptCreate(BaseModel):
    name: str
    description: str = ""


class VerticalCreate(BaseModel):
    name: str
    description: str = ""


class BatchCreate(BaseModel):
    name: str
    description: str = ""


class GroupCreate(BaseModel):
    name: str
    batch_id: int


async def _invalidate_org_caches() -> None:
    """Purge every cache namespace that embeds the org hierarchy."""
    for key in ("org_tree", "org", "global_stats"):
        await cache_manager.invalidate(key)
    try:
        await redis_client.delete("org:tree:data")
    except Exception as e:  # pragma: no cover - cache purge is best-effort
        logger.warning(f"Failed to purge org tree cache: {e}")


# --- Routes ---
@router.post("")
async def create_org(
    data: OrgCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    org = models.Organization(name=data.name, slug=data.slug)
    db.add(org)
    await db.commit()
    await db.refresh(org)
    await _invalidate_org_caches()

    await log_admin_action_async(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_ORG",
        resource_type="ORG",
        resource_id=org.id,
        details={"name": data.name, "slug": data.slug},
    )

    return org


@router.get("/organizations")
async def get_orgs(
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """List organizations visible to the caller.

    Previously UNAUTHENTICATED: any anonymous caller received every customer's
    name and slug — a customer-list disclosure in a multi-tenant product.
    """
    try:
        stmt = select(models.Organization).where(
            models.Organization.is_active.is_(True)
        )
        if not is_platform_admin(current_user):
            org_id = caller_org_id(current_user)
            if org_id is None:
                return []
            stmt = stmt.where(models.Organization.id == org_id)
        result = await db.execute(stmt)
        orgs = result.scalars().all()
        return [{"id": o.id, "name": o.name, "slug": o.slug} for o in orgs]
    except Exception as e:
        logger.error(f"Error fetching organizations: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Database error while fetching organizations: {str(e)}",
        )


@router.get("/tree")
async def get_org_tree(
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Enriched tree view for the LDAdmin dashboard."""
    redis_key = "org:tree:data"
    try:
        cached = await redis_client.get(redis_key)
        if cached:
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"Redis cache lookup failed for org tree: {e}")

    # Eager-load the whole hierarchy: async sessions raise MissingGreenlet on
    # implicit lazy loads, so every level traversed below must be loaded up front.
    result = await db.execute(
        select(models.Organization)
        .where(models.Organization.is_active.is_(True))
        .options(
            selectinload(models.Organization.departments)
            .selectinload(models.Department.verticals)
            .selectinload(models.Vertical.batches)
            .selectinload(models.Batch.groups)
        )
    )
    orgs = result.scalars().unique().all()

    tree = []
    for org in orgs:
        o_dict = {"id": org.id, "name": org.name, "slug": org.slug, "departments": []}
        for dept in org.departments:
            if not dept.is_active:
                continue
            d_dict = {"id": dept.id, "name": dept.name, "verticals": []}
            for vert in dept.verticals:
                if not vert.is_active:
                    continue
                v_dict = {"id": vert.id, "name": vert.name, "batches": []}
                for batch in vert.batches:
                    b_dict = {"id": batch.id, "name": batch.name, "groups": []}
                    for group in batch.groups:
                        if not group.is_active:
                            continue
                        b_dict["groups"].append({"id": group.id, "name": group.name})
                    v_dict["batches"].append(b_dict)
                d_dict["verticals"].append(v_dict)
            o_dict["departments"].append(d_dict)
        tree.append(o_dict)

    try:
        await redis_client.set(redis_key, json.dumps(tree), ex=3600)
    except Exception as e:
        logger.warning(f"Redis cache write failed for org tree: {e}")

    return tree


@router.post("/{org_id}/departments")
async def create_dept(
    org_id: int,
    data: DeptCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    dept = models.Department(
        organization_id=org_id, name=data.name, description=data.description
    )
    db.add(dept)
    await db.commit()
    await db.refresh(dept)
    await _invalidate_org_caches()

    await log_admin_action_async(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_DEPT",
        resource_type="DEPT",
        resource_id=dept.id,
        details={"name": data.name, "org_id": org_id},
    )

    return dept


@router.get("/departments")
async def get_depts(
    organization_id: int = Query(None, alias="organization_id"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Was unauthenticated and unscoped — leaked every customer's departments."""
    stmt = select(models.Department).where(models.Department.is_active.is_(True))
    stmt = scope_to_org(stmt, models.Department, current_user)
    if organization_id:
        stmt = stmt.where(models.Department.organization_id == organization_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/departments/{dept_id}/verticals")
async def create_vertical(
    dept_id: int,
    data: VerticalCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    vert = models.Vertical(
        department_id=dept_id, name=data.name, description=data.description
    )
    db.add(vert)
    await db.commit()
    await db.refresh(vert)
    await _invalidate_org_caches()

    await log_admin_action_async(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_VERTICAL",
        resource_type="VERTICAL",
        resource_id=vert.id,
        details={"name": data.name, "dept_id": dept_id},
    )

    return vert


@router.get("/verticals")
async def get_verticals(
    department_id: int = Query(None, alias="department_id"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Was unauthenticated. Verticals carry no org column, so they are scoped
    through their parent department."""
    stmt = (
        select(models.Vertical)
        .join(models.Department, models.Vertical.department_id == models.Department.id)
        .where(models.Vertical.is_active.is_(True))
    )
    stmt = scope_to_org(stmt, models.Department, current_user)
    if department_id:
        stmt = stmt.where(models.Vertical.department_id == department_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/verticals/{vert_id}/batches")
async def create_batch(
    vert_id: int,
    data: BatchCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    batch = models.Batch(
        vertical_id=vert_id, name=data.name, description=data.description
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    await _invalidate_org_caches()

    await log_admin_action_async(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_BATCH",
        resource_type="BATCH",
        resource_id=batch.id,
        details={"name": data.name, "vert_id": vert_id},
    )

    return batch


@router.get("/batches")
async def get_batches(
    vertical_id: int = Query(None, alias="vertical_id"),
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(verify_token),
):
    """Was unauthenticated. Batches are scoped through vertical -> department."""
    stmt = (
        select(models.Batch)
        .join(models.Vertical, models.Batch.vertical_id == models.Vertical.id)
        .join(models.Department, models.Vertical.department_id == models.Department.id)
    )
    stmt = scope_to_org(stmt, models.Department, current_user)
    if vertical_id:
        stmt = stmt.where(models.Batch.vertical_id == vertical_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/groups")
async def create_group(
    data: GroupCreate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    batch = await db.get(models.Batch, data.batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    vert = await db.get(models.Vertical, batch.vertical_id)

    new_group = models.Group(
        name=data.name,
        batch_id=data.batch_id,
        vertical_id=batch.vertical_id,
        department_id=vert.department_id if vert else None,
    )
    db.add(new_group)
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        if isinstance(e, IntegrityError):
            raise HTTPException(
                status_code=409,
                detail=f"A group with name '{data.name}' already exists in this sector.",
            )
        raise e
    await db.refresh(new_group)
    await _invalidate_org_caches()

    await log_admin_action_async(
        db=db,
        actor_id=int(current_user["sub"]),
        actor_role=current_user["role"],
        action="CREATE_GROUP",
        resource_type="GROUP",
        resource_id=new_group.id,
        details={"name": data.name, "batch_id": data.batch_id},
    )

    return new_group


# ─── Hierarchy Lifecycle Management (Full CRUD) ─────────────────────────────


async def _patch(db: AsyncSession, model, obj_id: int, updates) -> object:
    """Shared update path for every hierarchy level."""
    obj = await db.get(model, obj_id)
    if not obj:
        raise HTTPException(status_code=404)
    for k, v in updates.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await _invalidate_org_caches()
    return obj


async def _remove(db: AsyncSession, model, obj_id: int) -> dict:
    """Shared delete path for every hierarchy level.

    Deleting a hierarchy node fans out through `cascade="all, delete-orphan"`
    (dept→vertical→batch→group) *and* through un-cascaded one-to-manys that
    SQLAlchemy must load to NULL out (Group.users/mentor_assignments/resources,
    Vertical.vertical_courses). Those loads are implicit, so issuing the delete
    directly on the AsyncSession would raise MissingGreenlet. `run_sync` hands
    the ORM a real greenlet context, preserving today's exact cascade semantics
    without a hand-maintained eager-load map that would silently rot whenever a
    new relationship is added.
    """

    def _delete(sync_session) -> bool:
        obj = sync_session.get(model, obj_id)
        if obj is None:
            return False
        sync_session.delete(obj)
        sync_session.flush()
        return True

    found = await db.run_sync(_delete)
    if not found:
        raise HTTPException(status_code=404)
    await db.commit()
    await _invalidate_org_caches()
    return {"success": True}


@router.patch("/{org_id}")
async def update_org(
    org_id: int,
    updates: schemas.OrganizationUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _patch(db, models.Organization, org_id, updates)


@router.delete("/{org_id}")
async def delete_org(
    org_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _remove(db, models.Organization, org_id)


@router.patch("/departments/{dept_id}")
async def update_dept(
    dept_id: int,
    updates: schemas.DepartmentUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _patch(db, models.Department, dept_id, updates)


@router.delete("/departments/{dept_id}")
async def delete_dept(
    dept_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _remove(db, models.Department, dept_id)


@router.patch("/verticals/{vert_id}")
async def update_vertical(
    vert_id: int,
    updates: schemas.VerticalUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _patch(db, models.Vertical, vert_id, updates)


@router.delete("/verticals/{vert_id}")
async def delete_vertical(
    vert_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _remove(db, models.Vertical, vert_id)


@router.patch("/batches/{batch_id}")
async def update_batch(
    batch_id: int,
    updates: schemas.BatchUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _patch(db, models.Batch, batch_id, updates)


@router.delete("/batches/{batch_id}")
async def delete_batch(
    batch_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _remove(db, models.Batch, batch_id)


@router.patch("/groups/{group_id}")
async def update_group(
    group_id: int,
    updates: schemas.GroupUpdate,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _patch(db, models.Group, group_id, updates)


@router.delete("/groups/{group_id}")
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: dict = Depends(require_ldadmin),
):
    return await _remove(db, models.Group, group_id)
