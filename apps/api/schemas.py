from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class AIResponseEnvelope(BaseModel):
    ai_generated: bool
    fallback_reason: Optional[str] = None
    data: Any
    generated_at: Optional[str] = None


class GroupCreate(BaseModel):
    name: str
    password_pattern: str


class GroupRegisterAdmin(BaseModel):
    name: str
    password_pattern: str
    admin_name: str
    admin_email: str
    batch_id: int


class UserCreate(BaseModel):
    email: str
    full_name: str
    group_id: int
    role: str = "Member"
    member_id: Optional[str] = None
    password: Optional[str] = None


class LoginRequest(BaseModel):
    """Email-first login — individual credentials only.

    The legacy {group_id, full_name} shape is retired (Phase 6); the fields
    remain optional-and-ignored so old clients receive the 422 guidance from
    the handler instead of a schema-level validation wall.
    """

    password: str
    email: EmailStr | None = None
    group_id: int | None = None
    full_name: str | None = None


class SuperAdminLogin(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., max_length=72)


class CourseCreate(BaseModel):
    name: str
    group_id: Optional[int] = None


# ------------- Bank Schemas -------------
class AssignmentCreate(BaseModel):
    target_type: str  # "group" | "batch" | "vertical"
    target_id: int
    bank_id: Optional[int] = None
    coding_question_id: Optional[int] = None
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    max_attempts: Optional[int] = None
    passing_score_percent: Optional[int] = None
    lock_after_due: bool = False
    concept_tags: Optional[List[str]] = []

    @field_validator("due_date")
    @classmethod
    def validate_future_date(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v and v.replace(tzinfo=None) <= datetime.now():
            raise ValueError("due_date must be in the future")
        return v


class AssignmentUpdate(BaseModel):
    due_date: Optional[datetime] = None
    instructions: Optional[str] = None
    max_attempts: Optional[int] = None
    passing_score_percent: Optional[int] = None
    lock_after_due: Optional[bool] = None
    is_active: Optional[bool] = None


class QuestionCreate(BaseModel):
    question: str
    options: List[str]
    answer: str
    difficulty: Optional[str] = None
    user_description: Optional[str] = ""
    has_code: bool = False
    code_language: Optional[str] = None
    concept_tags: Optional[List[str]] = []


class QuestionBankCreate(BaseModel):
    name: str
    course_id: Optional[int] = None
    sprint_name: Optional[str] = ""
    chapter: Optional[str] = ""
    difficulty: Optional[str] = "Medium"
    created_by: Optional[int] = None
    description: Optional[str] = ""
    time_per_question: int = 30
    max_questions: Optional[int] = None
    show_timer: bool = True
    shuffle: bool = True
    allow_descriptive: bool = True
    quick_references: Optional[List[dict]] = None
    bank_type: Optional[str] = "Standard"
    questions: List[QuestionCreate]


class QuestionResponse(BaseModel):
    id: int
    question: str
    options: Any
    difficulty: Optional[str] = None
    user_description: Optional[str] = ""
    has_code: bool = False
    code_language: Optional[str] = None
    # Multi-type engine (additive; defaults keep legacy MCQ rows working). No
    # answer/correct_options here — never leak the key to the candidate.
    question_type: str = "mcq_single"
    content_format: str = "text"
    points: int = 1
    media_urls: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class AttemptSubmit(BaseModel):
    bank_id: int
    user_name: str
    user_id: Optional[int] = None
    time_taken: int
    question_ids: List[int]
    user_answers: List[str]
    user_notes: List[str]
    is_anonymous: bool = False  # L&D: toggle anonymous submission


class DescriptiveAnswerItem(BaseModel):
    """Strict structure for descriptive_answers JSONB field."""

    question_id: int
    question_text: str
    options: List[Any]
    user_answer: str
    correct_answer: str
    is_correct: bool
    note: str
    weighted_points: Optional[float] = 1.0


class CreateResourceRequest(BaseModel):
    file_name: str
    group_id: int
    user_id: int
    description: Optional[str] = ""
    category: Optional[str] = "General"


class RoleUpdate(BaseModel):
    role: str


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    password_pattern: Optional[str] = None
    batch_id: Optional[int] = None
    is_active: Optional[bool] = None


# ------------- Coding Practice Schemas -------------
# ------------- Test Case Schemas -------------
class CodingTestCaseCreate(BaseModel):
    input_data: str
    expected_output: str
    is_public: bool = True
    weight: Optional[int] = 1
    is_active: bool = True


# ------------- Coding Practice Schemas -------------
class CodingQuestionCreate(BaseModel):
    course_id: Optional[int] = None
    title: str
    description: str
    language: str
    expected_approach: Optional[str] = None
    sample_solution: str
    evaluation_criteria: List[str]
    concept_tags: Optional[List[str]] = None
    difficulty: str = "Medium"
    hint_1: Optional[str] = None
    hint_2: Optional[str] = None
    hint_3: Optional[str] = None
    max_hints_allowed: int = 3
    initial_code: Optional[str] = None
    time_limit_minutes: Optional[int] = None
    test_cases: Optional[List[CodingTestCaseCreate]] = []


class CodingQuestionResponse(BaseModel):
    id: int
    title: str
    description: str
    language: str
    difficulty: str
    initial_code: Optional[str] = None
    course_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CodingAttemptCreate(BaseModel):
    coding_question_id: int
    submitted_code: str = Field(..., max_length=50000)
    language: str
    time_spent_seconds: Optional[int] = 0


class CodingAttemptResponse(BaseModel):
    id: int
    coding_question_id: int
    user_id: int
    submitted_code: str
    language: str
    is_correct: bool
    score: int
    ai_feedback: Optional[str] = None
    ai_suggestions: Optional[str] = None
    rubric_json: Optional[str] = None
    mentor_score: Optional[int] = None
    mentor_feedback: Optional[str] = None
    is_verified: bool = False
    time_spent_seconds: int
    hints_used: int
    attempted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CodingHintRequest(BaseModel):
    coding_question_id: int
    hint_level: int  # 1, 2, or 3
    user_code: Optional[str] = None
    language: Optional[str] = "python"


class CodingHintResponse(BaseModel):
    hint_text: str
    hint_level: int
    from_cache: bool = False


class CodingEvaluationRequest(BaseModel):
    coding_question_id: int
    code_submitted: str = Field(..., max_length=5000)


class CodingTestCase(BaseModel):
    id: int
    coding_question_id: int
    input_data: str
    expected_output: str
    is_public: bool
    weight: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class BulkUserItem(BaseModel):
    full_name: str
    email: str
    role: str = "Member"
    member_id: Optional[str] = None
    password: Optional[str] = None


class BulkUserCreate(BaseModel):
    users: List[BulkUserItem] = Field(..., max_length=50)
    password_pattern: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    email: str
    group_id: int


class ResetPasswordRequest(BaseModel):
    email: str
    group_id: int
    otp_code: str
    new_password: str = Field(..., max_length=72)


# ------------- Profile & Scoping Schemas -------------
class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    profile_photo_url: Optional[str] = None
    intro_video_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    leetcode_url: Optional[str] = None
    codolio_url: Optional[str] = None
    expertise_json: Optional[Any] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    group_id: int
    role: str
    member_id: Optional[str] = None
    profile_photo_url: Optional[str] = None
    intro_video_url: Optional[str] = None
    github_url: Optional[str] = None
    linkedin_url: Optional[str] = None
    leetcode_url: Optional[str] = None
    codolio_url: Optional[str] = None
    streak_count: int
    expertise_json: Optional[Any] = None
    vertical_id: Optional[int] = None
    department_id: Optional[int] = None
    last_login: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationCreate(BaseModel):
    name: str
    slug: str


class DepartmentCreate(BaseModel):
    name: str
    description: Optional[str] = None


class VerticalCreate(BaseModel):
    name: str
    description: Optional[str] = None


class BatchCreate(BaseModel):
    name: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class VerticalUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class BatchUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class InterventionRequest(BaseModel):
    user_ids: List[int]
    message: str


# ------------- Question Report Schemas -------------
class QuestionReportCreate(BaseModel):
    question_id: int
    reason: str  # "wrong_answer" | "typo" | "unclear" | "duplicate" | "other"
    comment: Optional[str] = None


class QuestionReportResponse(BaseModel):
    id: int
    question_id: int
    reporter_id: int
    reason: str
    comment: Optional[str]
    is_resolved: bool
    resolved_by: Optional[int]
    resolved_at: Optional[datetime]
    created_at: datetime

    question_text: Optional[str] = None
    reporter_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., max_length=72)


class SessionResponse(BaseModel):
    id: int
    created_at: datetime
    expires_at: datetime
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class BulkActionRequest(BaseModel):
    user_ids: List[int]
    action: str  # "deactivate" | "activate" | "delete"


class AIEnvelope(BaseModel):
    """
    STRAT-AI-FALLBACK: Standardized response envelope for all AI interactions.
    Enables transparency when the system falls back to cached or pre-generated content.
    """

    # `model_used` collides with Pydantic's protected `model_` namespace;
    # the field name is part of the API contract, so silence the check.
    model_config = ConfigDict(protected_namespaces=())

    content: Any
    is_fallback: bool = False
    model_used: str
    cached_at: Optional[datetime] = None
    execution_time_ms: int = 0


class CommentRequest(BaseModel):
    content: str


class ProfileCommentResponse(BaseModel):
    id: int
    content: str
    created_at: datetime
    author_name: str
    author_initials: str
    author_email_prefix: str
    author_photo_url: Optional[str] = None
