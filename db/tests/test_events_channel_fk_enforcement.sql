-- Test: attribution_events.channel FK Enforcement
-- Purpose: Validate FK constraint enforces canonical channel codes at DB boundary
-- Phase: 2 - Schema Enforcement Validation
-- Migration: 202511161130_add_events_channel_fk.py

-- ============================================================================
-- Gate 2.1: Verify Zero Non-Taxonomy Channel Values (After Repair)
-- ============================================================================

-- Query to find any channel values that don't exist in taxonomy
-- Expected Result: Zero rows (all values repaired in migration)
SELECT DISTINCT channel
FROM attribution_events
WHERE channel NOT IN (SELECT code FROM channel_taxonomy);

-- Expected Result: 0 rows returned

-- Detailed count query for evidence
SELECT COUNT(DISTINCT channel) AS non_taxonomy_channel_count
FROM attribution_events
WHERE channel NOT IN (SELECT code FROM channel_taxonomy);

-- Expected Result: non_taxonomy_channel_count = 0

-- ============================================================================
-- Gate 2.2: Verify FK Constraint Exists
-- ============================================================================

-- Query to verify FK constraint exists and has correct definition
SELECT 
    tc.constraint_name,
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    rc.update_rule,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
    AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
    AND ccu.table_schema = tc.table_schema
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
    AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'attribution_events'
    AND kcu.column_name = 'channel';

-- Expected Result: 1 row with:
-- - constraint_name = 'fk_attribution_events_channel'
-- - table_name = 'attribution_events'
-- - column_name = 'channel'
-- - foreign_table_name = 'channel_taxonomy'
-- - foreign_column_name = 'code'
-- - update_rule = 'CASCADE'
-- - delete_rule = 'RESTRICT'

-- ============================================================================
-- Gate 2.3: FK Prevents Invalid INSERT (Negative Test)
-- ============================================================================

-- This test should be run in a transaction and rolled back
-- It demonstrates that FK constraint prevents invalid channel insertion

-- Test query (wrap in transaction):
/*
BEGIN;

-- Attempt to insert event with invalid channel
INSERT INTO attribution_events (
    tenant_id,
    session_id,
    idempotency_key,
    event_type,
    channel,
    event_timestamp,
    raw_payload,
    processing_status
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,  -- Test tenant
    '00000000-0000-0000-0000-000000000002'::uuid,  -- Test session
    'test-invalid-channel-' || gen_random_uuid()::text,
    'purchase',
    'invalid_channel_code',  -- This should violate FK
    NOW(),
    '{}'::jsonb,
    'pending'
);

ROLLBACK;
*/

-- Expected Result: ERROR with message like:
-- "insert or update on table "attribution_events" violates foreign key constraint "fk_attribution_events_channel""
-- Detail: Key (channel)=(invalid_channel_code) is not present in table "channel_taxonomy".

-- ============================================================================
-- Gate 2.4: FK Allows Valid INSERT with 'unknown' (Positive Test)
-- ============================================================================

-- This test demonstrates that FK constraint allows 'unknown' fallback
-- Run in transaction and rollback to avoid polluting test data

-- Test query (wrap in transaction):
/*
BEGIN;

-- Attempt to insert event with 'unknown' channel
INSERT INTO attribution_events (
    tenant_id,
    session_id,
    idempotency_key,
    event_type,
    channel,
    event_timestamp,
    raw_payload,
    processing_status
) VALUES (
    '00000000-0000-0000-0000-000000000001'::uuid,
    '00000000-0000-0000-0000-000000000002'::uuid,
    'test-unknown-channel-' || gen_random_uuid()::text,
    'purchase',
    'unknown',  -- This should succeed (canonical fallback)
    NOW(),
    '{}'::jsonb,
    'pending'
)
RETURNING id, channel;

ROLLBACK;
*/

-- Expected Result: INSERT succeeds, returns row with channel='unknown'

-- ============================================================================
-- Additional Test: FK Allows All Canonical Codes
-- ============================================================================

-- Verify FK allows insertion for all canonical channel codes
-- This generates INSERT statements for all taxonomy codes (for manual testing)

SELECT 
    'INSERT INTO attribution_events (tenant_id, session_id, idempotency_key, event_type, channel, event_timestamp, raw_payload, processing_status) ' ||
    'VALUES (''00000000-0000-0000-0000-000000000001''::uuid, ''00000000-0000-0000-0000-000000000002''::uuid, ' ||
    '''test-' || code || '-'' || gen_random_uuid()::text, ''purchase'', ''' || code || ''', NOW(), ''{}''::jsonb, ''pending'');' AS insert_statement
FROM channel_taxonomy
WHERE is_active = true
ORDER BY code;

-- These INSERT statements should all succeed when run in a transaction

-- ============================================================================
-- Summary Validation Query
-- ============================================================================

-- Comprehensive validation of Phase 2 implementation
SELECT 
    'Gate 2.1: Non-Taxonomy Count' AS test_gate,
    (SELECT COUNT(DISTINCT channel)::text FROM attribution_events WHERE channel NOT IN (SELECT code FROM channel_taxonomy)) AS result,
    '0' AS expected
UNION ALL
SELECT 
    'Gate 2.2: FK Exists' AS test_gate,
    (SELECT COUNT(*)::text FROM information_schema.table_constraints 
     WHERE table_name = 'attribution_events' 
     AND constraint_name = 'fk_attribution_events_channel' 
     AND constraint_type = 'FOREIGN KEY') AS result,
    '1' AS expected
UNION ALL
SELECT 
    'Total Canonical Codes' AS test_gate,
    (SELECT COUNT(*)::text FROM channel_taxonomy WHERE is_active = true) AS result,
    '10' AS expected;

-- Expected output:
-- Gate 2.1: Non-Taxonomy Count | 0    | 0
-- Gate 2.2: FK Exists          | 1    | 1
-- Total Canonical Codes        | 10   | 10

-- ============================================================================
-- Evidence Collection: FK Constraint Definition
-- ============================================================================

-- Detailed FK constraint definition for documentation
SELECT 
    tc.constraint_name,
    tc.constraint_type,
    kcu.column_name AS source_column,
    ccu.table_name || '.' || ccu.column_name AS target_reference,
    rc.update_rule,
    rc.delete_rule,
    obj_description(('attribution_events'::regclass)::oid, 'pg_class') AS table_comment,
    col_description('attribution_events'::regclass, 
        (SELECT attnum FROM pg_attribute 
         WHERE attrelid = 'attribution_events'::regclass 
         AND attname = 'channel')) AS column_comment
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_name = 'attribution_events'
    AND kcu.column_name = 'channel';

-- This provides complete FK definition including referential actions and documentation

-- ============================================================================
-- Phase 2 Exit Gate Summary
-- ============================================================================

-- All tests passed if:
-- 1. Gate 2.1: Zero non-taxonomy channel values exist in attribution_events
-- 2. Gate 2.2: FK constraint fk_attribution_events_channel exists with correct definition
-- 3. Gate 2.3: INSERT with invalid channel fails with FK violation error
-- 4. Gate 2.4: INSERT with 'unknown' channel succeeds
-- 5. All canonical codes can be inserted successfully (FK allows all taxonomy codes)



