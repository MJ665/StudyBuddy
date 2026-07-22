"""Add language column to kt_documents table.

Revision ID: 001_add_kt_language
Revises:
Create Date: 2026-07-13 12:57:00.000000

NOTE: this revision was authored as a SEPARATE ROOT (`down_revision = None`),
which is why the project had two alembic heads. It is now joined back into the
main chain by the merge revision, but because it is a root, alembic gives no
ordering guarantee relative to the revision that creates `kt_documents` on a
fresh database. The column was also applied by hand to the existing production
database before this ever ran through alembic.

Both hazards are handled by making the operation idempotent and table-aware
rather than by rewriting the revision graph.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_add_kt_language"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(bind, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(bind, table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(bind).get_columns(table)}


def upgrade():
    bind = op.get_bind()
    if not _has_table(bind, "kt_documents"):
        # This root revision can be ordered before kt_documents exists; the table's
        # own definition already carries `language`, so there is nothing to do.
        return
    if _has_column(bind, "kt_documents", "language"):
        return
    op.add_column(
        "kt_documents",
        sa.Column("language", sa.String(10), server_default="en", nullable=False),
    )


def downgrade():
    bind = op.get_bind()
    if _has_table(bind, "kt_documents") and _has_column(bind, "kt_documents", "language"):
        op.drop_column("kt_documents", "language")
