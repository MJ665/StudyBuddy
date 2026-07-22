"""add_coding_hint_cache_and_member_id

Revision ID: 47ecb64695b8
Revises: 872a4a801e1e
Create Date: 2026-04-21 12:57:08.795643

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore

# revision identifiers, used by Alembic.
revision: str = "47ecb64695b8"
down_revision: Union[str, Sequence[str], None] = "872a4a801e1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- member_id for users ---
    op.add_column("users", sa.Column("member_id", sa.String(length=50), nullable=True))
    op.create_index(op.f("ix_users_member_id"), "users", ["member_id"], unique=False)

    # --- coding_hint_cache table ---
    op.create_table(
        "coding_hint_cache",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("coding_question_id", sa.Integer(), nullable=False),
        sa.Column("hint_level", sa.Integer(), nullable=False),
        sa.Column("answer_hash", sa.String(length=64), nullable=False),
        sa.Column("hint_text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["coding_question_id"], ["coding_questions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "coding_question_id", "hint_level", "answer_hash", name="uq_hint_cache"
        ),
    )
    op.create_index(
        op.f("ix_coding_hint_cache_id"), "coding_hint_cache", ["id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_coding_hint_cache_id"), table_name="coding_hint_cache")
    op.drop_table("coding_hint_cache")
    op.drop_index(op.f("ix_users_member_id"), table_name="users")
    op.drop_column("users", "member_id")
