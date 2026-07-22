"""add durable background_jobs queue

Revision ID: f80b3dc1cc37
Revises: c23a9fbe9c69
Create Date: 2026-07-22

KT ingestion and transactional email ran on FastAPI BackgroundTasks — in-process,
so a deploy or crash mid-flight discarded the work silently, with no record and no
retry. This table is the durable record: a job is written in the SAME transaction
as the row it refers to, claimed with FOR UPDATE SKIP LOCKED (safe across
replicas), retried with exponential backoff, and reclaimed on startup if the
worker holding it died.

Written by hand, idempotent (see the neutralized revision d887cd121a07 for why
--autogenerate is not used in this project).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f80b3dc1cc37"
down_revision: Union[str, Sequence[str], None] = "c23a9fbe9c69"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "background_jobs"


def _insp(bind):
    return sa.inspect(bind)


def upgrade() -> None:
    bind = op.get_bind()
    if _insp(bind).has_table(TABLE):
        return

    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_background_jobs_job_type", TABLE, ["job_type"])
    op.create_index("ix_background_jobs_status", TABLE, ["status"])
    op.create_index("ix_background_jobs_run_after", TABLE, ["run_after"])
    # The claim query filters on exactly this pair.
    op.create_index("ix_background_jobs_claim", TABLE, ["status", "run_after"])


def downgrade() -> None:
    bind = op.get_bind()
    if _insp(bind).has_table(TABLE):
        op.drop_table(TABLE)
