"""Add auth_critical columns to tenants table

Revision ID: 202511151400
Revises: 202511141311
Create Date: 2025-11-15 14:00:00.000000

Phase 4 of B0.3 Schema Realignment Plan

This migration adds the two BLOCKING auth_critical columns required by the 
canonical schema specification:
1. api_key_hash - Hashed API key for tenant authentication (NOT NULL UNIQUE)
2. notification_email - Email for tenant notifications (NOT NULL)

These columns are required for Phase B0.4 (API ingestion) and Phase B1.2 (Auth).

Exit Gates:
- Migration applies cleanly without errors
- Both columns exist with correct types and constraints
- Cannot insert duplicate api_key_hash (unique constraint enforced)
- Cannot insert NULL values (not-null constraints enforced)

References:
- Architecture Guide §3.1 (Tenants Table)
- db/schema/canonical_schema.sql (lines 15-16)
- db/schema/schema_gap_catalogue.md (Table 1, rows 1-2)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151400'
down_revision: Union[str, None] = '202511141311'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Add api_key_hash and notification_email columns to tenants table.
    
    Implementation:
    1. Add columns as nullable first (to allow backfill)
    2. Backfill existing rows with placeholder values
    3. Set NOT NULL constraints
    4. Add UNIQUE constraint on api_key_hash
    5. Add comments with INVARIANT tags
    """
    
    # Step 1: Add columns as nullable
    op.execute("""
        ALTER TABLE tenants 
        ADD COLUMN api_key_hash VARCHAR(255)
    """)
    
    op.execute("""
        ALTER TABLE tenants 
        ADD COLUMN notification_email VARCHAR(255)
    """)
    
    # Step 2: Backfill existing data (if any rows exist)
    # Note: In production, these would be populated with actual values
    op.execute("""
        UPDATE tenants 
        SET api_key_hash = 'PLACEHOLDER_' || id::text,
            notification_email = 'placeholder@tenant-' || id::text || '.example.com'
        WHERE api_key_hash IS NULL
    """)
    
    # Step 3: Set NOT NULL constraints
    op.execute("""
        ALTER TABLE tenants 
        ALTER COLUMN api_key_hash SET NOT NULL
    """)
    
    op.execute("""
        ALTER TABLE tenants 
        ALTER COLUMN notification_email SET NOT NULL
    """)
    
    # Step 4: Add UNIQUE constraint on api_key_hash
    op.execute("""
        CREATE UNIQUE INDEX idx_tenants_api_key_hash 
        ON tenants (api_key_hash)
    """)
    
    # Step 5: Add comments with INVARIANT tags
    op.execute("""
        COMMENT ON COLUMN tenants.api_key_hash IS 
            'Hashed API key for tenant authentication. INVARIANT: auth_critical. Purpose: Authenticate API requests and link to tenant. Data class: Security credential (hashed). Required for: B0.4 ingestion, B1.2 auth service. Must be unique.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN tenants.notification_email IS 
            'Email address for tenant-specific notifications. INVARIANT: auth_critical. Purpose: Send reconciliation alerts, system notifications. Data class: PII (email address). Required for: B0.4 notifications, B2.x alerting. Must not be empty.'
    """)
    
    # Add comment on the unique index
    op.execute("""
        COMMENT ON INDEX idx_tenants_api_key_hash IS 
            'Ensures api_key_hash uniqueness for authentication. Purpose: Prevent duplicate API keys across tenants. Required for: B0.4 ingestion authentication.'
    """)


def downgrade() -> None:
    """
    Remove api_key_hash and notification_email columns from tenants table.
    
    WARNING: This will drop the columns and all data in them.
    """
    
    # Drop index first
    op.execute("DROP INDEX IF EXISTS idx_tenants_api_key_hash")
    
    # Drop columns
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS api_key_hash")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS notification_email")


