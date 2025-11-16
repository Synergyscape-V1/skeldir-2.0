-- Test: Channel Taxonomy FK Consistency
-- Purpose: Verify that all attribution_allocations.channel_code values reference valid channel_taxonomy codes
-- Phase: T3 - Channel Consistency Tests & Evidence Integration

-- ============================================================================
-- Test 1: Verify FK Constraint Exists
-- ============================================================================

-- Query to check if FK constraint exists
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'attribution_allocations'
    AND kcu.column_name = 'channel_code';

-- Expected Result:
-- - constraint_name = 'fk_attribution_allocations_channel_code'
-- - column_name = 'channel_code'
-- - foreign_table_name = 'channel_taxonomy'
-- - foreign_column_name = 'code'

-- ============================================================================
-- Test 2: Verify All channel_code Values Exist in Taxonomy
-- ============================================================================

-- Query to find any channel_code values that don't exist in channel_taxonomy
SELECT 
    channel_code,
    COUNT(*) AS allocation_count
FROM attribution_allocations
WHERE channel_code NOT IN (SELECT code FROM channel_taxonomy)
GROUP BY channel_code;

-- Expected Result: Zero rows (all channel_code values must exist in taxonomy)

-- ============================================================================
-- Test 3: Verify FK Constraint Prevents Invalid Inserts
-- ============================================================================

-- Attempt to insert allocation with invalid channel_code (should fail)
-- Note: This test requires a test tenant and event_id
-- INSERT INTO attribution_allocations (
--     tenant_id,
--     event_id,
--     channel_code,
--     allocation_ratio,
--     model_version,
--     allocated_revenue_cents
-- ) VALUES (
--     '<test_tenant_id>'::uuid,
--     '<test_event_id>'::uuid,
--     'invalid_channel_code',  -- This should not exist in taxonomy
--     0.5,
--     '1.0.0',
--     10000
-- );

-- Expected Result: Error "insert or update on table 'attribution_allocations' violates foreign key constraint 'fk_attribution_allocations_channel_code'"

-- ============================================================================
-- Test 4: Verify FK Constraint Prevents Invalid Updates
-- ============================================================================

-- Attempt to update channel_code to invalid value (should fail)
-- Note: This test requires an existing allocation
-- UPDATE attribution_allocations
-- SET channel_code = 'invalid_channel_code'
-- WHERE id = '<test_allocation_id>'::uuid;

-- Expected Result: Error "update or delete on table 'attribution_allocations' violates foreign key constraint 'fk_attribution_allocations_channel_code'"

-- ============================================================================
-- Test 5: Verify All Taxonomy Codes Are Used (Optional Hygiene Check)
-- ============================================================================

-- Query to find taxonomy codes that are not used in any allocations
SELECT 
    ct.code,
    ct.display_name,
    ct.is_active
FROM channel_taxonomy ct
LEFT JOIN attribution_allocations aa ON ct.code = aa.channel_code
WHERE aa.channel_code IS NULL
    AND ct.is_active = true;

-- Expected Result: May have rows (unused codes are allowed, but worth noting)
-- This is informational only, not a failure condition

-- ============================================================================
-- Test 6: Verify Column Name is channel_code (Not channel)
-- ============================================================================

-- Query to verify column name
SELECT 
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'attribution_allocations'
    AND column_name IN ('channel', 'channel_code');

-- Expected Result:
-- - column_name = 'channel_code' (not 'channel')
-- - data_type = 'text'
-- - is_nullable = 'NO'

-- ============================================================================
-- Test 7: Verify CHECK Constraint is Removed
-- ============================================================================

-- Query to check if old CHECK constraint still exists
SELECT 
    constraint_name,
    constraint_type
FROM information_schema.table_constraints
WHERE table_name = 'attribution_allocations'
    AND constraint_name = 'ck_attribution_allocations_channel_code_valid';

-- Expected Result: Zero rows (CHECK constraint should be removed)

-- ============================================================================
-- Summary Assertions
-- ============================================================================

-- After all tests, verify:
-- 1. FK constraint exists and references channel_taxonomy.code (Test 1 passes)
-- 2. All channel_code values exist in taxonomy (Test 2 passes - zero rows)
-- 3. FK prevents invalid inserts (Test 3 passes - error raised)
-- 4. FK prevents invalid updates (Test 4 passes - error raised)
-- 5. Column is named channel_code (Test 6 passes)
-- 6. CHECK constraint is removed (Test 7 passes - zero rows)

-- ============================================================================
-- Evidence Collection Queries
-- ============================================================================

-- These queries should be run and their outputs captured in evidence logs:

-- 1. FK constraint definition
-- SELECT 
--     tc.constraint_name,
--     tc.table_name,
--     kcu.column_name,
--     ccu.table_name AS foreign_table_name,
--     ccu.column_name AS foreign_column_name
-- FROM information_schema.table_constraints AS tc
-- JOIN information_schema.key_column_usage AS kcu
--     ON tc.constraint_name = kcu.constraint_name
-- JOIN information_schema.constraint_column_usage AS ccu
--     ON ccu.constraint_name = tc.constraint_name
-- WHERE tc.constraint_type = 'FOREIGN KEY'
--     AND tc.table_name = 'attribution_allocations'
--     AND kcu.column_name = 'channel_code';

-- 2. Validation query (should return zero rows)
-- SELECT 
--     channel_code,
--     COUNT(*) AS count
-- FROM attribution_allocations
-- WHERE channel_code NOT IN (SELECT code FROM channel_taxonomy)
-- GROUP BY channel_code;

-- 3. Column definition
-- SELECT 
--     column_name,
--     data_type,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'attribution_allocations'
--     AND column_name = 'channel_code';



