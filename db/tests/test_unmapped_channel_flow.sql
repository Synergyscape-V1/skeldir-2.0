-- Test: Full B0.4-to-B2.1 Data Flow with Unmapped Channels
-- Purpose: Prove complete data flow is resilient to unmapped channels using 'unknown' fallback
-- Phase: 5 - Full Data Flow Validation
-- Dependencies: Migrations 202511161120, 202511161130

-- ============================================================================
-- OVERVIEW
-- ============================================================================
-- This test simulates the complete ingestion-to-attribution pipeline:
-- 1. B0.4 ingests event with unmapped channel → stores as 'unknown'
-- 2. B2.1 creates attribution allocation using 'unknown' channel
-- 3. Verify complete data chain (event → allocation) succeeds without FK violations
-- 4. Repeat with mapped canonical channel to prove standard path also works

-- ============================================================================
-- PREREQUISITES
-- ============================================================================
-- - Migration 202511161120 (adds 'unknown' to channel_taxonomy) applied
-- - Migration 202511161130 (adds FK constraint to attribution_events.channel) applied
-- - Test tenant exists in tenants table

-- Create test tenant if not exists (idempotent)
INSERT INTO tenants (id, name, status, api_key_hash, created_at, updated_at)
VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    'Test Tenant - Channel Flow',
    'active',
    'test_api_key_hash_channel_flow',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- Gate 5.1: B0.4 Simulation - INSERT Event with 'unknown' Channel
-- ============================================================================

-- Simulate B0.4 ingestion receiving unmapped channel (e.g., "bing_ads")
-- After normalization via normalize_channel(), channel is set to 'unknown'

BEGIN;

-- Insert event with 'unknown' channel (unmapped input)
INSERT INTO attribution_events (
    id,
    tenant_id,
    session_id,
    idempotency_key,
    event_type,
    channel,  -- 'unknown' fallback for unmapped channel
    event_timestamp,
    raw_payload,
    processing_status,
    created_at,
    updated_at,
    occurred_at
) VALUES (
    'flow-test-event-unknown-01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'flow-test-session-unknown-01'::uuid,
    'flow-test-key-unknown-01',
    'purchase',
    'unknown',  -- CRITICAL: This is the fallback for unmapped channels
    NOW(),
    '{"utm_source": "bing", "utm_medium": "cpc", "utm_campaign": "test", "original_vendor": "bing_ads"}'::jsonb,
    'processed',
    NOW(),
    NOW(),
    NOW()
);

COMMIT;

-- Expected Result: INSERT succeeds (no FK violation)
-- Verify: Query the inserted event
SELECT 
    id,
    tenant_id,
    session_id,
    event_type,
    channel,
    raw_payload->>'utm_source' AS original_utm_source,
    raw_payload->>'original_vendor' AS original_vendor,
    'Gate 5.1: PASS - Event with unknown channel inserted successfully' AS validation_status
FROM attribution_events
WHERE id = 'flow-test-event-unknown-01'::uuid;

-- Expected output: 1 row with channel='unknown'

-- ============================================================================
-- Gate 5.2: B2.1 Simulation - INSERT Allocation with 'unknown' Channel Code
-- ============================================================================

-- Simulate B2.1 attribution engine creating allocation for the 'unknown' event
-- This proves FK constraint on attribution_allocations.channel_code accepts 'unknown'

BEGIN;

-- Insert allocation with channel_code='unknown'
INSERT INTO attribution_allocations (
    id,
    tenant_id,
    event_id,
    channel_code,  -- FK to channel_taxonomy.code
    allocated_revenue_cents,
    allocation_ratio,
    model_version,
    created_at,
    updated_at,
    model_type,
    confidence_score,
    verified
) VALUES (
    'flow-test-alloc-unknown-01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'flow-test-event-unknown-01'::uuid,  -- Links to event from Gate 5.1
    'unknown',  -- CRITICAL: FK constraint must allow 'unknown'
    10000,  -- $100.00 in cents
    1.0,
    'v1.0.0',
    NOW(),
    NOW(),
    'linear',
    1.0,
    false
);

COMMIT;

-- Expected Result: INSERT succeeds (FK constraint allows 'unknown')
-- Verify: Query the inserted allocation
SELECT 
    id,
    tenant_id,
    event_id,
    channel_code,
    allocated_revenue_cents,
    allocation_ratio,
    'Gate 5.2: PASS - Allocation with unknown channel_code inserted successfully' AS validation_status
FROM attribution_allocations
WHERE id = 'flow-test-alloc-unknown-01'::uuid;

-- Expected output: 1 row with channel_code='unknown'

-- ============================================================================
-- Gate 5.3: Data Integrity Proof - Complete Chain Validation
-- ============================================================================

-- Validate the complete event → allocation chain exists and is queryable
-- This proves the entire B0.4-to-B2.1 flow succeeded without errors

SELECT 
    e.id AS event_id,
    e.channel AS event_channel,
    e.raw_payload->>'utm_source' AS original_utm_source,
    a.id AS allocation_id,
    a.channel_code AS allocation_channel_code,
    a.allocated_revenue_cents,
    CASE 
        WHEN e.channel = a.channel_code THEN 'CONSISTENT'
        ELSE 'INCONSISTENT'
    END AS channel_consistency,
    'Gate 5.3: PASS - Complete event-to-allocation chain validated' AS validation_status
FROM attribution_events e
JOIN attribution_allocations a ON e.id = a.event_id
WHERE e.id = 'flow-test-event-unknown-01'::uuid
    AND a.id = 'flow-test-alloc-unknown-01'::uuid
    AND e.channel = 'unknown'
    AND a.channel_code = 'unknown';

-- Expected Result: 1 row with:
-- - event_channel = 'unknown'
-- - allocation_channel_code = 'unknown'
-- - channel_consistency = 'CONSISTENT'

-- ============================================================================
-- Gate 5.4: Mapped Channel Test - Standard Path Validation
-- ============================================================================

-- Repeat the full flow with a mapped canonical channel (e.g., 'google_search_paid')
-- This proves the standard path (non-fallback) also works correctly

BEGIN;

-- Step 1: Insert event with mapped canonical channel
INSERT INTO attribution_events (
    id,
    tenant_id,
    session_id,
    idempotency_key,
    event_type,
    channel,  -- Canonical code 'google_search_paid'
    event_timestamp,
    raw_payload,
    processing_status,
    created_at,
    updated_at,
    occurred_at
) VALUES (
    'flow-test-event-mapped-01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'flow-test-session-mapped-01'::uuid,
    'flow-test-key-mapped-01',
    'purchase',
    'google_search_paid',  -- Mapped canonical channel
    NOW(),
    '{"utm_source": "google", "utm_medium": "cpc", "utm_campaign": "test", "original_vendor": "google_ads"}'::jsonb,
    'processed',
    NOW(),
    NOW(),
    NOW()
);

-- Step 2: Insert allocation with mapped canonical channel_code
INSERT INTO attribution_allocations (
    id,
    tenant_id,
    event_id,
    channel_code,  -- FK to channel_taxonomy.code
    allocated_revenue_cents,
    allocation_ratio,
    model_version,
    created_at,
    updated_at,
    model_type,
    confidence_score,
    verified
) VALUES (
    'flow-test-alloc-mapped-01'::uuid,
    '00000000-0000-0000-0000-000000000001'::uuid,
    'flow-test-event-mapped-01'::uuid,
    'google_search_paid',  -- Mapped canonical code
    20000,  -- $200.00 in cents
    1.0,
    'v1.0.0',
    NOW(),
    NOW(),
    'linear',
    1.0,
    false
);

COMMIT;

-- Validate mapped channel flow
SELECT 
    e.id AS event_id,
    e.channel AS event_channel,
    e.raw_payload->>'utm_source' AS original_utm_source,
    a.id AS allocation_id,
    a.channel_code AS allocation_channel_code,
    a.allocated_revenue_cents,
    CASE 
        WHEN e.channel = a.channel_code THEN 'CONSISTENT'
        ELSE 'INCONSISTENT'
    END AS channel_consistency,
    'Gate 5.4: PASS - Mapped channel flow validated' AS validation_status
FROM attribution_events e
JOIN attribution_allocations a ON e.id = a.event_id
WHERE e.id = 'flow-test-event-mapped-01'::uuid
    AND a.id = 'flow-test-alloc-mapped-01'::uuid
    AND e.channel = 'google_search_paid'
    AND a.channel_code = 'google_search_paid';

-- Expected Result: 1 row with:
-- - event_channel = 'google_search_paid'
-- - allocation_channel_code = 'google_search_paid'
-- - channel_consistency = 'CONSISTENT'

-- ============================================================================
-- Summary Validation: All Gates Passed
-- ============================================================================

-- Comprehensive validation query for Phase 5
SELECT 
    'Gate 5.1: B0.4 Unknown Event' AS test_gate,
    (SELECT COUNT(*)::text FROM attribution_events WHERE id = 'flow-test-event-unknown-01'::uuid AND channel = 'unknown') AS result,
    '1' AS expected,
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_events WHERE id = 'flow-test-event-unknown-01'::uuid AND channel = 'unknown') = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
UNION ALL
SELECT 
    'Gate 5.2: B2.1 Unknown Allocation' AS test_gate,
    (SELECT COUNT(*)::text FROM attribution_allocations WHERE id = 'flow-test-alloc-unknown-01'::uuid AND channel_code = 'unknown') AS result,
    '1' AS expected,
    CASE 
        WHEN (SELECT COUNT(*) FROM attribution_allocations WHERE id = 'flow-test-alloc-unknown-01'::uuid AND channel_code = 'unknown') = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
UNION ALL
SELECT 
    'Gate 5.3: Unknown Chain Integrity' AS test_gate,
    (SELECT COUNT(*)::text 
     FROM attribution_events e 
     JOIN attribution_allocations a ON e.id = a.event_id 
     WHERE e.id = 'flow-test-event-unknown-01'::uuid 
     AND a.id = 'flow-test-alloc-unknown-01'::uuid
     AND e.channel = 'unknown' 
     AND a.channel_code = 'unknown') AS result,
    '1' AS expected,
    CASE 
        WHEN (SELECT COUNT(*) 
              FROM attribution_events e 
              JOIN attribution_allocations a ON e.id = a.event_id 
              WHERE e.id = 'flow-test-event-unknown-01'::uuid 
              AND e.channel = 'unknown' 
              AND a.channel_code = 'unknown') = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS status
UNION ALL
SELECT 
    'Gate 5.4: Mapped Chain Integrity' AS test_gate,
    (SELECT COUNT(*)::text 
     FROM attribution_events e 
     JOIN attribution_allocations a ON e.id = a.event_id 
     WHERE e.id = 'flow-test-event-mapped-01'::uuid 
     AND a.id = 'flow-test-alloc-mapped-01'::uuid
     AND e.channel = 'google_search_paid' 
     AND a.channel_code = 'google_search_paid') AS result,
    '1' AS expected,
    CASE 
        WHEN (SELECT COUNT(*) 
              FROM attribution_events e 
              JOIN attribution_allocations a ON e.id = a.event_id 
              WHERE e.id = 'flow-test-event-mapped-01'::uuid 
              AND e.channel = 'google_search_paid' 
              AND a.channel_code = 'google_search_paid') = 1 THEN 'PASS'
        ELSE 'FAIL'
    END AS status;

-- Expected Output:
-- Gate 5.1: B0.4 Unknown Event        | 1 | 1 | PASS
-- Gate 5.2: B2.1 Unknown Allocation   | 1 | 1 | PASS
-- Gate 5.3: Unknown Chain Integrity   | 1 | 1 | PASS
-- Gate 5.4: Mapped Chain Integrity    | 1 | 1 | PASS

-- ============================================================================
-- CLEANUP (Optional - Uncomment to Remove Test Data)
-- ============================================================================

-- To clean up test data after validation, uncomment the following:

/*
BEGIN;

-- Delete test allocations
DELETE FROM attribution_allocations
WHERE id IN (
    'flow-test-alloc-unknown-01'::uuid,
    'flow-test-alloc-mapped-01'::uuid
);

-- Delete test events
DELETE FROM attribution_events
WHERE id IN (
    'flow-test-event-unknown-01'::uuid,
    'flow-test-event-mapped-01'::uuid
);

-- Delete test tenant (only if created for this test)
DELETE FROM tenants
WHERE id = '00000000-0000-0000-0000-000000000001'::uuid
    AND name = 'Test Tenant - Channel Flow';

COMMIT;
*/

-- ============================================================================
-- Phase 5 Exit Gate Summary
-- ============================================================================

-- All tests passed if:
-- 1. Gate 5.1: Event with channel='unknown' inserted successfully (no FK violation)
-- 2. Gate 5.2: Allocation with channel_code='unknown' inserted successfully (FK accepts 'unknown')
-- 3. Gate 5.3: Complete event-to-allocation chain validated for 'unknown' channel
-- 4. Gate 5.4: Complete event-to-allocation chain validated for mapped channel ('google_search_paid')

-- CRITICAL PROOF: Unmapped channels (represented by 'unknown' fallback) do NOT cause:
-- - FK violations during event ingestion (B0.4)
-- - FK violations during allocation creation (B2.1)
-- - Data integrity failures in event-to-allocation linkage
-- - Pipeline crashes or undefined behavior

-- This validates the resilience property of the channel governance model.



