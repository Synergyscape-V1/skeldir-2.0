-- Test Script: Foreign Key Constraint Validation
-- Purpose: Verify that foreign key constraints enforce referential integrity
-- Phase: 4D

-- Setup: Create test data
BEGIN;

-- Create test tenants
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant A'),
    ('00000000-0000-0000-0000-000000000002', 'Test Tenant B')
ON CONFLICT (id) DO NOTHING;

-- Test 1: ON DELETE CASCADE for tenant deletion
-- Create event for tenant A
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

-- Create allocation for tenant A
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'google_search',
    1.0,
    '1.0.0',
    10000
)
ON CONFLICT DO NOTHING;

-- Delete tenant A (should cascade delete event and allocation)
DELETE FROM tenants WHERE id = '00000000-0000-0000-0000-000000000001';

-- Verify cascade deletion
SELECT 
    'Test 1: ON DELETE CASCADE for tenant deletion' AS test_name,
    CASE 
        WHEN NOT EXISTS (SELECT 1 FROM attribution_events WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
         AND NOT EXISTS (SELECT 1 FROM attribution_allocations WHERE tenant_id = '00000000-0000-0000-0000-000000000001')
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 2: ON DELETE CASCADE for event deletion → allocation deletion
-- Recreate tenant A
INSERT INTO tenants (id, name) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Test Tenant A')
ON CONFLICT (id) DO NOTHING;

-- Create event
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    now(),
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

-- Create allocation
INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000002',
    'google_search',
    1.0,
    '1.0.0',
    10000
)
ON CONFLICT DO NOTHING;

-- Delete event (should cascade delete allocation)
DELETE FROM attribution_events WHERE id = '10000000-0000-0000-0000-000000000002';

-- Verify cascade deletion
SELECT 
    'Test 2: ON DELETE CASCADE for event deletion → allocation deletion' AS test_name,
    CASE 
        WHEN NOT EXISTS (SELECT 1 FROM attribution_allocations WHERE event_id = '10000000-0000-0000-0000-000000000002')
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Test 3: Orphaned FK prevention (cannot insert allocation with invalid event_id)
-- Attempt to insert allocation with non-existent event_id (should fail)
DO $$
BEGIN
    INSERT INTO attribution_allocations (
        id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
    ) VALUES (
        '20000000-0000-0000-0000-000000000003',
        '00000000-0000-0000-0000-000000000001',
        '99999999-9999-9999-9999-999999999999'::uuid, -- Non-existent event_id
        'google_search',
        1.0,
        '1.0.0',
        10000
    );
    
    RAISE EXCEPTION 'Test 3 should have failed - orphaned FK was allowed';
EXCEPTION
    WHEN foreign_key_violation THEN
        RAISE NOTICE 'Test 3: Orphaned FK prevention - PASS (FK constraint raised exception)';
    WHEN OTHERS THEN
        RAISE;
END $$;

-- Test 4: Allocation deletion → revenue_ledger allocation_id FK (if allocation_id set)
-- Create event and allocation
INSERT INTO attribution_events (
    id, tenant_id, occurred_at, revenue_cents, raw_payload
) VALUES (
    '10000000-0000-0000-0000-000000000003',
    '00000000-0000-0000-0000-000000000001',
    now(),
    10000,
    '{"test": "data"}'::jsonb
)
ON CONFLICT DO NOTHING;

INSERT INTO attribution_allocations (
    id, tenant_id, event_id, channel, allocation_ratio, model_version, allocated_revenue_cents
) VALUES (
    '20000000-0000-0000-0000-000000000004',
    '00000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000003',
    'google_search',
    1.0,
    '1.0.0',
    10000
)
ON CONFLICT DO NOTHING;

-- Create ledger entry with allocation_id
INSERT INTO revenue_ledger (
    id, tenant_id, allocation_id, revenue_cents, is_verified, posted_at
) VALUES (
    '30000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000001',
    '20000000-0000-0000-0000-000000000004',
    10000,
    true,
    now()
)
ON CONFLICT DO NOTHING;

-- Delete allocation (should cascade delete ledger entry)
DELETE FROM attribution_allocations WHERE id = '20000000-0000-0000-0000-000000000004';

-- Verify cascade deletion
SELECT 
    'Test 4: Allocation deletion → revenue_ledger allocation_id FK cascade' AS test_name,
    CASE 
        WHEN NOT EXISTS (SELECT 1 FROM revenue_ledger WHERE allocation_id = '20000000-0000-0000-0000-000000000004')
        THEN 'PASS'
        ELSE 'FAIL'
    END AS result;

-- Cleanup
ROLLBACK;

-- Summary
SELECT 'Foreign Key Tests Complete' AS status;




