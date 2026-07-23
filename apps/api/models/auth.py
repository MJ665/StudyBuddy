import datetime
from typing import Any
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("batches.id"), nullable=True)
    # nullable for backward compat with V2 data; new groups always have batch_id
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Legacy group-pattern login (retired 2026-07-23): patterns are never
    # written or checked anymore; column kept nullable for old rows.
    password_pattern: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    vertical_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("verticals.id"), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)

    expertise_json: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch = relationship("Batch", back_populates="groups")
    users = relationship("User", back_populates="group")
    mentor_assignments = relationship("MentorGroupAssignment", back_populates="group")
    resources = relationship("Resource", back_populates="group")
    vertical = relationship("Vertical")
    department = relationship("Department")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", "group_id", name="uq_user_email_group"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Denormalized tenant key. Isolation previously depended on walking
    # user -> group -> batch -> vertical -> department -> organization, which no
    # query actually did, so cross-tenant reads were possible. Nullable because
    # legacy rows may predate attribution; scoping helpers treat NULL as "deny".
    organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="Member", nullable=False)
    # role values: "Member" | "GroupAdmin" | "Mentor" | "LDAdmin"
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Manual override if pattern reset used
    member_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )  # Strategic Entity ID (e.g. Employee Code)

    # Profile Expansion (NEW)
    profile_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    intro_video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    custom_slug: Mapped[str | None] = mapped_column(String(100), unique=True, index=True, nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    github_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    leetcode_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    codolio_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expertise_json: Mapped[dict | list | Any | None] = mapped_column(
        JSONB, nullable=True
    )  # { skills: [], tags: [], strengths: {} }
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Scoping for zero-leakage
    vertical_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("verticals.id"), nullable=True)
    department_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("departments.id"), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)
    last_login: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_active_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    group = relationship("Group", back_populates="users")
    attempts = relationship("Attempt", back_populates="user")
    coding_attempts = relationship("CodingAttempt", back_populates="user")
    # delete-orphan: removing a mentor removes their group assignments in the
    # same flush (previously SAWarning'd and left orphaned rows to FK-fail).
    mentor_assignments = relationship(
        "MentorGroupAssignment", back_populates="mentor", cascade="all, delete-orphan"
    )
    reset_tokens = relationship("PasswordResetToken", back_populates="user")
    scoped_roles = relationship(
        "UserRole", back_populates="user", cascade="all, delete-orphan"
    )
    learning_paths = relationship("UserLearningPath", back_populates="user")


class MentorGroupAssignment(Base):
    """Maps mentors (Users with role=Mentor) to Groups they oversee."""

    __tablename__ = "mentor_group_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mentor_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, ForeignKey("groups.id"), nullable=False)
    assigned_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    mentor = relationship("User", back_populates="mentor_assignments")
    group = relationship("Group", back_populates="mentor_assignments")

    __table_args__ = (
        UniqueConstraint("mentor_id", "group_id", name="uq_mentor_group"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    otp_code: Mapped[str] = mapped_column(String(10), nullable=False)
    # timezone=True: the async (asyncpg) path rejects tz-aware datetimes on a
    # naive column, which 500'd the forgot-password flow.
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool | None] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="reset_tokens")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    user = relationship("User")


class UserRole(Base):
    """
    Junction table for scoped role assignments.
    Enables one user to be 'GroupAdmin' for Group X and 'Member' for Group Y.
    STRAT-RBAC-01: Context-aware authorization.
    """

    __tablename__ = "user_roles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # NOTE: the physical DB columns are role_name/resource_type/resource_id (legacy).
    # We keep the clean Python attribute names role/scope_type/scope_id and map them
    # to the real columns, so no data migration is needed and all callers use the
    # canonical names.
    role: Mapped[str] = mapped_column("role_name", String(50), nullable=False)
    scope_type: Mapped[str | None] = mapped_column("resource_type", String(50), nullable=True)  # "group", "vertical"
    scope_id: Mapped[int | None] = mapped_column("resource_id", Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default="now()", nullable=False)

    user = relationship("User", back_populates="scoped_roles")