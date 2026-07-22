"""OrgUnit tree + UserOrgRole — the target org-hierarchy model.

Replaces the legacy 5-table chain (Organization → Department → Vertical →
Batch → Group) with one self-referencing tree. Introduced additively in
Phase 1; the legacy tables keep working via shared/compatibility.py until
Phase 5 flips all reads. See docs/product-plan/TARGET_ARCHITECTURE.md §3.
"""

import datetime

from database import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class OrgUnit(Base):
    """One node in the org tree.

    ``unit_type`` values come from shared.constants.OrgUnitType
    (organization | department | vertical | batch | group). Stored as a plain
    string — not a PG enum — so adding types never needs a type migration.

    ``legacy_table``/``legacy_id`` record which legacy row this unit was
    backfilled from; the unique constraint on the pair is what makes the
    backfill idempotent and lets the compatibility layer translate ids in
    both directions until Phase 5.

    NOTE: no unique (parent_id, name) constraint yet — legacy data was never
    held to that invariant (verticals/batches have no uniqueness at all), so
    enforcing it here would break the backfill. Phase 5 validation dedupes,
    then the constraint is added.
    """

    __tablename__ = "org_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("organizations.id"), index=True, nullable=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("org_units.id", ondelete="CASCADE"), index=True, nullable=True
    )
    unit_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Materialized path of ancestor ids ("/1/4/9/") + depth, maintained by
    # hierarchy_service. Fast subtree queries: WHERE path LIKE '/1/4/%'.
    path: Mapped[str | None] = mapped_column(String(1000), index=True, nullable=True)
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Backfill provenance (see class docstring).
    legacy_table: Mapped[str | None] = mapped_column(String(30), nullable=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parent = relationship("OrgUnit", remote_side=[id], backref="children")
    members = relationship(
        "UserOrgRole", back_populates="org_unit", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("legacy_table", "legacy_id", name="uq_org_unit_legacy_row"),
        Index("ix_org_units_org_type", "organization_id", "unit_type"),
    )


class UserOrgRole(Base):
    """User ⇄ role ⇄ OrgUnit. Replaces the trio of legacy mechanisms:
    ``users.role`` (global), ``user_roles`` (scoped), and
    ``mentor_group_assignments``.

    ``role`` uses the canonical strings from shared.constants.Role
    (Member | GroupAdmin | Mentor | LDAdmin | PlatformAdmin). A user may hold
    different roles on the same unit (e.g. Member + Mentor on one group),
    hence the 3-column uniqueness.
    """

    __tablename__ = "user_org_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    org_unit_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("org_units.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    assigned_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    assigned_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )

    user = relationship("User", foreign_keys=[user_id])
    org_unit = relationship("OrgUnit", back_populates="members")

    __table_args__ = (
        UniqueConstraint("user_id", "org_unit_id", "role", name="uq_user_unit_role"),
    )
