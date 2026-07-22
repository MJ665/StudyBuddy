"""Legacy-hierarchy ⇄ OrgUnit compatibility layer (Phase 1 → Phase 5).

During the migration both representations of the org tree exist:

- legacy: organizations / departments / verticals / batches / groups
  (+ users.role, user_roles, mentor_group_assignments)
- target: org_units (+ user_org_roles)

The backfill (scripts/phase1_provision.py) stamps every migrated OrgUnit with
``legacy_table``/``legacy_id``, so translation is a lookup, not a guess.
Readers that want the new model call these helpers; if the backfill has not
run (or missed a row) they fall back to legacy tables. Phase 5 flips all
call-sites to OrgUnit-only and this file is deleted.

All helpers are sync (legacy routers are sync); async twins can be added when
the async migration pass happens (Phase 3) — do NOT mix session types here.
"""

from sqlalchemy.orm import Session

from modules.org.models import OrgUnit, UserOrgRole


def org_unit_for_legacy(
    db: Session, legacy_table: str, legacy_id: int
) -> OrgUnit | None:
    """Translate a legacy hierarchy row (e.g. ('groups', 7)) to its OrgUnit."""
    return (
        db.query(OrgUnit)
        .filter(
            OrgUnit.legacy_table == legacy_table,
            OrgUnit.legacy_id == legacy_id,
        )
        .first()
    )


def org_units_for_user(db: Session, user_id: int) -> list[OrgUnit]:
    """All OrgUnits where the user holds any role (new model).

    Falls back to the user's legacy primary group if no UserOrgRole rows exist
    yet, so callers behave identically before and after the backfill.
    """
    units = (
        db.query(OrgUnit)
        .join(UserOrgRole, UserOrgRole.org_unit_id == OrgUnit.id)
        .filter(UserOrgRole.user_id == user_id)
        .all()
    )
    if units:
        return units

    # Fallback: synthesize from the legacy primary membership.
    from models import User  # local import to avoid import cycles

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or user.group_id is None:
        return []
    unit = org_unit_for_legacy(db, "groups", user.group_id)
    return [unit] if unit else []


def subtree_ids(db: Session, unit: OrgUnit) -> list[int]:
    """Ids of ``unit`` and every descendant, via the materialized path."""
    if not unit.path:
        return [unit.id]
    rows = (
        db.query(OrgUnit.id)
        .filter(OrgUnit.path.like(f"{unit.path}{unit.id}/%") | (OrgUnit.id == unit.id))
        .all()
    )
    return [r[0] for r in rows]
