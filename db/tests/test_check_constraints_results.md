# CHECK Constraint Test Results

**Test Script**: `db/tests/test_check_constraints.sql`  
**Date**: 2025-11-13  
**Status**: ⏳ **PENDING EXECUTION**

---

## Test Results

### Test 1: Negative Revenue Rejection (revenue_cents < 0)
**Status**: ⏳ Pending  
**Expected**: Constraint violation exception  
**Result**: TBD

### Test 2: Allocation Ratio Bounds (0-1)
**Status**: ⏳ Pending  
**Test 2a**: Negative allocation_ratio rejection  
**Test 2b**: allocation_ratio > 1 rejection  
**Test 2c**: allocation_ratio = 0 (should pass)  
**Test 2d**: allocation_ratio = 1 (should pass)  
**Result**: TBD

### Test 3: Channel Code Enum Validation
**Status**: ⏳ Pending  
**Test 3a**: Invalid channel code rejection  
**Test 3b**: Valid channel codes (should pass)  
**Result**: TBD

### Test 4: Negative allocated_revenue_cents Rejection
**Status**: ⏳ Pending  
**Expected**: Constraint violation exception  
**Result**: TBD

### Test 5: Negative revenue_ledger.revenue_cents Rejection
**Status**: ⏳ Pending  
**Expected**: Constraint violation exception  
**Result**: TBD

---

## Summary

**Total Tests**: 5 (with sub-tests)  
**Passed**: TBD  
**Failed**: TBD  
**Pending**: 5

---

## Notes

- Tests require database execution
- All tests use transaction rollback for cleanup
- Test data uses fixed UUIDs for reproducibility




