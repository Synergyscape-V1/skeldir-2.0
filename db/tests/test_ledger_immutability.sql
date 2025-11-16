-- Test: Ledger Immutability and Correction Semantics
-- Purpose: Verify that revenue_ledger is immutable for app_rw role and that correction semantics work correctly
-- Phase: L4 - Ledger Traceability Tests & Evidence Integration

-- Setup: Create test tenant and allocation for testing
-- Note: These tests assume a test database with proper roles and test data setup

BEGIN;

-- ============================================================================
-- Test 1: Verify app_rw can INSERT into revenue_ledger
-- ============================================================================

-- This test verifies that INSERT operations succeed for app_rw role
-- Expected: INSERT succeeds

-- Test INSERT (assuming test tenant and allocation exist)
-- SET ROLE app_rw;
-- SET app.current_tenant_id = '<test_tenant_id>';

-- INSERT INTO revenue_ledger (
--     tenant_id,
--     allocation_id,
--     revenue_cents,
--     is_verified,
--     posted_at
-- ) VALUES (
--     '<test_tenant_id>',
--     '<test_allocation_id>',
--     10000,  -- $100.00
--     false,
--     now()
-- );

-- Verify INSERT succeeded
-- SELECT COUNT(*) FROM revenue_ledger WHERE allocation_id = '<test_allocation_id>';
-- Expected: 1 row

-- ============================================================================
-- Test 2: Verify app_rw cannot UPDATE revenue_ledger
-- ============================================================================

-- This test verifies that UPDATE operations fail for app_rw role
-- Expected: UPDATE fails with permission denied or trigger exception

-- SET ROLE app_rw;
-- SET app.current_tenant_id = '<test_tenant_id>';

-- Attempt UPDATE (should fail)
-- UPDATE revenue_ledger 
-- SET revenue_cents = 20000 
-- WHERE id = '<test_ledger_entry_id>';

-- Expected error: Either:
-- 1. Permission denied (if privilege revocation is working)
-- 2. Trigger exception: "revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections."

-- ============================================================================
-- Test 3: Verify app_rw cannot DELETE from revenue_ledger
-- ============================================================================

-- This test verifies that DELETE operations fail for app_rw role
-- Expected: DELETE fails with permission denied or trigger exception

-- SET ROLE app_rw;
-- SET app.current_tenant_id = '<test_tenant_id>';

-- Attempt DELETE (should fail)
-- DELETE FROM revenue_ledger WHERE id = '<test_ledger_entry_id>';

-- Expected error: Either:
-- 1. Permission denied (if privilege revocation is working)
-- 2. Trigger exception: "revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections."

-- ============================================================================
-- Test 4: Correction Scenario - Additive Corrections
-- ============================================================================

-- This test verifies the correction pattern: reversal + replacement
-- Expected: All three entries (original, reversal, corrected) are consistent

-- Step 1: Insert original ledger entry
-- SET ROLE app_rw;
-- SET app.current_tenant_id = '<test_tenant_id>';

-- Original entry (incorrect amount)
-- INSERT INTO revenue_ledger (
--     tenant_id,
--     allocation_id,
--     revenue_cents,
--     is_verified,
--     posted_at
-- ) VALUES (
--     '<test_tenant_id>',
--     '<test_allocation_id>',
--     10000,  -- $100.00 (incorrect)
--     false,
--     now()
-- ) RETURNING id AS original_entry_id;

-- Step 2: Insert reversal entry (negative amount, same allocation_id)
-- INSERT INTO revenue_ledger (
--     tenant_id,
--     allocation_id,
--     revenue_cents,
--     is_verified,
--     posted_at
-- ) VALUES (
--     '<test_tenant_id>',
--     '<test_allocation_id>',
--     -10000,  -- -$100.00 (reversal)
--     false,
--     now()
-- ) RETURNING id AS reversal_entry_id;

-- Step 3: Insert corrected entry (correct amount, same allocation_id)
-- INSERT INTO revenue_ledger (
--     tenant_id,
--     allocation_id,
--     revenue_cents,
--     is_verified,
--     posted_at
-- ) VALUES (
--     '<test_tenant_id>',
--     '<test_allocation_id>',
--     15000,  -- $150.00 (corrected)
--     false,
--     now()
-- ) RETURNING id AS corrected_entry_id;

-- Step 4: Verify correction consistency
-- Assert: Sum of all entries for this allocation equals corrected amount
-- SELECT 
--     allocation_id,
--     SUM(revenue_cents) AS total_revenue_cents,
--     COUNT(*) AS entry_count
-- FROM revenue_ledger
-- WHERE allocation_id = '<test_allocation_id>'
-- GROUP BY allocation_id;

-- Expected:
-- - total_revenue_cents = 15000 (10000 - 10000 + 15000)
-- - entry_count = 3 (original + reversal + corrected)

-- ============================================================================
-- Test 5: Verify allocation_id NOT NULL constraint
-- ============================================================================

-- This test verifies that allocation_id cannot be NULL
-- Expected: INSERT with NULL allocation_id fails

-- SET ROLE app_rw;
-- SET app.current_tenant_id = '<test_tenant_id>';

-- Attempt INSERT with NULL allocation_id (should fail)
-- INSERT INTO revenue_ledger (
--     tenant_id,
--     allocation_id,
--     revenue_cents,
--     is_verified,
--     posted_at
-- ) VALUES (
--     '<test_tenant_id>',
--     NULL,  -- NULL allocation_id (should fail)
--     10000,
--     false,
--     now()
-- );

-- Expected error: "null value in column 'allocation_id' violates not-null constraint"

-- ============================================================================
-- Test 6: Verify trigger blocks superuser UPDATE (defense-in-depth)
-- ============================================================================

-- This test verifies that the trigger blocks UPDATE even for roles with privileges
-- Expected: UPDATE fails with trigger exception

-- SET ROLE postgres;  -- or another superuser role
-- SET app.current_tenant_id = '<test_tenant_id>';

-- Attempt UPDATE (should fail due to trigger)
-- UPDATE revenue_ledger 
-- SET revenue_cents = 20000 
-- WHERE id = '<test_ledger_entry_id>';

-- Expected error: "revenue_ledger is immutable; updates and deletes are not allowed. Use INSERT for corrections."

-- ============================================================================
-- Summary Assertions
-- ============================================================================

-- After all tests, verify:
-- 1. app_rw can INSERT (Test 1 passes)
-- 2. app_rw cannot UPDATE (Test 2 passes)
-- 3. app_rw cannot DELETE (Test 3 passes)
-- 4. Correction scenario works (Test 4 passes)
-- 5. allocation_id NOT NULL enforced (Test 5 passes)
-- 6. Trigger provides defense-in-depth (Test 6 passes)

ROLLBACK;  -- Rollback test transactions

-- ============================================================================
-- Evidence Collection Queries
-- ============================================================================

-- These queries should be run and their outputs captured in evidence logs:

-- 1. Privilege inspection
-- SELECT 
--     grantee,
--     privilege_type
-- FROM information_schema.table_privileges
-- WHERE table_name = 'revenue_ledger'
--     AND grantee = 'app_rw'
-- ORDER BY privilege_type;

-- Expected: Only SELECT and INSERT (no UPDATE or DELETE)

-- 2. Trigger verification
-- SELECT 
--     tgname AS trigger_name,
--     tgenabled AS enabled,
--     pg_get_triggerdef(oid) AS trigger_definition
-- FROM pg_trigger
-- WHERE tgname = 'trg_ledger_prevent_mutation';

-- Expected: Trigger exists and is enabled

-- 3. Column definition
-- SELECT 
--     column_name,
--     is_nullable,
--     data_type
-- FROM information_schema.columns
-- WHERE table_name = 'revenue_ledger'
--     AND column_name = 'allocation_id';

-- Expected: is_nullable = 'NO'



