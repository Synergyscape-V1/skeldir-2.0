"""Add guard trigger to prevent UPDATE/DELETE on attribution_events

Revision ID: 202511141201
Revises: 202511141200
Create Date: 2025-11-14 12:01:00

Migration Description:
Creates defense-in-depth trigger to block UPDATE/DELETE operations on
attribution_events table, even if privileges are accidentally re-granted.

This migration implements Phase E3 of B0.3 Events Immutability hardening:
- Creates trigger function fn_events_prevent_mutation()
- Creates trigger trg_events_prevent_mutation (BEFORE UPDATE OR DELETE)
- Allows migration_owner role for emergency repairs only
- Blocks all other UPDATE/DELETE attempts with clear error message

Contract Mapping:
- Enforces events immutability policy: attribution_events is append-only
- Provides defense-in-depth beyond privilege-level enforcement
- Supports correction model guidance in error message

Governance Compliance:
- Style guide compliance (snake_case, comments)
- Policy alignment (EVENTS_IMMUTABILITY_POLICY.md)
- DDL lint rules (comments on function and trigger)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141201'
down_revision: Union[str, None] = '202511141200'
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
        CREATE OR REPLACE FUNCTION fn_events_prevent_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            -- Allow migration_owner for emergency repairs (optional)
            IF current_user = 'migration_owner' THEN
                RETURN NULL; -- Allow operation
            END IF;
            
            -- Block all other UPDATE/DELETE attempts
            RAISE EXCEPTION 'attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.';
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION fn_events_prevent_mutation() IS
            'Prevents UPDATE/DELETE operations on attribution_events table. Purpose: Defense-in-depth enforcement of events immutability. Allows migration_owner for emergency repairs only. Raises exception for all other roles attempting UPDATE/DELETE.'
    """)
    
    # Create trigger
    op.execute("""
        CREATE TRIGGER trg_events_prevent_mutation
            BEFORE UPDATE OR DELETE ON attribution_events
            FOR EACH ROW
            EXECUTE FUNCTION fn_events_prevent_mutation();
    """)
    
    op.execute("""
        COMMENT ON TRIGGER trg_events_prevent_mutation ON attribution_events IS
            'Guard trigger preventing UPDATE/DELETE operations on attribution_events. Purpose: Defense-in-depth enforcement of events immutability. Timing: BEFORE UPDATE OR DELETE. Level: FOR EACH ROW. Function: fn_events_prevent_mutation().'
    """)


def downgrade() -> None:
    """
    Remove guard trigger and function.
    
    WARNING: This rollback removes defense-in-depth enforcement. The privilege
    revocation from the previous migration will still prevent app_rw from
    UPDATE/DELETE, but the trigger-level protection will be removed.
    """
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_events_prevent_mutation ON attribution_events")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS fn_events_prevent_mutation()")


