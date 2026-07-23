"""DROP THE WHOLE DATABASE and re-initialize it from zero, then seed operators.

    python scripts/reset_and_seed.py            # prompts for confirmation
    python scripts/reset_and_seed.py --yes      # non-interactive (CI / scripted)

Sequence:
  1. CREATE EXTENSION vector           (needed before the Vector columns exist)
  2. Base.metadata.drop_all()          (wipe every table — full zero state)
  3. Base.metadata.create_all()        (rebuild the entire schema)
  4. idempotent ALTERs                 (nullable password_pattern, tz-aware tokens)
  5. ensure_system()                   (Platform Admin + L&D Admin + seed org)

The seeded identities and org come entirely from .env / config
(APP_ADMIN_EMAIL/PASSWORD, LD_ADMIN_EMAIL/PASSWORD, SEED_ORG_NAME/SLUG), so this
is the single source of truth for "database initialized from zero".
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from database import Base, engine

# Import every model module so Base.metadata knows the full schema.
import models  # noqa: F401  (package __init__ registers the core tables)
from modules.org.models import OrgUnit, UserOrgRole  # noqa: F401
from modules.kt.models import KTDocumentChunk  # noqa: F401


def reset_and_seed() -> None:
    print("💣 Dropping ALL tables and re-initializing from zero...")

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.drop_all(bind=engine)
    print("   ✔ all tables dropped")

    Base.metadata.create_all(bind=engine)
    print("   ✔ schema recreated")

    with engine.begin() as conn:
        # Group-pattern login is retired: patterns are never written.
        conn.execute(
            text("ALTER TABLE groups ALTER COLUMN password_pattern DROP NOT NULL")
        )
        # Reset tokens are written tz-aware via asyncpg.
        conn.execute(
            text(
                "ALTER TABLE password_reset_tokens "
                "ALTER COLUMN expires_at TYPE TIMESTAMPTZ "
                "USING expires_at AT TIME ZONE 'UTC'"
            )
        )
    print("   ✔ idempotent ALTERs applied")

    from ensure_system_identity import ensure_system

    ensure_system()
    print("✅ Database initialized from zero and seeded.")


if __name__ == "__main__":
    if "--yes" not in sys.argv:
        ans = input(
            "This DROPS EVERY TABLE in the configured DATABASE_URL. Type 'DROP' to continue: "
        )
        if ans.strip() != "DROP":
            print("Aborted.")
            sys.exit(1)
    reset_and_seed()
