import os
import sys

# Unified Path Logic: Ensure apps/api and root are reachable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)

import os  # noqa: E402
import sys  # noqa: E402

import models  # noqa: E402
from database import SessionLocal  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402


def seed():
    db: Session = SessionLocal()
    try:
        # Check if Sigmoid HQ exists
        org = (
            db.query(models.Organization)
            .filter(models.Organization.slug == "sigmoid-hq")
            .first()
        )
        if not org:
            print("Seeding Sigmoid HQ...")
            org = models.Organization(name="Sigmoid HQ", slug="sigmoid-hq")
            db.add(org)
            db.commit()
            db.refresh(org)

            dept = models.Department(organization_id=org.id, name="Engineering")
            db.add(dept)
            db.commit()
            db.refresh(dept)

            vert = models.Vertical(department_id=dept.id, name="DataOps")
            db.add(vert)
            db.commit()
            db.refresh(vert)

            batch = models.Batch(vertical_id=vert.id, name="Spring 2026")
            db.add(batch)
            db.commit()
            db.refresh(batch)

            print(
                f"Seed complete: Org({org.id}), Dept({dept.id}), Vert({vert.id}), Batch({batch.id})"
            )
        else:
            print("Sigmoid HQ already exists.")

        # Ensure at least one Group exists linked to Batch
        batch = db.query(models.Batch).first()
        if (
            batch
            and not db.query(models.Group)
            .filter(models.Group.batch_id == batch.id)
            .first()
        ):
            print(f"Seeding default group for batch {batch.id}...")
            group = models.Group(
                name="Mavericks", batch_id=batch.id, password_pattern="<name>@123"
            )
            db.add(group)
            db.commit()
            print("Default group created.")

    except Exception as e:
        print(f"Error seeding: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    seed()
