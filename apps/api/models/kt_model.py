from typing import Any
import datetime
# kt_models.py
import enum
import uuid

from database import Base
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


def gen_uuid():
    return str(uuid.uuid4())


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────


class UserRoleEnum(str, enum.Enum):
    AUTHOR = "author"
    MENTOR = "mentor"
    GROUP_ADMIN = "group_admin"
    LD_ADMIN = "ld_admin"
    OWNER = "owner"


class DocStatusEnum(str, enum.Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    INGESTED = "ingested"
    DEPRECATED = "deprecated"


class DocTypeEnum(str, enum.Enum):
    ARCHITECTURE_DECISION = "architecture_decision"
    MEETING_NOTES = "meeting_notes"
    POST_MORTEM = "post_mortem"
    RUNBOOK = "runbook"
    DESIGN_DOC = "design_doc"
    ONBOARDING_GUIDE = "onboarding_guide"
    TECH_SPIKE = "tech_spike"
    RETROSPECTIVE = "retrospective"
    BUG_ANALYSIS = "bug_analysis"
    API_DOCUMENTATION = "api_documentation"
    DEPLOYMENT_GUIDE = "deployment_guide"
    SECURITY_REVIEW = "security_review"
    PERFORMANCE_ANALYSIS = "performance_analysis"
    KNOWLEDGE_BASE = "knowledge_base"


class KnowledgeDomainEnum(str, enum.Enum):
    BACKEND = "backend"
    FRONTEND = "frontend"
    DEVOPS = "devops"
    DATA = "data"
    SECURITY = "security"
    PRODUCT = "product"
    MOBILE = "mobile"
    QA = "qa"
    ARCHITECTURE = "architecture"
    ML_AI = "ml_ai"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"


class ComplexityEnum(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class AccessLevelEnum(str, enum.Enum):
    PROJECT_ONLY = "project_only"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"


class SensitivityEnum(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONFIDENTIAL = "confidential"


class IngestionStatusEnum(str, enum.Enum):
    PENDING = "pending"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    GRAPH_BUILDING = "graph_building"
    COMPLETE = "complete"
    FAILED = "failed"


class ReviewActionEnum(str, enum.Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMENTED = "commented"
    REQUESTED_CHANGES = "requested_changes"


class AuditActionEnum(str, enum.Enum):
    DOC_CREATED = "doc_created"
    DOC_UPDATED = "doc_updated"
    DOC_SUBMITTED = "doc_submitted"
    DOC_APPROVED = "doc_approved"
    DOC_REJECTED = "doc_rejected"
    DOC_FED = "doc_fed"
    DOC_DEPRECATED = "doc_deprecated"
    DOC_DELETED = "doc_deleted"
    KEY_GENERATED = "key_generated"
    KEY_REVOKED = "key_revoked"
    KEY_USED = "key_used"
    USER_LOGIN = "user_login"
    USER_CREATED = "user_created"
    USER_ROLE_CHANGED = "user_role_changed"
    CHAT_SESSION_STARTED = "chat_session_started"
    CHAT_MESSAGE_SENT = "chat_message_sent"
    CHAT_FEEDBACK_GIVEN = "chat_feedback_given"
    HANDOFF_INITIATED = "handoff_initiated"
    HANDOFF_COMPLETED = "handoff_completed"


# ─────────────────────────────────────────────────────────────────────────────
# CORE TABLES
# ─────────────────────────────────────────────────────────────────────────────


class KTCompany(Base):
    """Represents a client company — the top-level isolation boundary."""

    __tablename__ = "kt_companies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    # which StudyHub organization_id owns this company record
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Shared across the customer's business units (see SuperOrganization).
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, default=True)
    settings_data: Mapped[dict | list | Any | None] = mapped_column(JSONB, default={})
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    projects = relationship("KTProject", back_populates="company")
    access_keys = relationship("KTAccessKey", back_populates="company")
    health_snapshots = relationship("KTHealthSnapshot", back_populates="company")


class KTProject(Base):
    """A project scoped to a company. All docs and keys are project-scoped."""

    __tablename__ = "kt_projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=1)
    # Shared across the customer's business units (see SuperOrganization).
    super_organization_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    group_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    tech_stack: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    doc_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ingested_doc_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    knowledge_coverage_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company = relationship("KTCompany", back_populates="projects")
    documents = relationship("KTDocument", back_populates="project")
    members = relationship("KTProjectMember", back_populates="project", cascade="all, delete-orphan")

class KTDocument(Base):
    __tablename__ = "kt_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("kt_projects.id"), nullable=False)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    knowledge_domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    complexity: Mapped[str] = mapped_column(String(50), default="intermediate")
    access_level: Mapped[str] = mapped_column(String(50), default="project_only")
    sensitivity: Mapped[str] = mapped_column(String(50), default="low")
    is_evergreen: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    tech_stack: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    co_author_ids: Mapped[list[int] | None] = mapped_column(PG_ARRAY(Integer), default=[])
    co_author_names: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    co_author_emails: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    language: Mapped[str] = mapped_column(String(10), default="en")

    # Review routing: who was asked to approve, and who actually did.
    mentor_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    # Engagement/delivery context
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_range_start: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_range_end: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sprint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    milestone: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Context
    related_project_ids: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    related_doc_ids: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    jira_tickets: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    github_prs: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    
    # Knowledge
    problem_statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    decisions_made: Mapped[dict | list | None] = mapped_column(JSONB, default=[])
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    open_questions: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    lessons_learned: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])

    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary_ai: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_tags: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])

    status: Mapped[str] = mapped_column(SAEnum(DocStatusEnum), default=DocStatusEnum.DRAFT, nullable=False)
    version: Mapped[int | None] = mapped_column(Integer, default=1)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    header_completeness: Mapped[float | None] = mapped_column(Float, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, default=0)
    read_time_minutes: Mapped[int | None] = mapped_column(Integer, default=0)
    endorsement_count: Mapped[int | None] = mapped_column(Integer, default=0)

    ingestion_status: Mapped[str | None] = mapped_column(SAEnum(IngestionStatusEnum), nullable=True)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # (Phase 7) neo4j_episode_ids removed — chunks live in kt_document_chunks
    # (pgvector); the physical column is dropped by scripts/phase1_provision.

    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_queried_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deprecated_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("KTProject", back_populates="documents")
    reviews = relationship("KTDocumentReview", back_populates="document")
    versions = relationship("KTDocumentVersion", back_populates="document")
    ingestion_jobs = relationship("KTIngestionJob", back_populates="document")
    endorsements = relationship("KTEndorsement", back_populates="document")

    __table_args__ = (
        Index("idx_ktdoc_project_status", "project_id", "status"),
        Index("idx_ktdoc_company_status", "company_id", "status"),
        Index("idx_ktdoc_author", "author_id"),
        Index("idx_ktdoc_org", "organization_id"),
    )


class KTDocumentVersion(Base):
    """Immutable snapshot of a document's body at a point in time.

    NOTE: this class body previously contained a copy-paste of KTAccessKey's
    columns (key_hash, recipient_email, project_ids, ...) and `create_all`
    propagated that wrong shape into Postgres, so every KTDocumentVersion(...)
    call in routers/kt.py raised TypeError. The table was empty, so it is
    rebuilt here to match what the routers actually write.
    """

    __tablename__ = "kt_document_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_documents.id", ondelete="CASCADE"), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    body_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document = relationship("KTDocument", back_populates="versions")

    __table_args__ = (
        Index("idx_ktdocver_doc_version", "document_id", "version"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────────────────────────────────────────


class KTChatSession(Base):
    __tablename__ = "kt_chat_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    access_key_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_access_keys.id"), nullable=True)

    # Caller identity
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=True)

    # LOCKED retrieval scope, resolved once at session creation from the caller's
    # grants and never from request input. kt_engine's Cypher filters on these,
    # so they are the enforcement point for knowledge access.
    resolved_company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_project_ids: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    # User-facing thread title (ChatGPT-style). Auto-set from the first message.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)

    messages: Mapped[list[dict] | None] = mapped_column(JSONB, default=[])
    graph_hops: Mapped[dict | list | Any | None] = mapped_column(JSONB, default=[])
    message_count: Mapped[int | None] = mapped_column(Integer, default=0)
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())

    access_key = relationship("KTAccessKey", back_populates="chat_sessions")
    chat_messages = relationship("KTChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_ktchat_user", "user_id"),
        Index("idx_ktchat_org", "organization_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# KNOWLEDGE GAPS & AUDIT
# ─────────────────────────────────────────────────────────────────────────────


class KTUnansweredQuery(Base):
    __tablename__ = "kt_unanswered_queries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    company_id: Mapped[str] = mapped_column(String(36), nullable=False)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_ids: Mapped[Any | None] = mapped_column(PG_ARRAY(String), default=[])
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_normalized: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurrence_count: Mapped[int | None] = mapped_column(Integer, default=1)
    first_asked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_asked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved: Mapped[bool | None] = mapped_column(Boolean, default=False)
    resolved_by_doc_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, default=0)
    assigned_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    __table_args__ = (Index("idx_unanswered_company", "company_id", "resolved"),)


class KTAuditLog(Base):
    __tablename__ = "kt_audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[Any] = mapped_column(SAEnum(AuditActionEnum), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    metadata_json: Mapped[dict | list | Any | None] = mapped_column(JSONB, default={})
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("idx_kt_audit_org", "organization_id", "action"),)


class KTHealthSnapshot(Base):
    __tablename__ = "kt_health_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=False)
    metrics_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hr_approved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    company = relationship("KTCompany", back_populates="health_snapshots")


class KTDocumentAttachment(Base):
    __tablename__ = "kt_document_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_documents.id"), nullable=True)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    s3_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KTNotification(Base):
    __tablename__ = "kt_notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    organization_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_read: Mapped[bool | None] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (Index("idx_kt_notif_user", "user_id", "is_read"),)

class KTAccessKey(Base):
    __tablename__ = "kt_access_keys"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    issued_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(20))
    scope_label: Mapped[str | None] = mapped_column(String(255))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    max_uses: Mapped[int | None] = mapped_column(Integer)
    is_onboarding_key: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    use_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # NOTE: kt_companies.id is VARCHAR; this was previously declared Integer,
    # which did not match the physical column.
    company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=True)
    # Explicit grant list — ground truth for scope enforcement on key-based access.
    project_ids: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    company = relationship("KTCompany", back_populates="access_keys")
    chat_sessions = relationship("KTChatSession", back_populates="access_key")

class KTChatMessage(Base):
    __tablename__ = "kt_chat_messages"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("kt_chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[dict | list | None] = mapped_column(JSONB)
    # Richer citation payload (title/doc_id/project/score per source) written by the
    # RAG pipeline; `sources` is kept for backward compatibility with older rows.
    sources_metadata: Mapped[dict | list | None] = mapped_column(JSONB, default=[])
    retrieved_doc_ids: Mapped[list[str] | None] = mapped_column(PG_ARRAY(String), default=[])
    graph_hops: Mapped[dict | list | Any | None] = mapped_column(JSONB, default=[])
    confidence_score: Mapped[float | None] = mapped_column(Float)
    was_answered: Mapped[bool] = mapped_column(Boolean, default=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    session = relationship("KTChatSession", back_populates="chat_messages")

class KTDocumentReview(Base):
    __tablename__ = "kt_document_reviews"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("kt_documents.id", ondelete="CASCADE"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[ReviewActionEnum] = mapped_column(SAEnum(ReviewActionEnum))
    comment: Mapped[str | None] = mapped_column(Text)
    inline_comments: Mapped[dict | list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document = relationship("KTDocument", back_populates="reviews")
    
class KTEndorsement(Base):
    __tablename__ = "kt_endorsements"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("kt_documents.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    weight: Mapped[int] = mapped_column(Integer, default=1)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    document = relationship("KTDocument", back_populates="endorsements")

class KTHandoff(Base):
    """Offboarding handoff. Column names follow the router's domain language
    (departing/receiving) rather than the earlier generic from/to — the table was
    empty, so this is a rename, not a data migration."""

    __tablename__ = "kt_handoffs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("kt_projects.id", ondelete="CASCADE"), nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("kt_companies.id"), nullable=True)
    organization_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    departing_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    receiving_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    mentor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    departure_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handoff_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    checklist: Mapped[dict | list | None] = mapped_column(JSONB, default=[])
    gap_analysis: Mapped[dict | list | None] = mapped_column(JSONB, default={})
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

class KTIngestionJob(Base):
    __tablename__ = "kt_ingestion_jobs"
    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(ForeignKey("kt_documents.id", ondelete="CASCADE"))
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_re_ingestion: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    nodes_created: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    # Ordering column the ingestion-status endpoint reads to find the latest job.
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    document = relationship("KTDocument", back_populates="ingestion_jobs")

class KTProjectMember(Base):
    __tablename__ = "kt_project_members"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("kt_projects.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_in_project: Mapped[str] = mapped_column(String(20))
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User")
    project = relationship("KTProject", back_populates="members")
