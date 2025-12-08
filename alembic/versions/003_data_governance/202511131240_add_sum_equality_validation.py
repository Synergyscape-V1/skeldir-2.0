"""Add sum-equality validation for allocation revenue accounting

Revision ID: 202511131240
Revises: 202511131232
Create Date: 2025-11-13 12:40:00

Migration Description:
Implements sum-equality invariant per Phase 4B requirements:
- Materialized view (mv_allocation_summary) for reporting/validation
- Trigger function (check_allocation_sum) for real-time enforcement
- Defense-in-depth approach: both MV and trigger for correctness

Contract Mapping:
- Supports deterministic revenue accounting: allocations sum to event revenue per (tenant_id, event_id, model_version)
- Enables reconciliation and auditability

Governance Compliance:
- Style guide compliance (snake_case, comments, indexes)
- DDL lint rules (comments, constraints)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131240'
down_revision: Union[str, None] = '202511131232'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply migration changes.
    
    Creates:
    1. Materialized view (mv_allocation_summary) for reporting/validation
    2. Trigger function (check_allocation_sum) for real-time enforcement
    3. Trigger (trg_check_allocation_sum) on attribution_allocations table
    """
    
    # Create trigger function for sum-equality validation
    op.execute("""
        CREATE OR REPLACE FUNCTION check_allocation_sum()
        RETURNS TRIGGER AS $$
        DECLARE
            event_revenue INTEGER;
            allocated_sum INTEGER;
            tolerance_cents INTEGER := 1; -- ±1 cent rounding tolerance
        BEGIN
            SELECT revenue_cents INTO event_revenue
            FROM attribution_events
            WHERE id = COALESCE(NEW.event_id, OLD.event_id);
            
            SELECT COALESCE(SUM(allocated_revenue_cents), 0) INTO allocated_sum
            FROM attribution_allocations
            WHERE event_id = COALESCE(NEW.event_id, OLD.event_id)
              AND model_version = COALESCE(NEW.model_version, OLD.model_version);
            
            IF ABS(allocated_sum - event_revenue) > tolerance_cents THEN
                RAISE EXCEPTION 'Allocation sum mismatch: allocated=% expected=% drift=%', 
                    allocated_sum, event_revenue, ABS(allocated_sum - event_revenue);
            END IF;
            
            RETURN COALESCE(NEW, OLD);
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION check_allocation_sum() IS
            'Validates that allocations sum to event revenue per (event_id, model_version) with ±1 cent tolerance. Purpose: Enforce sum-equality invariant for deterministic revenue accounting. Raises exception if sum mismatch exceeds tolerance.'
    """)
    
    # Create trigger on attribution_allocations table
    op.execute("""
        CREATE TRIGGER trg_check_allocation_sum
            AFTER INSERT OR UPDATE OR DELETE ON attribution_allocations
            FOR EACH ROW EXECUTE FUNCTION check_allocation_sum();
    """)
    
    op.execute("""
        COMMENT ON TRIGGER trg_check_allocation_sum ON attribution_allocations IS
            'Enforces sum-equality invariant: allocations must sum to event revenue per (event_id, model_version) with ±1 cent tolerance. Purpose: Real-time validation of revenue accounting correctness.'
    """)
    
    # Create materialized view for reporting/validation
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
        INNER JOIN attribution_events e ON aa.event_id = e.id
        GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
    """)
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_allocation_summary IS
            'Aggregates allocation sums per (tenant_id, event_id, model_version) for sum-equality validation. Purpose: Enable reporting and validation of revenue accounting correctness. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).'
    """)
    
    # Create unique index on materialized view
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_allocation_summary_key
            ON mv_allocation_summary (tenant_id, event_id, model_version);
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_mv_allocation_summary_key IS
            'Unique index on (tenant_id, event_id, model_version). Purpose: Enable fast lookups for sum-equality validation queries.'
    """)
    
    # Create index on drift_cents for finding unbalanced allocations
    op.execute("""
        CREATE INDEX idx_mv_allocation_summary_drift
            ON mv_allocation_summary (drift_cents)
            WHERE drift_cents > 1;
    """)
    
    op.execute("""
        COMMENT ON INDEX idx_mv_allocation_summary_drift IS
            'Partial index on drift_cents WHERE drift_cents > 1. Purpose: Enable fast queries for unbalanced allocations (drift > 1 cent tolerance).'
    """)


def downgrade() -> None:
    """
    Rollback migration changes.
    
    Removes:
    1. Materialized view (mv_allocation_summary)
    2. Trigger (trg_check_allocation_sum)
    3. Trigger function (check_allocation_sum)
    """
    
    # Drop materialized view (drops indexes automatically)
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_allocation_summary CASCADE")
    
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_check_allocation_sum ON attribution_allocations")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS check_allocation_sum()")



