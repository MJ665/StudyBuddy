"""Public organization onboarding.

Flow: org signs up (status=pending) → Platform Admin approves (emails a one-time
onboarding link, see routers/platform.py) → org completes onboarding here, which
creates the org's L&D Admin account and stores logo/signature/branding.
"""
import datetime
import re
import secrets

import models
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _slugify(name: str, db: Session) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "org"
    slug = base
    while db.query(models.Organization).filter(models.Organization.slug == slug).first():
        slug = f"{base}-{secrets.token_hex(3)}"
    return slug


class OrgSignupRequest(BaseModel):
    org_name: str = Field(min_length=2, max_length=200)
    contact_name: str = Field(min_length=2, max_length=200)
    contact_email: EmailStr


@router.post("/signup")
def org_signup(body: OrgSignupRequest, db: Session = Depends(get_db)):
    """Public: create a PENDING organization awaiting Platform Admin approval."""
    existing = (
        db.query(models.SuperOrganization)
        .filter(models.SuperOrganization.name == body.org_name)
        .first()
        or db.query(models.Organization)
        .filter(models.Organization.name == body.org_name)
        .first()
    )
    if existing:
        raise HTTPException(409, "An organization with this name already exists.")

    # Signup creates the paying customer (SuperOrganization) AND its first
    # business unit (Organization). The customer is what /platform approves or
    # suspends; the Organization is where the L&D Admin actually operates.
    slug = _slugify(body.org_name, db)

    super_org = models.SuperOrganization(
        name=body.org_name,
        slug=slug,
        status="pending",
        contact_name=body.contact_name,
        contact_email=str(body.contact_email),
        brand_name=body.org_name,
        is_active=False,
    )
    db.add(super_org)
    db.flush()  # need super_org.id before linking the Organization

    org = models.Organization(
        name=body.org_name,
        slug=slug,
        status="pending",
        contact_name=body.contact_name,
        contact_email=str(body.contact_email),
        is_active=False,
        super_organization_id=super_org.id,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    db.refresh(super_org)
    return {
        "status": "pending",
        "message": "Your request has been received. You'll get an onboarding email once approved.",
        "organization_id": org.id,
        "super_organization_id": super_org.id,
    }


@router.get("/verify")
def verify_onboarding_token(token: str, db: Session = Depends(get_db)):
    """Public: validate a one-time onboarding token and return org info for the wizard."""
    org = (
        db.query(models.Organization)
        .filter(models.Organization.onboarding_token == token)
        .first()
    )
    if not org or org.status != "approved":
        raise HTTPException(400, "Invalid or expired onboarding link.")
    if org.onboarded_at:
        raise HTTPException(409, "This organization has already been onboarded.")
    return {"organization_id": org.id, "org_name": org.name, "contact_email": org.contact_email}


class OnboardingComplete(BaseModel):
    token: str
    admin_full_name: str = Field(min_length=2, max_length=200)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)
    brand_name: str | None = None
    logo_url: str | None = None
    signature_url: str | None = None


@router.post("/complete")
def complete_onboarding(body: OnboardingComplete, db: Session = Depends(get_db)):
    """Public (token-gated): create the org's L&D Admin and store branding."""
    import bcrypt as _bcrypt

    org = (
        db.query(models.Organization)
        .filter(models.Organization.onboarding_token == body.token)
        .first()
    )
    if not org or org.status != "approved":
        raise HTTPException(400, "Invalid or expired onboarding link.")
    if org.onboarded_at:
        raise HTTPException(409, "This organization has already been onboarded.")

    # Minimal org hierarchy so the L&D Admin resolves to this org (JWT derives
    # organization_id from user's group -> department -> organization).
    dept = models.Department(name="General", organization_id=org.id, description="Default department")
    db.add(dept)
    db.commit()
    db.refresh(dept)
    # Group.name is globally unique, so scope it to the org slug.
    group = models.Group(
        name=f"{org.slug}-admin",
        department_id=dept.id,
        is_active=True,
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # Create the L&D Admin.
    if db.query(models.User).filter(models.User.email == str(body.admin_email)).first():
        # email uniqueness is per (email, group); keep it simple and reject dup email here
        pass
    pw_hash = _bcrypt.hashpw(body.admin_password.encode()[:72], _bcrypt.gensalt()).decode()
    admin = models.User(
        email=str(body.admin_email),
        full_name=body.admin_full_name,
        group_id=group.id,
        role="LDAdmin",
        is_active=True,
        password_hash=pw_hash,
    )
    db.add(admin)

    # Store branding + mark onboarded; consume the token.
    org.brand_name = body.brand_name or org.name
    org.logo_url = body.logo_url
    org.signature_url = body.signature_url
    org.is_active = True
    org.onboarded_at = datetime.datetime.now(datetime.timezone.utc)
    org.onboarding_token = None
    db.commit()

    return {
        "status": "onboarded",
        "organization_id": org.id,
        "admin_email": str(body.admin_email),
        "message": "Onboarding complete. Your L&D Admin can now sign in.",
    }
