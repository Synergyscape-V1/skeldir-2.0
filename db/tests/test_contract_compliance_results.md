# Materialized View JSON Compliance Test Results

**Test Date**: TBD (to be filled after test execution)  
**Test Script**: `db/tests/test_contract_compliance.sql`  
**Database**: TBD  
**Migration Version**: `202511131119_add_materialized_views.py`

## Test Execution Summary

### Test 1: mv_realtime_revenue JSON Shape Compliance

**Status**: ⏳ PENDING  
**Contract**: `api-contracts/openapi/v1/attribution.yaml:39-64` (RealtimeRevenueResponse)

**Required Fields**:
- ✅ `total_revenue` (number float) - Verified in DDL spec
- ✅ `verified` (boolean) - Verified in DDL spec
- ✅ `data_freshness_seconds` (integer) - Verified in DDL spec
- ✅ `tenant_id` (string uuid) - Verified in DDL spec

**Expected JSON Shape**:
```json
{
  "total_revenue": 125000.50,
  "verified": true,
  "data_freshness_seconds": 45,
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Test Query Result**: TBD  
**Validation**: TBD

---

### Test 2: mv_reconciliation_status JSON Shape Compliance

**Status**: ⏳ PENDING  
**Contract**: `api-contracts/openapi/v1/reconciliation.yaml:39-64` (ReconciliationStatusResponse)

**Required Fields**:
- ✅ `state` (enum: idle|running|failed|completed) - Verified in DDL spec
- ✅ `last_run_at` (string date-time) - Verified in DDL spec
- ✅ `tenant_id` (string uuid) - Verified in DDL spec

**Expected JSON Shape**:
```json
{
  "state": "completed",
  "last_run_at": "2025-11-10T14:30:00Z",
  "tenant_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Test Query Result**: TBD  
**Validation**: TBD

---

### Test 3: Type Conversion Validation

**Status**: ⏳ PENDING  
**Test**: Verify total_revenue is converted from cents to dollars

**Expected**: `revenue_cents / 100.0 = total_revenue` (float)

**Test Query Result**: TBD  
**Validation**: TBD

---

### Test 4: Performance Validation (p95 < 50ms)

**Status**: ⏳ PENDING  
**Test**: Verify index usage for tenant-scoped queries

**Expected**:
- Index Scan on `idx_mv_realtime_revenue_tenant_id`
- Execution time < 50ms (p95 target)

**Test Query Result**: TBD  
**Validation**: TBD

---

## Overall Test Status

**Status**: ⏳ PENDING EXECUTION  
**Pass Rate**: TBD / 4 tests  
**JSON Compliance Proven**: TBD

## Notes

- Tests must be executed against a database with materialized views created
- All tests must pass for JSON compliance to be proven
- Test results should be documented with actual query outputs
- Evidence should include EXPLAIN ANALYZE results for performance validation

## Execution Instructions

1. Connect to test database
2. Run migrations: `alembic upgrade head`
3. Refresh materialized views: `REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_revenue; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_status;`
4. Execute test script: `psql -d test_db -f db/tests/test_contract_compliance.sql`
5. Document results in this file
6. Verify all tests pass before proceeding to deployment




