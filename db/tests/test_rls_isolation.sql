-- RLS Isolation Test Script
-- Purpose: Empirically prove tenant isolation via Row-Level Security
-- Usage: Run these tests against a database with RLS enabled
-- Expected: All tests must pass to prove RLS isolation

-- ============================================================================
-- Setup: Create test tenants and data
-- ============================================================================

-- Create two test tenants
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Tenant A'),
    ('00000000-0000-0000-0000-000000000002', 'Tenant B')
ON CONFLICT (id) DO NOTHING;

-- Create test data for Tenant A
SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, raw_payload) VALUES
    ('00000000-0000-0000-0000-000000000001', now(), 10000, '{"test": "data_a"}'::jsonb)
ON CONFLICT DO NOTHING;

-- Create test data for Tenant B
SET app.current_tenant_id = '00000000-0000-0000-0000-000000000002';
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, raw_payload) VALUES
    ('00000000-0000-0000-0000-000000000002', now(), 20000, '{"test": "data_b"}'::jsonb)
ON CONFLICT DO NOTHING;

-- ============================================================================
-- Test 1: Cross-Tenant Denial - SELECT
-- ============================================================================
-- Expected: Tenant A cannot SELECT Tenant B data

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- This query should return 0 rows (RLS blocks cross-tenant access)
SELECT 
    COUNT(*) as tenant_b_row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: Tenant A cannot access Tenant B data'
        ELSE 'FAIL: Tenant A can access Tenant B data (RLS breach)'
    END as test_result
FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002';

-- Expected: tenant_b_row_count = 0, test_result = 'PASS'

-- ============================================================================
-- Test 2: Cross-Tenant Denial - INSERT
-- ============================================================================
-- Expected: Tenant A cannot INSERT into Tenant B

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- This INSERT should fail or insert 0 rows (RLS blocks cross-tenant insert)
INSERT INTO attribution_events (tenant_id, occurred_at, revenue_cents, raw_payload) 
VALUES ('00000000-0000-0000-0000-000000000002', now(), 30000, '{"test": "cross_tenant_insert"}'::jsonb);

-- Verify no cross-tenant row was inserted
SELECT 
    COUNT(*) as cross_tenant_row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: Tenant A cannot INSERT into Tenant B'
        ELSE 'FAIL: Tenant A can INSERT into Tenant B (RLS breach)'
    END as test_result
FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002' 
    AND raw_payload->>'test' = 'cross_tenant_insert';

-- Expected: cross_tenant_row_count = 0, test_result = 'PASS'

-- ============================================================================
-- Test 3: Cross-Tenant Denial - UPDATE
-- ============================================================================
-- Expected: Tenant A cannot UPDATE Tenant B data

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- This UPDATE should affect 0 rows (RLS blocks cross-tenant update)
UPDATE attribution_events 
SET revenue_cents = 99999 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002';

-- Verify no cross-tenant row was updated
SELECT 
    COUNT(*) as updated_row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: Tenant A cannot UPDATE Tenant B data'
        ELSE 'FAIL: Tenant A can UPDATE Tenant B data (RLS breach)'
    END as test_result
FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002' 
    AND revenue_cents = 99999;

-- Expected: updated_row_count = 0, test_result = 'PASS'

-- ============================================================================
-- Test 4: Cross-Tenant Denial - DELETE
-- ============================================================================
-- Expected: Tenant A cannot DELETE Tenant B data

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- This DELETE should affect 0 rows (RLS blocks cross-tenant delete)
DELETE FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002';

-- Verify no cross-tenant row was deleted (original row should still exist)
SELECT 
    COUNT(*) as remaining_row_count,
    CASE 
        WHEN COUNT(*) > 0 THEN 'PASS: Tenant A cannot DELETE Tenant B data'
        ELSE 'FAIL: Tenant A can DELETE Tenant B data (RLS breach)'
    END as test_result
FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000002';

-- Expected: remaining_row_count > 0, test_result = 'PASS'

-- ============================================================================
-- Test 5: GUC Validation - Unset GUC = No Access
-- ============================================================================
-- Expected: Unset GUC results in no access (default-deny)

RESET app.current_tenant_id;

-- This query should return 0 rows (default-deny when GUC is unset)
SELECT 
    COUNT(*) as unset_guc_row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: Unset GUC = no access (default-deny)'
        ELSE 'FAIL: Unset GUC allows access (RLS breach)'
    END as test_result
FROM attribution_events;

-- Expected: unset_guc_row_count = 0, test_result = 'PASS'

-- ============================================================================
-- Test 6: GUC Validation - NULL GUC = No Access
-- ============================================================================
-- Expected: NULL GUC results in no access (default-deny)

SET app.current_tenant_id = NULL;

-- This query should return 0 rows or error (default-deny when GUC is NULL)
SELECT 
    COUNT(*) as null_guc_row_count,
    CASE 
        WHEN COUNT(*) = 0 THEN 'PASS: NULL GUC = no access (default-deny)'
        ELSE 'FAIL: NULL GUC allows access (RLS breach)'
    END as test_result
FROM attribution_events;

-- Expected: null_guc_row_count = 0, test_result = 'PASS'

-- ============================================================================
-- Test 7: Valid Tenant Access - Tenant A can access Tenant A data
-- ============================================================================
-- Expected: Tenant A can SELECT/INSERT/UPDATE/DELETE Tenant A data

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- This query should return rows (valid tenant access)
SELECT 
    COUNT(*) as tenant_a_row_count,
    CASE 
        WHEN COUNT(*) > 0 THEN 'PASS: Tenant A can access Tenant A data'
        ELSE 'FAIL: Tenant A cannot access Tenant A data (RLS too restrictive)'
    END as test_result
FROM attribution_events 
WHERE tenant_id = '00000000-0000-0000-0000-000000000001';

-- Expected: tenant_a_row_count > 0, test_result = 'PASS'

-- ============================================================================
-- Test 8: Multi-Table Isolation - Test all tenant-scoped tables
-- ============================================================================
-- Expected: RLS isolation works across all tenant-scoped tables

SET app.current_tenant_id = '00000000-0000-0000-0000-000000000001';

-- Test dead_events
SELECT 
    COUNT(*) as dead_events_count,
    CASE 
        WHEN COUNT(*) = 0 OR COUNT(*) = (SELECT COUNT(*) FROM dead_events WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
        THEN 'PASS: dead_events RLS isolation works'
        ELSE 'FAIL: dead_events RLS isolation broken'
    END as test_result
FROM dead_events;

-- Test attribution_allocations
SELECT 
    COUNT(*) as allocations_count,
    CASE 
        WHEN COUNT(*) = 0 OR COUNT(*) = (SELECT COUNT(*) FROM attribution_allocations WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
        THEN 'PASS: attribution_allocations RLS isolation works'
        ELSE 'FAIL: attribution_allocations RLS isolation broken'
    END as test_result
FROM attribution_allocations;

-- Test revenue_ledger
SELECT 
    COUNT(*) as revenue_ledger_count,
    CASE 
        WHEN COUNT(*) = 0 OR COUNT(*) = (SELECT COUNT(*) FROM revenue_ledger WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
        THEN 'PASS: revenue_ledger RLS isolation works'
        ELSE 'FAIL: revenue_ledger RLS isolation broken'
    END as test_result
FROM revenue_ledger;

-- Test reconciliation_runs
SELECT 
    COUNT(*) as reconciliation_runs_count,
    CASE 
        WHEN COUNT(*) = 0 OR COUNT(*) = (SELECT COUNT(*) FROM reconciliation_runs WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
        THEN 'PASS: reconciliation_runs RLS isolation works'
        ELSE 'FAIL: reconciliation_runs RLS isolation broken'
    END as test_result
FROM reconciliation_runs;

-- ============================================================================
-- Test Summary
-- ============================================================================
-- All tests must pass for RLS isolation to be proven.
-- Expected results:
-- - Test 1: PASS (cross-tenant SELECT blocked)
-- - Test 2: PASS (cross-tenant INSERT blocked)
-- - Test 3: PASS (cross-tenant UPDATE blocked)
-- - Test 4: PASS (cross-tenant DELETE blocked)
-- - Test 5: PASS (unset GUC = no access)
-- - Test 6: PASS (NULL GUC = no access)
-- - Test 7: PASS (valid tenant access works)
-- - Test 8: PASS (all tables have RLS isolation)




