"""Add unknown channel fallback to channel_taxonomy

Revision ID: 202511161120
Revises: 202511161110
Create Date: 2025-11-16 11:20:00

Migration Description:
Adds canonical 'unknown' fallback code to channel_taxonomy table to enable
resilient handling of unmapped channel inputs without FK violations.

This migration implements Phase 1 of Channel Governance Remediation:
- Adds 'unknown' channel code with semantic meaning "traffic/revenue seen but unclassified"
- Enables deterministic fallback for unmapped vendor channel indicators
- Prevents FK violations when B0.4 ingestion encounters unknown channels
- Idempotent INSERT (ON CONFLICT DO NOTHING) for safe re-running

Channel Semantics:
- code: 'unknown'
- family: 'direct' (neutral family grouping)
- is_paid: false (no spend tracking for unclassified channels)
- display_name: 'Unknown / Unclassified'
- is_active: true (available for use)

Data Quality Strategy:
- 'unknown' is a safety net, not a permanent bucket
- All occurrences must be logged and monitored
- High 'unknown' rates trigger mapping updates

Governance Compliance:
- Style guide compliance (idempotent migration, comments)
- Policy alignment (canonical fallback requirement from Directive 69)
- DDL lint rules (table/column comment updates)

Contract Mapping:
- Supports B0.4 ingestion resilience to unmapped channels
- Enables B2.1 attribution to proceed without FK failures
- Aligns with channel_mapping.yaml fallback behavior
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511161120'
down_revision: Union[str, None] = '202511161110'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add 'unknown' fallback code to channel_taxonomy.
    
    This code serves as the canonical fallback for all unmapped channel inputs.
    The INSERT is idempotent to allow safe re-running of the migration.
    """
    
    # Update table comment to document fallback behavior
    op.execute("""
        COMMENT ON TABLE channel_taxonomy IS 
            'Canonical channel taxonomy for attribution. Guarantees all allocation channel codes are valid. 
            All unmapped channels MUST be normalized to the ''unknown'' code. Purpose: Provide single source 
            of truth for channel codes, ensuring consistency across ingestion, allocation models, and UI. 
            Data class: Non-PII. Ownership: Attribution service.'
    """)
    
    # Insert 'unknown' fallback code (idempotent)
    op.execute("""
        INSERT INTO channel_taxonomy (code, family, is_paid, display_name, is_active) 
        VALUES 
            ('unknown', 'direct', false, 'Unknown / Unclassified', true)
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    """
    Remove 'unknown' fallback code from channel_taxonomy.
    
    WARNING: This rollback removes the canonical fallback. Any events or allocations
    with channel='unknown' or channel_code='unknown' will violate FK constraints
    after this migration is rolled back.
    """
    
    # Delete 'unknown' code
    op.execute("""
        DELETE FROM channel_taxonomy WHERE code = 'unknown'
    """)
    
    # Restore original table comment
    op.execute("""
        COMMENT ON TABLE channel_taxonomy IS 
            'Canonical channel taxonomy for attribution allocations and reporting. Purpose: Provide single source of truth for channel codes, ensuring consistency across ingestion, allocation models, and UI. Data class: Non-PII. Ownership: Attribution service.'
    """)


