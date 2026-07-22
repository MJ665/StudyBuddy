from typing import List, Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- INFRASTRUCTURE ---
    DATABASE_URL: str = ""
    REDIS_URL: Optional[str] = None
    UPSTASH_REDIS_REST_URL: Optional[str] = None
    UPSTASH_REDIS_REST_TOKEN: Optional[str] = None

    # Vector Database
    UPSTASH_VECTOR_REST_URL: Optional[str] = None
    UPSTASH_VECTOR_REST_TOKEN: Optional[str] = None

    # --- SECURITY (CRITICAL-001) ---
    JWT_SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ADMIN CREDENTIALS
    APP_ADMIN_PASSWORD: str = ""

    # --- CLOUD API CREDENTIALS ---
    GEMINI_API_KEY: Optional[str] = None
    RESEND_API_KEY: Optional[str] = None

    # --- KT PLATFORM (KNOWLEDGE TRANSFER) ---
    HMAC_KEY_SECRET: str = "kt_hmac_access_key_secret_studyhub_2025"
    NEO4J_URI: Optional[str] = None
    NEO4J_USERNAME: Optional[str] = None
    NEO4J_PASSWORD: Optional[str] = None
    NEO4J_INSTANCE: Optional[str] = None

    KEY_DEFAULT_TTL_DAYS: int = 90
    STALE_DOC_THRESHOLD_DAYS: int = 90
    MAX_CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    MAX_RETRIEVAL_RESULTS: int = 20
    RERANK_TOP_K: int = 8

    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_ACCESS_KEY_ID", "AWS_PUBLIC_KEY"),
    )
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("AWS_SECRET_ACCESS_KEY", "AWS_PRIVATE_KEY"),
    )
    AWS_REGION: str = Field(
        default="us-east-1",
        validation_alias=AliasChoices("AWS_REGION", "AWS_REGION_NAME"),
    )
    S3_BUCKET_NAME: Optional[str] = Field(
        default=None, validation_alias=AliasChoices("S3_BUCKET_NAME", "AWS_S3_BUCKET")
    )
    S3_USE_CLOUDFRONT: bool = False
    CLOUDFRONT_DOMAIN: Optional[str] = None

    @property
    def S3_PUBLIC_URL_BASE(self) -> str:
        if self.S3_USE_CLOUDFRONT and self.CLOUDFRONT_DOMAIN:
            return f"https://{self.CLOUDFRONT_DOMAIN}"
        return f"https://{self.S3_BUCKET_NAME}.s3.{self.AWS_REGION}.amazonaws.com"

    # --- APPLICATION SETTINGS ---
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    APP_TIMEZONE: str = "Asia/Kolkata"
    PRIMARY_AI_MODEL: str = "gemini-2.5-flash"
    SECONDARY_AI_MODEL: str = "gemini-2.5-flash"
    FAST_AI_MODEL: str = "gemini-2.5-flash"
    APP_VERSION: str = "3.1.0"
    ALLOWED_ORIGINS: List[str] = []
    ENFORCE_HTTPS: bool = False
    RESEND_FROM_EMAIL: str = "StudyHub L&D <noreply@email.mj665.in>"

    # --- SANDBOX ---
    JUDGE0_API_URL: Optional[str] = None
    JUDGE0_API_KEY: Optional[str] = None

    # --- DYNAMIC ENUMS (STRAT-102) ---
    SUPPORTED_LANGUAGES: List[dict] = [
        {"id": "python", "name": "Python 3", "monaco_language": "python"},
        {"id": "javascript", "name": "JavaScript", "monaco_language": "javascript"},
        {"id": "java", "name": "Java", "monaco_language": "java"},
        {"id": "cpp", "name": "C++", "monaco_language": "cpp"},
        {"id": "bash", "name": "Bash", "monaco_language": "shell"},
    ]
    DIFFICULTY_LEVELS: List[str] = ["Easy", "Medium", "Hard", "Mixed"]
    RESOURCE_CATEGORIES: List[str] = [
        "Video",
        "Document",
        "Code Sample",
        "Link",
        "Assignment",
    ]
    AI_LANGUAGES: List[str] = ["English", "Hindi", "Spanish", "French", "German"]
    LEARNER_LEVELS: List[str] = ["Beginner", "Intermediate", "Advanced"]
    PASSWORD_PATTERNS: List[str] = [
        "<name>sigmoid@123",
        "<name>@2026",
        "sigmoid@<year>",
    ]
    NOTIFICATION_TYPES: List[dict] = [
        {
            "id": "resource_shared",
            "icon": "BookOpen",
            "color": "text-blue-400",
            "bg": "bg-blue-500/10",
        },
        {
            "id": "quiz_assigned",
            "icon": "Star",
            "color": "text-amber-400",
            "bg": "bg-amber-500/10",
        },
        {
            "id": "assignment_assigned",
            "icon": "AlertTriangle",
            "color": "text-orange-400",
            "bg": "bg-orange-500/10",
        },
        {
            "id": "achievement",
            "icon": "Trophy",
            "color": "text-yellow-400",
            "bg": "bg-yellow-500/10",
        },
        {
            "id": "code_feedback",
            "icon": "Code2",
            "color": "text-indigo-400",
            "bg": "bg-indigo-500/10",
        },
        {
            "id": "mentor_comment",
            "icon": "MessageSquare",
            "color": "text-purple-400",
            "bg": "bg-purple-500/10",
        },
        {
            "id": "ai_suggestion",
            "icon": "Sparkles",
            "color": "text-emerald-400",
            "bg": "bg-emerald-500/10",
        },
        {
            "id": "system",
            "icon": "Info",
            "color": "text-slate-400",
            "bg": "bg-slate-500/10",
        },
    ]

    model_config = SettingsConfigDict(
        env_file=[".env", "../../.env"], env_file_encoding="utf-8", extra="ignore"
    )

    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    def validate_production_config(self):
        if self.is_production():
            missing = []
            if not self.JWT_SECRET_KEY:
                missing.append("JWT_SECRET_KEY")
            if not self.APP_ADMIN_PASSWORD:
                missing.append("APP_ADMIN_PASSWORD")
            if not self.DATABASE_URL:
                missing.append("DATABASE_URL")
            if not self.S3_BUCKET_NAME:
                missing.append("S3_BUCKET_NAME")
            if not self.GEMINI_API_KEY:
                missing.append("GEMINI_API_KEY")
            if not self.ALLOWED_ORIGINS and not self.DEBUG:
                missing.append("ALLOWED_ORIGINS")

            if missing:
                raise ValueError(
                    f"CRITICAL: Missing required production configuration keys: {', '.join(missing)}"
                )


# Singleton instance for platform-wide access
settings = Settings()
settings.validate_production_config()
