"""reattribute question banks by actual usage

Revision ID: bfe447d090dc
Revises: e5f5c12f133e
Create Date: 2026-07-21

The previous revision attributed `question_banks` via `created_by`. That is wrong
for content created by the seeding/system account: the system user belongs to one
organization, while the learners actually attempting the bank belong to another.
The result is a bank owned by org A carrying only org B's attempts — so org B,
whose data it is, gets an empty gradebook while org A sees a bank with no results.

Usage is the stronger ownership signal. Where every attempt on a bank belongs to a
single organization, that organization owns the bank. Banks with attempts spanning
multiple organizations are left ALONE and reported, because that is a genuine
content-sharing question (see "shared content" note in the plan) rather than
something a migration should silently decide.

Questions follow their bank.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bfe447d090dc"
down_revision: Union[str, Sequence[str], None] = "e5f5c12f133e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Re-attribute only banks whose attempts unanimously belong to ONE org that
    # differs from the current attribution.
    op.execute(
        """
        WITH usage AS (
            SELECT bank_id,
                   MIN(organization_id) AS org_id,
                   COUNT(DISTINCT organization_id) AS org_count
            FROM attempts
            WHERE organization_id IS NOT NULL
            GROUP BY bank_id
        )
        UPDATE question_banks qb
        SET organization_id = usage.org_id
        FROM usage
        WHERE qb.id = usage.bank_id
          AND usage.org_count = 1
          AND qb.organization_id IS DISTINCT FROM usage.org_id
        """
    )

    # Keep questions consistent with their (possibly re-attributed) bank.
    op.execute(
        """
        UPDATE questions q
        SET organization_id = qb.organization_id
        FROM question_banks qb
        WHERE q.bank_id = qb.id
          AND qb.organization_id IS NOT NULL
          AND q.organization_id IS DISTINCT FROM qb.organization_id
        """
    )


def downgrade() -> None:
    # Ownership cannot be un-derived; the prior values were themselves a guess.
    pass
