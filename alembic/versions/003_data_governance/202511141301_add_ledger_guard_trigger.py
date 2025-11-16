"""Add guard trigger to prevent UPDATE/DELETE on revenue_ledger

Revision ID: 202511141301
Revises: 202511141300
Create Date: 2025-11-14 13:01:00

Migration Description:
Creates defense-in-depth trigger to block UPDATE/DELETE operations on
revenue_ledger table, even if privileges are accidentally re-granted.

This migration implements Phase L2 of B0.3 Ledger Traceability:
- Creates trigger function fn_ledger_prevent_mutation()
- Creates trigger trg_ledger_prevent_mutation (BEFORE UPDATE OR DELETE)
- Allows migration_owner role for emergency repairs only
- Blocks all other UPDATE/DELETE attempts with clear error message

Contract Mapping:
- Enforces ledger immutability policy: revenue_ledger is write-once
- Provides defense-in-depth beyond privilege-level enforcement
- Supports correction model guidance in error message

Governance Compliance:
- Style guide compliance (snake_case, comments)
- Policy alignment (IMMUTABILITY_POLICY.md)
- DDL lint rules (comments on function and trigger)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141301'
down_revision: Union[str, None] = '202511141300'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create guard trigger function and trigger to prevent UPDATE/DELETE operations.
    
    This provides defense-in-depth beyond privilege revocation, ensuring
    immutability is enforced even if privileges are accidentally re-granted.
    
    Whitelist Policy:
    - migration_owner: Allowed (for emergency repairs only)
    - All other roles: Blocked with exception
    """
    
    # Create trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_ledger_prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Allow migration_owner for emergency repairs (optional)
            IF current_user = 'migration_owner' THEN
                RETURN NULL; -- Allow operation
            END IF;
            
            -- Block all other UPDATE/DELETE attempts
            RAISE EXCEPTION 'revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections.';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION fn_ledger_prevent_mutation() IS
            'Prevents UPDATE/DELETE operations on revenue_ledger table. Purpose: Defense-in-depth enforcement of ledger immutability. Allows migration_owner for emergency repairs only. Raises exception for all other roles attempting UPDATE/DELETE.'
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trg_ledger_prevent_mutation
            BEFORE UPDATE OR DELETE ON revenue_ledger
            FOR EACH ROW
            EXECUTE FUNCTION fn_ledger_prevent_mutation();
    """)
    
    op.execute("""
        COMMENT ON TRIGGER trg_ledger_prevent_mutation ON revenue_ledger IS
            'Guard trigger preventing UPDATE/DELETE operations on revenue_ledger. Purpose: Defense-in-depth enforcement of ledger immutability. Timing: BEFORE UPDATE OR DELETE. Level: FOR EACH ROW. Function: fn_ledger_prevent_mutation().'
    """)


def downgrade() -> None:
    """
    Remove guard trigger and function.
    
    WARNING: This rollback removes defense-in-depth enforcement. The privilege
    revocation from the previous migration will still prevent app_rw from
    UPDATE/DELETE, but the trigger-level protection will be removed.
    """
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_ledger_prevent_mutation ON revenue_ledger")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS fn_ledger_prevent_mutation()")


