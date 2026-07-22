"""
KT projects and membership
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()

@router.post("/projects", response_model=KTProjectOut)
async def create_project(
    body: KTProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_role(current_user, "Member", "Mentor", "GroupAdmin", "LDAdmin", "Owner")
    org_id = int(current_user["organization_id"])
    user_id = int(current_user["sub"])

    if not body.company_id:
        # 1. Try to find an active company
        res = await db.execute(
            select(KTCompany).where(
                KTCompany.organization_id == org_id, KTCompany.is_active == True
            )
        )
        company = res.scalars().first()

        # 2. If no active, try any company for this org
        if not company:
            res = await db.execute(
                select(KTCompany).where(KTCompany.organization_id == org_id)
            )
            company = res.scalars().first()

        # 3. If still none, create a default company for this organization
        if not company:
            company = KTCompany(
                organization_id=org_id, name="Primary Knowledge Entity", is_active=True
            )
            db.add(company)
            await db.flush()  # Get ID without committing entire transaction yet

        body.company_id = company.id
    else:
        company = await db.get(KTCompany, body.company_id)
        if not company or company.organization_id != org_id:
            raise HTTPException(404, "Company not found")

    p = KTProject(
        company_id=body.company_id,
        organization_id=org_id,
        group_id=body.group_id,
        name=body.name,
        description=body.description,
        client_name=body.client_name,
        tech_stack=body.tech_stack or [],
    )
    db.add(p)
    await db.commit()
    await db.refresh(p)

    # Auto-add creator as member
    db.add(KTProjectMember(user_id=user_id, project_id=p.id, role_in_project="lead"))
    await db.commit()

    # Eagerly load members and their user details for the response model to avoid MissingGreenlet error
    res = await db.execute(
        select(KTProject)
        .options(selectinload(KTProject.members).selectinload(KTProjectMember.user))
        .where(KTProject.id == p.id)
    )
    return res.scalars().first()



@router.get("/projects", response_model=List[KTProjectOut])
async def list_projects(
    company_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    _db_user_res = await db.execute(
        select(User.role).where(User.id == int(current_user["sub"]))
    )
    role = _db_user_res.scalar_one_or_none() or current_user.get("role", "Member")
    uid = int(current_user["sub"])

    q = (
        select(KTProject)
        .where(
            KTProject.organization_id == org_id,
            KTProject.status == "active",
        )
        .options(selectinload(KTProject.members).selectinload(KTProjectMember.user))
    )
    if company_id:
        q = q.where(KTProject.company_id == company_id)

    # Authors only see projects they're members of
    if role not in ["Mentor", "GroupAdmin", "LDAdmin", "Owner"]:
        q = q.join(KTProjectMember, KTProject.id == KTProjectMember.project_id).where(
            KTProjectMember.user_id == uid
        )
    # GroupAdmin sees only their group's projects
    elif role == "GroupAdmin":
        group_id = current_user.get("group_id")
        if group_id:
            q = q.where(KTProject.group_id == group_id)

    result = await db.execute(q)
    return result.scalars().all()



@router.get("/projects/{project_id}", response_model=KTProjectOut)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    return await _get_project_or_404(project_id, org_id, db)



@router.patch("/projects/{project_id}", response_model=KTProjectOut)
async def update_project(
    project_id: str,
    body: KTProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    p = await _get_project_or_404(project_id, org_id, db)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(p, k, v)
    await db.commit()
    return p



@router.post("/projects/{project_id}/members")
async def add_project_member(
    project_id: str,
    user_id: int,
    role_in_project: str = "member",
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    await _get_project_or_404(project_id, org_id, db)
    m = KTProjectMember(
        user_id=user_id, project_id=project_id, role_in_project=role_in_project
    )
    db.add(m)
    try:
        await db.commit()
    except Exception:
        raise HTTPException(409, "User is already a member")
    return {"message": "Member added"}


# ════════════════════════════════════════════════════════════════════════════
# CO-AUTHOR PICKER (users must exist in DB)
# ════════════════════════════════════════════════════════════════════════════



