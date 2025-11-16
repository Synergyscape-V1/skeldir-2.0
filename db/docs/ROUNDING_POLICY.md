# Rounding Policy for Revenue Allocation

**Document Version**: 1.0  
**Date**: 2025-11-13  
**Purpose**: Define rounding tolerance for sum-equality validation

---

## Policy Statement

Revenue allocations must sum to event revenue within **±1 cent tolerance** to account for rounding differences in allocation calculations.

---

## Rationale

Attribution models may allocate revenue using ratios (e.g., `allocation_ratio numeric(6,5)`), which can result in fractional cent values. When converting these ratios to integer cents (`allocated_revenue_cents INTEGER`), rounding may cause the sum of allocations to differ from the event revenue by up to 1 cent.

**Example**:
- Event revenue: `10000 cents` ($100.00)
- Allocation ratio 1: `0.333333` → `3333 cents` (rounded)
- Allocation ratio 2: `0.333333` → `3333 cents` (rounded)
- Allocation ratio 3: `0.333334` → `3334 cents` (rounded)
- Sum: `3333 + 3333 + 3334 = 10000 cents` ✅ (exact match)

**Alternative scenario**:
- Event revenue: `10000 cents` ($100.00)
- Allocation ratio 1: `0.333333` → `3333 cents` (rounded)
- Allocation ratio 2: `0.333333` → `3333 cents` (rounded)
- Allocation ratio 3: `0.333333` → `3333 cents` (rounded)
- Sum: `3333 + 3333 + 3333 = 9999 cents` (1 cent short)
- **Result**: Within tolerance (±1 cent) ✅

---

## Implementation

### Trigger Function Tolerance

The `check_allocation_sum()` trigger function enforces this policy:

```sql
tolerance_cents INTEGER := 1; -- ±1 cent rounding tolerance

IF ABS(allocated_sum - event_revenue) > tolerance_cents THEN
    RAISE EXCEPTION 'Allocation sum mismatch: allocated=% expected=% drift=%', 
        allocated_sum, event_revenue, ABS(allocated_sum - event_revenue);
END IF;
```

### Materialized View Drift Tracking

The `mv_allocation_summary` materialized view tracks drift:

```sql
ABS(SUM(aa.allocated_revenue_cents) - e.revenue_cents) AS drift_cents
```

Queries can filter for allocations with drift > 1 cent:

```sql
SELECT * FROM mv_allocation_summary WHERE drift_cents > 1;
```

---

## Validation Rules

1. **Within Tolerance** (`drift_cents <= 1`): ✅ Valid
   - Sum-equality validation passes
   - No action required

2. **Exceeds Tolerance** (`drift_cents > 1`): ❌ Invalid
   - Trigger raises exception (prevents insert/update/delete)
   - Materialized view flags as unbalanced (`is_balanced = false`)
   - Requires investigation and correction

---

## Correction Process

If drift exceeds tolerance:

1. **Investigate**: Review allocation ratios and rounding logic
2. **Correct**: Adjust allocations to sum to event revenue
3. **Verify**: Re-run sum-equality validation

---

## Cross-References

- **Sum-Equality Invariant**: `db/docs/SUM_EQUALITY_INVARIANT.md`
- **Trigger Function**: `check_allocation_sum()` in migration `202511131240_add_sum_equality_validation.py`
- **Materialized View**: `mv_allocation_summary` in migration `202511131240_add_sum_equality_validation.py`




