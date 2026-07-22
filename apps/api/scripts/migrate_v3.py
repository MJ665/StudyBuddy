import os
import sys

# Unified Path Logic: Ensure apps/api and root are reachable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.append(BASE_DIR)

import logging  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402

from database import DATABASE_URL, Base  # noqa: E402
from sqlalchemy import create_engine, inspect, text  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migration")


def check_and_add_columns():
    """
    Additive migration script to ensure V3 enterprise schema consistency.
    This script is safe to run multiple times (idempotent).
    """
    if not DATABASE_URL:
        logger.warning("DATABASE_URL not set. Skipping migration.")
        return

    # Use a sync engine for schema inspection/modification
    sync_url = DATABASE_URL
    if sync_url.startswith("postgresql+asyncpg://"):
        sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://")

    engine = create_engine(sync_url)
    inspector = inspect(engine)

    # 1. Ensure all core tables exist
    logger.info("Verifying table existence...")
    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        # 2. Additive Column Checks

        # Table: groups
        columns_groups = [c["name"] for c in inspector.get_columns("groups")]
        if "is_active" not in columns_groups:
            logger.info("Adding 'is_active' to 'groups' table...")
            conn.execute(
                text(
                    "ALTER TABLE groups ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )
        if "batch_id" not in columns_groups:
            logger.info("Adding 'batch_id' to 'groups' table...")
            conn.execute(
                text(
                    "ALTER TABLE groups ADD COLUMN batch_id INTEGER REFERENCES batches(id)"
                )
            )

        # Table: users
        columns_users = [c["name"] for c in inspector.get_columns("users")]
        if "role" not in columns_users:
            logger.info("Adding 'role' to 'users' table...")
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'Member' NOT NULL"
                )
            )
        if "is_active" not in columns_users:
            logger.info("Adding 'is_active' to 'users' table...")
            conn.execute(
                text(
                    "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )
        if "password_hash" not in columns_users:
            logger.info("Adding 'password_hash' to 'users' table...")
            conn.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")
            )
        if "last_login" not in columns_users:
            logger.info("Adding 'last_login' to 'users' table...")
            conn.execute(
                text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP WITH TIME ZONE")
            )
        if "member_id" not in columns_users:
            logger.info("Adding 'member_id' to 'users' table...")
            conn.execute(text("ALTER TABLE users ADD COLUMN member_id VARCHAR(50)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_users_member_id ON users (member_id)"
                )
            )
        # Phase 2: Profile expansion columns
        user_profile_cols = [
            "profile_photo_url",
            "intro_video_url",
            "github_url",
            "linkedin_url",
            "leetcode_url",
            "codolio_url",
            "streak_count",
            "last_active_date",
            "expertise_json",
        ]
        for col in user_profile_cols:
            if col not in columns_users:
                logger.info(f"Adding '{col}' to 'users' table...")
                if col == "streak_count":
                    conn.execute(
                        text(
                            f"ALTER TABLE users ADD COLUMN {col} INTEGER DEFAULT 0 NOT NULL"
                        )
                    )
                elif col == "expertise_json":
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} JSONB"))
                elif col == "last_active_date":
                    conn.execute(
                        text(
                            f"ALTER TABLE users ADD COLUMN {col} TIMESTAMP WITH TIME ZONE"
                        )
                    )
                else:
                    conn.execute(
                        text(f"ALTER TABLE users ADD COLUMN {col} VARCHAR(500)")
                    )

        # Table: question_banks
        columns_banks = [c["name"] for c in inspector.get_columns("question_banks")]
        if "bank_type" not in columns_banks:
            logger.info("Adding 'bank_type' to 'question_banks' table...")
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN bank_type VARCHAR(20) DEFAULT 'practice' NOT NULL"
                )
            )
        if "icon_slug" not in columns_banks:
            logger.info("Adding 'icon_slug' to 'question_banks' table...")
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN icon_slug VARCHAR(50) DEFAULT 'folder' NOT NULL"
                )
            )
        if "is_org_public" not in columns_banks:
            logger.info("Adding 'is_org_public' to 'question_banks' table...")
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN is_org_public BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
        if "course_id" not in columns_banks:
            logger.info("Adding 'course_id' to 'question_banks' table...")
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN course_id INTEGER REFERENCES courses(id)"
                )
            )

        # Table: questions
        columns_questions = [c["name"] for c in inspector.get_columns("questions")]
        if "has_code" not in columns_questions:
            logger.info("Adding 'has_code' to 'questions' table...")
            conn.execute(
                text(
                    "ALTER TABLE questions ADD COLUMN has_code BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
        if "code_language" not in columns_questions:
            logger.info("Adding 'code_language' to 'questions' table...")
            conn.execute(
                text("ALTER TABLE questions ADD COLUMN code_language VARCHAR(30)")
            )
        if "concept_tags" not in columns_questions:
            logger.info("Adding 'concept_tags' to 'questions' table...")
            # For Postgres, use ARRAY[VARCHAR]
            conn.execute(
                text("ALTER TABLE questions ADD COLUMN concept_tags VARCHAR[]")
            )

        # Table: coding_questions
        columns_coding = [c["name"] for c in inspector.get_columns("coding_questions")]
        if "is_org_public" not in columns_coding:
            logger.info("Adding 'is_org_public' to 'coding_questions' table...")
            conn.execute(
                text(
                    "ALTER TABLE coding_questions ADD COLUMN is_org_public BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
        if "initial_code" not in columns_coding:
            logger.info("Adding 'initial_code' to 'coding_questions' table...")
            conn.execute(
                text("ALTER TABLE coding_questions ADD COLUMN initial_code TEXT")
            )

        # Phase 2: question_banks visibility
        if "visibility_scope" not in columns_banks:
            logger.info("Adding 'visibility_scope' to 'question_banks' table...")
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN visibility_scope VARCHAR(20) DEFAULT 'group-private' NOT NULL"
                )
            )
        if "created_by_role" not in columns_banks:
            conn.execute(
                text(
                    "ALTER TABLE question_banks ADD COLUMN created_by_role VARCHAR(20)"
                )
            )
        if "subscriber_groups" not in columns_banks:
            conn.execute(
                text("ALTER TABLE question_banks ADD COLUMN subscriber_groups JSONB")
            )

        # Table: assignments — add assignment_type
        columns_assignments = [c["name"] for c in inspector.get_columns("assignments")]
        if "assignment_type" not in columns_assignments:
            logger.info("Adding 'assignment_type' to 'assignments' table...")
            conn.execute(
                text(
                    "ALTER TABLE assignments ADD COLUMN assignment_type VARCHAR(20) DEFAULT 'quiz' NOT NULL"
                )
            )
        if "visibility_scope" not in columns_assignments:
            conn.execute(
                text(
                    "ALTER TABLE assignments ADD COLUMN visibility_scope VARCHAR(20) DEFAULT 'group' NOT NULL"
                )
            )
        if "created_by_role" not in columns_assignments:
            conn.execute(
                text("ALTER TABLE assignments ADD COLUMN created_by_role VARCHAR(20)")
            )

        # Table: coding_attempts — add leaderboard_eligible
        columns_coding_attempts = [
            c["name"] for c in inspector.get_columns("coding_attempts")
        ]
        if "leaderboard_eligible" not in columns_coding_attempts:
            logger.info("Adding 'leaderboard_eligible' to 'coding_attempts' table...")
            conn.execute(
                text(
                    "ALTER TABLE coding_attempts ADD COLUMN leaderboard_eligible BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )
        if "is_verified" not in columns_coding_attempts:
            conn.execute(
                text(
                    "ALTER TABLE coding_attempts ADD COLUMN is_verified BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
        if "ai_score" not in columns_coding_attempts:
            logger.info("Adding 'ai_score' to 'coding_attempts' table...")
            conn.execute(
                text("ALTER TABLE coding_attempts ADD COLUMN ai_score INTEGER")
            )
        if "criteria_scores" not in columns_coding_attempts:
            logger.info("Adding 'criteria_scores' to 'coding_attempts' table...")
            conn.execute(
                text("ALTER TABLE coding_attempts ADD COLUMN criteria_scores JSONB")
            )
        if "rank_computation" not in columns_coding_attempts:
            conn.execute(
                text("ALTER TABLE coding_attempts ADD COLUMN rank_computation INTEGER")
            )

        # Table: attempts — add is_verified
        columns_attempts = [c["name"] for c in inspector.get_columns("attempts")]
        if "is_daily_challenge" not in columns_attempts:
            logger.info("Adding 'is_daily_challenge' to 'attempts' table...")
            conn.execute(
                text(
                    "ALTER TABLE attempts ADD COLUMN is_daily_challenge BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )
        if "is_verified" not in columns_attempts:
            conn.execute(
                text(
                    "ALTER TABLE attempts ADD COLUMN is_verified BOOLEAN DEFAULT FALSE NOT NULL"
                )
            )

        # Table: notifications — add expires_at
        columns_notifs = [c["name"] for c in inspector.get_columns("notifications")]
        if "expires_at" not in columns_notifs:
            logger.info("Adding 'expires_at' to 'notifications' table...")
            conn.execute(
                text(
                    "ALTER TABLE notifications ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE"
                )
            )

        # Create email_log table if missing
        existing_tables = inspector.get_table_names()
        if "email_log" not in existing_tables:
            logger.info("Creating 'email_log' table...")
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS email_log (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id),
                    email_type VARCHAR(50) NOT NULL,
                    to_email VARCHAR(255) NOT NULL,
                    sent_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
                    success BOOLEAN DEFAULT TRUE NOT NULL
                )
            """)
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_email_log_user_type ON email_log(user_id, email_type, sent_at)"
                )
            )

        # Create user_bookmarks table if missing
        if "user_bookmarks" not in existing_tables:
            logger.info("Creating 'user_bookmarks' table...")
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS user_bookmarks (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    question_id INTEGER REFERENCES questions(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL
                )
            """)
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_user_bookmarks_user_id ON user_bookmarks(user_id)"
                )
            )

        # Create performance indexes
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_attempts_group_user ON attempts(user_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id)"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"))
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_coding_attempts_user ON coding_attempts(user_id)"
            )
        )

        # Table: organizations
        columns_orgs = [c["name"] for c in inspector.get_columns("organizations")]
        if "is_active" not in columns_orgs:
            logger.info("Adding 'is_active' to 'organizations' table...")
            conn.execute(
                text(
                    "ALTER TABLE organizations ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )

        # Table: departments
        columns_depts = [c["name"] for c in inspector.get_columns("departments")]
        if "is_active" not in columns_depts:
            logger.info("Adding 'is_active' to 'departments' table...")
            conn.execute(
                text(
                    "ALTER TABLE departments ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )

        # Table: verticals
        columns_verts = [c["name"] for c in inspector.get_columns("verticals")]
        if "is_active" not in columns_verts:
            logger.info("Adding 'is_active' to 'verticals' table...")
            conn.execute(
                text(
                    "ALTER TABLE verticals ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"
                )
            )

        # Table: kt_handoffs
        if "kt_handoffs" in inspector.get_table_names():
            columns_handoffs = [c["name"] for c in inspector.get_columns("kt_handoffs")]
            if "handoff_type" not in columns_handoffs:
                logger.info("Adding 'handoff_type' to 'kt_handoffs' table...")
                conn.execute(
                    text(
                        "ALTER TABLE kt_handoffs ADD COLUMN handoff_type VARCHAR(50) DEFAULT 'senior_to_junior' NOT NULL"
                    )
                )

        # 3. Role Migration Consolidation
        logger.info("Consolidating roles (Admin -> GroupAdmin)...")
        conn.execute(text("UPDATE users SET role = 'GroupAdmin' WHERE role = 'Admin'"))
        conn.commit()

        # 4. Critical Seeding: Global L&D Context (ID 0)
        # We use ID 0 for the system-level LDAdmin to match hardcoded JWT context
        logger.info("Verifying Global L&D System Records...")

        # Ensure Global Group exists
        conn.execute(
            text("""
            INSERT INTO groups (id, name, password_pattern, is_active, created_at)
            SELECT 0, 'Global L&D', 'sigmoid@123', TRUE, now()
            WHERE NOT EXISTS (SELECT 1 FROM groups WHERE id = 0)
        """)
        )

        # Ensure LDAdmin User exists
        conn.execute(
            text("""
            INSERT INTO users (id, email, full_name, group_id, role, is_active, created_at)
            SELECT 0, 'admin@studyhub.local', 'L&D SuperAdmin', 0, 'LDAdmin', TRUE, now()
            WHERE NOT EXISTS (SELECT 1 FROM users WHERE id = 0)
        """)
        )
        conn.commit()

    logger.info("Migration check complete.")


if __name__ == "__main__":
    check_and_add_columns()
