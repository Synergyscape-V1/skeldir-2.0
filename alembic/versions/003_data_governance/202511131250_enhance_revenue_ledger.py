"""Enhance revenue_ledger with allocation-based posting support

Revision ID: 202511131250
Revises: 202511131240
Create Date: 2025-11-13 12:50:00

Migration Description:
Adds allocation-based posting support to revenue_ledger per Phase 4C requirements:
- allocation_id: nullable FK to attribution_allocations (supports allocation-based posting)
- posted_at: timestamp for when revenue was posted (Jamie's requirement)
- Unique constraint on (tenant_id, allocation_id) for idempotency (where allocation_id IS NOT NULL)

Contract Mapping:
- Supports both allocation-based and run-based revenue posting patterns
- Enables idempotent allocation-to-ledger posting

Governance Compliance:
- Style guide compliance (snake_case, FK constraints, comments)
- Contract mapping (allocation_id, posted_at fields)
- DDL lint rules (comments, constraints, indexes)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131250'
down_revision: Union[str, None] = '202511131240'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply migration changes.
    
    Adds:
    1. allocation_id column (uuid FK to attribution_allocations, nullable)
    2. posted_at column (timestamptz NOT NULL)
    3. Unique constraint on (tenant_id, allocation_id) where allocation_id IS NOT NULL
    """
    
    # Add allocation_id FK (nullable, supports both allocation-based and run-based posting)
    op.execute("""
        ALTER TABLE revenue_ledger
            ADD COLUMN allocation_id uuid REFERENCES attribution_allocations(id) ON DELETE CASCADE
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.allocation_id IS
            'Foreign key to attribution_allocations table (nullable). Purpose: Link ledger entry to specific allocation for allocation-based posting. Supports both allocation-based (allocation_id set) and run-based (reconciliation_run_id set) posting patterns. Data class: Non-PII.'
    """)
    
    # Add posted_at timestamp
    op.execute("""
        ALTER TABLE revenue_ledger
            ADD COLUMN posted_at timestamptz NOT NULL DEFAULT now()
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_ledger.posted_at IS
            'Timestamp when revenue was posted to the ledger. Purpose: Track posting time for audit trail and reconciliation. Data class: Non-PII.'
    """)
    
    # Add idempotency unique constraint (Jamie's requirement)
    op.execute("""
        CREATE UNIQUE INDEX idx_revenue_ledger_tenant_allocation_id
            ON revenue_ledger (tenant_id, allocation_id)
            WHERE allocation_id IS NOT NULL
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_revenue_ledger_tenant_allocation_id IS
            'Unique index on (tenant_id, allocation_id) where allocation_id IS NOT NULL. Purpose: Prevent duplicate ledger entries for the same allocation, ensuring idempotent allocation-based posting. Data class: Non-PII.'
    """)


def downgrade() -> None:
    """
    Rollback migration changes.
    
    Removes:
    1. allocation_id column
    2. posted_at column
    3. Unique constraint on (tenant_id, allocation_id)
    """
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_revenue_ledger_tenant_allocation_id")
    
    # Drop columns
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS posted_at")
    op.execute("ALTER TABLE revenue_ledger DROP COLUMN IF EXISTS allocation_id")



