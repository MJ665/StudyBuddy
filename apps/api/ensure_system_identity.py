import models
from database import SessionLocal


def ensure_system(db=None):
    if db is None:
        db = SessionLocal()
        should_close = True
    else:
        should_close = False
    try:
        print("🔍 Checking System Identity (ID 0)...")

        # 1. Ensure Group 0 exists
        group = db.query(models.Group).filter(models.Group.id == 0).first()
        if not group:
            print("🚀 Creating System Group (ID 0)...")
            system_group = models.Group(
                id=0,
                name="System Registry",
                password_pattern="<name>@sigmoid",
                is_active=True,
            )
            db.add(system_group)
            db.commit()
            print("✅ System Group created.")
        else:
            print("✅ System Group exists.")

        # 2. Ensure User 0 exists
        user = db.query(models.User).filter(models.User.id == 0).first()
        if not user:
            print("🚀 Creating System Admin (ID 0)...")
            system_admin = models.User(
                id=0,
                email="system@studyhub.ai",
                full_name="System Admin",
                group_id=0,
                role="LDAdmin",
                is_active=True,
                custom_slug="admin",
                bio="Master System Architect of the Sigmoid Intelligence Ecosystem.",
                expertise_json={
                    "skills": [
                        "System Governance",
                        "AI Orchestration",
                        "Rapid Provisioning",
                    ]
                },
            )
            db.add(system_admin)
            db.commit()
            print("✅ System Admin created with tactical profile.")
        else:
            print("✅ System Admin exists.")
            if not user.custom_slug:
                user.custom_slug = "admin"
                user.bio = (
                    "Master System Architect of the Sigmoid Intelligence Ecosystem."
                )
                user.expertise_json = {
                    "skills": [
                        "System Governance",
                        "AI Orchestration",
                        "Rapid Provisioning",
                    ]
                }
                db.commit()
                print("✅ System Admin profile backfilled.")

        # 2b. Ensure Platform Super Admin (top of hierarchy, owns /platform).
        # ONE credential source: settings.APP_ADMIN_PASSWORD — the same value
        # /auth/superadmin/login verifies. (Previously this hardcoded a
        # literal password that drifted from the env value, so the operator
        # had two different credentials for the same identity.)
        from config import settings as _settings

        PLATFORM_EMAIL = "meet.jain563@gmail.com"
        _admin_pw = (_settings.APP_ADMIN_PASSWORD or "").encode()
        padmin = (
            db.query(models.User)
            .filter(models.User.email == PLATFORM_EMAIL)
            .first()
        )
        if not _admin_pw:
            print("⚠️ APP_ADMIN_PASSWORD unset — skipping Platform Admin seeding.")
        elif not padmin:
            import bcrypt as _bcrypt

            pw_hash = _bcrypt.hashpw(_admin_pw, _bcrypt.gensalt()).decode()
            padmin = models.User(
                email=PLATFORM_EMAIL,
                full_name="Platform Admin",
                group_id=0,
                role="PlatformAdmin",
                is_active=True,
                password_hash=pw_hash,
            )
            db.add(padmin)
            db.commit()
            print("✅ Platform Super Admin seeded.")
        else:
            # Enforce the designated role AND env-sourced credentials (this
            # email may already exist as an L&D Admin).
            import bcrypt as _bcrypt

            changed = False
            if padmin.role != "PlatformAdmin":
                padmin.role = "PlatformAdmin"
                changed = True
            if not padmin.password_hash or not _bcrypt.checkpw(
                _admin_pw, padmin.password_hash.encode()
            ):
                padmin.password_hash = _bcrypt.hashpw(
                    _admin_pw, _bcrypt.gensalt()
                ).decode()
                changed = True
            if changed:
                db.commit()
                print("✅ Platform Super Admin role/credentials enforced.")

        # 3. STEALTH RECOVERY: Seed Default Org if Registry is Empty
        org_count = db.query(models.Organization).count()
        if org_count == 0:
            print("🏛️ Zero State Detected: Provisioning Stealth Hierarchy...")

            # Default Org
            org = models.Organization(name="Sigmoid HQ", slug="sigmoid-hq")
            db.add(org)
            db.commit()
            db.refresh(org)

            # Default Dept
            dept = models.Department(
                name="DataOps",
                organization_id=org.id,
                description="Default Intelligence Sector",
            )
            db.add(dept)
            db.commit()
            db.refresh(dept)

            # Default Vertical
            vert = models.Vertical(name="AI Core", department_id=dept.id)
            db.add(vert)
            db.commit()
            db.refresh(vert)

            # Default Batch
            batch = models.Batch(name="Genesis 2024", vertical_id=vert.id)
            db.add(batch)
            db.commit()
            db.refresh(batch)

            # Update System Group with Hierarchical Alignment
            group = db.query(models.Group).filter(models.Group.id == 0).first()
            if group:
                group.batch_id = batch.id
                group.vertical_id = vert.id
                group.department_id = dept.id
                db.commit()

            print(
                f"✅ Stealth Hierarchy Provisioned: {org.name} -> {dept.name} -> {vert.name}"
            )

        print("✨ System Identity Protocol Stabilized.")
    except Exception as e:
        print(f"❌ Error setting up system identity: {e}")
        db.rollback()
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    ensure_system()
