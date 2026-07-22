"""Canonical enums and constants shared across modules.

Single source of truth for role names and org-unit types. The role strings
match the values already stored in ``users.role`` and ``user_roles.role_name``
(canonical RBAC vocabulary — do NOT invent parallel names).
"""

import enum


class Role:
    """Canonical role strings as persisted in the database."""

    MEMBER = "Member"
    GROUP_ADMIN = "GroupAdmin"
    MENTOR = "Mentor"
    LD_ADMIN = "LDAdmin"
    PLATFORM_ADMIN = "PlatformAdmin"

    ALL = (MEMBER, GROUP_ADMIN, MENTOR, LD_ADMIN, PLATFORM_ADMIN)


class OrgUnitType(str, enum.Enum):
    """Node types in the OrgUnit tree, top to bottom.

    Mirrors the legacy 5-table hierarchy:
    Organization → Department → Vertical → Batch → Group.
    """

    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    VERTICAL = "vertical"
    BATCH = "batch"
    GROUP = "group"


# Legacy table names used for OrgUnit backfill provenance (see
# modules/org/models.py: OrgUnit.legacy_table / legacy_id).
LEGACY_TABLE_FOR_UNIT_TYPE = {
    OrgUnitType.ORGANIZATION: "organizations",
    OrgUnitType.DEPARTMENT: "departments",
    OrgUnitType.VERTICAL: "verticals",
    OrgUnitType.BATCH: "batches",
    OrgUnitType.GROUP: "groups",
}
