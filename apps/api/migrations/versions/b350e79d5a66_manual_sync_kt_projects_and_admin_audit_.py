"""manual_sync_kt_projects_and_admin_audit_log

Revision ID: b350e79d5a66
Revises: 9a8b7c6d5e4f
Create Date: 2026-06-12 14:04:58.315278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b350e79d5a66'
down_revision: Union[str, Sequence[str], None] = '9a8b7c6d5e4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE kt_projects ADD COLUMN IF NOT EXISTS organization_id INTEGER DEFAULT 1")
    op.execute("ALTER TABLE kt_projects ADD COLUMN IF NOT EXISTS group_id INTEGER")
    op.execute("ALTER TABLE admin_audit_log ADD COLUMN IF NOT EXISTS actor_role VARCHAR(50)")
    op.execute("ALTER TABLE admin_audit_log ADD COLUMN IF NOT EXISTS resource_id INTEGER")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE kt_projects DROP COLUMN IF EXISTS organization_id")
    op.execute("ALTER TABLE kt_projects DROP COLUMN IF EXISTS group_id")
    op.execute("ALTER TABLE admin_audit_log DROP COLUMN IF EXISTS actor_role")
    op.execute("ALTER TABLE admin_audit_log DROP COLUMN IF EXISTS resource_id")
