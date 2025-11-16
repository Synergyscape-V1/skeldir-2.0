"""Create channel_taxonomy table and seed from channel_mapping.yaml

Revision ID: 202511141310
Revises: 202511141302
Create Date: 2025-11-14 13:10:00

Migration Description:
Creates channel_taxonomy table as the single source of truth for canonical
channel codes and populates it with codes extracted from channel_mapping.yaml.

This migration implements Phase T1 of B0.3 Channel Taxonomy:
- Creates channel_taxonomy table with columns: code, family, is_paid, display_name, is_active, created_at
- Seeds table with canonical codes from channel_mapping.yaml
- Ensures 1:1 match between YAML canonical codes and taxonomy table

Contract Mapping:
- Provides canonical channel taxonomy for attribution allocations
- Supports channel_mapping.yaml as ingestion mapping source
- Enables FK constraint from attribution_allocations.channel_code

Governance Compliance:
- Style guide compliance (snake_case, comments, constraints)
- Policy alignment (canonical taxonomy requirement)
- DDL lint rules (comments on table and columns)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511141310'
down_revision: Union[str, None] = '202511141302'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create channel_taxonomy table and populate with canonical codes.
    
    Canonical codes extracted from db/channel_mapping.yaml:
    - facebook_paid, facebook_brand, google_search_paid, google_display_paid,
      tiktok_paid, direct, organic, referral, email
    
    All codes are inserted with appropriate family, is_paid, and display_name
    values based on their semantic meaning.
    """
    
    # Create channel_taxonomy table
    op.execute("""
        CREATE TABLE channel_taxonomy (
            code          text PRIMARY KEY,
            family        text NOT NULL,
            is_paid       boolean NOT NULL,
            display_name  text NOT NULL,
            is_active     boolean NOT NULL DEFAULT true,
            created_at    timestamptz NOT NULL DEFAULT now()
        )
    """)
    
    # Add table comment
    op.execute("""
        COMMENT ON TABLE channel_taxonomy IS 
            'Canonical channel taxonomy for attribution allocations and reporting. Purpose: Provide single source of truth for channel codes, ensuring consistency across ingestion, allocation models, and UI. Data class: Non-PII. Ownership: Attribution service.'
    """)
    
    # Add column comments
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.code IS 
            'Canonical channel identifier used throughout system. Primary key. Must match values referenced by attribution_allocations.channel_code FK. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.family IS 
            'Normalized family grouping for higher-level reporting (e.g., "paid_social", "paid_search", "organic", "referral"). Purpose: Enable family-level aggregation and analysis. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.is_paid IS 
            'Indicates whether spend is expected for this channel. Purpose: Enable paid vs organic channel segmentation. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.display_name IS 
            'Human-friendly label for UI display. Purpose: Provide user-facing channel name. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.is_active IS 
            'Used to soft-deprecate channels without breaking existing rows. Purpose: Allow channel retirement while preserving historical data. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_taxonomy.created_at IS 
            'Timestamp when channel was added to taxonomy. Purpose: Audit trail for channel lifecycle. Data class: Non-PII.'
    """)
    
    # Insert canonical codes from channel_mapping.yaml
    # Using idempotent INSERT (ON CONFLICT DO NOTHING) to allow re-running migration
    op.execute("""
        INSERT INTO channel_taxonomy (code, family, is_paid, display_name) VALUES
            ('facebook_paid', 'paid_social', true, 'Facebook Paid'),
            ('facebook_brand', 'paid_social', true, 'Facebook Brand'),
            ('google_search_paid', 'paid_search', true, 'Google Search Paid'),
            ('google_display_paid', 'paid_search', true, 'Google Display Paid'),
            ('tiktok_paid', 'paid_social', true, 'TikTok Paid'),
            ('direct', 'direct', false, 'Direct'),
            ('organic', 'organic', false, 'Organic'),
            ('referral', 'referral', false, 'Referral'),
            ('email', 'email', false, 'Email')
        ON CONFLICT (code) DO NOTHING
    """)


def downgrade() -> None:
    """
    Drop channel_taxonomy table.
    
    WARNING: This rollback removes the canonical taxonomy. Any FK constraints
    referencing channel_taxonomy will need to be dropped first.
    """
    
    # Drop table (CASCADE will drop any dependent objects)
    op.execute("DROP TABLE IF EXISTS channel_taxonomy CASCADE")


