"""Add materialized views for contract-compliant JSON responses

Revision ID: 202511131119
Revises: 202511131115
Create Date: 2025-11-13 11:19:00

Migration Description:
Creates materialized views for contract-compliant JSON responses:
- mv_realtime_revenue: Aggregates revenue data for GET /api/attribution/revenue/realtime
- mv_reconciliation_status: Aggregates reconciliation status for GET /api/reconciliation/status

Contract Mapping:
- mv_realtime_revenue: api-contracts/openapi/v1/attribution.yaml:39-64 (RealtimeRevenueResponse)
- mv_reconciliation_status: api-contracts/openapi/v1/reconciliation.yaml:39-64 (ReconciliationStatusResponse)

Refresh Policy:
- CONCURRENTLY: Use REFRESH MATERIALIZED VIEW CONCURRENTLY to avoid locking
- TTL-based: Refresh every 30-60 seconds (application responsibility)
- Indexes: Unique indexes on tenant_id for p95 < 50ms performance target
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '202511131119'
down_revision: Union[str, None] = '202511131115'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Apply migration changes.
    
    Creates materialized views with:
    - Contract-compliant JSON shape (field names, types match contracts)
    - Performance indexes (unique on tenant_id for p95 < 50ms)
    - Comments explaining refresh policy
    """
    
    # Create mv_realtime_revenue materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW mv_realtime_revenue AS
        SELECT 
            rl.tenant_id,
            COALESCE(SUM(rl.revenue_cents), 0) / 100.0 AS total_revenue,
            BOOL_OR(rl.is_verified) AS verified,
            EXTRACT(EPOCH FROM (now() - MAX(rl.updated_at)))::INTEGER AS data_freshness_seconds
        FROM revenue_ledger rl
        GROUP BY rl.tenant_id
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id 
            ON mv_realtime_revenue (tenant_id)
    """)
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_realtime_revenue IS 
            'Aggregates realtime revenue data for GET /api/attribution/revenue/realtime endpoint. Purpose: Provide contract-compliant JSON response shape. Data class: Non-PII. Ownership: Attribution service. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).'
    """)
    
    # Create mv_reconciliation_status materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW mv_reconciliation_status AS
        SELECT 
            rr.tenant_id,
            rr.state,
            rr.last_run_at,
            rr.id AS reconciliation_run_id
        FROM reconciliation_runs rr
        INNER JOIN (
            SELECT tenant_id, MAX(last_run_at) AS max_last_run_at
            FROM reconciliation_runs
            GROUP BY tenant_id
        ) latest ON rr.tenant_id = latest.tenant_id 
            AND rr.last_run_at = latest.max_last_run_at
    """)
    
    op.execute("""
        CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id 
            ON mv_reconciliation_status (tenant_id)
    """)
    
    op.execute("""
        COMMENT ON MATERIALIZED VIEW mv_reconciliation_status IS 
            'Aggregates reconciliation pipeline status for GET /api/reconciliation/status endpoint. Purpose: Provide contract-compliant JSON response shape. Data class: Non-PII. Ownership: Reconciliation service. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).'
    """)


def downgrade() -> None:
    """
    Rollback migration changes.
    
    Drops materialized views in reverse order.
    """
    
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_reconciliation_status CASCADE")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_realtime_revenue CASCADE")



