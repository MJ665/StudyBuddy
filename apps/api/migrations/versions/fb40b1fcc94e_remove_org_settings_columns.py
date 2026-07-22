"""remove_org_settings_columns

Revision ID: fb40b1fcc94e
Revises: b350e79d5a66
Create Date: 2026-07-06 11:53:40.876040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fb40b1fcc94e'
down_revision: Union[str, Sequence[str], None] = 'b350e79d5a66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('groups', 'is_public')
    op.drop_column('groups', 'ai_coaching_enabled')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('groups', sa.Column('is_public', sa.Boolean(), server_default='false', nullable=True))
    op.add_column('groups', sa.Column('ai_coaching_enabled', sa.Boolean(), server_default='true', nullable=True))
