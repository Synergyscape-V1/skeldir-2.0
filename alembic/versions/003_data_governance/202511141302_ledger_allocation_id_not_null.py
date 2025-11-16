"""Enforce allocation_id NOT NULL on revenue_ledger

Revision ID: 202511141302
Revises: 202511141301
Create Date: 2025-11-14 13:02:00

Migration Description:
Enforces NOT NULL constraint on allocation_id column in revenue_ledger table
to ensure all ledger entries are traceable.

This migration implements Phase L3 of B0.3 Ledger Traceability:
- Validates that no NULL allocation_id values exist
- Applies NOT NULL constraint if validation passes
- Migration will fail if NULL values exist (desired behavior)

Contract Mapping:
- Enforces traceability: every ledger entry must be linked to an allocation
- Supports audit trail: all entries traceable via allocation_id → attribution_allocations → attribution_events

Governance Compliance:
- Style guide compliance (snake_case, constraints, comments)
- Policy alignment (traceability requirement)
- DDL lint rules (comments, constraint naming)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141302'
down_revision: Union[str, None] = '202511141301'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enforce NOT NULL constraint on allocation_id column.
    
    This migration will fail if any NULL allocation_id values exist, which is
    the desired behavior. All ledger entries must be traceable via allocation_id.
    
    Data Validation:
    - Checks for existing NULL allocation_id values
    - Migration fails if NULLs exist (prevents orphan rows)
    - Only proceeds if all rows have allocation_id set
    """
    
    # Check for NULL allocation_id values
    # This query will raise an exception if NULLs exist, preventing the migration
    op.execute("""
        DO $$
        DECLARE
            null_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO null_count
            FROM revenue_ledger
            WHERE allocation_id IS NULL;
            
            IF null_count > 0 THEN
                RAISE EXCEPTION 'Cannot enforce NOT NULL: % rows have NULL allocation_id. All ledger entries must be traceable. Backfill NULL values before applying this constraint.', null_count;
            END IF;
        END $$;
    """)
    
    # Apply NOT NULL constraint (only reached if no NULLs exist)
    op.execute("ALTER TABLE revenue_ledger ALTER COLUMN allocation_id SET NOT NULL")
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.allocation_id IS
            'Foreign key to attribution_allocations table (NOT NULL). Purpose: Link ledger entry to specific allocation for allocation-based posting. Ensures all ledger entries are traceable. Data class: Non-PII.'
    """)


def downgrade() -> None:
    """
    Remove NOT NULL constraint from allocation_id column.
    
    WARNING: This rollback allows NULL allocation_id values, which creates
    orphan rows that are not traceable. Only use if absolutely necessary.
    """
    
    # Remove NOT NULL constraint
    op.execute("ALTER TABLE revenue_ledger ALTER COLUMN allocation_id DROP NOT NULL")
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.allocation_id IS
            'Foreign key to attribution_allocations table (nullable). Purpose: Link ledger entry to specific allocation for allocation-based posting. Supports both allocation-based (allocation_id set) and run-based (reconciliation_run_id set) posting patterns. Data class: Non-PII.'
    """)


