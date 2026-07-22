import datetime

from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship


class SuperOrganization(Base):
    """The paying customer — the top of the tenant hierarchy.

    Hierarchy:
        PlatformAdmin (us)
          └── SuperOrganization   ← purchases the app; managed from /platform
               └── Organization   ← business unit (L&D Admin operates here)
                    └── Department → Vertical → Batch → Group → Users

    Authored CONTENT (question banks, questions, exams, KT knowledge) is scoped to
    the super organization, so a customer's business units can share it. LEARNER
    data (attempts, gradebooks, reports, users, certificates) stays scoped to the
    Organization, so one business unit cannot read another's results.
    """

    __tablename__ = "super_organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)

    # Commercial + lifecycle: this is the entity /platform approves and suspends.
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    subscription_tier: Mapped[str] = mapped_column(String(50), default="Free", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Customer-level branding; an Organization may still override for co-branding.
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    signature_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    onboarding_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    onboarded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    organizations = relationship("Organization", back_populates="super_organization")


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_tier: Mapped[str] = mapped_column(String(50), default="Free", nullable=False)

    # ── Multi-tenant onboarding + white-label (Platform Admin governed) ───────
    # pending → (Platform Admin approves) → approved → (may be) suspended.
    # Existing orgs default to "approved" so they keep working.
    status: Mapped[str] = mapped_column(String(20), default="approved", nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # org logo (co-branding)
    signature_url: Mapped[str | None] = mapped_column(String(500), nullable=True)  # admin signature (certificates)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # display name; defaults to name
    onboarding_token: Mapped[str | None] = mapped_column(String(64), nullable=True)  # one-time onboarding link
    onboarded_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    # Parent tenant. Nullable so pre-existing rows stay valid until backfilled;
    # scoping helpers treat NULL as "deny" rather than "match everything".
    super_organization_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("super_organizations.id"), index=True, nullable=True
    )

    super_organization = relationship("SuperOrganization", back_populates="organizations")
    departments = relationship(
        "Department", back_populates="organization", cascade="all, delete-orphan"
    )


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    organization = relationship("Organization", back_populates="departments")
    verticals = relationship(
        "Vertical", back_populates="department", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_dept_name_per_org"),
    )


class Vertical(Base):
    __tablename__ = "verticals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    department_id: Mapped[int] = mapped_column(Integer, ForeignKey("departments.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    department = relationship("Department", back_populates="verticals")
    batches = relationship(
        "Batch", back_populates="vertical", cascade="all, delete-orphan"
    )
    vertical_courses = relationship("VerticalCourse", back_populates="vertical")


class Batch(Base):
    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vertical_id: Mapped[int] = mapped_column(Integer, ForeignKey("verticals.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    end_date: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    # status values: "active" | "completed" | "archived"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    vertical = relationship("Vertical", back_populates="batches")
    groups = relationship("Group", back_populates="batch", cascade="all, delete-orphan")
