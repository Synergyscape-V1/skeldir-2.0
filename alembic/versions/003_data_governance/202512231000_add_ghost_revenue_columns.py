"""Add ghost revenue reconciliation columns to revenue_ledger

Revision ID: 202512231000
Revises: 202512201000
Create Date: 2025-12-23 10:00:00

Migration Description:
Adds forensic reconciliation columns for ghost revenue detection:
- claimed_total_cents: Sum of platform claims (Meta + Google etc)
- verified_total_cents: Verified truth from payment processor
- ghost_revenue_cents: Discrepancy (claimed - verified, clamped to 0)
- discrepancy_bps: Basis points (avoids floats for percentages)

These columns enable penny-perfect ghost revenue reconciliation where
multiple attribution platforms may claim credit for the same order.

Contract Mapping:
- Supports VALUE_01-WIN forensic test scenario
- Enables deterministic conflict resolution
- Proves "verified wins" semantics

Exit Gates:
- All 4 columns exist with correct INTEGER types
- CHECK constraints enforce non-negative values
- Index on tenant_id, order_id for reconciliation queries
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '202512231000'
down_revision: Union[str, None] = '202512201000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add ghost revenue reconciliation columns."""

    # Add claimed_total_cents column
    op.execute("""
        ALTER TABLE revenue_ledger
        ADD COLUMN claimed_total_cents BIGINT NOT NULL DEFAULT 0
    """)

    op.execute("""
        ALTER TABLE revenue_ledger
        ADD CONSTRAINT ck_revenue_ledger_claimed_positive
        CHECK (claimed_total_cents >= 0)
    """)

    op.execute("""
        COMMENT ON COLUMN revenue_ledger.claimed_total_cents IS
            'Sum of all platform claims in cents for this order (Meta + Google + etc). INVARIANT: financial_critical. Purpose: Track total claimed revenue for ghost detection. Data class: Non-PII.'
    """)

    # Add verified_total_cents column
    op.execute("""
        ALTER TABLE revenue_ledger
        ADD COLUMN verified_total_cents BIGINT NOT NULL DEFAULT 0
    """)

    op.execute("""
        ALTER TABLE revenue_ledger
        ADD CONSTRAINT ck_revenue_ledger_verified_positive
        CHECK (verified_total_cents >= 0)
    """)

    op.execute("""
        COMMENT ON COLUMN revenue_ledger.verified_total_cents IS
            'Verified truth amount in cents from payment processor webhook. INVARIANT: financial_critical. Purpose: Store canonical verified revenue. Data class: Non-PII.'
    """)

    # Add ghost_revenue_cents column
    op.execute("""
        ALTER TABLE revenue_ledger
        ADD COLUMN ghost_revenue_cents BIGINT NOT NULL DEFAULT 0
    """)

    op.execute("""
        ALTER TABLE revenue_ledger
        ADD CONSTRAINT ck_revenue_ledger_ghost_positive
        CHECK (ghost_revenue_cents >= 0)
    """)

    op.execute("""
        COMMENT ON COLUMN revenue_ledger.ghost_revenue_cents IS
            'Ghost revenue in cents: max(0, claimed_total_cents - verified_total_cents). INVARIANT: financial_critical. Purpose: Track over-claimed revenue for reconciliation. Data class: Non-PII.'
    """)

    # Add discrepancy_bps column (basis points, avoids floats)
    op.execute("""
        ALTER TABLE revenue_ledger
        ADD COLUMN discrepancy_bps INTEGER NOT NULL DEFAULT 0
    """)

    op.execute("""
        ALTER TABLE revenue_ledger
        ADD CONSTRAINT ck_revenue_ledger_discrepancy_positive
        CHECK (discrepancy_bps >= 0)
    """)

    op.execute("""
        COMMENT ON COLUMN revenue_ledger.discrepancy_bps IS
            'Discrepancy in basis points: (ghost_revenue_cents * 10000) / verified_total_cents. INVARIANT: financial_critical. Purpose: Track percentage discrepancy without floats. Data class: Non-PII.'
    """)

    # Add index for reconciliation queries
    op.execute("""
        CREATE INDEX idx_revenue_ledger_tenant_order_reconciliation
        ON revenue_ledger (tenant_id, order_id, created_at DESC)
        WHERE order_id IS NOT NULL
    """)

    op.execute("""
        COMMENT ON INDEX idx_revenue_ledger_tenant_order_reconciliation IS
            'Optimizes reconciliation queries by tenant and order. Purpose: Fast lookup for ghost revenue detection.'
    """)


def downgrade() -> None:
    """Remove ghost revenue reconciliation columns."""

    op.execute("DROP INDEX IF EXISTS idx_revenue_ledger_tenant_order_reconciliation")
    op.execute("ALTER TABLE revenue_ledger DROP CONSTRAINT IF EXISTS ck_revenue_ledger_discrepancy_positive")
    op.execute("ALTER TABLE revenue_ledger DROP CONSTRAINT IF EXISTS ck_revenue_ledger_ghost_positive")
    op.execute("ALTER TABLE revenue_ledger DROP CONSTRAINT IF EXISTS ck_revenue_ledger_verified_positive")
    op.execute("ALTER TABLE revenue_ledger DROP CONSTRAINT IF EXISTS ck_revenue_ledger_claimed_positive")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS discrepancy_bps")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS ghost_revenue_cents")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS verified_total_cents")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS claimed_total_cents")
