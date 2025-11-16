# Data Governance Evidence

**Purpose**: Empirical evidence of data integrity controls (RLS, immutability, sum-equality) operational effectiveness.

**Last Updated**: 2025-11-16  
**Status**: ⚠️ PENDING (Requires database connection for execution)

## RLS (Row-Level Security) Evidence

### Test Protocol

**Script**: `scripts/database/test-data-integrity.sh`

### Test Results

#### Test 1: Cross-Tenant Data Access Blocked

**Setup**:
```sql
-- Create test tenants
INSERT INTO tenants (id, name) VALUES 
    (gen_random_uuid(), 'test_tenant_1'),
    (gen_random_uuid(), 'test_tenant_2');

-- Create event for tenant 1
INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload, revenue_cents)
VALUES (
    (SELECT id FROM tenants WHERE name = 'test_tenant_1'),
    NOW(),
    '{"order_id": "test-123"}'::jsonb,
    10000
);
```

**Test as Tenant 1**:
```sql
SET app.current_tenant_id = (SELECT id::text FROM tenants WHERE name = 'test_tenant_1');
SELECT COUNT(*) FROM attribution_events;
```

**Expected Output**: Returns count > 0 (tenant 1's data)

**Test as Tenant 2**:
```sql
SET app.current_tenant_id = (SELECT id::text FROM tenants WHERE name = 'test_tenant_2');
SELECT COUNT(*) FROM attribution_events;
```

**Expected Output**: Returns 0 (no tenant 2 data, tenant 1 data blocked)

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

## Immutability Evidence

### Test Results

#### Test 1: UPDATE Blocked on attribution_events

**Command**:
```sql
UPDATE attribution_events 
SET revenue_cents = 2000 
WHERE id = '550e8400-e29b-41d4-a716-446655440000'::uuid;
```

**Expected Output**:
```
ERROR:  attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 2: DELETE Blocked on attribution_events

**Command**:
```sql
DELETE FROM attribution_events 
WHERE id = '550e8400-e29b-41d4-a716-446655440000'::uuid;
```

**Expected Output**:
```
ERROR:  attribution_events is append-only; updates and deletes are not allowed. Use INSERT with correlation_id for corrections.
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 3: UPDATE Blocked on revenue_ledger

**Command**:
```sql
UPDATE revenue_ledger 
SET amount_cents = 2000 
WHERE id = '550e8400-e29b-41d4-a716-446655440000'::uuid;
```

**Expected Output**:
```
ERROR:  revenue_ledger is append-only; updates and deletes are not allowed.
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

## Sum-Equality Invariant Evidence

### Test Results

#### Test 1: Invalid Allocation Sum (Should FAIL)

**Setup**:
```sql
-- Create event with revenue
INSERT INTO attribution_events (tenant_id, occurred_at, raw_payload, revenue_cents)
VALUES (
    '550e8400-e29b-41d4-a716-446655440000'::uuid,
    NOW(),
    '{}'::jsonb,
    10000  -- Event revenue: 10000 cents
);
```

**Test Invalid Sum**:
```sql
-- Attempt to create allocations that don't sum to event revenue
-- Event revenue: 10000 cents
-- Allocations: 5000 + 4000 = 9000 cents (should fail)
INSERT INTO attribution_allocations (tenant_id, event_id, channel_code, allocated_revenue_cents, confidence_score)
VALUES 
    ('550e8400-e29b-41d4-a716-446655440000'::uuid, 
     (SELECT id FROM attribution_events WHERE revenue_cents = 10000 LIMIT 1),
     'organic', 5000, 0.5),
    ('550e8400-e29b-41d4-a716-446655440000'::uuid,
     (SELECT id FROM attribution_events WHERE revenue_cents = 10000 LIMIT 1),
     'paid', 4000, 0.5);
```

**Expected Output**:
```
ERROR:  Allocation sum mismatch: allocated=9000 expected=10000 drift=1000
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

#### Test 2: Valid Allocation Sum (Should SUCCEED)

**Command**:
```sql
-- Create allocations that sum to event revenue
-- Event revenue: 10000 cents
-- Allocations: 6000 + 4000 = 10000 cents (should succeed)
INSERT INTO attribution_allocations (tenant_id, event_id, channel_code, allocated_revenue_cents, confidence_score)
VALUES 
    ('550e8400-e29b-41d4-a716-446655440000'::uuid,
     (SELECT id FROM attribution_events WHERE revenue_cents = 10000 LIMIT 1),
     'organic', 6000, 0.6),
    ('550e8400-e29b-41d4-a716-446655440000'::uuid,
     (SELECT id FROM attribution_events WHERE revenue_cents = 10000 LIMIT 1),
     'paid', 4000, 0.4);
```

**Expected Output**:
```
INSERT 0 2
```

**Actual Output**: ⚠️ PENDING (requires database connection)

**Status**: ✅ Test protocol documented, execution pending

---

## Summary

**Test Protocols**: ✅ All documented  
**Test Execution**: ⚠️ PENDING (requires database connection)  
**Evidence Collection**: Ready for execution

**Coverage**:
- ✅ RLS tenant isolation (1 test)
- ✅ Immutability controls (3 tests)
- ✅ Sum-equality invariant (2 tests)

**Total Tests**: 6 test protocols documented

**Next Steps**: Execute tests when database is available and capture actual SQL outputs as evidence.

