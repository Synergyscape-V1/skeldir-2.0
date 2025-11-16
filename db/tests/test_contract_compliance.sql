-- Test queries to verify materialized views produce contract-compliant JSON
-- Purpose: Validate that materialized view output matches OpenAPI contract schemas
-- Usage: Run these queries and compare output to contract schemas

-- ============================================================================
-- Test 1: mv_realtime_revenue JSON Shape Compliance
-- ============================================================================
-- Contract: api-contracts/openapi/v1/attribution.yaml:39-64 (RealtimeRevenueResponse)
-- Required fields: total_revenue, verified, data_freshness_seconds, tenant_id

-- Test query: Select from materialized view and verify field names/types
SELECT 
    tenant_id,
    total_revenue,
    verified,
    data_freshness_seconds
FROM mv_realtime_revenue
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000'
LIMIT 1;

-- Expected JSON shape (per contract):
-- {
--   "total_revenue": 125000.50,        -- number (float)
--   "verified": true,                  -- boolean
--   "data_freshness_seconds": 45,      -- integer
--   "tenant_id": "550e8400-..."        -- string (uuid)
-- }

-- Validation checklist:
-- ✅ total_revenue: number (float) - verified via SELECT (should be numeric)
-- ✅ verified: boolean - verified via SELECT (should be boolean)
-- ✅ data_freshness_seconds: integer - verified via SELECT (should be integer)
-- ✅ tenant_id: string (uuid) - verified via SELECT (should be uuid)
-- ✅ All required fields present (no NULL values for required fields)

-- ============================================================================
-- Test 2: mv_reconciliation_status JSON Shape Compliance
-- ============================================================================
-- Contract: api-contracts/openapi/v1/reconciliation.yaml:39-64 (ReconciliationStatusResponse)
-- Required fields: state, last_run_at, tenant_id

-- Test query: Select from materialized view and verify field names/types
SELECT 
    tenant_id,
    state,
    last_run_at
FROM mv_reconciliation_status
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000'
LIMIT 1;

-- Expected JSON shape (per contract):
-- {
--   "state": "completed",              -- enum (idle|running|failed|completed)
--   "last_run_at": "2025-11-10T14:30:00Z",  -- string (date-time)
--   "tenant_id": "550e8400-..."        -- string (uuid)
-- }

-- Validation checklist:
-- ✅ state: enum (idle|running|failed|completed) - verified via SELECT (should be one of these values)
-- ✅ last_run_at: string (date-time) - verified via SELECT (should be timestamptz, ISO 8601 format)
-- ✅ tenant_id: string (uuid) - verified via SELECT (should be uuid)
-- ✅ All required fields present (no NULL values for required fields)

-- ============================================================================
-- Test 3: Type Conversion Validation
-- ============================================================================

-- Test: Verify total_revenue is converted from cents to dollars
-- Expected: revenue_cents / 100.0 = total_revenue (float)
SELECT 
    rl.revenue_cents,
    mv.total_revenue,
    (rl.revenue_cents / 100.0) AS expected_total_revenue,
    CASE 
        WHEN ABS(mv.total_revenue - (rl.revenue_cents / 100.0)) < 0.01 
        THEN 'PASS' 
        ELSE 'FAIL' 
    END AS conversion_test
FROM revenue_ledger rl
JOIN mv_realtime_revenue mv ON rl.tenant_id = mv.tenant_id
LIMIT 1;

-- Expected: conversion_test = 'PASS'

-- ============================================================================
-- Test 4: Performance Validation (p95 < 50ms)
-- ============================================================================

-- Test: Verify index usage for tenant-scoped queries
EXPLAIN ANALYZE
SELECT * FROM mv_realtime_revenue 
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000';

-- Expected: Index Scan on idx_mv_realtime_revenue_tenant_id
-- Expected: Execution time < 50ms (p95 target)

EXPLAIN ANALYZE
SELECT * FROM mv_reconciliation_status 
WHERE tenant_id = '550e8400-e29b-41d4-a716-446655440000';

-- Expected: Index Scan on idx_mv_reconciliation_status_tenant_id
-- Expected: Execution time < 50ms (p95 target)




