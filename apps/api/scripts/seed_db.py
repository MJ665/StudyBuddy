import os
import sys

# Unified Path Logic: Ensure apps/api and root are reachable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)

import os  # noqa: E402
import sys  # noqa: E402

from dotenv import load_dotenv  # noqa: E402

# Load env before importing database
env_path = os.path.join(ROOT_DIR, ".env")
load_dotenv(env_path)


from database import SessionLocal  # noqa: E402
from models.auth import Group, MentorGroupAssignment, User  # noqa: E402
from models.org import Batch, Department, Organization, Vertical  # noqa: E402


def seed():
    db = SessionLocal()
    try:
        # Create Org
        org = db.query(Organization).filter_by(slug="sigmoid-hq").first()
        if not org:
            org = Organization(name="Sigmoid HQ", slug="sigmoid-hq")
            db.add(org)
            db.commit()
            db.refresh(org)

        # Create Dept
        dept = db.query(Department).filter_by(name="Engineering").first()
        if not dept:
            dept = Department(
                organization_id=org.id, name="Engineering", description="Eng Dept"
            )
            db.add(dept)
            db.commit()
            db.refresh(dept)

        # Create Vertical
        vert = db.query(Vertical).filter_by(name="Data Engineering").first()
        if not vert:
            vert = Vertical(department_id=dept.id, name="Data Engineering")
            db.add(vert)
            db.commit()
            db.refresh(vert)

        # Create Batch
        batch = db.query(Batch).filter_by(name="Batch 2026").first()
        if not batch:
            batch = Batch(vertical_id=vert.id, name="Batch 2026")
            db.add(batch)
            db.commit()
            db.refresh(batch)

        # Create Group
        grp = db.query(Group).filter_by(name="Alphas").first()
        if not grp:
            grp = Group(batch_id=batch.id, name="Alphas", password_pattern="alpha_pass")
            db.add(grp)
            db.commit()
            db.refresh(grp)

        grp2 = db.query(Group).filter_by(name="LD_Admin_Group").first()
        if not grp2:
            grp2 = Group(
                batch_id=batch.id, name="LD_Admin_Group", password_pattern="admin_pass"
            )
            db.add(grp2)
            db.commit()
            db.refresh(grp2)

        # Create Users
        ld_admin = db.query(User).filter_by(email="ldadmin@sigmoid.com").first()
        if not ld_admin:
            ld_admin = User(
                email="ldadmin@sigmoid.com",
                full_name="L&D Admin",
                group_id=grp2.id,
                role="LDAdmin",
            )
            db.add(ld_admin)

        mentor = db.query(User).filter_by(email="mentor@sigmoid.com").first()
        if not mentor:
            mentor = User(
                email="mentor@sigmoid.com",
                full_name="Mentor User",
                group_id=grp2.id,
                role="Mentor",
            )
            db.add(mentor)

        group_admin = db.query(User).filter_by(email="grpadmin@sigmoid.com").first()
        if not group_admin:
            group_admin = User(
                email="grpadmin@sigmoid.com",
                full_name="Group Admin",
                group_id=grp.id,
                role="GroupAdmin",
            )
            db.add(group_admin)

        member = db.query(User).filter_by(email="member@sigmoid.com").first()
        if not member:
            member = User(
                email="member@sigmoid.com",
                full_name="Member User",
                group_id=grp.id,
                role="Member",
            )
            db.add(member)

        db.commit()

        # Mentor Assignment
        if mentor:
            assignment = (
                db.query(MentorGroupAssignment)
                .filter_by(mentor_id=mentor.id, group_id=grp.id)
                .first()
            )
            if not assignment:
                assignment = MentorGroupAssignment(mentor_id=mentor.id, group_id=grp.id)
                db.add(assignment)
                db.commit()

        print("Database seeded successfully with roles and hierarchy!")
    except Exception as e:
        print(f"Error seeding DB: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
