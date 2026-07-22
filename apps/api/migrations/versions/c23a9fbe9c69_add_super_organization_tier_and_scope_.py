"""add super_organization tier and scope shared content to it

Revision ID: c23a9fbe9c69
Revises: bfe447d090dc
Create Date: 2026-07-22

Introduces the paying-customer tier above Organization:

    PlatformAdmin (us)
      └── SuperOrganization   ← purchases the app; approved/suspended from /platform
           └── Organization   ← business unit (L&D Admin operates here)
                └── Department → Vertical → Batch → Group → Users

Authored CONTENT (question banks, questions, exams, KT companies/projects) gains a
`super_organization_id`, so a customer's business units can share it. LEARNER data
(attempts, exam attempts, gradebooks, reports, users) keeps its `organization_id`
scope, so one business unit still cannot read another's results.

BACKFILL POLICY — deliberately conservative: every existing Organization gets its
OWN SuperOrganization. Nothing that is currently isolated becomes shared. Merging
two organizations under one customer is a business decision, done from /platform,
not silently by a migration.

Written by hand, not `--autogenerate` (see the neutralized revision d887cd121a07
for why). All DDL is idempotent and every new column is nullable, so partial
application is safe and un-backfilled rows fail closed in the scoping helpers.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c23a9fbe9c69"
down_revision: Union[str, Sequence[str], None] = "bfe447d090dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONTENT_TABLES = {
    "question_banks": "ix_question_banks_super_organization_id",
    "questions": "ix_questions_super_organization_id",
    "exams": "ix_exams_super_organization_id",
    "kt_companies": "ix_kt_companies_super_organization_id",
    "kt_projects": "ix_kt_projects_super_organization_id",
}


def _insp(bind):
    return sa.inspect(bind)


def _has_table(bind, table: str) -> bool:
    return _insp(bind).has_table(table)


def _has_column(bind, table: str, column: str) -> bool:
    if not _has_table(bind, table):
        return True
    return column in {c["name"] for c in _insp(bind).get_columns(table)}


def _has_index(bind, table: str, index: str) -> bool:
    if not _has_table(bind, table):
        return True
    return index in {i["name"] for i in _insp(bind).get_indexes(table)}


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. the new tenant table ──────────────────────────────────────────────
    if not _has_table(bind, "super_organizations"):
        op.create_table(
            "super_organizations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=255), nullable=False, unique=True),
            sa.Column("slug", sa.String(length=100), nullable=False, unique=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column(
                "subscription_tier", sa.String(length=50), nullable=False, server_default="Free"
            ),
            sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
            sa.Column("contact_email", sa.String(length=255), nullable=True),
            sa.Column("contact_name", sa.String(length=255), nullable=True),
            sa.Column("logo_url", sa.String(length=500), nullable=True),
            sa.Column("signature_url", sa.String(length=500), nullable=True),
            sa.Column("brand_name", sa.String(length=255), nullable=True),
            sa.Column("onboarding_token", sa.String(length=64), nullable=True),
            sa.Column("onboarded_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_super_organizations_slug", "super_organizations", ["slug"])
        op.create_index(
            "ix_super_organizations_onboarding_token",
            "super_organizations",
            ["onboarding_token"],
        )

    # ── 2. link Organization -> SuperOrganization ────────────────────────────
    if not _has_column(bind, "organizations", "super_organization_id"):
        op.add_column(
            "organizations", sa.Column("super_organization_id", sa.Integer(), nullable=True)
        )
    if not _has_index(bind, "organizations", "ix_organizations_super_organization_id"):
        op.create_index(
            "ix_organizations_super_organization_id",
            "organizations",
            ["super_organization_id"],
        )

    # ── 3. content scope key ─────────────────────────────────────────────────
    for table, index in CONTENT_TABLES.items():
        if not _has_table(bind, table):
            continue
        if not _has_column(bind, table, "super_organization_id"):
            op.add_column(table, sa.Column("super_organization_id", sa.Integer(), nullable=True))
        if not _has_index(bind, table, index):
            op.create_index(index, table, ["super_organization_id"])

    # ── 4. backfill: ONE SuperOrganization per existing Organization ─────────
    # The slug is derived from the organization's slug + id, so re-running cannot
    # create a second SuperOrg for the same Organization.
    op.execute(
        """
        INSERT INTO super_organizations
            (name, slug, status, subscription_tier, stripe_customer_id,
             contact_email, contact_name, logo_url, signature_url, brand_name,
             onboarded_at, is_active, created_at)
        SELECT o.name,
               o.slug || '-' || o.id::text,
               COALESCE(o.status, 'approved'),
               COALESCE(o.subscription_tier, 'Free'),
               o.stripe_customer_id,
               o.contact_email,
               o.contact_name,
               o.logo_url,
               o.signature_url,
               COALESCE(o.brand_name, o.name),
               o.onboarded_at,
               COALESCE(o.is_active, true),
               NOW()
        FROM organizations o
        WHERE o.super_organization_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE organizations o
        SET super_organization_id = s.id
        FROM super_organizations s
        WHERE o.super_organization_id IS NULL
          AND s.slug = o.slug || '-' || o.id::text
        """
    )

    # ── 5. propagate the content scope key from each row's organization ──────
    for table in ("question_banks", "questions", "exams", "kt_companies", "kt_projects"):
        if not _has_table(bind, table):
            continue
        op.execute(
            f"""
            UPDATE {table} t
            SET super_organization_id = o.super_organization_id
            FROM organizations o
            WHERE t.organization_id = o.id
              AND t.super_organization_id IS NULL
              AND o.super_organization_id IS NOT NULL
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    for table, index in CONTENT_TABLES.items():
        if not _has_table(bind, table):
            continue
        if index in {i["name"] for i in _insp(bind).get_indexes(table)}:
            op.drop_index(index, table_name=table)
        if "super_organization_id" in {c["name"] for c in _insp(bind).get_columns(table)}:
            op.drop_column(table, "super_organization_id")

    if _has_table(bind, "organizations"):
        if "ix_organizations_super_organization_id" in {
            i["name"] for i in _insp(bind).get_indexes("organizations")
        }:
            op.drop_index("ix_organizations_super_organization_id", table_name="organizations")
        if "super_organization_id" in {
            c["name"] for c in _insp(bind).get_columns("organizations")
        }:
            op.drop_column("organizations", "super_organization_id")

    if _has_table(bind, "super_organizations"):
        op.drop_table("super_organizations")
