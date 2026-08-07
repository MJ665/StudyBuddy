from datetime import date, datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# ── Enums ──────────────────────────────────────────────────────────────────


class UserRoleEnum(str, Enum):
    AUTHOR = "author"
    MENTOR = "mentor"
    GROUP_ADMIN = "group_admin"
    LD_ADMIN = "ld_admin"
    OWNER = "owner"


class DocStatusEnum(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    INGESTED = "ingested"
    DEPRECATED = "deprecated"


class DocTypeEnum(str, Enum):
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


class KnowledgeDomainEnum(str, Enum):
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


class ComplexityEnum(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class AccessLevelEnum(str, Enum):
    PROJECT_ONLY = "project_only"
    COMPANY_WIDE = "company_wide"
    PUBLIC = "public"


class SensitivityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CONFIDENTIAL = "confidential"


class ReviewActionEnum(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    COMMENTED = "commented"
    REQUESTED_CHANGES = "requested_changes"


# ── Company ────────────────────────────────────────────────────────────────


class KTCompanyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    domain: Optional[str] = None


class KTCompanyOut(BaseModel):
    id: str
    name: str
    domain: Optional[str]
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Project ────────────────────────────────────────────────────────────────


class KTProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    company_id: Optional[str] = None  # Auto-resolved from org if not provided
    description: Optional[str] = None
    client_name: Optional[str] = None
    group_id: Optional[int] = None
    tech_stack: Optional[List[str]] = []


class KTProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    tech_stack: Optional[List[str]] = None
    status: Optional[str] = None


class KTProjectMemberOut(BaseModel):
    user_id: int
    full_name: Optional[str] = None
    role_in_project: str
    model_config = ConfigDict(from_attributes=True)


class KTProjectOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    company_id: str
    client_name: Optional[str]
    tech_stack: List[str]
    status: str
    doc_count: int
    ingested_doc_count: int
    knowledge_coverage_score: float
    created_at: datetime
    members: List[KTProjectMemberOut] = []
    model_config = ConfigDict(from_attributes=True)


# ── Co-author picker ───────────────────────────────────────────────────────


class CoAuthorPickRequest(BaseModel):
    """Frontend sends user_id of existing DB user to add as co-author."""

    user_id: int


class CoAuthorOut(BaseModel):
    user_id: int
    name: str
    email: str
    group_name: Optional[str] = None


# ── Document ───────────────────────────────────────────────────────────────


class KTDocumentCreate(BaseModel):
    project_id: str
    title: str = Field(..., min_length=3, max_length=500)
    doc_type: DocTypeEnum
    knowledge_domain: Optional[KnowledgeDomainEnum] = None
    tech_stack: Optional[List[str]] = []
    tags: Optional[List[str]] = []
    complexity: Optional[ComplexityEnum] = ComplexityEnum.INTERMEDIATE
    is_evergreen: bool = False
    access_level: Optional[AccessLevelEnum] = AccessLevelEnum.PROJECT_ONLY
    sensitivity: Optional[SensitivityEnum] = SensitivityEnum.MEDIUM
    language: str = "en"
    # Co-authors: list of user_ids — must exist in DB
    co_author_ids: Optional[List[int]] = []
    client_name: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    sprint: Optional[str] = None
    milestone: Optional[str] = None
    related_project_ids: Optional[List[str]] = []
    related_doc_ids: Optional[List[str]] = []
    jira_tickets: Optional[List[str]] = []
    github_prs: Optional[List[str]] = []
    problem_statement: Optional[str] = None
    decisions_made: Optional[List[Dict]] = []
    outcome: Optional[str] = None
    conclusion: Optional[str] = None
    open_questions: Optional[List[str]] = []
    lessons_learned: Optional[List[str]] = []
    body_markdown: str = ""
    mentor_id: Optional[int] = None

    @field_validator("date_range_end")
    @classmethod
    def end_after_start(cls, v, info):
        if (
            v
            and info.data.get("date_range_start")
            and v < info.data["date_range_start"]
        ):
            raise ValueError("date_range_end must be after date_range_start")
        return v


class KTDocumentUpdate(BaseModel):
    title: Optional[str] = None
    doc_type: Optional[DocTypeEnum] = None
    knowledge_domain: Optional[KnowledgeDomainEnum] = None
    tech_stack: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    complexity: Optional[ComplexityEnum] = None
    is_evergreen: Optional[bool] = None
    access_level: Optional[AccessLevelEnum] = None
    sensitivity: Optional[SensitivityEnum] = None
    co_author_ids: Optional[List[int]] = None
    client_name: Optional[str] = None
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None
    sprint: Optional[str] = None
    milestone: Optional[str] = None
    related_project_ids: Optional[List[str]] = None
    related_doc_ids: Optional[List[str]] = None
    jira_tickets: Optional[List[str]] = None
    github_prs: Optional[List[str]] = None
    problem_statement: Optional[str] = None
    decisions_made: Optional[List[Dict]] = None
    outcome: Optional[str] = None
    conclusion: Optional[str] = None
    open_questions: Optional[List[str]] = None
    lessons_learned: Optional[List[str]] = None
    body_markdown: Optional[str] = None
    mentor_id: Optional[int] = None
    change_summary: Optional[str] = None


class KTEndorsementOut(BaseModel):
    id: str
    user_id: int
    comment: Optional[str]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class KTDocumentOut(BaseModel):
    id: str
    project_id: str
    company_id: str
    author_id: Optional[int]
    mentor_id: Optional[int]
    title: str
    doc_type: str
    knowledge_domain: Optional[str]
    tech_stack: List[str]
    tags: List[str]
    complexity: str
    is_evergreen: bool
    access_level: str
    sensitivity: str
    co_author_ids: List[int]
    co_author_names: List[str]
    co_author_emails: List[str]
    client_name: Optional[str]
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    sprint: Optional[str]
    milestone: Optional[str]
    problem_statement: Optional[str]
    decisions_made: List[Dict]
    outcome: Optional[str]
    conclusion: Optional[str]
    open_questions: List[str]
    lessons_learned: List[str]
    body_markdown: str
    summary_ai: Optional[str]
    auto_tags: List[str]
    status: str
    version: int
    quality_score: Optional[float]
    header_completeness: Optional[float]
    word_count: int
    read_time_minutes: int
    ingestion_status: Optional[str]
    endorsement_count: int
    endorsements: List[KTEndorsementOut] = []
    created_at: datetime
    updated_at: Optional[datetime]
    submitted_at: Optional[datetime]
    approved_at: Optional[datetime]
    ingested_at: Optional[datetime]
    # Computed fields
    can_edit: bool = False  # set by router based on current user
    model_config = ConfigDict(from_attributes=True)

    @field_validator("date_range_start", "date_range_end", mode="before")
    @classmethod
    def _coerce_datetime_to_date(cls, v):
        # The DB stores these as DateTime(timezone=True); this schema field is a
        # `date`. Pydantic v2 rejects a datetime with a non-zero time for a date
        # field (date_from_datetime_inexact), which 500'd document serialization.
        if isinstance(v, datetime):
            return v.date()
        return v


class SubmitDocumentRequest(BaseModel):
    mentor_id: Optional[int] = None


class ReviewRequest(BaseModel):
    action: ReviewActionEnum
    comment: Optional[str] = None
    inline_comments: Optional[List[Dict]] = []


# ── Access Keys ────────────────────────────────────────────────────────────


class GenerateKeyRequest(BaseModel):
    project_ids: List[str] = Field(..., min_length=1)
    company_id: Optional[str] = None  # Auto-resolved from org if not provided
    scope_label: Optional[str] = None
    recipient_email: Optional[EmailStr] = None
    recipient_name: Optional[str] = None
    ttl_days: int = Field(default=90, ge=1, le=365)
    max_uses: Optional[int] = None
    is_onboarding_key: bool = False
    notes: Optional[str] = None
    send_email: bool = True


class KTKeyOut(BaseModel):
    id: str
    key_prefix: str
    scope_label: Optional[str]
    company_id: str
    project_ids: List[str]
    recipient_name: Optional[str] = None
    recipient_email: Optional[str]
    expires_at: Optional[datetime]
    use_count: int
    max_uses: Optional[int]
    # Computed for the UI (were missing → 'undefined/100', 'System Account',
    # and every key showing 'Revoked/Inactive').
    uses_remaining: Optional[int] = None  # None = unlimited
    is_active: bool = True
    is_onboarding_key: bool
    created_at: datetime
    revoked_at: Optional[datetime]
    last_used_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)


class KTKeyWithRaw(KTKeyOut):
    raw_key: str  # Returned ONCE on creation only


# ── Chat ───────────────────────────────────────────────────────────────────


class KTChatStartRequest(BaseModel):
    # For internal users (JWT) — provide project_ids explicitly
    project_ids: Optional[List[str]] = None
    company_id: Optional[str] = None


class KTChatMessageRequest(BaseModel):
    session_id: str
    message: str = Field(..., min_length=1, max_length=4000)
    stream: bool = False


class KTChatFeedbackRequest(BaseModel):
    message_id: str
    feedback: int = Field(..., ge=-1, le=1)
    note: Optional[str] = None


class KTSourceMetadata(BaseModel):
    doc_id: str
    doc_title: str
    doc_type: str
    project_name: str
    date_range: Optional[str]
    excerpt: str
    relevance_score: float


class KTChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: List[KTSourceMetadata] = []
    confidence_score: Optional[float]
    was_answered: Optional[bool]
    latency_ms: Optional[int]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Insights ───────────────────────────────────────────────────────────────


class KTProjectInsightsOut(BaseModel):
    project_id: str
    project_name: str
    company_id: str
    total_docs: int
    approved_docs: int
    ingested_docs: int
    pending_docs: int
    quality_avg: Optional[float]
    contributor_count: int
    top_queried_topics: List[Dict]
    unanswered_count: int
    last_activity_at: Optional[datetime]


class KTCompanyInsightsOut(BaseModel):
    health_score: float
    score_trend: float
    coverage_score: float
    freshness_score: float
    depth_score: float
    engagement_score: float
    contribution_score: float
    handoff_score: float
    total_docs: int
    ingested_docs: int
    total_projects: int
    covered_projects: int
    total_queries: int
    unanswered_queries: int
    active_contributors: int
    at_risk_users: int
    stale_docs: int
    top_contributors: List[Dict]
    knowledge_gaps: List[Dict]
    domain_coverage: Dict[str, int]


class KTHandoffInitiateRequest(BaseModel):
    departing_user_id: int
    company_id: str
    receiving_user_id: Optional[int] = None
    mentor_id: Optional[int] = None
    departure_date: Optional[date] = None
    notes: Optional[str] = None
    handoff_type: str = "senior_to_junior"  # senior_to_junior | departure | cross_team | project_reassignment


class KTOnboardingBundleRequest(BaseModel):
    project_id: str
    company_id: str
    new_user_id: Optional[int] = None
    ttl_days: int = 30


# ── Attachments ────────────────────────────────────────────────────────────


class KTAttachmentPresignRequest(BaseModel):
    filename: str = Field(..., max_length=255)
    content_type: str = Field(
        ...,
        pattern=r"^(application/pdf|application/msword|application/vnd\.openxmlformats-officedocument\.wordprocessingml\.document|text/plain|text/csv|image/.*|application/json)$",
    )
    file_size_bytes: Optional[int] = Field(default=None, le=52428800)  # Max 50MB


class KTAttachmentRegisterRequest(BaseModel):
    filename: str
    s3_key: str
    file_type: Optional[str] = None
    file_size: Optional[int] = None


class KTAttachmentOut(BaseModel):
    id: str
    document_id: str
    filename: str
    file_type: str
    file_size: int
    download_url: Optional[str] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
