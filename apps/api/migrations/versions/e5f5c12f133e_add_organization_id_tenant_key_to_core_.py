"""add organization_id tenant key to core content tables

Revision ID: e5f5c12f133e
Revises: 53b070e9cbee
Create Date: 2026-07-21 23:06:37.326128

Multi-tenant isolation could not be enforced because the core content tables had
no tenant column at all. Ownership was only implicit, via
`user -> group -> batch -> vertical -> department -> organization`, and no query
actually walked that chain — so a mentor could read another organization's
gradebook, exam attempts and reports by guessing an id.

This adds a denormalized `organization_id` to those tables and backfills it from
the existing hierarchy. Written BY HAND rather than with `--autogenerate`: an
autogenerate in this project once emitted `drop_table` for 54 tables (see the
neutralized revision d887cd121a07).

The column stays NULLABLE. Rows that cannot be attributed to an organization are
left NULL, and the scoping helpers treat NULL as "deny" rather than "match all",
so an un-backfillable row fails closed instead of leaking into every tenant.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f5c12f133e"
down_revision: Union[str, Sequence[str], None] = "53b070e9cbee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# table -> index name
TARGETS = {
    "users": "ix_users_organization_id",
    "question_banks": "ix_question_banks_organization_id",
    "questions": "ix_questions_organization_id",
    "attempts": "ix_attempts_organization_id",
    "exam_attempts": "ix_exam_attempts_organization_id",
}


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return True  # nothing to do for a table that doesn't exist here
    return column in {c["name"] for c in insp.get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return True
    return index in {i["name"] for i in insp.get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    for table, index in TARGETS.items():
        if not _has_column(bind, table, "organization_id"):
            op.add_column(table, sa.Column("organization_id", sa.Integer(), nullable=True))
        if not _has_index(bind, table, index):
            op.create_index(index, table, ["organization_id"])

    # ── Backfill, ordered so each step can rely on the previous one ──────────
    # 1. users: department first (most direct), then group -> department.
    op.execute(
        """
        UPDATE users u SET organization_id = d.organization_id
        FROM departments d
        WHERE u.department_id = d.id AND u.organization_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE users u SET organization_id = d.organization_id
        FROM groups g JOIN departments d ON d.id = g.department_id
        WHERE u.group_id = g.id AND u.organization_id IS NULL
        """
    )
    # Groups may reach a department only through batch -> vertical.
    op.execute(
        """
        UPDATE users u SET organization_id = d.organization_id
        FROM groups g
        JOIN batches b ON b.id = g.batch_id
        JOIN verticals v ON v.id = b.vertical_id
        JOIN departments d ON d.id = v.department_id
        WHERE u.group_id = g.id AND u.organization_id IS NULL
        """
    )

    # 2. question_banks: attributed via their creator.
    op.execute(
        """
        UPDATE question_banks qb SET organization_id = u.organization_id
        FROM users u
        WHERE qb.created_by = u.id AND qb.organization_id IS NULL
          AND u.organization_id IS NOT NULL
        """
    )

    # 3. questions inherit their bank's tenant.
    op.execute(
        """
        UPDATE questions q SET organization_id = qb.organization_id
        FROM question_banks qb
        WHERE q.bank_id = qb.id AND q.organization_id IS NULL
          AND qb.organization_id IS NOT NULL
        """
    )

    # 4. attempts: the attempting user is the source of truth, falling back to
    #    the bank when the user row is unattributed.
    op.execute(
        """
        UPDATE attempts a SET organization_id = u.organization_id
        FROM users u
        WHERE a.user_id = u.id AND a.organization_id IS NULL
          AND u.organization_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE attempts a SET organization_id = qb.organization_id
        FROM question_banks qb
        WHERE a.bank_id = qb.id AND a.organization_id IS NULL
          AND qb.organization_id IS NOT NULL
        """
    )

    # 5. exam_attempts: via the user, falling back to the exam (which already
    #    carries organization_id).
    op.execute(
        """
        UPDATE exam_attempts ea SET organization_id = u.organization_id
        FROM users u
        WHERE ea.user_id = u.id AND ea.organization_id IS NULL
          AND u.organization_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE exam_attempts ea SET organization_id = e.organization_id
        FROM exams e
        WHERE ea.exam_id = e.id AND ea.organization_id IS NULL
          AND e.organization_id IS NOT NULL
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table, index in TARGETS.items():
        insp = sa.inspect(bind)
        if not insp.has_table(table):
            continue
        if index in {i["name"] for i in insp.get_indexes(table)}:
            op.drop_index(index, table_name=table)
        if "organization_id" in {c["name"] for c in insp.get_columns(table)}:
            op.drop_column(table, "organization_id")
