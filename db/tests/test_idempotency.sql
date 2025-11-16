-- Test Script: Idempotency Constraint Validation
-- Purpose: Verify that idempotency constraints prevent duplicate entries
-- Phase: 4D

-- Setup: Create test data
BEGIN;

-- Create test tenant
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant A')
ON CONFLICT (id) DO NOTHING;

-- Test 1: Duplicate (tenant_id, external_event_id) rejection in attribution_events
-- Should fail due to unique constraint
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, external_event_id, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    now(),
    'ext_event_123',
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Attempt duplicate insert (should fail)
DO $$
BEGIN
    INSERT INTO attribution_events (
        id, tenant_id, occurred_at, external_event_id, revenue_cents, raw_payload
    ) VALUES (
        '10000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        now(),
        'ext_event_123', -- Same external_event_id
        10000,
        '{"test": "data2"}'::jsonb
    );
    
    RAISE EXCEPTION 'Test 1 should have failed - duplicate (tenant_id, external_event_id) was allowed';
EXCEPTION
    WHEN unique_violation THEN
        RAISE NOTICE 'Test 1: Duplicate (tenant_id, external_event_id) rejection - PASS (constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 2: Duplicate (tenant_id, correlation_id) rejection when external_event_id NULL
-- Should fail due to unique constraint
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, correlation_id, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000001',
    now(),
    '00000000-0000-0000-0000-000000000099'::uuid,
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Attempt duplicate insert (should fail)
DO $$
BEGIN
    INSERT INTO attribution_events (
        id, tenant_id, occurred_at, correlation_id, revenue_cents, raw_payload
    ) VALUES (
        '10000000-0000-0000-0000-000000000004',
        '00000000-0000-0000-0000-000000000001',
        now(),
        '00000000-0000-0000-0000-000000000099'::uuid, -- Same correlation_id, external_event_id NULL
        10000,
        '{"test": "data2"}'::jsonb
    );
    
    RAISE EXCEPTION 'Test 2 should have failed - duplicate (tenant_id, correlation_id) was allowed';
EXCEPTION
    WHEN unique_violation THEN
        RAISE NOTICE 'Test 2: Duplicate (tenant_id, correlation_id) rejection - PASS (constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 3: Duplicate (tenant_id, event_id, model_version, channel) rejection in allocations
-- Create test event first
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000005',
    '00000000-0000-0000-0000-000000000001',
    now(),
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Insert first allocation
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000005',
    'google_search',
    0.5,
    '1.0.0',
    5000
)
ON CONFLICT DO NOTHING;

-- Attempt duplicate insert (should fail)
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000002',
        '00000000-0000-0000-0000-000000000001',
        '10000000-0000-0000-0000-000000000005', -- Same event_id
        'google_search', -- Same channel
        0.5,
        '1.0.0', -- Same model_version
        5000
    );
    
    RAISE EXCEPTION 'Test 3 should have failed - duplicate (tenant_id, event_id, model_version, channel) was allowed';
EXCEPTION
    WHEN unique_violation THEN
        RAISE NOTICE 'Test 3: Duplicate (tenant_id, event_id, model_version, channel) rejection - PASS (constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 4: Different model versions can have same channel (should pass)
-- This should succeed - different model_version
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000005',
    'google_search', -- Same channel
    0.6,
    '2.0.0', -- Different model_version
    6000
)
ON CONFLICT DO NOTHING;

SELECT 
    'Test 4: Different model versions can have same channel' AS test_name,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM attribution_allocations 
            WHERE event_id = '10000000-0000-0000-0000-000000000005' 
              AND channel = 'google_search' 
              AND model_version = '2.0.0'
        )
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Cleanup
ROLLBACK;

-- Summary
SELECT 'Idempotency Tests Complete' AS status;




