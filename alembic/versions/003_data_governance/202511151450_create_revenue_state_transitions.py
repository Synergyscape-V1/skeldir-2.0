"""Create revenue_state_transitions audit table

Revision ID: 202511151450
Revises: 202511151440
Create Date: 2025-11-15 14:50:00.000000

Phase 8b of B0.3 Schema Realignment Plan

This migration creates the revenue_state_transitions table for audit logging
of all state changes in the revenue_ledger table. This table is BLOCKING for
the revenue state machine implementation.

Table structure:
- id: Primary key (UUID)
- ledger_id: Foreign key to revenue_ledger (ON DELETE CASCADE)
- from_state: Previous state (nullable for initial transitions)
- to_state: New state (NOT NULL)
- reason: Optional reason for the transition
- transitioned_at: Timestamp of the transition (NOT NULL DEFAULT now())

This table supports:
- Complete audit trail of revenue state changes
- Refund and chargeback tracking
- Compliance and financial audit requirements
- State transition analytics

These changes are BLOCKING for:
- B2.4 Refund Tracking (state machine audit)
- Financial compliance and audit requirements

Exit Gates:
- Migration applies cleanly
- Table exists with all 6 columns
- Foreign key to revenue_ledger enforced
- Canonical index on ledger_id exists
- CASCADE delete behavior works

References:
- Architecture Guide §3.1 (Revenue State Transitions Table)
- db/schema/canonical_schema.sql (revenue_state_transitions table)
- db/schema/schema_gap_catalogue.md (Table 6, missing table)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151450'
down_revision: Union[str, None] = '202511151440'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Create revenue_state_transitions audit table.
    
    Implementation:
    1. Create table with all columns and constraints
    2. Create index on ledger_id for fast lookups
    3. Enable RLS (if needed for tenant isolation)
    4. Add comments with INVARIANT tags
    """
    
    # ========================================================================
    # Step 1: Create revenue_state_transitions table
    # ========================================================================
    
    op.execute("""
        CREATE TABLE revenue_state_transitions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ledger_id UUID NOT NULL REFERENCES revenue_ledger(id) ON DELETE CASCADE,
            from_state VARCHAR(50),
            to_state VARCHAR(50) NOT NULL,
            reason TEXT,
            transitioned_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    
    # ========================================================================
    # Step 2: Create index for fast lookups by ledger_id
    # ========================================================================
    
    op.execute("""
        CREATE INDEX idx_revenue_state_transitions_ledger_id 
        ON revenue_state_transitions (ledger_id, transitioned_at DESC)
    """)
    
    # ========================================================================
    # Step 3: Add comments with INVARIANT tags
    # ========================================================================
    
    op.execute("""
        COMMENT ON TABLE revenue_state_transitions IS 
            'Audit log for revenue ledger state changes. INVARIANT: financial_critical. Purpose: Track complete history of revenue state transitions for compliance and analytics. Data class: Non-PII. Ownership: Revenue service. Required for: B2.4 refund tracking, financial audit, compliance.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.id IS 
            'Primary key UUID for the state transition record. Purpose: Unique identifier for each transition. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.ledger_id IS 
            'Foreign key to revenue_ledger table. INVARIANT: financial_critical. Purpose: Link transition to specific ledger entry. Data class: Non-PII. Required for: B2.4 state transition audit trail. ON DELETE CASCADE ensures transitions are deleted with ledger entry.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.from_state IS 
            'State before the transition (nullable for initial state). INVARIANT: financial_critical. Purpose: Track previous state for audit trail. Data class: Non-PII. Required for: B2.4 state transition analysis, compliance audit.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.to_state IS 
            'State after the transition (NOT NULL). INVARIANT: financial_critical. Purpose: Track new state for audit trail. Data class: Non-PII. Required for: B2.4 state machine enforcement, refund tracking. Must not be NULL.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.reason IS 
            'Optional reason for the state transition (e.g., customer_request, fraud_detected, chargeback_received). INVARIANT: financial_critical. Purpose: Document business reason for transition. Data class: Non-PII. Required for: B2.4 refund reason tracking, compliance documentation.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN revenue_state_transitions.transitioned_at IS 
            'Timestamp when the state transition occurred (NOT NULL DEFAULT now()). INVARIANT: financial_critical. Purpose: Track exact timing of state changes for audit. Data class: Non-PII. Required for: B2.4 state transition timeline, compliance audit. Must not be NULL.'
    """)
    
    # Add comment on index
    op.execute("""
        COMMENT ON INDEX idx_revenue_state_transitions_ledger_id IS 
            'Optimizes lookups of state transitions by ledger entry with temporal ordering. Purpose: Enable fast retrieval of state history for a ledger entry. Required for: B2.4 state history queries, refund audit trail.'
    """)


def downgrade() -> None:
    """
    Drop revenue_state_transitions table.
    
    WARNING: This will drop the table and all audit data in it.
    """
    
    op.execute("DROP TABLE IF EXISTS revenue_state_transitions CASCADE")


