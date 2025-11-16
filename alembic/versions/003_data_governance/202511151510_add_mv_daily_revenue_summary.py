"""Add materialized view for daily revenue summary analytics

Revision ID: 202511151510
Revises: 202511151500
Create Date: 2025-11-15 15:10:00.000000

Phase MV-3 of B0.3 MV Remediation Plan

This migration creates the mv_daily_revenue_summary materialized view required for:
- B2.6 Attribution API Endpoints (daily revenue dashboards)
- Fast revenue aggregation queries with <500ms p95 SLO
- Multi-currency revenue tracking
- Refund and chargeback visibility

The view pre-aggregates daily revenue metrics from revenue_ledger with
state-based filtering (captured, refunded, chargeback) for dashboard KPIs.

Key Features:
- Filters to verified financial states: 'captured', 'refunded', 'chargeback'
- Day-level granularity (DATE_TRUNC('day', verification_timestamp))
- Unique index on (tenant_id, revenue_date, state, currency) for REFRESH CONCURRENTLY
- Multi-currency support (currency column)
- Aggregates: total amount in cents, transaction count

Exit Gates:
- Migration applies cleanly
- View supports REFRESH MATERIALIZED VIEW CONCURRENTLY
- Index enables fast tenant + date range + state queries
- EXPLAIN shows index-only scans for typical dashboard queries

References:
- Architecture Guide §3.1 (Materialized Views)
- B0.3_MV_VALIDATOR_IMPLEMENTATION.md (Phase MV-1 canonical contract)
- db/schema/live_schema_snapshot.sql (revenue_ledger schema)
"""
from alembic import op
import sqlalchemy as sa
from typing import Union


# revision identifiers, used by Alembic.
revision: str = '202511151510'
down_revision: Union[str, None] = '202511151500'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """
    Create mv_daily_revenue_summary materialized view.
    
    Implementation:
    1. Create materialized view filtering to verified financial states
    2. Add unique index on (tenant_id, revenue_date, state, currency)
    3. Add comment explaining purpose and refresh policy
    
    Query Pattern:
    - Filter by tenant_id (RLS enforcement)
    - Filter by revenue_date range (typically last 30-90 days)
    - Filter by state ('captured', 'refunded', 'chargeback')
    - Optional filter by currency
    - Order by revenue_date DESC
    
    Expected Performance:
    - P50 < 50ms, P95 < 500ms
    - Index-only scan on idx_mv_daily_revenue_summary_unique
    - ~360 rows per tenant (90 days × 4 states × 1 currency average)
    """
    
    # ========================================================================
    # Step 1: Create mv_daily_revenue_summary materialized view
    # ========================================================================
    
    op.execute("""
        CREATE MATERIALIZED VIEW mv_daily_revenue_summary AS
        SELECT
            tenant_id,
            DATE_TRUNC('day', verification_timestamp) AS revenue_date,
            state,
            currency,
            SUM(amount_cents) AS total_amount_cents,
            COUNT(*) AS transaction_count
        FROM revenue_ledger
        WHERE state IN ('captured', 'refunded', 'chargeback')
        GROUP BY tenant_id, DATE_TRUNC('day', verification_timestamp), state, currency
    """)
    
    # ========================================================================
    # Step 2: Create unique index for REFRESH CONCURRENTLY support
    # ========================================================================
    
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_daily_revenue_summary_unique
        ON mv_daily_revenue_summary (tenant_id, revenue_date, state, currency)
    """)
    
    # ========================================================================
    # Step 3: Add comment explaining purpose and refresh policy
    # ========================================================================
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_daily_revenue_summary IS 
            'Pre-aggregates daily revenue, refunds, and chargebacks by currency. Supports B2.6 API. Refresh CONCURRENTLY. Purpose: Enable sub-500ms p95 daily revenue queries for KPI dashboards without full table scans on revenue_ledger. Columns: tenant_id, revenue_date (day), state (captured/refunded/chargeback), currency (ISO 4217), total_amount_cents (sum), transaction_count (count). Refresh policy: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary on schedule (recommended: hourly or on-demand). Index: UNIQUE on (tenant_id, revenue_date, state, currency) enables REFRESH CONCURRENTLY and fast multi-currency queries.'
    """)


def downgrade() -> None:
    """
    Drop mv_daily_revenue_summary materialized view.
    
    Index is automatically dropped with the view via CASCADE.
    """
    
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_daily_revenue_summary CASCADE")


