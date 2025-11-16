-- Test: Unknown Channel Fallback Existence
-- Purpose: Validate that 'unknown' fallback code exists in channel_taxonomy
-- Phase: 1 - Canonical Fallback Taxonomy Validation
-- Migration: 202511161120_add_unknown_channel_fallback.py

-- ============================================================================
-- Gate 1.2: Verify 'unknown' Code Count
-- ============================================================================

-- Query to verify 'unknown' code exists (should return count = 1)
SELECT COUNT(*) AS unknown_count
FROM channel_taxonomy
WHERE code = 'unknown';

-- Expected Result: 1 row with unknown_count = 1

-- ============================================================================
-- Gate 1.3: Verify 'unknown' Code Details
-- ============================================================================

-- Query to verify 'unknown' code structure and semantics
SELECT 
    code,
    family,
    is_paid,
    display_name,
    is_active,
    created_at
FROM channel_taxonomy
WHERE code = 'unknown';

-- Expected Result: 1 row with:
-- - code = 'unknown'
-- - family = 'direct'
-- - is_paid = false
-- - display_name = 'Unknown / Unclassified'
-- - is_active = true
-- - created_at = (timestamp when migration ran)

-- ============================================================================
-- Additional Validation: All Canonical Codes
-- ============================================================================

-- Query to list all canonical codes including 'unknown'
SELECT 
    code,
    family,
    is_paid,
    display_name,
    is_active
FROM channel_taxonomy
ORDER BY 
    CASE 
        WHEN code = 'unknown' THEN 0  -- Show 'unknown' first
        ELSE 1
    END,
    code;

-- Expected Result: 10 rows total (9 original + 1 'unknown')
-- - unknown
-- - direct
-- - email
-- - facebook_brand
-- - facebook_paid
-- - google_display_paid
-- - google_search_paid
-- - organic
-- - referral
-- - tiktok_paid

-- ============================================================================
-- Validation: Table Comment Updated
-- ============================================================================

-- Query to verify table comment includes fallback documentation
SELECT 
    obj_description('channel_taxonomy'::regclass) AS table_comment;

-- Expected Result: Comment should mention "All unmapped channels MUST be normalized to the 'unknown' code"

-- ============================================================================
-- Summary Assertions for Phase 1
-- ============================================================================

-- After migration 202511161120, verify:
-- 1. 'unknown' code exists in channel_taxonomy (Gate 1.2: count = 1)
-- 2. 'unknown' has correct attributes (Gate 1.3: family='direct', is_paid=false, etc.)
-- 3. Table comment documents fallback behavior
-- 4. Total canonical codes = 10 (9 original + 1 'unknown')

-- ============================================================================
-- Evidence Collection
-- ============================================================================

-- Run this comprehensive query to capture all evidence in one result:
SELECT 
    'Gate 1.2: Count' AS test_gate,
    (SELECT COUNT(*)::text FROM channel_taxonomy WHERE code = 'unknown') AS result
UNION ALL
SELECT 
    'Gate 1.3: Code Details' AS test_gate,
    (SELECT code || ' | ' || family || ' | ' || is_paid::text || ' | ' || display_name 
     FROM channel_taxonomy WHERE code = 'unknown') AS result
UNION ALL
SELECT 
    'Total Codes' AS test_gate,
    (SELECT COUNT(*)::text FROM channel_taxonomy) AS result;

-- Expected output:
-- Gate 1.2: Count          | 1
-- Gate 1.3: Code Details   | unknown | direct | false | Unknown / Unclassified
-- Total Codes              | 10



