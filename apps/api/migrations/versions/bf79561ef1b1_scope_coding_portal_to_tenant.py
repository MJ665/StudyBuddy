"""scope coding portal to tenant

Revision ID: bf79561ef1b1
Revises: f80b3dc1cc37
Create Date: 2026-07-22

The coding portal was the last product surface with NO tenancy: `coding_questions`
and `coding_attempts` had no tenant column at all, exactly where `question_banks`
and `attempts` were before e5f5c12f133e. Two of its endpoints were also completely
unauthenticated.

Same split as the quiz side:
  * coding_questions = authored CONTENT -> super_organization_id (shared across the
    customer's business units)
  * coding_attempts  = LEARNER data     -> organization_id only

Hand-written and idempotent; all columns nullable so scoping helpers fail closed on
anything that cannot be attributed.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "bf79561ef1b1"
down_revision: Union[str, Sequence[str], None] = "f80b3dc1cc37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLS = {
    "coding_questions": [
        ("organization_id", "ix_coding_questions_organization_id"),
        ("super_organization_id", "ix_coding_questions_super_organization_id"),
    ],
    "coding_attempts": [("organization_id", "ix_coding_attempts_organization_id")],
}


def _insp(bind):
    return sa.inspect(bind)


def upgrade() -> None:
    bind = op.get_bind()
    for table, cols in COLS.items():
        if not _insp(bind).has_table(table):
            continue
        existing = {c["name"] for c in _insp(bind).get_columns(table)}
        indexes = {i["name"] for i in _insp(bind).get_indexes(table)}
        for col, idx in cols:
            if col not in existing:
                op.add_column(table, sa.Column(col, sa.Integer(), nullable=True))
            if idx not in indexes:
                op.create_index(idx, table, [col])

    # Backfill questions from their creator's organization.
    op.execute(
        """
        UPDATE coding_questions cq
        SET organization_id = u.organization_id
        FROM users u
        WHERE cq.created_by = u.id
          AND cq.organization_id IS NULL
          AND u.organization_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE coding_questions cq
        SET super_organization_id = o.super_organization_id
        FROM organizations o
        WHERE cq.organization_id = o.id
          AND cq.super_organization_id IS NULL
          AND o.super_organization_id IS NOT NULL
        """
    )
    # Attempts follow the attempting user; fall back to the question.
    op.execute(
        """
        UPDATE coding_attempts ca
        SET organization_id = u.organization_id
        FROM users u
        WHERE ca.user_id = u.id
          AND ca.organization_id IS NULL
          AND u.organization_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE coding_attempts ca
        SET organization_id = cq.organization_id
        FROM coding_questions cq
        WHERE ca.coding_question_id = cq.id
          AND ca.organization_id IS NULL
          AND cq.organization_id IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table, cols in COLS.items():
        if not _insp(bind).has_table(table):
            continue
        indexes = {i["name"] for i in _insp(bind).get_indexes(table)}
        existing = {c["name"] for c in _insp(bind).get_columns(table)}
        for col, idx in cols:
            if idx in indexes:
                op.drop_index(idx, table_name=table)
            if col in existing:
                op.drop_column(table, col)
