-- Test Script: CHECK Constraint Validation
-- Purpose: Verify that CHECK constraints enforce data validation rules
-- Phase: 4D

-- Setup: Create test data
BEGIN;

-- Create test tenant
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant A')
ON CONFLICT (id) DO NOTHING;

-- Create test event
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

-- Test 1: Negative revenue rejection (revenue_cents < 0)
-- Should fail due to CHECK constraint
DO $$
BEGIN
    INSERT INTO attribution_events (
        id, tenant_id, occurred_at, revenue_cents, raw_payload
    ) VALUES (
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        now(),
        -1000, -- Negative revenue
        '{"test": "data"}'::jsonb
    );
    
    RAISE EXCEPTION 'Test 1 should have failed - negative revenue was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 1: Negative revenue rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 2: Allocation ratio bounds (0-1)
-- Test 2a: allocation_ratio < 0 (should fail)
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'google_search',
        -0.1, -- Negative ratio
        '1.0.0',
        5000
    );
    
    RAISE EXCEPTION 'Test 2a should have failed - negative allocation_ratio was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 2a: Negative allocation_ratio rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 2b: allocation_ratio > 1 (should fail)
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'google_search',
        1.5, -- Ratio > 1
        '1.0.0',
        5000
    );
    
    RAISE EXCEPTION 'Test 2b should have failed - allocation_ratio > 1 was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 2b: allocation_ratio > 1 rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 2c: allocation_ratio = 0 (should pass)
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'google_search',
    0.0, -- Ratio = 0 (valid)
    '1.0.0',
    0
)
ON CONFLICT DO NOTHING;

-- Test 2d: allocation_ratio = 1 (should pass)
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000004',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'facebook_ads',
    1.0, -- Ratio = 1 (valid)
    '1.0.0',
    10000
)
ON CONFLICT DO NOTHING;

SELECT 
    'Test 2: Allocation ratio bounds (0-1)' AS test_name,
    CASE 
        WHEN EXISTS (SELECT 1 FROM attribution_allocations WHERE allocation_ratio = 0.0)
         AND EXISTS (SELECT 1 FROM attribution_allocations WHERE allocation_ratio = 1.0)
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 3: Channel code enum validation
-- Test 3a: Invalid channel code (should fail)
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000005',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'invalid_channel', -- Invalid channel code
        0.5,
        '1.0.0',
        5000
    );
    
    RAISE EXCEPTION 'Test 3a should have failed - invalid channel code was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 3a: Invalid channel code rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 3b: Valid channel codes (should pass)
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES 
    ('20000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'google_search', 0.25, '1.0.0', 2500),
    ('20000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'facebook_ads', 0.25, '1.0.0', 2500),
    ('20000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'direct', 0.25, '1.0.0', 2500),
    ('20000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', '10000000-0000-0000-0000-000000000001', 'email', 0.25, '1.0.0', 2500)
ON CONFLICT DO NOTHING;

SELECT 
    'Test 3: Channel code enum validation' AS test_name,
    CASE 
        WHEN EXISTS (SELECT 1 FROM attribution_allocations WHERE channel = 'google_search')
         AND EXISTS (SELECT 1 FROM attribution_allocations WHERE channel = 'facebook_ads')
         AND EXISTS (SELECT 1 FROM attribution_allocations WHERE channel = 'direct')
         AND EXISTS (SELECT 1 FROM attribution_allocations WHERE channel = 'email')
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 4: Negative allocated_revenue_cents rejection
-- Should fail due to CHECK constraint
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000010',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000001',
        'google_search',
        0.5,
        '1.0.0',
        -1000 -- Negative allocated revenue
    );
    
    RAISE EXCEPTION 'Test 4 should have failed - negative allocated_revenue_cents was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 4: Negative allocated_revenue_cents rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 5: Negative revenue_ledger.revenue_cents rejection
-- Should fail due to CHECK constraint
DO $$
BEGIN
    INSERT INTO revenue_ledger (
        id, tenant_id, revenue_cents, is_verified, posted_at
    ) VALUES (
        '30000000-0000-0000-0000-000000000001',
        '00000000-0000-0000-0000-000000000001',
        -1000, -- Negative revenue
        true,
        now()
    );
    
    RAISE EXCEPTION 'Test 5 should have failed - negative revenue_ledger.revenue_cents was allowed';
EXCEPTION
    WHEN check_violation THEN
        RAISE NOTICE 'Test 5: Negative revenue_ledger.revenue_cents rejection - PASS (CHECK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Cleanup
ROLLBACK;

-- Summary
SELECT 'CHECK Constraint Tests Complete' AS status;




