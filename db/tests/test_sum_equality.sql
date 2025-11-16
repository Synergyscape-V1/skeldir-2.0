-- Test Script: Sum-Equality Invariant Validation
-- Purpose: Verify that allocations sum to event revenue per (tenant_id, event_id, model_version)
-- Phase: 4B

-- Setup: Create test data
BEGIN;

-- Create test tenant
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant A')
ON CONFLICT (id) DO NOTHING;

-- Create test event with revenue_cents = 10000 ($100.00)
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    now(),
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Test 1: Exact Match (should pass)
-- Allocations sum exactly to event revenue
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES 
    ('20000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.5, '1.0.0', 5000),
    ('20000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.5, '1.0.0', 5000)
ON CONFLICT DO NOTHING;

-- Verify exact match
SELECT 
    'Test 1: Exact Match' AS test_name,
    CASE 
        WHEN (SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001' AND model_version = '1.0.0') = 10000
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 2: Within Tolerance (should pass)
-- Allocations sum to event revenue - 1 cent (within ±1 cent tolerance)
-- First, delete existing allocations
DELETE FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001';

INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES 
    ('20000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.333333, '1.0.0', 3333),
    ('20000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.333333, '1.0.0', 3333),
    ('20000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'direct', 0.333334, '1.0.0', 3333)
ON CONFLICT DO NOTHING;

-- Verify within tolerance (sum = 9999, drift = 1 cent)
SELECT 
    'Test 2: Within Tolerance' AS test_name,
    CASE 
        WHEN ABS((SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001' AND model_version = '1.0.0') - 10000) <= 1
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 3: Exceeds Tolerance (should fail trigger)
-- Allocations sum to event revenue - 2 cents (exceeds ±1 cent tolerance)
-- This test expects the trigger to raise an exception
DO $$
BEGIN
    DELETE FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001';
    
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES 
        ('20000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.5, '1.0.0', 4999),
        ('20000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.5, '1.0.0', 4999);
    
    RAISE EXCEPTION 'Test 3 should have failed - trigger did not raise exception';
EXCEPTION
    WHEN OTHERS THEN
        IF SQLERRM LIKE '%Allocation sum mismatch%' THEN
            RAISE NOTICE 'Test 3: Exceeds Tolerance - PASS (trigger raised exception as expected)';
        ELSE
            RAISE;
        END IF;
END $$;

-- Test 4: Materialized View Validation
-- Verify mv_allocation_summary correctly identifies balanced allocations
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary;

SELECT 
    'Test 4: Materialized View Validation' AS test_name,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM mv_allocation_summary 
            WHERE event_id = '10000000-0000-0000-0000-000000000001' 
              AND model_version = '1.0.0'
              AND is_balanced = true
              AND drift_cents <= 1
        )
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 5: Per-Model Version Isolation
-- Verify that different model versions can have different allocations for the same event
DELETE FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001';

-- Model version 1.0.0: 50/50 split
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES 
    ('20000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.5, '1.0.0', 5000),
    ('20000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.5, '1.0.0', 5000)
ON CONFLICT DO NOTHING;

-- Model version 2.0.0: 60/40 split
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES 
    ('20000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.6, '2.0.0', 6000),
    ('20000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.4, '2.0.0', 4000)
ON CONFLICT DO NOTHING;

-- Verify both model versions sum correctly
SELECT 
    'Test 5: Per-Model Version Isolation' AS test_name,
    CASE 
        WHEN (SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001' AND model_version = '1.0.0') = 10000
         AND (SELECT SUM(allocated_revenue_cents) FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000001' AND model_version = '2.0.0') = 10000
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Cleanup
ROLLBACK;

-- Summary
SELECT 'Sum-Equality Tests Complete' AS status;




