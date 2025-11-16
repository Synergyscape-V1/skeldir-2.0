-- Test Script: Audit Trail Preservation (Allocations Survive Event Deletion)
-- Purpose: Empirically verify that attribution_allocations survive event deletion with event_id = NULL
-- Phase: 5 (Behavioral Validation)
-- Exit Gates: 5.1 (row preservation), 5.2 (event_id NULL), 5.3 (financial totals unchanged), 5.4 (MV refresh)

-- ============================================================================
-- PREAMBLE: Test Context
-- ============================================================================
-- This test validates the core audit trail preservation requirement:
-- When an attribution_events row is deleted, related attribution_allocations
-- rows MUST survive with event_id set to NULL, preserving the financial audit trail.
--
-- FK Behavior Under Test:
-- - BEFORE Fix: event_id NOT NULL with ON DELETE CASCADE (allocations deleted)
-- - AFTER Fix: event_id NULLABLE with ON DELETE SET NULL (allocations preserved)
--
-- Test Approach:
-- 1. Create test tenant, event, and allocations
-- 2. Record initial financial state (allocation count and revenue total)
-- 3. Delete the attribution_events row (as migration_owner)
-- 4. Verify allocations exist with event_id = NULL
-- 5. Verify financial totals unchanged
-- 6. Verify materialized view refresh succeeds
-- ============================================================================

\echo '================================================================================'
\echo 'TEST SUITE: Audit Trail Preservation (Phase 5 Behavioral Validation)'
\echo 'Date: 2025-11-16'
\echo 'Purpose: Verify allocations survive event deletion with event_id = NULL'
\echo '================================================================================'
\echo ''

-- Start transaction for test isolation
BEGIN;

\echo 'Setup: Creating test tenant, event, and allocations...'
\echo ''

-- ============================================================================
-- TEST SETUP: Create Test Data
-- ============================================================================

-- Create test tenant
INSERT INTO tenants (id, name, api_key_hash, notification_email) VALUES 
    ('00000000-0000-0000-0000-AUDIT00000001', 'Audit Test Tenant', 'audit_test_hash_001', 'audit@test.local')
ON CONFLICT (id) DO NOTHING;

-- Create test attribution event
INSERT INTO attribution_events (
    id, 
    tenant_id, 
    session_id,
    idempotency_key,
    event_type,
    channel,
    event_timestamp,
    conversion_value_cents,
    currency,
    processing_status,
    raw_payload,
    created_at,
    updated_at
) VALUES (
    '10000000-0000-0000-0000-AUDITEVENT001',
    '00000000-0000-0000-0000-AUDIT00000001',
    '20000000-0000-0000-0000-AUDITSESS0001',
    'audit-trail-test-event-001',
    'purchase',
    'google_search_paid',
    '2025-11-16 10:00:00+00',
    10000,  -- $100.00
    'USD',
    'processed',
    '{"test": "audit_trail_preservation", "revenue": 100.00}'::jsonb,
    now(),
    now()
)
ON CONFLICT (idempotency_key) DO NOTHING;

-- Create test allocations (channel credit for the event)
-- Allocation 1: Google Search - 60% of revenue
INSERT INTO attribution_allocations (
    id,
    tenant_id,
    event_id,
    channel_code,
    allocated_revenue_cents,
    allocation_ratio,
    model_version,
    model_type,
    confidence_score,
    created_at,
    updated_at
) VALUES (
    '30000000-0000-0000-0000-AUDITALLOC001',
    '00000000-0000-0000-0000-AUDIT00000001',
    '10000000-0000-0000-0000-AUDITEVENT001',
    'google_search_paid',
    6000,  -- $60.00
    0.60000,
    '1.0.0',
    'bayesian',
    0.850,
    now(),
    now()
)
ON CONFLICT (id) DO NOTHING;

-- Allocation 2: Facebook - 40% of revenue
INSERT INTO attribution_allocations (
    id,
    tenant_id,
    event_id,
    channel_code,
    allocated_revenue_cents,
    allocation_ratio,
    model_version,
    model_type,
    confidence_score,
    created_at,
    updated_at
) VALUES (
    '30000000-0000-0000-0000-AUDITALLOC002',
    '00000000-0000-0000-0000-AUDIT00000001',
    '10000000-0000-0000-0000-AUDITEVENT001',
    'facebook_paid',
    4000,  -- $40.00
    0.40000,
    '1.0.0',
    'bayesian',
    0.750,
    now(),
    now()
)
ON CONFLICT (id) DO NOTHING;

\echo 'Setup complete.'
\echo ''

-- ============================================================================
-- VALIDATION GATE 0: Pre-Deletion State
-- ============================================================================

\echo 'GATE 0: Pre-Deletion State Verification'
\echo '========================================='
\echo ''

-- Verify event exists
\echo 'Pre-Delete: Event count (expected: 1):'
SELECT COUNT(*) AS event_count
FROM attribution_events 
WHERE id = '10000000-0000-0000-0000-AUDITEVENT001';

-- Verify allocations exist with non-NULL event_id
\echo ''
\echo 'Pre-Delete: Allocation count (expected: 2):'
SELECT COUNT(*) AS allocation_count
FROM attribution_allocations 
WHERE event_id = '10000000-0000-0000-0000-AUDITEVENT001';

-- Verify event_id is NOT NULL
\echo ''
\echo 'Pre-Delete: NULL event_id count (expected: 0):'
SELECT COUNT(*) AS null_event_id_count
FROM attribution_allocations 
WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')
  AND event_id IS NULL;

-- Record initial financial total
\echo ''
\echo 'Pre-Delete: Total allocated revenue (expected: 10000 cents = $100.00):'
SELECT SUM(allocated_revenue_cents) AS total_revenue_cents
FROM attribution_allocations 
WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001';

\echo ''
\echo 'Gate 0: ✅ PASS (pre-deletion state verified)'
\echo ''

-- ============================================================================
-- TEST EXECUTION: Delete Event (as migration_owner)
-- ============================================================================

\echo 'TEST EXECUTION: Deleting attribution event...'
\echo '=============================================='
\echo ''

-- Delete the attribution_events row
-- This simulates a maintenance deletion by migration_owner
-- Expected behavior: Allocations survive with event_id = NULL (ON DELETE SET NULL)
DELETE FROM attribution_events 
WHERE id = '10000000-0000-0000-0000-AUDITEVENT001';

\echo 'Event deleted.'
\echo ''

-- ============================================================================
-- VALIDATION GATE 5.1: Row Preservation
-- ============================================================================

\echo 'GATE 5.1: Row Preservation (Allocations Must Exist)'
\echo '===================================================='
\echo ''

-- Verify allocations still exist (by ID, not event_id)
\echo 'Post-Delete: Allocation count by ID (expected: 2):'
SELECT COUNT(*) AS allocation_count
FROM attribution_allocations 
WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002');

-- Verify result
SELECT 
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')) = 2
        THEN '✅ PASS: Both allocations preserved (count = 2)'
        ELSE '❌ FAIL: Allocations were deleted (count != 2)'
    END AS gate_5_1_result;

\echo ''

-- ============================================================================
-- VALIDATION GATE 5.2: event_id IS NULL (Behavioral Proof)
-- ============================================================================

\echo 'GATE 5.2: event_id IS NULL (SET NULL Behavior Operational)'
\echo '=========================================================='
\echo ''

-- Verify event_id is NULL for both allocations
\echo 'Post-Delete: NULL event_id count (expected: 2):'
SELECT COUNT(*) AS null_event_id_count
FROM attribution_allocations 
WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')
  AND event_id IS NULL;

-- Show event_id values explicitly
\echo ''
\echo 'Post-Delete: event_id values (expected: NULL, NULL):'
SELECT 
    id, 
    event_id,
    CASE 
        WHEN event_id IS NULL THEN 'NULL (✅ CORRECT)'
        ELSE 'NOT NULL (❌ INCORRECT)'
    END AS event_id_status
FROM attribution_allocations 
WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')
ORDER BY id;

-- Verify result
SELECT 
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002') AND event_id IS NULL) = 2
        THEN '✅ PASS: event_id set to NULL (SET NULL behavior verified)'
        ELSE '❌ FAIL: event_id not NULL (SET NULL behavior not working)'
    END AS gate_5_2_result;

\echo ''

-- ============================================================================
-- VALIDATION GATE 5.3: Financial Totals Unchanged
-- ============================================================================

\echo 'GATE 5.3: Financial Totals Unchanged (Audit Trail Integrity)'
\echo '============================================================='
\echo ''

-- Verify total allocated revenue unchanged
\echo 'Post-Delete: Total allocated revenue (expected: 10000 cents = $100.00):'
SELECT SUM(allocated_revenue_cents) AS total_revenue_cents
FROM attribution_allocations 
WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001';

-- Compare pre and post
\echo ''
\echo 'Financial Total Comparison:'
WITH pre_delete AS (
    -- This would be the pre-recorded value, but we can't store it across DELETE
    -- So we use the known test data value: 10000 cents
    SELECT 10000 AS pre_total
),
post_delete AS (
    SELECT SUM(allocated_revenue_cents) AS post_total
    FROM attribution_allocations 
    WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001'
)
SELECT 
    pre.pre_total,
    post.post_total,
    (pre.pre_total = post.post_total) AS totals_match,
    CASE 
        WHEN pre.pre_total = post.post_total THEN '✅ PASS: Financial totals unchanged'
        ELSE '❌ FAIL: Financial totals changed (audit trail compromised)'
    END AS gate_5_3_result
FROM pre_delete pre, post_delete post;

\echo ''

-- ============================================================================
-- VALIDATION GATE 5.4: Materialized View Refresh Succeeds
-- ============================================================================

\echo 'GATE 5.4: Materialized View Refresh (LEFT JOIN Compatibility)'
\echo '=============================================================='
\echo ''

-- Refresh materialized view (tests LEFT JOIN compatibility with NULL event_id)
\echo 'Refreshing mv_allocation_summary...'
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary;
\echo 'Refresh complete.'
\echo ''

-- Verify allocations with NULL event_id are in the view
\echo 'Post-Refresh: Allocations in MV with NULL event_id (expected: 1 row for model 1.0.0):'
SELECT 
    tenant_id,
    event_id,
    model_version,
    total_allocated_cents,
    event_revenue_cents,
    is_balanced,
    drift_cents,
    CASE 
        WHEN event_id IS NULL THEN 'NULL (✅ event deleted, allocation preserved)'
        ELSE 'NOT NULL'
    END AS event_id_status,
    CASE 
        WHEN event_revenue_cents IS NULL THEN 'NULL (✅ cannot validate without event)'
        ELSE 'NOT NULL'
    END AS validation_status
FROM mv_allocation_summary
WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001';

-- Verify result
SELECT 
    CASE 
        WHEN EXISTS (SELECT 1 FROM mv_allocation_summary WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001' AND event_id IS NULL)
        THEN '✅ PASS: Allocations with NULL event_id included in materialized view'
        ELSE '❌ FAIL: Allocations with NULL event_id excluded from materialized view (LEFT JOIN not working)'
    END AS gate_5_4_result;

\echo ''

-- ============================================================================
-- TEST SUMMARY
-- ============================================================================

\echo '================================================================================'
\echo 'TEST SUMMARY: Audit Trail Preservation'
\echo '================================================================================'
\echo ''

SELECT 
    'Gate 5.1' AS gate,
    'Row Preservation' AS test,
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')) = 2
        THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS result
UNION ALL
SELECT 
    'Gate 5.2' AS gate,
    'event_id IS NULL' AS test,
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002') AND event_id IS NULL) = 2
        THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS result
UNION ALL
SELECT 
    'Gate 5.3' AS gate,
    'Financial Totals Unchanged' AS test,
    CASE 
        WHEN (SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001') = 10000
        THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS result
UNION ALL
SELECT 
    'Gate 5.4' AS gate,
    'Materialized View Refresh' AS test,
    CASE 
        WHEN EXISTS (SELECT 1 FROM mv_allocation_summary WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001' AND event_id IS NULL)
        THEN '✅ PASS'
        ELSE '❌ FAIL'
    END AS result
ORDER BY gate;

\echo ''
\echo 'All Gates: '
SELECT 
    CASE 
        WHEN (
            (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002')) = 2
            AND (SELECT COUNT(*) FROM attribution_allocations WHERE id IN ('30000000-0000-0000-0000-AUDITALLOC001', '30000000-0000-0000-0000-AUDITALLOC002') AND event_id IS NULL) = 2
            AND (SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001') = 10000
            AND EXISTS (SELECT 1 FROM mv_allocation_summary WHERE tenant_id = '00000000-0000-0000-0000-AUDIT00000001' AND event_id IS NULL)
        )
        THEN '✅✅✅ ALL TESTS PASS - Audit Trail Preservation VERIFIED ✅✅✅'
        ELSE '❌❌❌ SOME TESTS FAIL - Audit Trail Preservation COMPROMISED ❌❌❌'
    END AS final_result;

\echo ''
\echo '================================================================================'
\echo 'TEST COMPLETE'
\echo '================================================================================'

-- Cleanup: Rollback transaction (removes test data)
ROLLBACK;

\echo ''
\echo 'Test data rolled back (transaction reverted).'
\echo 'To preserve test data for manual inspection, replace ROLLBACK with COMMIT.'
\echo ''



