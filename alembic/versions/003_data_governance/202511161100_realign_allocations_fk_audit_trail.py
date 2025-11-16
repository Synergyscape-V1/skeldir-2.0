"""Realign attribution_allocations.event_id FK for audit trail preservation

Revision ID: 202511161100
Revises: 202511151510
Create Date: 2025-11-16 11:00:00.000000

Phase 2 of B0.3 Audit Trail FK Realignment

This migration corrects the foreign key constraint on attribution_allocations.event_id
from ON DELETE CASCADE to ON DELETE SET NULL, ensuring financial allocations persist
immutably even when source attribution events are deleted.

CRITICAL CHANGE:
- BEFORE: event_id NOT NULL with ON DELETE CASCADE (destroys audit trail)
- AFTER: event_id NULLABLE with ON DELETE SET NULL (preserves audit trail)

Rationale:
- Financial allocations are immutable audit trail (Product Vision requirement)
- Events may be deleted for maintenance or data cleanup (rare)
- Allocations must outlive events for financial record-keeping and compliance
- NULL event_id semantics: "allocation valid, event context unavailable"

Implementation:
1. Drop existing FK constraint (CASCADE behavior)
2. Alter column to nullable (prerequisite for SET NULL)
3. Add new FK constraint with SET NULL (audit preservation)

Impact Analysis:
- Materialized view mv_allocation_summary requires LEFT JOIN fix (Phase 3)
- Test scripts need NULL event_id test cases (Phase 5)
- No application code exists yet (B0.4 not implemented)

Exit Gates (Phase 2):
- Gate 2.1: Migration applies cleanly
- Gate 2.2: event_id column is NULLABLE
- Gate 2.3: FK constraint has confdeltype = 'n' (SET NULL)

References:
- db/docs/AUDIT_TRAIL_FK_IMPACT_ANALYSIS.md (Phase 1 analysis)
- db/docs/AUDIT_TRAIL_DELETION_SEMANTICS.md (deletion protocol)
- db/schema/canonical_schema.sql line 167 (canonical specification)
- Directive from Jamie & Schmidt (68. Directive.md)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511161100'
down_revision: Union[str, None] = '202511151510'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Transform event_id FK from CASCADE to SET NULL for audit trail preservation.
    
    Three-step atomic sequence:
    1. Drop existing FK constraint (ON DELETE CASCADE)
    2. Alter column to nullable (required for SET NULL to work)
    3. Add new FK constraint (ON DELETE SET NULL)
    
    This ensures that when an attribution_event is deleted (rare, maintenance-only),
    the related attribution_allocations rows survive with event_id set to NULL,
    preserving the financial audit trail.
    """
    
    # Step 1: Drop existing FK constraint
    # Note: PostgreSQL auto-generated name from inline REFERENCES clause
    op.drop_constraint(
        'attribution_allocations_event_id_fkey',
        'attribution_allocations',
        type_='foreignkey'
    )
    
    # Step 2: Alter column to nullable
    # This is a prerequisite for ON DELETE SET NULL to function
    # Without this, database would reject SET NULL action (cannot set NOT NULL column to NULL)
    op.alter_column(
        'attribution_allocations',
        'event_id',
        nullable=True
    )
    
    # Step 3: Add new FK constraint with SET NULL
    # This enforces audit trail preservation at the database level
    op.create_foreign_key(
        'fk_allocations_event_id_set_null',
        'attribution_allocations',
        'attribution_events',
        ['event_id'],
        ['id'],
        ondelete='SET NULL'
    )
    
    # Update table comment to reflect audit trail semantics
    op.execute("""
        COMMENT ON TABLE attribution_allocations IS 
            'Stores attribution model allocations (channel credit assignments). Purpose: Store channel credit for attribution calculations. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation. AUDIT TRAIL: Allocations persist even when source events are deleted (event_id becomes NULL).'
    """)
    
    # Update column comment to document NULL semantics
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.event_id IS 
            'Foreign key to attribution_events table. Purpose: Link allocation to source event for context. Data class: Non-PII. NULLABLE: event_id = NULL means event was deleted but allocation preserved for audit trail. ON DELETE SET NULL preserves financial records.'
    """)


def downgrade() -> None:
    """
    Rollback to CASCADE behavior (NOT RECOMMENDED in production).
    
    WARNING: This rollback removes audit trail preservation enforcement.
    Rolling back this migration means allocations will be deleted when events
    are deleted, destroying the financial audit trail.
    
    Only use this rollback if:
    1. Migration causes unexpected issues in dev/staging
    2. Explicit approval from Backend Lead + Product Owner
    3. No events have been deleted since upgrade (no NULL event_ids exist)
    
    Pre-rollback validation (manual):
    SELECT COUNT(*) FROM attribution_allocations WHERE event_id IS NULL;
    -- If count > 0, rollback will FAIL (cannot make NULL column NOT NULL)
    -- Must either:
    --   a) Delete allocations with NULL event_id (LOSES AUDIT TRAIL)
    --   b) Do not rollback (RECOMMENDED)
    """
    
    # Step 1: Drop SET NULL constraint
    op.drop_constraint(
        'fk_allocations_event_id_set_null',
        'attribution_allocations',
        type_='foreignkey'
    )
    
    # Step 2: Alter column to NOT NULL
    # WARNING: This will FAIL if any event_id values are NULL
    # Operator must manually handle NULL values before rollback
    op.alter_column(
        'attribution_allocations',
        'event_id',
        nullable=False
    )
    
    # Step 3: Re-add CASCADE constraint (original behavior)
    op.create_foreign_key(
        'attribution_allocations_event_id_fkey',
        'attribution_allocations',
        'attribution_events',
        ['event_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Restore original table comment
    op.execute("""
        COMMENT ON TABLE attribution_allocations IS 
            'Stores attribution model allocations (channel credit assignments). Purpose: Store channel credit for attribution calculations. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation.'
    """)
    
    # Restore original column comment
    op.execute("""
        COMMENT ON COLUMN attribution_allocations.event_id IS 
            'Foreign key to attribution_events table. Purpose: Link allocation to source event for context. Data class: Non-PII. ON DELETE CASCADE ensures allocations are deleted with their source event.'
    """)


