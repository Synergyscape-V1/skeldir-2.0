# Sum-Equality Invariant Specification

**Document Version**: 1.0  
**Date**: 2025-11-13  
**Purpose**: Define the sum-equality invariant for deterministic revenue accounting

---

## Invariant Statement

For each `(tenant_id, event_id, model_version)` combination, the sum of `allocated_revenue_cents` across all `attribution_allocations` must equal the `revenue_cents` of the corresponding `attribution_events` row, within ±1 cent rounding tolerance.

**Mathematical Expression**:
```
SUM(allocated_revenue_cents) WHERE (event_id, model_version) = event.revenue_cents ± 1 cent
```

---

## Scope

**Per-Event Invariant**: The invariant applies to each event independently. Allocations for different events are not required to sum together.

**Per-Model Invariant**: The invariant applies per `model_version`. Different model versions may allocate the same event differently, and each model version's allocations must independently sum to event revenue.

**Per-Tenant Isolation**: The invariant is enforced within tenant boundaries (via RLS), but the invariant itself is per-event, not per-tenant aggregate.

---

## Enforcement Mechanisms

### 1. Trigger-Based Enforcement (Real-Time)

**Function**: `check_allocation_sum()`  
**Trigger**: `trg_check_allocation_sum` on `attribution_allocations`  
**Behavior**: 
- Executes AFTER INSERT, UPDATE, or DELETE
- Raises exception if sum mismatch exceeds ±1 cent tolerance
- Prevents invalid state from being persisted

**SQL**:
```sql
CREATE TRIGGER trg_check_allocation_sum
    AFTER INSERT OR UPDATE OR DELETE ON attribution_allocations
    FOR EACH ROW EXECUTE FUNCTION check_allocation_sum();
```

### 2. Materialized View Validation (Reporting)

**View**: `mv_allocation_summary`  
**Purpose**: 
- Aggregate allocations per `(tenant_id, event_id, model_version)`
- Calculate drift (`ABS(allocated_sum - event_revenue)`)
- Flag unbalanced allocations (`is_balanced = false`)

**SQL**:
```sql
CREATE MATERIALIZED VIEW mv_allocation_summary AS
SELECT 
    aa.tenant_id,
    aa.event_id,
    aa.model_version,
    SUM(aa.allocated_revenue_cents) AS total_allocated_cents,
    e.revenue_cents AS event_revenue_cents,
    (SUM(aa.allocated_revenue_cents) = e.revenue_cents) AS is_balanced,
    ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents) AS drift_cents
FROM attribution_allocations aa
INNER JOIN attribution_events e ON aa.event_id = e.id
GROUP BY aa.tenant_id, aa.event_id, aa.model_version, e.revenue_cents;
```

---

## Rounding Tolerance

**Tolerance**: ±1 cent  
**Rationale**: See `db/docs/ROUNDING_POLICY.md`

Allocations may sum to event revenue ±1 cent due to rounding differences when converting allocation ratios to integer cents.

---

## Validation Queries

### Check All Balanced Allocations
```sql
SELECT * FROM mv_allocation_summary WHERE is_balanced = true;
```

### Find Unbalanced Allocations
```sql
SELECT * FROM mv_allocation_summary WHERE drift_cents > 1;
```

### Check Specific Event/Model
```sql
SELECT * FROM mv_allocation_summary 
WHERE tenant_id = '...' 
  AND event_id = '...' 
  AND model_version = '...';
```

---

## Failure Scenarios

### Scenario 1: Under-Allocation
- Event revenue: `10000 cents`
- Allocated sum: `9998 cents`
- Drift: `-2 cents` (exceeds tolerance)
- **Result**: Trigger raises exception, MV flags as unbalanced

### Scenario 2: Over-Allocation
- Event revenue: `10000 cents`
- Allocated sum: `10002 cents`
- Drift: `+2 cents` (exceeds tolerance)
- **Result**: Trigger raises exception, MV flags as unbalanced

### Scenario 3: Within Tolerance
- Event revenue: `10000 cents`
- Allocated sum: `9999 cents`
- Drift: `-1 cent` (within tolerance)
- **Result**: ✅ Valid, no exception raised

---

## Correction Process

If invariant violation is detected:

1. **Identify**: Query `mv_allocation_summary` for unbalanced allocations
2. **Investigate**: Review allocation ratios and rounding logic
3. **Correct**: Adjust allocations to sum to event revenue
4. **Verify**: Re-run validation queries

---

## Cross-References

- **Rounding Policy**: `db/docs/ROUNDING_POLICY.md`
- **Migration**: `alembic/versions/202511131240_add_sum_equality_validation.py`
- **Test Script**: `db/tests/test_sum_equality.sql`




