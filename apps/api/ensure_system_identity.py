"""Idempotent system-identity + seed bootstrap.

Runs on every app startup (main.on_startup) AND on a full reset
(scripts/reset_and_seed.py). Everything here is idempotent and env-driven:

  APP_ADMIN_EMAIL / APP_ADMIN_PASSWORD  -> Platform Admin (owns /platform)
  LD_ADMIN_EMAIL  / LD_ADMIN_PASSWORD   -> L&D Admin for the seed organization
  SEED_ORG_NAME   / SEED_ORG_SLUG       -> the default organization

So whenever the database is initialized from zero, the two operator accounts
exist with the configured credentials and the seed org hierarchy is in place.
"""

import bcrypt

import models
from database import SessionLocal


def _hash(pw: str) -> str:
    # bcrypt caps at 72 bytes; encode+truncate matches the login path.
    return bcrypt.hashpw(pw.encode()[:72], bcrypt.gensalt()).decode()


def _ensure_system_group_and_user(db) -> None:
    group = db.query(models.Group).filter(models.Group.id == 0).first()
    if not group:
        db.add(models.Group(id=0, name="System Registry", is_active=True))
        db.commit()
        print("✅ System Group (ID 0) created.")

    user = db.query(models.User).filter(models.User.id == 0).first()
    if not user:
        db.add(
            models.User(
                id=0,
                email="system@studyhub.ai",
                full_name="System Admin",
                group_id=0,
                role="LDAdmin",
                is_active=True,
                custom_slug="admin",
                bio="Master System Architect of the Sigmoid Intelligence Ecosystem.",
                expertise_json={
                    "skills": ["System Governance", "AI Orchestration", "Rapid Provisioning"]
                },
            )
        )
        db.commit()
        print("✅ System Admin (ID 0) created.")
    elif not user.custom_slug:
        user.custom_slug = "admin"
        db.commit()


def _ensure_hierarchy(db, settings):
    """Ensure SuperOrg -> Org -> Dept -> Vertical -> Batch and align Group 0.

    Returns (org, dept). Idempotent by org slug. Content scoping
    (`assert_same_super_org`) requires org.super_organization_id to be set, so a
    SuperOrganization is created and linked here.
    """
    org = (
        db.query(models.Organization)
        .filter(models.Organization.slug == settings.SEED_ORG_SLUG)
        .first()
    )
    if not org:
        org = models.Organization(
            name=settings.SEED_ORG_NAME, slug=settings.SEED_ORG_SLUG
        )
        db.add(org)
        db.commit()
        db.refresh(org)
        print(f"🏛️ Seed org created: {org.name}")

    # SuperOrganization link (required for shared-content scoping).
    if getattr(org, "super_organization_id", None) is None:
        super_org = db.query(models.SuperOrganization).first()
        if not super_org:
            super_org = models.SuperOrganization(
                name=f"{settings.SEED_ORG_NAME} Enterprise",
                slug=f"{settings.SEED_ORG_SLUG}-enterprise",
                status="active",
            )
            db.add(super_org)
            db.commit()
            db.refresh(super_org)
        org.super_organization_id = super_org.id
        db.commit()

    dept = (
        db.query(models.Department)
        .filter(models.Department.organization_id == org.id)
        .first()
    )
    if not dept:
        dept = models.Department(
            name="DataOps", organization_id=org.id, description="Default sector"
        )
        db.add(dept)
        db.commit()
        db.refresh(dept)

    vert = (
        db.query(models.Vertical)
        .filter(models.Vertical.department_id == dept.id)
        .first()
    )
    if not vert:
        vert = models.Vertical(name="AI Core", department_id=dept.id)
        db.add(vert)
        db.commit()
        db.refresh(vert)

    batch = (
        db.query(models.Batch).filter(models.Batch.vertical_id == vert.id).first()
    )
    if not batch:
        batch = models.Batch(name="Genesis", vertical_id=vert.id)
        db.add(batch)
        db.commit()
        db.refresh(batch)

    # Align System Group 0 into the hierarchy so org resolution works.
    group = db.query(models.Group).filter(models.Group.id == 0).first()
    if group and (group.department_id != dept.id or group.batch_id != batch.id):
        group.batch_id = batch.id
        group.vertical_id = vert.id
        group.department_id = dept.id
        db.commit()

    return org, dept


def _enforce_admin(db, *, email, password, role, org=None, dept=None) -> None:
    """Create-or-enforce an operator account with the configured credentials."""
    if not email or not password:
        print(f"⚠️ {role} email/password unset — skipping seed.")
        return
    user = db.query(models.User).filter(models.User.email == email).first()
    org_id = org.id if org is not None else None
    dept_id = dept.id if dept is not None else None
    if not user:
        db.add(
            models.User(
                email=email,
                full_name=f"{'Platform' if role == 'PlatformAdmin' else 'L&D'} Admin",
                group_id=0,
                organization_id=org_id,
                department_id=dept_id,
                role=role,
                is_active=True,
                password_hash=_hash(password),
            )
        )
        db.commit()
        print(f"✅ {role} seeded: {email}")
        return

    # Enforce role, org attribution, and credentials.
    changed = False
    if user.role != role:
        user.role = role
        changed = True
    if org_id is not None and getattr(user, "organization_id", None) != org_id:
        user.organization_id = org_id
        changed = True
    if dept_id is not None and getattr(user, "department_id", None) != dept_id:
        user.department_id = dept_id
        changed = True
    if not user.password_hash or not bcrypt.checkpw(
        password.encode()[:72], user.password_hash.encode()
    ):
        user.password_hash = _hash(password)
        changed = True
    if changed:
        db.commit()
        print(f"✅ {role} enforced: {email}")


def ensure_system(db=None):
    should_close = db is None
    if db is None:
        db = SessionLocal()
    try:
        from config import settings

        print("🔍 Ensuring system identity + seed operators...")
        _ensure_system_group_and_user(db)
        org, dept = _ensure_hierarchy(db, settings)

        # Platform Admin — org-less by design (get_user_jwt_payload exempts it).
        _enforce_admin(
            db,
            email=settings.APP_ADMIN_EMAIL,
            password=settings.APP_ADMIN_PASSWORD,
            role="PlatformAdmin",
        )
        # L&D Admin — owns the seed organization.
        _enforce_admin(
            db,
            email=settings.LD_ADMIN_EMAIL,
            password=settings.LD_ADMIN_PASSWORD,
            role="LDAdmin",
            org=org,
            dept=dept,
        )
        print("✨ System identity + seed operators stabilized.")
    except Exception as e:
        print(f"❌ Error in ensure_system: {e}")
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    ensure_system()
