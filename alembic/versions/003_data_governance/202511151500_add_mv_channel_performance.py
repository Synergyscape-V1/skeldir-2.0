"""Add materialized view for channel performance analytics

Revision ID: 202511151500
Revises: 202511151450
Create Date: 2025-11-15 15:00:00.000000

Phase MV-2 of B0.3 MV Remediation Plan

This migration creates the mv_channel_performance materialized view required for:
- B2.6 Attribution API Endpoints (channel performance dashboards)
- Fast channel-level aggregation queries with <500ms p95 SLO

The view pre-aggregates channel performance metrics from attribution_allocations
with a 90-day rolling window to support high-frequency dashboard reads.

Key Features:
- 90-day rolling window (created_at >= CURRENT_DATE - INTERVAL '90 days')
- Day-level granularity (DATE_TRUNC('day', created_at))
- Unique index on (tenant_id, channel_code, allocation_date) for REFRESH CONCURRENTLY
- Aggregates: total conversions, total revenue, avg confidence, allocation count

Exit Gates:
- Migration applies cleanly
- View supports REFRESH MATERIALIZED VIEW CONCURRENTLY
- Index enables fast tenant + date range queries
- EXPLAIN shows index-only scans for typical dashboard queries

References:
- Architecture Guide §3.1 (Materialized Views)
- B0.3_MV_VALIDATOR_IMPLEMENTATION.md (Phase MV-1 canonical contract)
- db/schema/live_schema_snapshot.sql (attribution_allocations schema)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151500'
down_revision: Union[str, None] = '202511151450'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Create mv_channel_performance materialized view.
    
    Implementation:
    1. Create materialized view with 90-day rolling window
    2. Add unique index on (tenant_id, channel_code, allocation_date)
    3. Add comment explaining purpose and refresh policy
    
    Query Pattern:
    - Filter by tenant_id (RLS enforcement)
    - Filter by allocation_date range (typically last 30 days)
    - Optional filter by channel_code
    - Order by total_revenue_cents DESC
    
    Expected Performance:
    - P50 < 50ms, P95 < 500ms
    - Index-only scan on idx_mv_channel_performance_unique
    - ~2,700 rows per tenant (90 days × 30 channels average)
    """
    
    # ========================================================================
    # Step 1: Create mv_channel_performance materialized view
    # ========================================================================
    
    op.execute("""
        CREATE MATERIALIZED VIEW mv_channel_performance AS
        SELECT
            tenant_id,
            channel_code,
            DATE_TRUNC('day', created_at) AS allocation_date,
            COUNT(DISTINCT event_id) AS total_conversions,
            SUM(allocated_revenue_cents) AS total_revenue_cents,
            AVG(confidence_score) AS avg_confidence_score,
            COUNT(*) AS total_allocations
        FROM attribution_allocations
        WHERE created_at >= CURRENT_DATE - INTERVAL '90 days'
        GROUP BY tenant_id, channel_code, DATE_TRUNC('day', created_at)
    """)
    
    # ========================================================================
    # Step 2: Create unique index for REFRESH CONCURRENTLY support
    # ========================================================================
    
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_channel_performance_unique
        ON mv_channel_performance (tenant_id, channel_code, allocation_date)
    """)
    
    # ========================================================================
    # Step 3: Add comment explaining purpose and refresh policy
    # ========================================================================
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_channel_performance IS 
            'Pre-aggregates channel performance by day for fast dashboard queries. Supports B2.6 API. Refresh CONCURRENTLY. 90-day rolling window. Purpose: Enable sub-500ms p95 channel performance queries without full table scans on attribution_allocations. Columns: tenant_id, channel_code, allocation_date (day), total_conversions (distinct events), total_revenue_cents (sum), avg_confidence_score, total_allocations (count). Refresh policy: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance on schedule (recommended: hourly or on-demand). Index: UNIQUE on (tenant_id, channel_code, allocation_date) enables REFRESH CONCURRENTLY.'
    """)


def downgrade() -> None:
    """
    Drop mv_channel_performance materialized view.
    
    Index is automatically dropped with the view via CASCADE.
    """
    
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_channel_performance CASCADE")


