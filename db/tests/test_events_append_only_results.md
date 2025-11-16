# Events Append-Only Test Results

**Test File**: `db/tests/test_events_append_only.sql`  
**Schema Revision**: `202511141201` (after privilege revocation and trigger creation)  
**Execution Date**: 2025-11-14  
**Execution Status**: ⏳ **PENDING EXECUTION**

---

## Test Prerequisites

- [ ] Database connection with test database
- [ ] Schema applied (all migrations up to revision `202511141201`)
- [ ] Roles created: `app_rw`, `app_ro`, `migration_owner`
- [ ] Test tenant created in `tenants` table
- [ ] Test data: At least one event in `attribution_events` table

---

## Test Execution Results

### Test 1.6.7: Verify GRANT State (Static Verification)

**Objective**: Verify that `app_rw` has only SELECT and INSERT privileges on `attribution_events`.

**Query**:
```sql
SELECT grantee, privilege_type 
FROM information_schema.table_privileges 
WHERE table_name = 'attribution_events' 
  AND grantee = 'app_rw';
```

**Expected Result**:
- grantee = 'app_rw'
- privilege_type IN ('SELECT', 'INSERT')
- privilege_type NOT IN ('UPDATE', 'DELETE')

**Expected Rows**:
| grantee | privilege_type |
|---------|----------------|
| app_rw  | SELECT         |
| app_rw  | INSERT         |

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.4: INSERT as app_rw → Should Succeed

**Objective**: Verify that `app_rw` can INSERT new events.

**Setup**:
```sql
SET ROLE app_rw;
SET LOCAL app.current_tenant_id = '<test_tenant_id>'::text;
```

**Action**:
```sql
INSERT INTO attribution_events (
    tenant_id,
    occurred_at,
    revenue_cents,
    correlation_id,
    raw_payload
) VALUES (
    '<test_tenant_id>'::uuid,
    now(),
    15000,
    gen_random_uuid(),
    '{"test": "data"}'::jsonb
);
```

**Expected Result**: INSERT succeeds, row created

**Verification**:
```sql
SELECT COUNT(*) FROM attribution_events WHERE tenant_id = '<test_tenant_id>'::uuid;
```
Count should increase by 1

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.5: SELECT as app_rw → Should Succeed

**Objective**: Verify that `app_rw` can SELECT events.

**Setup**:
```sql
SET ROLE app_rw;
SET LOCAL app.current_tenant_id = '<test_tenant_id>'::text;
```

**Action**:
```sql
SELECT * FROM attribution_events 
WHERE tenant_id = '<test_tenant_id>'::uuid;
```

**Expected Result**: SELECT succeeds, returns rows (if any)

**Verification**: 
- Rows are returned (if test data exists)
- RLS is working (only returns rows for current tenant)

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.1: UPDATE as app_rw → Should Fail (GRANT Revoked)

**Objective**: Verify that `app_rw` cannot UPDATE events (privilege revoked).

**Setup**:
```sql
SET ROLE app_rw;
SET LOCAL app.current_tenant_id = '<test_tenant_id>'::text;
```

**Action**:
```sql
UPDATE attribution_events 
SET revenue_cents = 20000 
WHERE id = '<test_event_id>';
```

**Expected Result**: Error "permission denied" or "insufficient privilege"
- Error should indicate that UPDATE privilege is not granted to app_rw

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.2: DELETE as app_rw → Should Fail (GRANT Revoked)

**Objective**: Verify that `app_rw` cannot DELETE events (privilege revoked).

**Setup**:
```sql
SET ROLE app_rw;
SET LOCAL app.current_tenant_id = '<test_tenant_id>'::text;
```

**Action**:
```sql
DELETE FROM attribution_events 
WHERE id = '<test_event_id>';
```

**Expected Result**: Error "permission denied" or "insufficient privilege"
- Error should indicate that DELETE privilege is not granted to app_rw

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.3: UPDATE with Trigger → Should Fail (Trigger Blocks)

**Objective**: Verify that trigger blocks UPDATE even if privileges somehow exist.

**Note**: This test is relevant if testing trigger behavior independently, or if testing as superuser with UPDATE privilege.

**Setup**: Connect as superuser (or role with UPDATE privilege)

**Action**:
```sql
UPDATE attribution_events 
SET revenue_cents = 20000 
WHERE id = '<test_event_id>';
```

**Expected Result**: Error "attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections."
- Error message should match trigger exception message

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

### Test 1.6.6: UPDATE as migration_owner → Should Succeed (Whitelisted)

**Objective**: Verify that `migration_owner` can UPDATE events (emergency repair path).

**Setup**:
```sql
SET ROLE migration_owner;
```

**Action**:
```sql
UPDATE attribution_events 
SET revenue_cents = 20000 
WHERE id = '<test_event_id>';
```

**Expected Result**: UPDATE succeeds (trigger allows migration_owner)
- Verify: Row is updated, revenue_cents = 20000

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

## Trigger Verification

### Verify Trigger Exists and is Enabled

**Query**:
```sql
SELECT tgname, tgenabled 
FROM pg_trigger 
WHERE tgrelid = 'attribution_events'::regclass 
  AND tgname = 'trg_events_prevent_mutation';
```

**Expected Result**: One row with `tgenabled = 'O'` (origin/always)

**Actual Result**: ⏳ *Pending execution*

**Status**: ⏳ PENDING

---

## Summary

| Test | Expected Result | Actual Result | Status |
|------|----------------|---------------|--------|
| 1.6.7 - GRANT State | SELECT, INSERT only | ⏳ Pending | ⏳ PENDING |
| 1.6.4 - INSERT | Success | ⏳ Pending | ⏳ PENDING |
| 1.6.5 - SELECT | Success | ⏳ Pending | ⏳ PENDING |
| 1.6.1 - UPDATE (app_rw) | Permission denied | ⏳ Pending | ⏳ PENDING |
| 1.6.2 - DELETE (app_rw) | Permission denied | ⏳ Pending | ⏳ PENDING |
| 1.6.3 - UPDATE (trigger) | Trigger exception | ⏳ Pending | ⏳ PENDING |
| 1.6.6 - UPDATE (migration_owner) | Success | ⏳ Pending | ⏳ PENDING |
| Trigger Verification | Trigger exists, enabled | ⏳ Pending | ⏳ PENDING |

**Overall Status**: ⏳ **PENDING EXECUTION**

**Note**: This document serves as a template for test results. Actual execution against a test database is required to populate the "Actual Result" fields and verify all tests pass.

---

## Execution Instructions

1. Ensure test database is set up with:
   - All migrations applied up to `202511141201`
   - Roles `app_rw`, `app_ro`, `migration_owner` exist
   - Test tenant created
   - Test event data inserted

2. Execute each test in sequence as documented above

3. Capture actual SQL outputs and error messages verbatim

4. Update this document with actual results

5. Update Evidence Registry in `B0.3_Events_Immutability_Implementation.md` Section D
