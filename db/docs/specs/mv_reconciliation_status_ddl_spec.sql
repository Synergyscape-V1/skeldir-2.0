-- DDL Specification for mv_reconciliation_status materialized view
-- Purpose: Aggregate reconciliation pipeline status for GET /api/reconciliation/status endpoint
-- Data Class: Non-PII
-- Ownership: Reconciliation service
-- Contract Mapping: api-contracts/openapi/v1/reconciliation.yaml:39-64 (ReconciliationStatusResponse)

-- Materialized view aggregates:
-- - state: Current state of reconciliation pipeline (idle|running|failed|completed)
-- - last_run_at: Timestamp of the last reconciliation run
-- - tenant_id: Tenant identifier

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
    AND rr.last_run_at = latest.max_last_run_at;

-- Index for p95 < 50ms performance target
CREATE UNIQUE INDEX idx_mv_reconciliation_status_tenant_id 
    ON mv_reconciliation_status (tenant_id);

-- Comments on all objects (Style Guide, Lint Rules)
COMMENT ON MATERIALIZED VIEW mv_reconciliation_status IS 
    'Aggregates reconciliation pipeline status for GET /api/reconciliation/status endpoint. Purpose: Provide contract-compliant JSON response shape. Data class: Non-PII. Ownership: Reconciliation service. Refresh policy: CONCURRENTLY with TTL-based refresh (30-60s).';

COMMENT ON COLUMN mv_reconciliation_status.tenant_id IS 
    'Tenant identifier. Purpose: Tenant isolation. Contract mapping: tenant_id (string uuid). Data class: Non-PII.';

COMMENT ON COLUMN mv_reconciliation_status.state IS 
    'Current state of the reconciliation pipeline. Purpose: Track pipeline status. Contract mapping: state enum (idle|running|failed|completed). Data class: Non-PII.';

COMMENT ON COLUMN mv_reconciliation_status.last_run_at IS 
    'Timestamp of the last reconciliation run. Purpose: Track last execution time. Contract mapping: last_run_at (string date-time). Data class: Non-PII.';

COMMENT ON INDEX idx_mv_reconciliation_status_tenant_id IS 
    'Unique index on tenant_id. Purpose: Enable fast tenant-scoped queries. Supports p95 < 50ms performance target.';




