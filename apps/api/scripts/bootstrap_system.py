import os
import sys

# Unified Path Logic: Ensure apps/api and root are reachable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from dotenv import load_dotenv  # noqa: E402

ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

from database import Base, SessionLocal, engine  # noqa: E402
from ensure_system_identity import ensure_system  # noqa: E402


def bootstrap():
    print("🚀 StudyBuddy V3 | Enterprise Infrastructure Bootstrap")
    print("──────────────────────────────────────────────────")

    # 1. Initialize Schema
    print("📦 Provisioning Database Schema...")
    try:
        # Import all models to ensure they are registered with Base
        import models
        from sqlalchemy import inspect

        Base.metadata.create_all(bind=engine)
        inspector = inspect(engine)
        print(f"✅ Schema provisioned. Tables: {inspector.get_table_names()}")
    except Exception as e:
        print(f"❌ Schema provisioning failed: {e}")
        return

    # 2. Ensure System Identity
    ensure_system()

    # 3. Seed Standard Organizational Hierarchy
    db = SessionLocal()
    try:
        print("🏛️ Seeding Standard Organizational Hierarchy...")

        # Org: Sigmoid HQ
        org = db.query(models.Organization).filter_by(slug="sigmoid-hq").first()
        if not org:
            org = models.Organization(name="Sigmoid HQ", slug="sigmoid-hq")
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"  + Org: {org.name}")

        # Dept: DataOps
        dept = (
            db.query(models.Department)
            .filter_by(name="DataOps", organization_id=org.id)
            .first()
        )
        if not dept:
            dept = models.Department(
                name="DataOps",
                organization_id=org.id,
                description="Data Engineering & Operations",
            )
            db.add(dept)
            db.commit()
            db.refresh(dept)
            print(f"  + Dept: {dept.name}")

        # Vertical: AI Core
        vert = (
            db.query(models.Vertical)
            .filter_by(name="AI Core", department_id=dept.id)
            .first()
        )
        if not vert:
            vert = models.Vertical(name="AI Core", department_id=dept.id)
            db.add(vert)
            db.commit()
            db.refresh(vert)
            print(f"  + Vertical: {vert.name}")

        # Batch: Engineering 2024
        batch = (
            db.query(models.Batch)
            .filter_by(name="Engineering 2024", vertical_id=vert.id)
            .first()
        )
        if not batch:
            batch = models.Batch(name="Engineering 2024", vertical_id=vert.id)
            db.add(batch)
            db.commit()
            db.refresh(batch)
            print(f"  + Batch: {batch.name}")

        # Group: Team Delta
        group = (
            db.query(models.Group)
            .filter_by(name="Team Delta", batch_id=batch.id)
            .first()
        )
        if not group:
            group = models.Group(
                name="Team Delta", batch_id=batch.id, password_pattern="delta@<name>"
            )
            db.add(group)
            db.commit()
            db.refresh(group)
            print(f"  + Group: {group.name}")

        # 4. Register Background Workers (Tasks)
        print("🤖 Registering Automation Workers...")
        tasks_to_register = [
            "generate_daily_challenges",
            "send_daily_challenge_notifications",
            "send_deadline_reminders",
            "auto_lock_assignments",
            "maintain_streaks",
            "send_weekly_digest",
            "process_reengagement_lifecycle",
            "cleanup_stale_data",
            "calculate_global_intel",
            "sync_s3_resources",
        ]

        for task_name in tasks_to_register:
            task = (
                db.query(models.SystemTaskStatus).filter_by(task_name=task_name).first()
            )
            if not task:
                task = models.SystemTaskStatus(
                    task_name=task_name, last_status="STANDBY", run_count=0
                )
                db.add(task)
                print(f"  + Registered Task: {task_name}")

        db.commit()

        # 5. Purge Stale Cache (Strategic Freshness)
        print("🧹 Purging Stale Cache...")
        try:
            import asyncio

            from scripts.clear_cache import clear_redis

            asyncio.run(clear_redis())
        except Exception as e:
            print(f"⚠️ Cache purge skipped: {e}")

        print("✅ Infrastructure Seeded and Standardized.")

    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        db.rollback()
    finally:
        db.close()

    print("──────────────────────────────────────────────────")
    print("✨ StudyBuddy V3 is now Production-Ready.")


if __name__ == "__main__":
    bootstrap()
