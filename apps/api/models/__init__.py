from .ai_cache import AICache  # noqa: F401
from .ai_usage import AIUsage  # noqa: F401
from .assignment import Assignment, AssignmentCompletion  # noqa: F401
from .attempt import Attempt, CodingAttempt, CodingHint  # noqa: F401
from .audit import AdminAuditLog, EmailLog  # noqa: F401
from .auth import (
    Group,  # noqa: F401
    MentorGroupAssignment,  # noqa: F401
    PasswordResetToken,  # noqa: F401
    RefreshToken,  # noqa: F401
    User,  # noqa: F401
    UserRole,  # noqa: F401
)
from .bank import Question, QuestionBank  # noqa: F401
from .bookmark import UserBookmark  # noqa: F401
from .challenge import DailyChallenge  # noqa: F401
from .coding import CodingHintCache, CodingQuestion, CodingTestCase  # noqa: F401
from .course import Course, GroupCourseSubscription, VerticalCourse  # noqa: F401
from .discussion import QuestionDiscussion  # noqa: F401
from .exam import Exam, ExamAttempt, ProctorEvent  # noqa: F401
from .kt_model import *  # noqa: F403
from .learning_path import UserLearningPath  # noqa: F401
from .mentor import MentorComment  # noqa: F401
from .notification import Notification  # noqa: F401
from .org import (  # noqa: F401
    Batch,
    Department,
    Organization,
    SuperOrganization,
    Vertical,
)
from .profile import ProfileComment  # noqa: F401
from .report import QuestionReport  # noqa: F401
from .resource import Resource, ResourceComment  # noqa: F401
from .system import SystemTaskStatus  # noqa: F401
from .job import BackgroundJob, JobStatus  # noqa: F401

# ── Target-architecture models (modular monolith, Phase 1+) ──────────────────
# New entities live under modules/*/models.py; imported here so
# Base.metadata (and main.py's create_all) sees them.
from modules.org.models import OrgUnit, UserOrgRole  # noqa: F401
from modules.kt.models import KTDocumentChunk  # noqa: F401
