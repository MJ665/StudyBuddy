"""
Handoff endpoints
"""

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from modules.kt.routers._shared import *  # noqa: F401, F403

router = APIRouter()

@router.post("/handoffs")
async def initiate_handoff(
    body: KTHandoffInitiateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    uid = int(current_user["sub"])

    # Gap analysis using Gemini
    departing = await db.get(User, body.departing_user_id)
    if not departing:
        raise HTTPException(404, "Departing user not found")

    authored_docs = await db.execute(
        select(KTDocument.title, KTDocument.doc_type).where(
            KTDocument.author_id == body.departing_user_id,
            KTDocument.status.in_([DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]),
            KTDocument.company_id == body.company_id,
        )
    )
    doc_rows = authored_docs.fetchall()
    covered_types = list({r.doc_type for r in doc_rows})
    expected = {"runbook", "architecture_decision", "deployment_guide"}
    missing = expected - set(covered_types)

    gap_analysis = {
        "documented_count": len(doc_rows),
        "covered_doc_types": covered_types,
        "missing_doc_types": list(missing),
        "risk_level": "HIGH" if len(missing) >= 2 else "MEDIUM" if missing else "LOW",
    }

    handoff = KTHandoff(
        company_id=body.company_id,
        organization_id=org_id,
        departing_user_id=body.departing_user_id,
        receiving_user_id=body.receiving_user_id,
        mentor_id=body.mentor_id or uid,
        departure_date=body.departure_date,
        handoff_type=body.handoff_type,
        checklist=DEFAULT_CHECKLIST.copy(),
        gap_analysis=gap_analysis,
        notes=body.notes,
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
    return handoff



@router.get("/handoffs")
async def list_handoffs(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    """List all handoffs for the org. Mentor+ only."""
    _require_mentor_plus(current_user)
    org_id = int(current_user["organization_id"])
    result = await db.execute(
        select(KTHandoff)
        .join(KTProject, KTHandoff.project_id == KTProject.id)
        .where(KTProject.organization_id == org_id)
        .order_by(KTHandoff.created_at.desc())
    )
    return result.scalars().all()



@router.get("/handoffs/analyze")
async def analyze_handoff_pre(
    departing_user_id: int,
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user_with_db_role),
):
    org_id = int(current_user["organization_id"])

    # Simple gap analysis: check if user has documented core artifacts
    authored_docs = await db.execute(
        select(KTDocument.doc_type).where(
            KTDocument.author_id == departing_user_id,
            KTDocument.status.in_([DocStatusEnum.APPROVED, DocStatusEnum.INGESTED]),
            KTDocument.company_id == company_id,
            KTDocument.organization_id == org_id,
        )
    )
    covered_types = {r[0] for r in authored_docs.fetchall()}
    expected = {
        "runbook",
        "architecture_decision",
        "deployment_guide",
        "design_doc",
        "post_mortem",
    }
    missing = expected - covered_types

    # Map missing to friendly strings for the UI
    gaps = [f"Missing {m.replace('_', ' ').title()}" for m in missing]

    return {
        "gaps": gaps,
        "attrition_risk": "MEDIUM" if len(missing) > 1 else "LOW",
        "documented_count": len(covered_types),
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
    return h



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

    checklist = list(h.checklist)
    if 0 <= item_index < len(checklist):
        checklist[item_index]["done"] = done
        if done:
            checklist[item_index]["completed_at"] = datetime.now(
                timezone.utc
            ).isoformat()
    h.checklist = checklist

    total = len(checklist)
    done_count = sum(1 for item in checklist if item.get("done"))
    h.knowledge_transfer_score = round((done_count / total * 100) if total else 0, 1)

    req_done = all(item.get("done") for item in checklist if item.get("required"))
    if req_done and h.knowledge_transfer_score >= 80:
        h.status = "completed"
        h.completed_at = datetime.now(timezone.utc)
        await _audit(
            db,
            org_id,
            AuditActionEnum.HANDOFF_COMPLETED,
            user_id=int(current_user["sub"]),
            resource_id=handoff_id,
        )

    await db.commit()
    return {
        "handoff_id": handoff_id,
        "status": h.status,
        "knowledge_transfer_score": h.knowledge_transfer_score,
    }


# ════════════════════════════════════════════════════════════════════════════
# ONBOARDING BUNDLE
# ════════════════════════════════════════════════════════════════════════════



