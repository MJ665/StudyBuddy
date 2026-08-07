"""
Team Transition / Handoff engine.

Flow: a mentor/L&D initiates a handoff (departing → receiving, optional mentor)
→ a gap audit of the departing user's authored docs drives a checklist
(defaults + one item per missing doc type) → progress is tracked as items are
checked → once every required item is done the handoff moves to
``awaiting_signoff`` → the mentor/L&D signs off → ``completed``. Accounts are
never deleted by this flow.
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403
# DEFAULT_CHECKLIST lives in the insights_shared module; import it explicitly
# (star-import from _shared does not carry it, which previously made
# initiate_handoff raise NameError at call time).
from modules.kt.routers.insights_shared import DEFAULT_CHECKLIST

router = APIRouter()

EXPECTED_DOC_TYPES = {
    "runbook": "Runbook",
    "architecture_decision": "Architecture Decision",
    "deployment_guide": "Deployment Guide",
    "design_doc": "Design Doc",
    "post_mortem": "Post-mortem",
}


async def _gap_analysis(db: AsyncSession, departing_user_id: int, company_id: str, org_id: int) -> dict:
    rows = (
        await db.execute(
            select(KTDocument.doc_type).where(
                KTDocument.author_id == departing_user_id,
                KTDocument.status.in_([DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]),
                KTDocument.company_id == company_id,
            )
        )
    ).fetchall()
    covered = {r[0] for r in rows}
    missing = [k for k in EXPECTED_DOC_TYPES if k not in covered]
    return {
        "documented_count": len(rows),
        "covered_doc_types": sorted(covered),
        "missing_doc_types": missing,
        "risk_level": "HIGH" if len(missing) >= 3 else "MEDIUM" if missing else "LOW",
    }


def _build_checklist(gap: dict) -> list:
    """Default checklist + one gap-driven item per missing doc type."""
    checklist = [dict(item) for item in DEFAULT_CHECKLIST]
    for key in gap.get("missing_doc_types", []):
        label = EXPECTED_DOC_TYPES.get(key, key.replace("_", " ").title())
        checklist.insert(
            0,
            {"item": f"Document the missing {label}", "done": False, "required": True},
        )
    return checklist


def _progress(checklist) -> float:
    items = checklist or []
    total = len(items)
    done = sum(1 for i in items if i.get("done"))
    return round((done / total * 100) if total else 0.0, 1)


async def _name(db: AsyncSession, uid) -> str | None:
    if not uid:
        return None
    u = await db.get(User, uid)
    return (u.full_name or u.email) if u else None


async def _serialize(db: AsyncSession, h: KTHandoff) -> dict:
    return {
        "id": h.id,
        "company_id": h.company_id,
        "handoff_type": h.handoff_type,
        "status": h.status,
        "departure_date": h.departure_date.isoformat() if h.departure_date else None,
        "departing_user_id": h.departing_user_id,
        "receiving_user_id": h.receiving_user_id,
        "mentor_id": h.mentor_id,
        "departing_user_name": await _name(db, h.departing_user_id),
        "receiving_user_name": await _name(db, h.receiving_user_id),
        "mentor_name": await _name(db, h.mentor_id),
        "checklist": h.checklist or [],
        "gap_analysis": h.gap_analysis or {},
        "notes": h.notes,
        "progress": _progress(h.checklist),
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "completed_at": h.completed_at.isoformat() if h.completed_at else None,
    }


@router.post("/handoffs")
async def initiate_handoff(
    body: KTHandoffInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    departing = await db.get(User, body.departing_user_id)
    if not departing:
        raise HTTPException(404, "Departing user not found")

    gap = await _gap_analysis(db, body.departing_user_id, body.company_id, org_id)
    handoff = KTHandoff(
        company_id=body.company_id,
        organization_id=org_id,
        departing_user_id=body.departing_user_id,
        receiving_user_id=body.receiving_user_id,
        mentor_id=body.mentor_id or uid,
        departure_date=body.departure_date,
        handoff_type=body.handoff_type,
        checklist=_build_checklist(gap),
        gap_analysis=gap,
        notes=body.notes,
        status="in_progress",
    )
    db.add(handoff)
    await _audit(
        db,
        org_id,
        AuditActionEnum.HANDOFF_INITIATED,
        user_id=uid,
        resource_type="handoff",
        resource_id=str(body.departing_user_id),
    )
    await db.commit()
    await db.refresh(handoff)
    return await _serialize(db, handoff)


@router.get("/handoffs")
async def list_handoffs(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """List all handoffs for the org. Mentor+ only."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    # Scope by the handoff's own organization_id — NOT via a join to KTProject
    # (project_id is optional and usually null, which previously dropped every
    # initiated handoff from this list).
    result = await db.execute(
        select(KTHandoff)
        .where(KTHandoff.organization_id == org_id)
        .order_by(KTHandoff.created_at.desc())
    )
    handoffs = result.scalars().all()
    return [await _serialize(db, h) for h in handoffs]


@router.get("/handoffs/analyze")
async def analyze_handoff_pre(
    departing_user_id: int,
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    gap = await _gap_analysis(db, departing_user_id, company_id, org_id)
    gaps = [
        f"Missing {EXPECTED_DOC_TYPES.get(m, m.replace('_', ' ').title())}"
        for m in gap["missing_doc_types"]
    ]
    return {
        "gaps": gaps,
        "attrition_risk": gap["risk_level"],
        "documented_count": gap["documented_count"],
    }


@router.get("/handoffs/{handoff_id}")
async def get_handoff(
    handoff_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Get a specific handoff detail. Mentor+ only."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    h = await db.get(KTHandoff, handoff_id)
    if not h or h.organization_id != org_id:
        raise HTTPException(404, "Handoff not found")
    return await _serialize(db, h)


@router.patch("/handoffs/{handoff_id}/checklist")
async def update_handoff_checklist(
    handoff_id: str,
    item_index: int,
    done: bool,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])
    h = await db.get(KTHandoff, handoff_id)
    if not h or h.organization_id != org_id:
        raise HTTPException(404, "Handoff not found")
    if h.status == "completed":
        raise HTTPException(400, "Handoff is already completed")

    checklist = list(h.checklist or [])
    if not (0 <= item_index < len(checklist)):
        raise HTTPException(400, "Invalid checklist item index")
    checklist[item_index] = dict(checklist[item_index])
    checklist[item_index]["done"] = done
    if done:
        checklist[item_index]["completed_at"] = datetime.now(timezone.utc).isoformat()
    else:
        checklist[item_index].pop("completed_at", None)
    h.checklist = checklist

    # All required items done → ready for the mentor's sign-off (an explicit
    # act, not auto-completion).
    required_done = all(i.get("done") for i in checklist if i.get("required"))
    if required_done and h.status != "completed":
        h.status = "awaiting_signoff"
    elif not required_done and h.status == "awaiting_signoff":
        h.status = "in_progress"

    await db.commit()
    return {
        "handoff_id": handoff_id,
        "status": h.status,
        "progress": _progress(checklist),
    }


@router.post("/handoffs/{handoff_id}/signoff")
async def signoff_handoff(
    handoff_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """Mentor / L&D sign-off that finalizes a handoff. Requires every required
    checklist item to be done first."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    h = await db.get(KTHandoff, handoff_id)
    if not h or h.organization_id != org_id:
        raise HTTPException(404, "Handoff not found")
    if h.status == "completed":
        return await _serialize(db, h)

    checklist = list(h.checklist or [])
    if not all(i.get("done") for i in checklist if i.get("required")):
        raise HTTPException(
            400, "All required checklist items must be completed before sign-off."
        )

    h.status = "completed"
    h.completed_at = datetime.now(timezone.utc)
    await _audit(
        db,
        org_id,
        AuditActionEnum.HANDOFF_COMPLETED,
        user_id=int(current_user["sub"]),
        resource_type="handoff",
        resource_id=handoff_id,
    )
    await db.commit()
    await db.refresh(h)
    return await _serialize(db, h)
