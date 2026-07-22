"""add missing company_id columns and fix types

Revision ID: 9a8b7c6d5e4f
Revises: 3e9f8a1b2c3d
Create Date: 2026-05-13 22:05:43.091610

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "9a8b7c6d5e4f"
down_revision: Union[str, Sequence[str], None] = "3e9f8a1b2c3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add company_id to kt_notifications
    op.add_column(
        "kt_notifications", sa.Column("company_id", sa.String(length=36), nullable=True)
    )
    op.create_foreign_key(
        "fk_kt_notifications_company",
        "kt_notifications",
        "kt_companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # Add company_id to kt_handoffs
    op.add_column(
        "kt_handoffs", sa.Column("company_id", sa.String(length=36), nullable=True)
    )
    op.create_foreign_key(
        "fk_kt_handoffs_company",
        "kt_handoffs",
        "kt_companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_kt_handoffs_company", "kt_handoffs", type_="foreignkey")
    op.drop_column("kt_handoffs", "company_id")
    op.drop_constraint(
        "fk_kt_notifications_company", "kt_notifications", type_="foreignkey"
    )
    op.drop_column("kt_notifications", "company_id")
