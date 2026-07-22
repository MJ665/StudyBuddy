"""add kt module tables

Revision ID: 8a2b3c4d5e6f
Revises: 404dab57395c
Create Date: 2026-05-11 08:50:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op  # type: ignore
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "8a2b3c4d5e6f"
down_revision: Union[str, Sequence[str], None] = "404dab57395c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Projects ---
    op.create_table(
        "kt_projects",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("domain_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tech_stack", sa.String(length=500), nullable=True),
        sa.Column("client_name", sa.String(length=255), nullable=True),
        sa.Column("doc_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "ingested_doc_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "total_tokens_consumed", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "knowledge_coverage_score", sa.Float(), server_default="0.0", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt_projects_id"), "kt_projects", ["id"], unique=False)

    # --- Project Members ---
    op.create_table(
        "kt_project_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["kt_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_user"),
    )

    # --- Documents ---
    op.create_table(
        "kt_documents",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.String(length=50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column(
            "doc_type", sa.String(length=50), server_default="general", nullable=False
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="draft", nullable=False
        ),
        sa.Column("body_markdown", sa.Text(), nullable=False),
        sa.Column("summary_ai", sa.Text(), nullable=True),
        sa.Column("quality_score", sa.Float(), server_default="0.0", nullable=False),
        sa.Column("auto_tags", sa.JSON(), nullable=True),
        sa.Column("knowledge_domain", sa.String(length=255), nullable=True),
        sa.Column("tech_stack", sa.String(length=500), nullable=True),
        sa.Column("problem_statement", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("conclusion", sa.Text(), nullable=True),
        sa.Column("tags", sa.String(length=500), nullable=True),
        sa.Column(
            "ingestion_status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("neo4j_node_ids", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["kt_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_kt_documents_id"), "kt_documents", ["id"], unique=False)

    # --- Ingestion Jobs ---
    op.create_table(
        "kt_ingestion_jobs",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("document_id", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("chunks_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("nodes_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"], ["kt_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Access Keys ---
    op.create_table(
        "kt_access_keys",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("issued_by_id", sa.Integer(), nullable=False),
        sa.Column("key_hash", sa.String(length=255), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("scope_label", sa.String(length=255), nullable=True),
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
        sa.Column("recipient_name", sa.String(length=255), nullable=True),
        sa.Column("max_uses", sa.Integer(), nullable=True),
        sa.Column(
            "is_onboarding_key", sa.Boolean(), server_default="false", nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["issued_by_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_kt_access_keys_key_hash"), "kt_access_keys", ["key_hash"], unique=True
    )

    # --- Access Key Projects ---
    op.create_table(
        "kt_access_key_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("access_key_id", sa.String(length=50), nullable=False),
        sa.Column("project_id", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["access_key_id"], ["kt_access_keys.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["project_id"], ["kt_projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("access_key_id", "project_id", name="uq_key_project"),
    )

    # --- Chat Sessions ---
    op.create_table(
        "kt_chat_sessions",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("access_key_id", sa.String(length=50), nullable=True),
        sa.Column("resolved_project_ids", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["access_key_id"],
            ["kt_access_keys.id"],
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Chat Messages ---
    op.create_table(
        "kt_chat_messages",
        sa.Column("id", sa.String(length=50), nullable=False),
        sa.Column("session_id", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("was_answered", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["kt_chat_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- Unanswered Queries ---
    op.create_table(
        "kt_unanswered_queries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("query_normalized", sa.String(length=500), nullable=False),
        sa.Column("occurrence_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "last_asked_at",
            sa.DateTime(timezone=True),
            server_default="now()",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "query_normalized", name="uq_unanswered_query"
        ),
    )


def downgrade() -> None:
    op.drop_table("kt_unanswered_queries")
    op.drop_table("kt_chat_messages")
    op.drop_table("kt_chat_sessions")
    op.drop_table("kt_access_key_projects")
    op.drop_table("kt_access_keys")
    op.drop_table("kt_ingestion_jobs")
    op.drop_table("kt_documents")
    op.drop_table("kt_project_members")
    op.drop_table("kt_projects")
