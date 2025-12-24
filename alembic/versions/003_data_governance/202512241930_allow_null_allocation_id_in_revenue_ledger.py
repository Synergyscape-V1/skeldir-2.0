"""Allow NULL allocation_id in revenue_ledger (supports reconciliation rows)

Revision ID: 202512241930
Revises: 202512231020
Create Date: 2025-12-24 19:30:00

Context:
The codebase supports both:
- allocation-based posting (allocation_id set)
- reconciliation / transaction-based rows (transaction_id/order_id set)

Some value-trace gates (e.g. VALUE_01) insert reconciliation rows into
revenue_ledger keyed by transaction_id and do not have a meaningful allocation_id.

The earlier migration `202511141302` enforced allocation_id NOT NULL. This
blocks reconciliation entries and breaks VALUE gates.

Fix:
Drop the NOT NULL constraint to restore the intended dual-mode design.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "202512241930"
down_revision: Union[str, None] = "202512231020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE revenue_ledger ALTER COLUMN allocation_id DROP NOT NULL")
    op.execute(
        """
        COMMENT ON COLUMN revenue_ledger.allocation_id IS
            'Foreign key to attribution_allocations table (nullable). Purpose: '
            'Link ledger entry to a specific allocation when applicable; '
            'supports both allocation-based posting and transaction-based reconciliation rows.'
        """
    )


def downgrade() -> None:
    # NOTE: Restoring NOT NULL may require backfilling existing reconciliation rows.
    op.execute("ALTER TABLE revenue_ledger ALTER COLUMN allocation_id SET NOT NULL")


