"""Add revenue ledger audit trigger and tenant_id to revenue_state_transitions

Revision ID: 202511171300
Revises: 202511171200
Create Date: 2025-11-17 13:00:00.000000

Phase 5 of B0.3 Functional Implementation Plan

This migration implements the audit wiring for revenue_ledger state changes:
1. Adds tenant_id column to revenue_state_transitions (per Answer 2)
2. Creates trigger function fn_log_revenue_state_change() for atomic audit logging
3. Creates trigger trg_revenue_ledger_state_audit on revenue_ledger
4. Adds RLS policy to revenue_state_transitions

This migration is BLOCKING for:
- B2.4 Revenue Matching (state machine audit)
- Financial compliance and audit requirements

Exit Gates:
- Migration applies cleanly
- Trigger function exists and is SECURITY DEFINER
- Trigger fires on state changes
- RLS policy enables tenant isolation
"""

from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511171300'
down_revision: Union[str, None] = '202511171200'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Add tenant_id to revenue_state_transitions and create audit trigger.
    
    Implementation:
    1. Add tenant_id column to revenue_state_transitions
    2. Create trigger function fn_log_revenue_state_change()
    3. Create trigger trg_revenue_ledger_state_audit
    4. Enable RLS on revenue_state_transitions
    5. Create RLS policy for tenant isolation
    """
    
    # ========================================================================
    # Step 1: Add tenant_id column to revenue_state_transitions
    # ========================================================================
    
    op.execute("""
        ALTER TABLE revenue_state_transitions
        ADD COLUMN tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE
    """)
    
    # Populate existing rows (if any) with tenant_id from revenue_ledger
    op.execute("""
        UPDATE revenue_state_transitions rst
        SET tenant_id = rl.tenant_id
        FROM revenue_ledger rl
        WHERE rst.ledger_id = rl.id
    """)
    
    # Create index on tenant_id for RLS performance
    op.execute("""
        CREATE INDEX idx_revenue_state_transitions_tenant_id
        ON revenue_state_transitions (tenant_id, transitioned_at DESC)
    """)
    
    # ========================================================================
    # Step 2: Create trigger function for audit logging
    # ========================================================================
    
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_log_revenue_state_change() 
        RETURNS trigger AS $$
        BEGIN
            IF NEW.state IS DISTINCT FROM OLD.state THEN
                INSERT INTO revenue_state_transitions (
                    ledger_id,
                    tenant_id,
                    from_state,
                    to_state,
                    reason,
                    transitioned_at
                ) VALUES (
                    OLD.id,
                    OLD.tenant_id,
                    OLD.state,
                    NEW.state,
                    COALESCE(NEW.metadata->>'state_change_reason', 'unspecified'),
                    now()
                );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    
    # Add comment on function
    op.execute("""
        COMMENT ON FUNCTION fn_log_revenue_state_change() IS 
            'Trigger function for atomic audit logging of revenue_ledger state changes. 
            Purpose: Ensure every state change produces a corresponding revenue_state_transitions row. 
            Invariant: No ledger state change without matching transition row. 
            Security: SECURITY DEFINER to bypass RLS on revenue_state_transitions during trigger execution.'
    """)
    
    # ========================================================================
    # Step 3: Create trigger on revenue_ledger
    # ========================================================================
    
    op.execute("""
        CREATE TRIGGER trg_revenue_ledger_state_audit
        AFTER UPDATE OF state ON revenue_ledger
        FOR EACH ROW
        WHEN (OLD.state IS DISTINCT FROM NEW.state)
        EXECUTE FUNCTION fn_log_revenue_state_change();
    """)
    
    # Add comment on trigger
    op.execute("""
        COMMENT ON TRIGGER trg_revenue_ledger_state_audit ON revenue_ledger IS 
            'Audit trigger for revenue_ledger state changes. 
            Purpose: Automatically log all state transitions to revenue_state_transitions table. 
            Fires: AFTER UPDATE OF state when state value changes. 
            Atomicity: Trigger execution is atomic within the same transaction as the UPDATE.'
    """)
    
    # ========================================================================
    # Step 4: Enable RLS on revenue_state_transitions
    # ========================================================================
    
    op.execute("ALTER TABLE revenue_state_transitions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revenue_state_transitions FORCE ROW LEVEL SECURITY")
    
    # ========================================================================
    # Step 5: Create RLS policy for tenant isolation
    # ========================================================================
    
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON revenue_state_transitions
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
    """)
    
    op.execute("""
        COMMENT ON POLICY tenant_isolation_policy ON revenue_state_transitions IS 
            'RLS policy enforcing tenant isolation on audit table. 
            Purpose: Prevent cross-tenant access to audit trail. 
            Requires app.current_tenant_id to be set via set_config().'
    """)


def downgrade() -> None:
    """
    Remove audit trigger and tenant_id column.
    
    WARNING: This will remove the audit trigger and tenant_id column.
    Audit history will be preserved but tenant_id will be lost.
    """
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_revenue_ledger_state_audit ON revenue_ledger")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS fn_log_revenue_state_change()")
    
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON revenue_state_transitions")
    
    # Disable RLS
    op.execute("ALTER TABLE revenue_state_transitions DISABLE ROW LEVEL SECURITY")
    
    # Drop index
    op.execute("DROP INDEX IF EXISTS idx_revenue_state_transitions_tenant_id")
    
    # Drop tenant_id column
    op.execute("ALTER TABLE revenue_state_transitions DROP COLUMN IF EXISTS tenant_id")




