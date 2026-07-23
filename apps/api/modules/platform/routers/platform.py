"""Platform Admin governance — the top tier above L&D Admin.

Owns organization approval/suspension and the AI cost/utilization dashboard.
All endpoints require the Platform Super Admin (seeded meet.jain563@gmail.com).
Plain `def` endpoints run in FastAPI's threadpool (safe with the sync session).
"""
import datetime
import secrets

import models
from auth_utils import require_platform_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services import email_service
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/platform", tags=["platform_admin"])

ONBOARD_BASE_URL_ENV = "APP_URL"


def _org_out(o: models.Organization) -> dict:
    return {
        "id": o.id,
        "name": o.name,
        "slug": o.slug,
        "status": o.status,
        "contact_name": o.contact_name,
        "contact_email": o.contact_email,
        "brand_name": o.brand_name or o.name,
        "logo_url": o.logo_url,
        "subscription_tier": o.subscription_tier,
        "onboarded_at": o.onboarded_at.isoformat() if o.onboarded_at else None,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


@router.get("/organizations")
def list_organizations(
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    q = db.query(models.Organization)
    if status:
        q = q.filter(models.Organization.status == status)
    orgs = q.order_by(models.Organization.created_at.desc()).all()
    return {"organizations": [_org_out(o) for o in orgs]}


def _set_customer_status(org, new_status: str, db: Session) -> None:
    """Apply a lifecycle change to the whole CUSTOMER, not just one business unit.

    Suspending is a commercial action against the paying customer
    (SuperOrganization), so it must reach every Organization beneath it —
    otherwise a suspended customer keeps working through a sibling unit.
    """
    org.status = new_status
    org.is_active = new_status == "approved"

    super_id = getattr(org, "super_organization_id", None)
    if super_id is None:
        return

    super_org = (
        db.query(models.SuperOrganization)
        .filter(models.SuperOrganization.id == super_id)
        .first()
    )
    if super_org:
        super_org.status = new_status
        super_org.is_active = new_status == "approved"

    for sibling in (
        db.query(models.Organization)
        .filter(models.Organization.super_organization_id == super_id)
        .all()
    ):
        sibling.status = new_status
        sibling.is_active = new_status == "approved"


@router.post("/organizations/{org_id}/approve")
def approve_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    """Approve a pending org and email the contact a one-time onboarding link."""
    import os

    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")

    _set_customer_status(org, "approved", db)
    org.onboarding_token = secrets.token_urlsafe(32)
    db.commit()

    base = (os.environ.get(ONBOARD_BASE_URL_ENV) or "http://localhost:3000").rstrip("/")
    onboard_url = f"{base}/onboard?token={org.onboarding_token}"
    try:
        if org.contact_email:
            email_service._send(
                org.contact_email,
                "Your StudyBuddy workspace is approved 🎉",
                f"<p>Hi {org.contact_name or 'there'},</p>"
                f"<p>Your organization <b>{org.name}</b> has been approved on StudyBuddy.</p>"
                f'<p><a href="{onboard_url}">Click here to finish onboarding</a> — '
                f"you'll set up your L&amp;D Admin account, upload your logo and signature.</p>"
                f"<p>— Powered by StudyBuddy</p>",
            )
    except Exception:
        pass  # email failure must not block approval; link is returned below

    return {"status": "approved", "onboarding_url": onboard_url}


@router.post("/organizations/{org_id}/suspend")
def suspend_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    _set_customer_status(org, "suspended", db)
    db.commit()
    return {"status": "suspended"}


@router.post("/organizations/{org_id}/reactivate")
def reactivate_organization(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
    if not org:
        raise HTTPException(404, "Organization not found")
    _set_customer_status(org, "approved", db)
    db.commit()
    return {"status": "approved"}


@router.get("/ai-usage")
def ai_usage_dashboard(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    """Per-org and per-feature AI cost/utilization over the last `days` days."""
    since = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    U = models.AIUsage

    def _rows(group_col):
        return (
            db.query(
                group_col.label("key"),
                func.count(U.id).label("calls"),
                func.coalesce(func.sum(U.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(U.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(U.est_cost_usd), 0.0).label("cost_usd"),
            )
            .filter(U.created_at >= since)
            .group_by(group_col)
            .all()
        )

    org_names = {o.id: (o.brand_name or o.name) for o in db.query(models.Organization).all()}
    by_org = [
        {
            "organization_id": r.key,
            "organization": org_names.get(r.key, "Unattributed" if r.key is None else str(r.key)),
            "calls": r.calls,
            "input_tokens": int(r.input_tokens),
            "output_tokens": int(r.output_tokens),
            "cost_usd": round(float(r.cost_usd), 4),
        }
        for r in _rows(U.organization_id)
    ]
    by_feature = [
        {
            "feature": r.key,
            "calls": r.calls,
            "cost_usd": round(float(r.cost_usd), 4),
        }
        for r in _rows(U.feature)
    ]
    totals = (
        db.query(
            func.count(U.id),
            func.coalesce(func.sum(U.est_cost_usd), 0.0),
        )
        .filter(U.created_at >= since)
        .first()
    )
    return {
        "window_days": days,
        "total_calls": totals[0] or 0,
        "total_cost_usd": round(float(totals[1] or 0.0), 4),
        "by_organization": sorted(by_org, key=lambda x: -x["cost_usd"]),
        "by_feature": sorted(by_feature, key=lambda x: -x["cost_usd"]),
    }


class PlatformStats(BaseModel):
    total_orgs: int
    pending: int
    approved: int
    suspended: int


@router.get("/stats", response_model=PlatformStats)
def platform_stats(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_platform_admin),
):
    def _count(status=None):
        q = db.query(func.count(models.Organization.id))
        if status:
            q = q.filter(models.Organization.status == status)
        return q.scalar() or 0

    return PlatformStats(
        total_orgs=_count(),
        pending=_count("pending"),
        approved=_count("approved"),
        suspended=_count("suspended"),
    )
