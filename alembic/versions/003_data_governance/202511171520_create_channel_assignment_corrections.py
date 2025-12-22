"""Create channel_assignment_corrections audit table

Revision ID: 202511171520
Revises: 202511171510
Create Date: 2025-11-17 15:20:00.000000

Phase 4 of Channel Governance Auditability Implementation

This migration creates the channel_assignment_corrections audit table to log
all post-ingestion channel assignment corrections:
1. Creates channel_assignment_corrections table
2. Adds indexes for correction history and channel movement queries
3. Sets up FK relationships to tenants and channel_taxonomy
4. Enables RLS for tenant isolation

This migration is BLOCKING for:
- Channel assignment correction auditability
- Revenue reclassification tracking

Exit Gates:
- Migration applies cleanly
- Table exists with correct schema
- RLS policy enables tenant isolation
- Indexes support query patterns
"""

from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511171520'
down_revision: Union[str, None] = '202511171510'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Create channel_assignment_corrections audit table.
    
    Implementation:
    1. Create table with all required columns
    2. Add primary key and indexes
    3. Add FK constraints to tenants and channel_taxonomy
    4. Enable RLS and create tenant isolation policy
    5. Add table and column comments
    """
    
    # Step 1: Create channel_assignment_corrections table
    op.execute("""
        CREATE TABLE channel_assignment_corrections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN ('event', 'allocation')),
            entity_id UUID NOT NULL,
            from_channel VARCHAR(50) NOT NULL,
            to_channel VARCHAR(50) NOT NULL REFERENCES channel_taxonomy(code),
            corrected_by VARCHAR(255) NOT NULL,
            corrected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reason TEXT NOT NULL,
            metadata JSONB
        )
    """)
    
    # Step 2: Add indexes for query patterns
    # Index for correction history per entity
    op.execute("""
        CREATE INDEX idx_channel_assignment_corrections_entity 
        ON channel_assignment_corrections (tenant_id, entity_type, entity_id, corrected_at DESC)
    """)
    
    # Index for channel movement queries
    op.execute("""
        CREATE INDEX idx_channel_assignment_corrections_channels 
        ON channel_assignment_corrections (from_channel, to_channel, corrected_at DESC)
    """)
    
    # Index for tenant corrections (compliance reports)
    op.execute("""
        CREATE INDEX idx_channel_assignment_corrections_tenant 
        ON channel_assignment_corrections (tenant_id, corrected_at DESC)
    """)
    
    # Step 3: Enable RLS
    op.execute("ALTER TABLE channel_assignment_corrections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE channel_assignment_corrections FORCE ROW LEVEL SECURITY")
    
    # Step 4: Create RLS policy for tenant isolation
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON channel_assignment_corrections
        USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
    """)
    
    op.execute("""
        COMMENT ON POLICY tenant_isolation_policy ON channel_assignment_corrections IS 
            'Ensures tenants can only see their own correction records. Purpose: Multi-tenant isolation for audit data. Security: Default deny if app.current_tenant_id is unset.'
    """)
    
    # Step 5: Add table comment
    op.execute("""
        COMMENT ON TABLE channel_assignment_corrections IS 
            'Audit log of all post-ingestion channel assignment corrections. Purpose: Provide immutable audit trail for revenue reclassifications, enabling reconciliation and dispute resolution. Data class: Non-PII. Ownership: Data Governance.'
    """)
    
    # Step 6: Add column comments
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.id IS 
            'Primary key for correction record. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.tenant_id IS 
            'Tenant whose data was corrected (FK to tenants.id). Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.entity_type IS 
            'Type of entity corrected: ''event'' or ''allocation''. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.entity_id IS 
            'ID of corrected entity (references attribution_events.id or attribution_allocations.id). Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.from_channel IS 
            'Previous channel assignment. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.to_channel IS 
            'New channel assignment (FK to channel_taxonomy.code). Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.corrected_by IS 
            'User/service that made correction (e.g., support@skeldir.com). Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.corrected_at IS 
            'Timestamp when correction occurred. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.reason IS 
            'Mandatory explanation for correction. Data class: Non-PII.'
    """)
    
    op.execute("""
        COMMENT ON COLUMN channel_assignment_corrections.metadata IS 
            'Additional context (e.g., ticket reference). Data class: Non-PII.'
    """)
    
    # Step 7: Log completion
    op.execute("""
        DO $$
        BEGIN
            RAISE NOTICE 'channel_assignment_corrections table created';
            RAISE NOTICE 'Indexes added for correction history and channel movement queries';
            RAISE NOTICE 'RLS enabled with tenant isolation policy';
            RAISE NOTICE 'FK constraints link to tenants and channel_taxonomy';
        END $$;
    """)


def downgrade() -> None:
    """
    Drop channel_assignment_corrections audit table.
    
    WARNING: This rollback removes the audit trail for channel assignment corrections.
    After this migration is rolled back, assignment corrections are unaudited.
    """
    
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON channel_assignment_corrections")
    
    # Disable RLS
    op.execute("ALTER TABLE channel_assignment_corrections DISABLE ROW LEVEL SECURITY")
    
    # Drop table (CASCADE will drop indexes and constraints)
    op.execute("DROP TABLE IF EXISTS channel_assignment_corrections CASCADE")
    
    # Log rollback
    op.execute("""
        DO $$
        BEGIN
            RAISE WARNING 'channel_assignment_corrections table dropped';
            RAISE WARNING 'Channel assignment correction audit trail removed';
        END $$;
    """)




