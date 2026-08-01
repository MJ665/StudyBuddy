"""Phase 1 provisioning: pgvector extension, new tables, OrgUnit backfill.

Idempotent and strictly ADDITIVE — safe to re-run. It never alters or deletes
legacy tables/rows (the configured DATABASE_URL is production Neon).

What it does:
1. CREATE EXTENSION IF NOT EXISTS vector
2. Create org_units / user_org_roles / kt_document_chunks (checkfirst)
3. Backfill the OrgUnit tree from organizations→departments→verticals→
   batches→groups, stamping legacy_table/legacy_id (unique) so re-runs no-op.
4. Compute materialized path/depth for every unit.
5. Backfill user_org_roles from users.role (primary group membership),
   user_roles (scoped roles on group/vertical), and mentor_group_assignments.

Run:  cd apps/api && .venv/bin/python scripts/phase1_provision.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

import models  # noqa: F401 — registers every table on Base.metadata
from database import Base, SessionLocal, engine
from models import (
    Batch,
    Department,
    Group,
    MentorGroupAssignment,
    Organization,
    User,
    UserRole,
    Vertical,
)
from modules.org.models import OrgUnit, UserOrgRole
from shared.constants import OrgUnitType

NEW_TABLES = ["org_units", "user_org_roles", "kt_document_chunks"]


def provision_schema() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Group-pattern login retired (2026-07-23): patterns are no longer
        # written, so the legacy NOT NULL constraint must go. Idempotent.
        conn.execute(
            text("ALTER TABLE groups ALTER COLUMN password_pattern DROP NOT NULL")
        )
        # password_reset_tokens.expires_at must be timestamptz — the asyncpg
        # forgot-password path writes tz-aware datetimes. Conditional (only
        # converts when the column is still naive), so reruns are no-ops.
        conn.execute(text("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'password_reset_tokens'
                      AND column_name = 'expires_at'
                      AND data_type = 'timestamp without time zone'
                ) THEN
                    ALTER TABLE password_reset_tokens
                        ALTER COLUMN expires_at TYPE TIMESTAMPTZ
                        USING expires_at AT TIME ZONE 'UTC';
                END IF;
            END $$;
        """))
        # Email is now a GLOBAL unique identity (was unique per (email, group_id)).
        # 1) Anonymize any duplicate emails (keep the lowest id — the canonical
        #    account, e.g. the Platform Admin), so the unique index can be added.
        # 2) Swap uq_user_email_group → uq_user_email. All idempotent.
        conn.execute(text("""
            UPDATE users u
            SET email = 'dup-' || u.id || '-' || u.email, is_active = false
            WHERE EXISTS (
                SELECT 1 FROM users k
                WHERE lower(k.email) = lower(u.email) AND k.id < u.id
            );
        """))
        # kt_ingestion_jobs.created_at — the ingestion-status endpoint orders by
        # it; the column was missing from the table. Idempotent.
        conn.execute(text(
            "ALTER TABLE kt_ingestion_jobs ADD COLUMN IF NOT EXISTS "
            "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ))
        # Multi-session chat threads carry a user-facing title (ChatGPT-style).
        conn.execute(text(
            "ALTER TABLE kt_chat_sessions ADD COLUMN IF NOT EXISTS title VARCHAR(200)"
        ))
        # Exams carry the internal-user recipients emailed + notified on publish.
        conn.execute(text(
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS recipient_emails "
            "VARCHAR[] NOT NULL DEFAULT '{}'::varchar[]"
        ))
        # Assignments record their creator's user id (per-creator ownership checks).
        conn.execute(text(
            "ALTER TABLE assignments ADD COLUMN IF NOT EXISTS created_by INTEGER"
        ))
        # Discussion upvotes are a per-user toggle (voter_ids), not a raw counter.
        conn.execute(text(
            "ALTER TABLE question_discussions ADD COLUMN IF NOT EXISTS voter_ids "
            "INTEGER[] NOT NULL DEFAULT '{}'::integer[]"
        ))
        # Proctor snapshots can be inline data-URLs (live face-presence capture),
        # which exceed VARCHAR(500) — widen media_url to TEXT.
        conn.execute(text(
            "ALTER TABLE proctor_events ALTER COLUMN media_url TYPE TEXT"
        ))
        # Exam scheduling window + granular Mettl-style config (settings JSONB).
        conn.execute(text(
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ"
        ))
        conn.execute(text(
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ"
        ))
        conn.execute(text(
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'"
        ))
        conn.execute(text(
            "ALTER TABLE exams ADD COLUMN IF NOT EXISTS settings JSONB NOT NULL DEFAULT '{}'::jsonb"
        ))
        # Every org must belong to a SuperOrganization so L&D admins (enterprise-
        # wide) can scope into orgs they create. Backfill orphaned orgs to the
        # single seed super-org (single-enterprise deploy).
        conn.execute(text(
            "UPDATE organizations SET super_organization_id = "
            "(SELECT id FROM super_organizations ORDER BY id LIMIT 1) "
            "WHERE super_organization_id IS NULL "
            "AND EXISTS (SELECT 1 FROM super_organizations)"
        ))
        conn.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_user_email_group"))
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'uq_user_email'
                ) THEN
                    ALTER TABLE users ADD CONSTRAINT uq_user_email UNIQUE (email);
                END IF;
            END $$;
        """))
    Base.metadata.create_all(
        bind=engine,
        tables=[Base.metadata.tables[t] for t in NEW_TABLES],
        checkfirst=True,
    )
    print(f"[schema] extension + tables ensured: {', '.join(NEW_TABLES)}")


def _upsert_unit(db, *, legacy_table, legacy_id, unit_type, name, description,
                 organization_id, parent_unit_id, is_active=True) -> None:
    stmt = (
        pg_insert(OrgUnit.__table__)
        .values(
            legacy_table=legacy_table,
            legacy_id=legacy_id,
            unit_type=unit_type.value,
            name=name,
            description=description,
            organization_id=organization_id,
            parent_id=parent_unit_id,
            is_active=is_active,
            depth=0,
        )
        .on_conflict_do_nothing(index_elements=["legacy_table", "legacy_id"])
    )
    db.execute(stmt)


def _unit_id_map(db, legacy_table: str) -> dict[int, int]:
    rows = (
        db.query(OrgUnit.legacy_id, OrgUnit.id)
        .filter(OrgUnit.legacy_table == legacy_table)
        .all()
    )
    return {legacy: uid for legacy, uid in rows}


def backfill_units() -> None:
    db = SessionLocal()
    try:
        # 1. Organizations (roots)
        for org in db.query(Organization).all():
            _upsert_unit(
                db, legacy_table="organizations", legacy_id=org.id,
                unit_type=OrgUnitType.ORGANIZATION, name=org.name,
                description=None, organization_id=org.id,
                parent_unit_id=None, is_active=org.is_active,
            )
        db.commit()
        org_map = _unit_id_map(db, "organizations")

        # 2. Departments
        for dept in db.query(Department).all():
            _upsert_unit(
                db, legacy_table="departments", legacy_id=dept.id,
                unit_type=OrgUnitType.DEPARTMENT, name=dept.name,
                description=dept.description,
                organization_id=dept.organization_id,
                parent_unit_id=org_map.get(dept.organization_id),
                is_active=dept.is_active,
            )
        db.commit()
        dept_map = _unit_id_map(db, "departments")
        dept_org = {d.id: d.organization_id for d in db.query(Department).all()}

        # 3. Verticals
        for vert in db.query(Vertical).all():
            _upsert_unit(
                db, legacy_table="verticals", legacy_id=vert.id,
                unit_type=OrgUnitType.VERTICAL, name=vert.name,
                description=vert.description,
                organization_id=dept_org.get(vert.department_id),
                parent_unit_id=dept_map.get(vert.department_id),
                is_active=vert.is_active,
            )
        db.commit()
        vert_map = _unit_id_map(db, "verticals")
        vert_org = {
            v.id: dept_org.get(v.department_id) for v in db.query(Vertical).all()
        }

        # 4. Batches (Batch has no is_active; status drives it)
        for batch in db.query(Batch).all():
            _upsert_unit(
                db, legacy_table="batches", legacy_id=batch.id,
                unit_type=OrgUnitType.BATCH, name=batch.name,
                description=batch.description,
                organization_id=vert_org.get(batch.vertical_id),
                parent_unit_id=vert_map.get(batch.vertical_id),
                is_active=(batch.status != "archived"),
            )
        db.commit()
        batch_map = _unit_id_map(db, "batches")
        batch_org = {
            b.id: vert_org.get(b.vertical_id) for b in db.query(Batch).all()
        }

        # 5. Groups — parent preference: batch > vertical > department.
        orphan_groups = []
        for grp in db.query(Group).all():
            parent_unit_id = None
            org_id = None
            if grp.batch_id and grp.batch_id in batch_map:
                parent_unit_id = batch_map[grp.batch_id]
                org_id = batch_org.get(grp.batch_id)
            elif grp.vertical_id and grp.vertical_id in vert_map:
                parent_unit_id = vert_map[grp.vertical_id]
                org_id = vert_org.get(grp.vertical_id)
            elif grp.department_id and grp.department_id in dept_map:
                parent_unit_id = dept_map[grp.department_id]
                org_id = dept_org.get(grp.department_id)
            else:
                orphan_groups.append(grp.id)
            _upsert_unit(
                db, legacy_table="groups", legacy_id=grp.id,
                unit_type=OrgUnitType.GROUP, name=grp.name,
                description=grp.description, organization_id=org_id,
                parent_unit_id=parent_unit_id, is_active=grp.is_active,
            )
        db.commit()

        counts = {
            t: db.query(OrgUnit).filter(OrgUnit.legacy_table == t).count()
            for t in ["organizations", "departments", "verticals", "batches", "groups"]
        }
        print(f"[units] backfilled: {counts}")
        if orphan_groups:
            print(
                f"[units] WARNING: {len(orphan_groups)} groups have no batch/"
                f"vertical/department parent (ids: {orphan_groups[:20]}…) — "
                "recorded with parent_id=NULL for Phase 5 resolution"
            )
    finally:
        db.close()


def compute_paths() -> None:
    """Recompute path/depth for the whole tree (idempotent)."""
    db = SessionLocal()
    try:
        units = db.query(OrgUnit).all()
        by_id = {u.id: u for u in units}

        def resolve(u: OrgUnit, seen: set[int]) -> tuple[str, int]:
            if u.parent_id is None or u.parent_id not in by_id or u.id in seen:
                return "/", 0
            parent = by_id[u.parent_id]
            p_path, p_depth = resolve(parent, seen | {u.id})
            return f"{p_path}{parent.id}/", p_depth + 1

        changed = 0
        for u in units:
            path, depth = resolve(u, set())
            if u.path != path or u.depth != depth:
                u.path, u.depth = path, depth
                changed += 1
        db.commit()
        print(f"[paths] {len(units)} units, {changed} updated")
    finally:
        db.close()


def backfill_roles() -> None:
    db = SessionLocal()
    try:
        group_map = _unit_id_map(db, "groups")
        vert_map = _unit_id_map(db, "verticals")

        def upsert_role(user_id: int, org_unit_id: int, role: str) -> None:
            stmt = (
                pg_insert(UserOrgRole.__table__)
                .values(user_id=user_id, org_unit_id=org_unit_id, role=role)
                .on_conflict_do_nothing(
                    index_elements=["user_id", "org_unit_id", "role"]
                )
            )
            db.execute(stmt)

        # 1. Primary membership: users.group_id + users.role
        n_primary = 0
        for uid, gid, role in db.query(User.id, User.group_id, User.role).all():
            if gid in group_map and role:
                upsert_role(uid, group_map[gid], role)
                n_primary += 1

        # 2. Scoped roles: user_roles (scope_type group|vertical)
        n_scoped = 0
        for ur in db.query(UserRole).all():
            target = None
            if ur.scope_type == "group" and ur.scope_id in group_map:
                target = group_map[ur.scope_id]
            elif ur.scope_type == "vertical" and ur.scope_id in vert_map:
                target = vert_map[ur.scope_id]
            if target and ur.role:
                upsert_role(ur.user_id, target, ur.role)
                n_scoped += 1

        # 3. Mentor assignments → Mentor on the group unit
        n_mentor = 0
        for ma in db.query(MentorGroupAssignment).filter(
            MentorGroupAssignment.is_active.is_(True)
        ).all():
            if ma.group_id in group_map:
                upsert_role(ma.mentor_id, group_map[ma.group_id], "Mentor")
                n_mentor += 1

        db.commit()
        total = db.query(UserOrgRole).count()
        print(
            f"[roles] processed primary={n_primary} scoped={n_scoped} "
            f"mentor={n_mentor}; user_org_roles total={total}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    provision_schema()
    backfill_units()
    compute_paths()
    backfill_roles()
    print("[done] phase1 provisioning complete (idempotent — safe to re-run)")
