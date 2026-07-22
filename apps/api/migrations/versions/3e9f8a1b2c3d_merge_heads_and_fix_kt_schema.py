"""merge_heads_and_fix_kt_schema

Revision ID: 3e9f8a1b2c3d
Revises: 8a2b3c4d5e6f
Create Date: 2026-05-13 21:42:08.188214

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "3e9f8a1b2c3d"
down_revision: Union[str, Sequence[str], None] = ("4acdbf1cd2c0", "8a2b3c4d5e6f")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add company_id to kt_projects (nullable for now)
    op.add_column(
        "kt_projects", sa.Column("company_id", sa.String(length=36), nullable=True)
    )
    op.create_foreign_key(
        "fk_kt_projects_company",
        "kt_projects",
        "kt_companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 2. Add missing columns to kt_documents
    op.add_column(
        "kt_documents", sa.Column("company_id", sa.String(length=36), nullable=True)
    )
    op.add_column(
        "kt_documents",
        sa.Column("co_author_ids", postgresql.ARRAY(sa.Integer()), nullable=True),
    )
    op.add_column(
        "kt_documents",
        sa.Column("co_author_emails", postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.create_foreign_key(
        "fk_kt_documents_company",
        "kt_documents",
        "kt_companies",
        ["company_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_kt_documents_company", "kt_documents", type_="foreignkey")
    op.drop_column("kt_documents", "co_author_emails")
    op.drop_column("kt_documents", "co_author_ids")
    op.drop_column("kt_documents", "company_id")

    op.drop_constraint("fk_kt_projects_company", "kt_projects", type_="foreignkey")
    op.drop_column("kt_projects", "company_id")
