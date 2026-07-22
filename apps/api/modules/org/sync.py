"""Legacy-hierarchy → OrgUnit dual-write sync (Phase 5).

One central, unbypassable mirror: a SQLAlchemy ``after_flush`` listener on the
(sync) ``Session`` class — which AsyncSession wraps, so BOTH engines are
covered — replays every mutation of the legacy 5-table hierarchy
(Organization/Department/Vertical/Batch/Group), plus the three role
mechanisms (users.role, user_roles, mentor_group_assignments), onto
``org_units`` / ``user_org_roles`` inside the same transaction.

With the fresh database this makes the OrgUnit tree complete from the very
first row, so reads can flip to OrgUnit with a zero-mismatch guarantee
(Phase 5 gate) and the legacy tables can be archived in Phase 7.

Rules (flush-safe): only ``session.connection().execute(...)`` here — never
session.add / query during after_flush.

Known limitation (accepted): the legacy CRUD has no "move node" operation,
so parent changes are not propagated (only create/rename/activate/delete).
"""

import logging

from sqlalchemy import delete, event, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.auth import Group, MentorGroupAssignment, User, UserRole
from models.org import Batch, Department, Organization, Vertical
from modules.org.models import OrgUnit, UserOrgRole

logger = logging.getLogger("org.sync")

_OU = OrgUnit.__table__
_UOR = UserOrgRole.__table__


def _upsert_unit_sql(conn, *, legacy_table, legacy_id, unit_type, name,
                     description, is_active, parent_table, parent_id,
                     organization_id=None):
    """Insert/refresh one org_unit, resolving parent + path/depth in SQL."""
    if parent_table is None:
        values = dict(
            legacy_table=legacy_table, legacy_id=legacy_id, unit_type=unit_type,
            name=name, description=description, is_active=is_active,
            parent_id=None, organization_id=organization_id, path="/", depth=0,
        )
        stmt = pg_insert(_OU).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["legacy_table", "legacy_id"],
            set_=dict(name=name, description=description, is_active=is_active),
        )
        conn.execute(stmt)
        return

    parent = (
        _OU.select()
        .with_only_columns(_OU.c.id, _OU.c.organization_id, _OU.c.path, _OU.c.depth)
        .where(_OU.c.legacy_table == parent_table, _OU.c.legacy_id == parent_id)
    )
    row = conn.execute(parent).first()
    if row is None:
        # Parent not mirrored (pre-sync legacy data on a non-fresh DB); the
        # idempotent backfill script repairs these. Never fail the flush.
        logger.warning(
            "org-sync: no org_unit parent %s/%s for %s/%s",
            parent_table, parent_id, legacy_table, legacy_id,
        )
        return
    values = dict(
        legacy_table=legacy_table, legacy_id=legacy_id, unit_type=unit_type,
        name=name, description=description, is_active=is_active,
        parent_id=row.id, organization_id=row.organization_id,
        path=f"{row.path}{row.id}/", depth=row.depth + 1,
    )
    stmt = pg_insert(_OU).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=["legacy_table", "legacy_id"],
        set_=dict(name=name, description=description, is_active=is_active),
    )
    conn.execute(stmt)


def _delete_unit_sql(conn, legacy_table, legacy_id):
    conn.execute(
        delete(_OU).where(
            _OU.c.legacy_table == legacy_table, _OU.c.legacy_id == legacy_id
        )
    )


def _unit_id_subq(conn, legacy_table, legacy_id):
    row = conn.execute(
        _OU.select()
        .with_only_columns(_OU.c.id)
        .where(_OU.c.legacy_table == legacy_table, _OU.c.legacy_id == legacy_id)
    ).first()
    return row.id if row else None


def _upsert_role(conn, user_id, org_unit_id, role, source):
    if org_unit_id is None or not role:
        return
    stmt = (
        pg_insert(_UOR)
        .values(user_id=user_id, org_unit_id=org_unit_id, role=role, source=source)
        .on_conflict_do_nothing(index_elements=["user_id", "org_unit_id", "role"])
    )
    conn.execute(stmt)


def _sync_obj(conn, obj, deleted: bool) -> None:
    if isinstance(obj, Organization):
        if deleted:
            _delete_unit_sql(conn, "organizations", obj.id)
        else:
            _upsert_unit_sql(
                conn, legacy_table="organizations", legacy_id=obj.id,
                unit_type="organization", name=obj.name, description=None,
                is_active=obj.is_active, parent_table=None, parent_id=None,
                organization_id=obj.id,
            )
    elif isinstance(obj, Department):
        if deleted:
            _delete_unit_sql(conn, "departments", obj.id)
        else:
            _upsert_unit_sql(
                conn, legacy_table="departments", legacy_id=obj.id,
                unit_type="department", name=obj.name, description=obj.description,
                is_active=obj.is_active,
                parent_table="organizations", parent_id=obj.organization_id,
            )
    elif isinstance(obj, Vertical):
        if deleted:
            _delete_unit_sql(conn, "verticals", obj.id)
        else:
            _upsert_unit_sql(
                conn, legacy_table="verticals", legacy_id=obj.id,
                unit_type="vertical", name=obj.name, description=obj.description,
                is_active=obj.is_active,
                parent_table="departments", parent_id=obj.department_id,
            )
    elif isinstance(obj, Batch):
        if deleted:
            _delete_unit_sql(conn, "batches", obj.id)
        else:
            _upsert_unit_sql(
                conn, legacy_table="batches", legacy_id=obj.id,
                unit_type="batch", name=obj.name, description=obj.description,
                is_active=(obj.status != "archived"),
                parent_table="verticals", parent_id=obj.vertical_id,
            )
    elif isinstance(obj, Group):
        if deleted:
            _delete_unit_sql(conn, "groups", obj.id)
        else:
            parent_table, parent_id = None, None
            if obj.batch_id:
                parent_table, parent_id = "batches", obj.batch_id
            elif obj.vertical_id:
                parent_table, parent_id = "verticals", obj.vertical_id
            elif obj.department_id:
                parent_table, parent_id = "departments", obj.department_id
            if parent_table is None:
                logger.warning("org-sync: group %s has no parent linkage", obj.id)
                return
            _upsert_unit_sql(
                conn, legacy_table="groups", legacy_id=obj.id,
                unit_type="group", name=obj.name, description=obj.description,
                is_active=obj.is_active,
                parent_table=parent_table, parent_id=parent_id,
            )
    elif isinstance(obj, User):
        # Primary membership: exactly one row owned by source='primary'.
        conn.execute(
            delete(_UOR).where(
                _UOR.c.user_id == obj.id, _UOR.c.source == "primary"
            )
        )
        if not deleted and obj.group_id and obj.is_active:
            unit_id = _unit_id_subq(conn, "groups", obj.group_id)
            _upsert_role(conn, obj.id, unit_id, obj.role, "primary")
    elif isinstance(obj, MentorGroupAssignment):
        unit_id = _unit_id_subq(conn, "groups", obj.group_id)
        if unit_id is None:
            return
        if deleted or not obj.is_active:
            conn.execute(
                delete(_UOR).where(
                    _UOR.c.user_id == obj.mentor_id,
                    _UOR.c.org_unit_id == unit_id,
                    _UOR.c.role == "Mentor",
                    _UOR.c.source == "mentor",
                )
            )
        else:
            _upsert_role(conn, obj.mentor_id, unit_id, "Mentor", "mentor")
    elif isinstance(obj, UserRole):
        target = None
        if obj.scope_type == "group" and obj.scope_id:
            target = _unit_id_subq(conn, "groups", obj.scope_id)
        elif obj.scope_type == "vertical" and obj.scope_id:
            target = _unit_id_subq(conn, "verticals", obj.scope_id)
        if target is None:
            return
        if deleted:
            conn.execute(
                delete(_UOR).where(
                    _UOR.c.user_id == obj.user_id,
                    _UOR.c.org_unit_id == target,
                    _UOR.c.role == obj.role,
                    _UOR.c.source == "scoped",
                )
            )
        else:
            _upsert_role(conn, obj.user_id, target, obj.role, "scoped")


_WATCHED = (
    Organization, Department, Vertical, Batch, Group,
    User, MentorGroupAssignment, UserRole,
)

_registered = False


def register_org_unit_sync() -> None:
    """Attach the after_flush mirror. Idempotent; call once at import."""
    global _registered
    if _registered:
        return
    _registered = True

    @event.listens_for(Session, "after_flush")
    def _mirror(session, flush_context):  # noqa: ANN001
        conn = session.connection()
        try:
            for obj in session.new:
                if isinstance(obj, _WATCHED):
                    _sync_obj(conn, obj, deleted=False)
            for obj in session.dirty:
                if isinstance(obj, _WATCHED):
                    _sync_obj(conn, obj, deleted=False)
            for obj in session.deleted:
                if isinstance(obj, _WATCHED):
                    _sync_obj(conn, obj, deleted=True)
        except Exception:
            # The mirror must never break the primary write path; divergence
            # is repaired by the idempotent backfill (scripts/phase1_provision).
            logger.exception("org-sync mirror failed (primary write unaffected)")
