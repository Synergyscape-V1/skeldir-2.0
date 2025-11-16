"""Revoke UPDATE/DELETE privileges from app_rw on revenue_ledger

Revision ID: 202511141300
Revises: 202511141201
Create Date: 2025-11-14 13:00:00

Migration Description:
Revokes UPDATE and DELETE privileges from app_rw role on revenue_ledger table
to enforce ledger immutability policy.

This migration implements Phase L1 of B0.3 Ledger Traceability:
- REVOKE UPDATE, DELETE ON TABLE revenue_ledger FROM app_rw
- app_rw retains only SELECT and INSERT privileges
- migration_owner retains full privileges for emergency repairs only

Contract Mapping:
- Enforces ledger immutability policy: revenue_ledger is write-once for app roles
- Supports correction model: corrections via additive entries, not mutations

Governance Compliance:
- Policy alignment (IMMUTABILITY_POLICY.md)
- Defense-in-depth: Privilege revocation is first line of defense
- Guard trigger (Phase L2) provides second line of defense
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141300'
down_revision: Union[str, None] = '202511141201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Revoke UPDATE and DELETE privileges from app_rw on revenue_ledger.
    
    This enforces the ledger immutability policy: application roles may only
    INSERT new rows. UPDATE/DELETE are forbidden for app_rw.
    
    Note: migration_owner retains full privileges for emergency repairs only.
    """
    
    # Revoke UPDATE and DELETE from app_rw
    op.execute("REVOKE UPDATE, DELETE ON TABLE revenue_ledger FROM app_rw")
    
    op.execute("""
        COMMENT ON TABLE revenue_ledger IS 
            'Write-once financial ledger. Application roles may only INSERT. No UPDATE/DELETE for app roles; corrections via new ledger entries. Purpose: Revenue verification and aggregation. Data class: Non-PII. Ownership: Reconciliation service. RLS enabled for tenant isolation.'
    """)


def downgrade() -> None:
    """
    Restore UPDATE and DELETE privileges to app_rw on revenue_ledger.
    
    WARNING: This rollback removes immutability enforcement. Only use if
    absolutely necessary for operational requirements.
    """
    
    # Re-grant UPDATE and DELETE to app_rw
    op.execute("GRANT UPDATE, DELETE ON TABLE revenue_ledger TO app_rw")


