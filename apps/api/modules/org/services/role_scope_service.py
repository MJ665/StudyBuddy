"""OrgUnit-based scope resolution (Phase 5) — the target read API.

"Which part of the org tree can this user touch?" — answered from
org_units/user_org_roles (kept complete by modules/org/sync.py), replacing
ad-hoc walks over the legacy 5-table chain.

Sync sessions for now (most legacy routers are sync; async twins land with
the async-migration pass). Materialized paths make subtree queries a single
LIKE — no recursive CTE needed.
"""

from sqlalchemy.orm import Session

from modules.org.models import OrgUnit, UserOrgRole


def user_units(db: Session, user_id: int, roles: list[str] | None = None) -> list[OrgUnit]:
    """OrgUnits where the user holds any (or one of the given) roles."""
    q = (
        db.query(OrgUnit)
        .join(UserOrgRole, UserOrgRole.org_unit_id == OrgUnit.id)
        .filter(UserOrgRole.user_id == user_id, OrgUnit.is_active.is_(True))
    )
    if roles:
        q = q.filter(UserOrgRole.role.in_(roles))
    return q.all()


def subtree_unit_ids(db: Session, unit: OrgUnit) -> list[int]:
    """The unit plus every descendant (materialized-path prefix match)."""
    prefix = f"{unit.path}{unit.id}/"
    rows = (
        db.query(OrgUnit.id)
        .filter((OrgUnit.id == unit.id) | OrgUnit.path.like(f"{prefix}%"))
        .all()
    )
    return [r[0] for r in rows]


def reach_unit_ids(db: Session, user_id: int, roles: list[str] | None = None) -> set[int]:
    """Union of subtree ids over every unit where the user holds a role."""
    out: set[int] = set()
    for unit in user_units(db, user_id, roles):
        out.update(subtree_unit_ids(db, unit))
    return out


def reach_group_ids(db: Session, user_id: int, roles: list[str] | None = None) -> set[int]:
    """The user's reach expressed as LEGACY group ids — the transitional
    currency most existing scoping helpers speak. Lets call-sites flip to
    OrgUnit-derived scope without changing their downstream queries."""
    ids = reach_unit_ids(db, user_id, roles)
    if not ids:
        return set()
    rows = (
        db.query(OrgUnit.legacy_id)
        .filter(
            OrgUnit.id.in_(ids),
            OrgUnit.unit_type == "group",
            OrgUnit.legacy_id.isnot(None),
        )
        .all()
    )
    return {r[0] for r in rows}
