"""merge kt language orphan branch into main chain

Revision ID: 53b070e9cbee
Revises: 001_add_kt_language, d887cd121a07
Create Date: 2026-07-21 22:59:29.788667

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '53b070e9cbee'
down_revision: Union[str, Sequence[str], None] = ('001_add_kt_language', 'd887cd121a07')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
