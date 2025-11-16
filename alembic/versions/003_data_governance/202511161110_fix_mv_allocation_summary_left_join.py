"""Fix mv_allocation_summary to use LEFT JOIN for nullable event_id

Revision ID: 202511161110
Revises: 202511161100
Create Date: 2025-11-16 11:10:00.000000

Phase 3 of B0.3 Audit Trail FK Realignment

This migration updates the mv_allocation_summary materialized view to use LEFT JOIN
instead of INNER JOIN, ensuring allocations with NULL event_id (where source event
was deleted) are included in the view and revenue totals.

CRITICAL CHANGE:
- BEFORE: INNER JOIN (excludes allocations with event_id = NULL)
- AFTER: LEFT JOIN (includes all allocations, handles NULL event_id)

Rationale:
- Phase 2 made event_id nullable with ON DELETE SET NULL
- INNER JOIN would exclude allocations where event was deleted
- Financial totals would be UNDERSTATED (missing revenue)
- LEFT JOIN ensures complete financial accounting

NULL Handling Semantics:
- When event_id IS NULL:
  - event_revenue_cents = NULL (cannot determine original event revenue)
  - is_balanced = NULL (cannot validate sum-equality without event revenue)
  - drift_cents = NULL (no baseline to compare against)
- Allocations with NULL event_id are still INCLUDED in view for reporting
- Revenue totals must SUM(total_allocated_cents) including NULL event_id rows

Impact Analysis:
- Existing queries using mv_allocation_summary continue to work
- SUM() aggregations correctly include NULL event_id allocations
- Validation logic gracefully handles NULL validation status
- No breaking changes to view schema (same columns)

Exit Gates (Phase 3):
- Gate 3.1: Materialized view recreated with LEFT JOIN
- Gate 3.2: View schema unchanged (same columns, types)
- Gate 3.3: UNIQUE index remains functional for REFRESH CONCURRENTLY

References:
- db/docs/AUDIT_TRAIL_FK_IMPACT_ANALYSIS.md (Section 2.1, critical finding)
- db/docs/AUDIT_TRAIL_DELETION_SEMANTICS.md (Section 3, join semantics)
- alembic/versions/202511131240_add_sum_equality_validation.py (original view)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511161110'
down_revision: Union[str, None] = '202511161100'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Recreate mv_allocation_summary with LEFT JOIN to handle nullable event_id.
    
    This ensures allocations with NULL event_id (where source event was deleted)
    are included in the view, maintaining complete financial accounting.
    """
    
    # Step 1: Drop existing materialized view (and its dependent index)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_allocation_summary CASCADE")
    
    # Step 2: Recreate materialized view with LEFT JOIN
    op.execute("""
        CREATE MATERIALIZED VIEW mv_allocation_summary AS
        SELECT 
            aa.tenant_id,
            aa.event_id,  -- May be NULL (event deleted)
            aa.model_version,
            SUM(aa.allocated_revenue_cents) AS total_allocated_cents,
            e.revenue_cents AS event_revenue_cents,  -- NULL when event_id IS NULL
            CASE 
                WHEN e.revenue_cents IS NULL THEN NULL  -- Cannot validate without event
                ELSE (SUM(aa.allocated_revenue_cents) = e.revenue_cents)
            END AS is_balanced,
            CASE 
                WHEN e.revenue_cents IS NULL THEN NULL  -- Cannot compute drift without event
                ELSE ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents)
            END AS drift_cents
        FROM attribution_allocations aa
        LEFT JOIN attribution_events e ON aa.event_id = e.id  -- ✅ LEFT JOIN for nullable event_id
        GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
    """)
    
    # Step 3: Update comment to document NULL handling
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_allocation_summary IS
            'Aggregates allocation sums per (tenant_id, event_id, model_version) for sum-equality validation. Purpose: Enable reporting and validation of revenue accounting correctness. NULL HANDLING: event_id may be NULL (event deleted); validation fields (is_balanced, drift_cents) are NULL when event unavailable. LEFT JOIN ensures all allocations included in financial totals. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).'
    """)
    
    # Step 4: Recreate unique index for REFRESH CONCURRENTLY
    # Note: PostgreSQL treats NULL as distinct in unique indexes, so multiple NULL event_ids allowed
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_allocation_summary_key
            ON mv_allocation_summary (tenant_id, event_id, model_version);
    """)
    
    # Step 5: Add index comment
    op.execute("""
        COMMENT ON INDEX idx_mv_allocation_summary_key IS
            'Unique index on (tenant_id, event_id, model_version) for REFRESH CONCURRENTLY support. NULL event_id values are treated as distinct (multiple NULLs allowed).'
    """)


def downgrade() -> None:
    """
    Rollback to INNER JOIN (original behavior).
    
    WARNING: This rollback reintroduces the bug where allocations with NULL event_id
    are excluded from the materialized view, causing financial totals to be understated.
    
    Only use this rollback if Phase 2 (FK realignment) is also rolled back.
    """
    
    # Step 1: Drop LEFT JOIN version
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_allocation_summary CASCADE")
    
    # Step 2: Recreate original INNER JOIN version
    op.execute("""
        CREATE MATERIALIZED VIEW mv_allocation_summary AS
        SELECT 
            aa.tenant_id,
            aa.event_id,
            aa.model_version,
            SUM(aa.allocated_revenue_cents) AS total_allocated_cents,
            e.revenue_cents AS event_revenue_cents,
            (SUM(aa.allocated_revenue_cents) = e.revenue_cents) AS is_balanced,
            ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents) AS drift_cents
        FROM attribution_allocations aa
        INNER JOIN attribution_events e ON aa.event_id = e.id  -- Original INNER JOIN
        GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
    """)
    
    # Step 3: Restore original comment
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_allocation_summary IS
            'Aggregates allocation sums per (tenant_id, event_id, model_version) for sum-equality validation. Purpose: Enable reporting and validation of revenue accounting correctness. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).'
    """)
    
    # Step 4: Recreate original unique index
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_allocation_summary_key
            ON mv_allocation_summary (tenant_id, event_id, model_version);
    """)
    
    # Step 5: Restore original index comment
    op.execute("""
        COMMENT ON INDEX idx_mv_allocation_summary_key IS
            'Unique index on (tenant_id, event_id, model_version) for REFRESH CONCURRENTLY support.'
    """)


