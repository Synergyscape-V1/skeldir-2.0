-- Test: Channel Mapping Consistency
-- Purpose: Verify that channel_mapping.yaml canonical codes match channel_taxonomy codes
-- Phase: T3 - Channel Consistency Tests & Evidence Integration

-- ============================================================================
-- Test 1: Verify All Mapping YAML Codes Exist in Taxonomy
-- ============================================================================

-- This test verifies that all canonical codes referenced in channel_mapping.yaml
-- exist in the channel_taxonomy table.

-- Expected canonical codes from channel_mapping.yaml:
-- - facebook_paid
-- - facebook_brand
-- - google_search_paid
-- - google_display_paid
-- - tiktok_paid
-- - direct
-- - organic
-- - referral
-- - email

-- Query to verify all expected codes exist
SELECT 
    code,
    display_name,
    family,
    is_paid,
    is_active
FROM channel_taxonomy
WHERE code IN (
    'facebook_paid',
    'facebook_brand',
    'google_search_paid',
    'google_display_paid',
    'tiktok_paid',
    'direct',
    'organic',
    'referral',
    'email'
)
ORDER BY code;

-- Expected Result: 9 rows (all codes from mapping YAML)

-- ============================================================================
-- Test 2: Verify No Missing Codes
-- ============================================================================

-- Query to find any expected codes that are missing from taxonomy
-- This is a negative test: should return zero rows
SELECT 
    expected_code
FROM (
    VALUES 
        ('facebook_paid'),
        ('facebook_brand'),
        ('google_search_paid'),
        ('google_display_paid'),
        ('tiktok_paid'),
        ('direct'),
        ('organic'),
        ('referral'),
        ('email')
) AS expected_codes(expected_code)
WHERE expected_code NOT IN (SELECT code FROM channel_taxonomy);

-- Expected Result: Zero rows (all expected codes exist)

-- ============================================================================
-- Test 3: Verify Taxonomy Codes Match Mapping Structure
-- ============================================================================

-- Query to verify taxonomy structure matches expectations
SELECT 
    code,
    family,
    is_paid,
    CASE 
        WHEN code IN ('facebook_paid', 'facebook_brand', 'google_search_paid', 'google_display_paid', 'tiktok_paid') 
            AND is_paid = true THEN 'PASS'
        WHEN code IN ('direct', 'organic', 'referral', 'email') 
            AND is_paid = false THEN 'PASS'
        ELSE 'FAIL'
    END AS validation_status
FROM channel_taxonomy
WHERE code IN (
    'facebook_paid',
    'facebook_brand',
    'google_search_paid',
    'google_display_paid',
    'tiktok_paid',
    'direct',
    'organic',
    'referral',
    'email'
)
ORDER BY code;

-- Expected Result: All rows have validation_status = 'PASS'

-- ============================================================================
-- Test 4: Verify Family Groupings Are Correct
-- ============================================================================

-- Query to verify family groupings match semantic expectations
SELECT 
    code,
    family,
    CASE 
        WHEN code IN ('facebook_paid', 'facebook_brand', 'tiktok_paid') 
            AND family = 'paid_social' THEN 'PASS'
        WHEN code IN ('google_search_paid', 'google_display_paid') 
            AND family = 'paid_search' THEN 'PASS'
        WHEN code = 'direct' AND family = 'direct' THEN 'PASS'
        WHEN code = 'organic' AND family = 'organic' THEN 'PASS'
        WHEN code = 'referral' AND family = 'referral' THEN 'PASS'
        WHEN code = 'email' AND family = 'email' THEN 'PASS'
        ELSE 'FAIL'
    END AS family_validation
FROM channel_taxonomy
WHERE code IN (
    'facebook_paid',
    'facebook_brand',
    'google_search_paid',
    'google_display_paid',
    'tiktok_paid',
    'direct',
    'organic',
    'referral',
    'email'
)
ORDER BY code;

-- Expected Result: All rows have family_validation = 'PASS'

-- ============================================================================
-- Test 5: Verify All Active Taxonomy Codes Are Used (Optional)
-- ============================================================================

-- Query to find active taxonomy codes that are not used in any allocations
-- This is informational only, not a failure condition
SELECT 
    ct.code,
    ct.display_name,
    ct.family,
    COUNT(aa.id) AS allocation_count
FROM channel_taxonomy ct
LEFT JOIN attribution_allocations aa ON ct.code = aa.channel_code
WHERE ct.is_active = true
GROUP BY ct.code, ct.display_name, ct.family
ORDER BY allocation_count, ct.code;

-- Expected Result: May show some codes with zero allocations (acceptable)

-- ============================================================================
-- Test 6: Verify Mapping YAML Structure (Manual Review)
-- ============================================================================

-- Note: This test requires manual review of db/channel_mapping.yaml
-- Verify that:
-- 1. All vendor mappings point to valid taxonomy codes
-- 2. No typos or case mismatches in canonical code references
-- 3. All canonical codes used in mappings exist in taxonomy

-- Expected structure from channel_mapping.yaml:
-- sources:
--   facebook_ads:
--     "FB_ADS": facebook_paid
--     "FB_BRAND": facebook_brand
--   google_ads:
--     "SEARCH": google_search_paid
--     "DISPLAY": google_display_paid
--   ... etc

-- ============================================================================
-- Summary Assertions
-- ============================================================================

-- After all tests, verify:
-- 1. All mapping YAML codes exist in taxonomy (Test 1 passes - 9 rows)
-- 2. No missing codes (Test 2 passes - zero rows)
-- 3. Taxonomy structure matches expectations (Test 3 passes - all PASS)
-- 4. Family groupings are correct (Test 4 passes - all PASS)
-- 5. Manual review of mapping YAML structure (Test 6 passes)

-- ============================================================================
-- Evidence Collection Queries
-- ============================================================================

-- These queries should be run and their outputs captured in evidence logs:

-- 1. All taxonomy codes matching mapping YAML
-- SELECT 
--     code,
--     display_name,
--     family,
--     is_paid,
--     is_active
-- FROM channel_taxonomy
-- WHERE code IN (
--     'facebook_paid', 'facebook_brand', 'google_search_paid', 
--     'google_display_paid', 'tiktok_paid', 'direct', 
--     'organic', 'referral', 'email'
-- )
-- ORDER BY code;

-- 2. Missing codes check (should return zero rows)
-- SELECT 
--     expected_code
-- FROM (
--     VALUES 
--         ('facebook_paid'), ('facebook_brand'), ('google_search_paid'),
--         ('google_display_paid'), ('tiktok_paid'), ('direct'),
--         ('organic'), ('referral'), ('email')
-- ) AS expected_codes(expected_code)
-- WHERE expected_code NOT IN (SELECT code FROM channel_taxonomy);

-- 3. Taxonomy structure validation
-- SELECT 
--     code,
--     family,
--     is_paid,
--     CASE 
--         WHEN code IN ('facebook_paid', 'facebook_brand', 'google_search_paid', 'google_display_paid', 'tiktok_paid') 
--             AND is_paid = true THEN 'PASS'
--         WHEN code IN ('direct', 'organic', 'referral', 'email') 
--             AND is_paid = false THEN 'PASS'
--         ELSE 'FAIL'
--     END AS validation_status
-- FROM channel_taxonomy
-- WHERE code IN (
--     'facebook_paid', 'facebook_brand', 'google_search_paid',
--     'google_display_paid', 'tiktok_paid', 'direct',
--     'organic', 'referral', 'email'
-- )
-- ORDER BY code;



