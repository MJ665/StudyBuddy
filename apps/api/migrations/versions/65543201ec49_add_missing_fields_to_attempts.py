"""Add missing fields to attempts

Revision ID: 65543201ec49
Revises: fb40b1fcc94e
Create Date: 2026-07-06 17:03:32.182755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = '65543201ec49'
down_revision: Union[str, Sequence[str], None] = 'fb40b1fcc94e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('attempts', sa.Column('user_name', sa.String(length=255), nullable=True))
    op.add_column('attempts', sa.Column('time_taken', sa.Integer(), nullable=True))
    op.add_column('attempts', sa.Column('descriptive_answers', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('attempts', 'descriptive_answers')
    op.drop_column('attempts', 'time_taken')
    op.drop_column('attempts', 'user_name')
