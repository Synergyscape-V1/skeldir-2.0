-- DDL Specification for mv_realtime_revenue materialized view
-- Purpose: Aggregate realtime revenue data for GET /api/attribution/revenue/realtime endpoint
-- Data Class: Non-PII
-- Ownership: Attribution service
-- Contract Mapping: api-contracts/openapi/v1/attribution.yaml:39-64 (RealtimeRevenueResponse)

-- Materialized view aggregates:
-- - total_revenue: Sum of revenue_cents from revenue_ledger (converted to dollars)
-- - verified: Boolean flag indicating if revenue is verified
-- - data_freshness_seconds: Seconds since last update (calculated from updated_at)
-- - tenant_id: Tenant identifier

CREATE MATERIALIZED VIEW mv_realtime_revenue AS
SELECT 
    rl.tenant_id,
    COALESCE(SUM(rl.revenue_cents), 0) / 100.0 AS total_revenue,
    BOOL_OR(rl.is_verified) AS verified,
    EXTRACT(EPOCH FROM (now() - MAX(rl.updated_at)))::INTEGER AS data_freshness_seconds
FROM revenue_ledger rl
GROUP BY rl.tenant_id;

-- Index for p95 < 50ms performance target
CREATE UNIQUE INDEX idx_mv_realtime_revenue_tenant_id 
    ON mv_realtime_revenue (tenant_id);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON MATERIALIZED VIEW mv_realtime_revenue IS 
    'Aggregates realtime revenue data for GET /api/attribution/revenue/realtime endpoint. Purpose: Provide contract-compliant JSON response shape. Data class: Non-PII. Ownership: Attribution service. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).';

COMMENT ON COLUMN mv_realtime_revenue.tenant_id IS 
    'Tenant identifier. Purpose: Tenant isolation. Contract mapping: tenant_id (string uuid). Data class: Non-PII.';

COMMENT ON COLUMN mv_realtime_revenue.total_revenue IS 
    'Total revenue in dollars (float). Purpose: Aggregate revenue sum. Contract mapping: total_revenue (number float). Data class: Non-PII.';

COMMENT ON COLUMN mv_realtime_revenue.verified IS 
    'Whether revenue has been verified. Purpose: Reconciliation status. Contract mapping: verified (boolean). Data class: Non-PII.';

COMMENT ON COLUMN mv_realtime_revenue.data_freshness_seconds IS 
    'Seconds since data was last updated. Purpose: Data freshness tracking. Contract mapping: data_freshness_seconds (integer). Data class: Non-PII.';

COMMENT ON INDEX idx_mv_realtime_revenue_tenant_id IS 
    'Unique index on tenant_id. Purpose: Enable fast tenant-scoped queries. Supports p95 < 50ms performance target.';




