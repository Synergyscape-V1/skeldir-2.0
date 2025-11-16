"""Revoke UPDATE and DELETE privileges on attribution_events from app_rw

Revision ID: 202511141200
Revises: 202511131250
Create Date: 2025-11-14 12:00:00

Migration Description:
Removes UPDATE and DELETE privileges from app_rw role on attribution_events table
to enforce append-only semantics per B0.3 Events Immutability requirements.

This migration implements Phase E2 of B0.3 Events Immutability hardening:
- Revokes UPDATE, DELETE privileges from app_rw on attribution_events
- Ensures app_rw has only SELECT, INSERT privileges (append-only)
- Maintains app_ro as SELECT-only (no change)
- Retains migration_owner full access for emergency repairs only

Contract Mapping:
- Enforces events immutability policy: attribution_events is append-only
- Supports correction model: corrections via new events with correlation_id

Governance Compliance:
- Style guide compliance (snake_case, comments)
- Policy alignment (EVENTS_IMMUTABILITY_POLICY.md)
- DDL lint rules (comments, explicit privilege statements)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141200'
down_revision: Union[str, None] = '202511131250'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Revoke UPDATE and DELETE privileges from app_rw on attribution_events.
    
    This enforces append-only semantics at the privilege level, ensuring
    application roles cannot mutate existing event rows.
    
    After this migration:
    - app_rw: SELECT, INSERT only (no UPDATE, DELETE)
    - app_ro: SELECT only (no change)
    - migration_owner: Full access (unchanged, for emergency repairs only)
    """
    
    # Revoke UPDATE and DELETE privileges from app_rw
    op.execute("REVOKE UPDATE, DELETE ON TABLE attribution_events FROM app_rw")
    
    op.execute("""
        COMMENT ON TABLE attribution_events IS 
            'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation. Append-only: No UPDATE/DELETE for app roles; corrections via new events only.'
    """)


def downgrade() -> None:
    """
    Re-grant UPDATE and DELETE privileges to app_rw on attribution_events.
    
    WARNING: This rollback removes immutability enforcement. Only use if
    absolutely necessary for operational requirements. Re-granting these
    privileges contradicts the events immutability policy.
    """
    
    # Re-grant UPDATE and DELETE privileges to app_rw
    op.execute("GRANT UPDATE, DELETE ON TABLE attribution_events TO app_rw")
    
    # Restore original table comment (without append-only note)
    op.execute("""
        COMMENT ON TABLE attribution_events IS 
            'Stores attribution events for revenue tracking. Purpose: Event ingestion and attribution calculations. Data class: Non-PII (PII stripped from raw_payload). Ownership: Attribution service. RLS enabled for tenant isolation.'
    """)


