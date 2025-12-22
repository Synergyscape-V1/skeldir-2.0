# B0.5.3.6 Context Baseline — Deterministic Test Vector

**Investigation Date:** 2025-12-18
**Branch:** `b0534-worker-tenant-ci` @ `8b2a806`
**Directive:** B0.5.3.6 Hypothesis-Driven Context Gathering
**Authorization:** Evidence collection ONLY (no implementation changes)

---

## Executive Summary

**Deterministic Baseline:** ✅ **COMPUTABLE** — Exact expected allocations can be asserted

**Rounding Policy:** Integer truncation (`int()`) causes **predictable revenue loss**
- Example: 10000 cents → 3333 + 3333 + 3333 = 9999 cents (1 cent lost)
- This is **acceptable** for deterministic baseline (not production-ready, but testable)

**Test Vector:** 2 events, 3 channels, equal split → 6 allocation rows with exact values

---

## Minimal Deterministic Dataset

### Test Parameters

**Tenant:** `test_tenant_00000000-0000-0000-0000-000000000001`
**Window:** `2025-06-01T00:00:00Z` (inclusive) to `2025-06-01T23:59:59.999999Z` (exclusive)
**Model Version:** `1.0.0`
**Channels:** `["google_search", "direct", "email"]` (fixed, deterministic order)
**Allocation Ratio:** `1.0 / 3 = 0.333...` (equal split)

---

### Input Events

#### Event 1
```json
{
  "id": "event_a_10k_001",
  "tenant_id": "test_tenant_00000000-0000-0000-0000-000000000001",
  "occurred_at": "2025-06-01T10:00:00Z",
  "revenue_cents": 10000,
  "raw_payload": {"channel": "google_search", "utm_source": "google"}
}
```

**SQL Insert:**
```sql
INSERT INTO attribution_events (id, tenant_id, occurred_at, revenue_cents, raw_payload)
VALUES (
    'event_a_10k_001',
    'test_tenant_00000000-0000-0000-0000-000000000001',
    '2025-06-01T10:00:00Z'::timestamptz,
    10000,
    '{"channel": "google_search", "utm_source": "google"}'::jsonb
)
ON CONFLICT DO NOTHING;
```

---

#### Event 2
```json
{
  "id": "event_b_15k_002",
  "tenant_id": "test_tenant_00000000-0000-0000-0000-000000000001",
  "occurred_at": "2025-06-01T15:00:00Z",
  "revenue_cents": 15000,
  "raw_payload": {"channel": "direct", "utm_source": null}
}
```

**SQL Insert:**
```sql
INSERT INTO attribution_events (id, tenant_id, occurred_at, revenue_cents, raw_payload)
VALUES (
    'event_b_15k_002',
    'test_tenant_00000000-0000-0000-0000-000000000001',
    '2025-06-01T15:00:00Z'::timestamptz,
    15000,
    '{"channel": "direct", "utm_source": null}'::jsonb
)
ON CONFLICT DO NOTHING;
```

---

## Expected Allocations (Exact Values)

### Allocation Logic (from `_compute_allocations_deterministic_baseline`)

**Code:**
```python
BASELINE_CHANNELS = ["google_search", "direct", "email"]
allocation_ratio = 1.0 / len(BASELINE_CHANNELS)  # 0.333...

for event_row in events:
    revenue_cents = event_row[1]
    for channel in BASELINE_CHANNELS:
        allocated_revenue = int(revenue_cents * allocation_ratio)  # Integer truncation
```

---

### Event 1 Allocations (10000 cents)

**Calculation:**
- `allocation_ratio = 1.0 / 3 = 0.333...`
- `allocated_revenue = int(10000 * 0.333...) = int(3333.333...) = 3333`

**Expected Rows:**

| event_id | channel | allocation_ratio | allocated_revenue_cents | model_version |
|----------|---------|------------------|-------------------------|---------------|
| `event_a_10k_001` | `google_search` | `0.333...` | `3333` | `1.0.0` |
| `event_a_10k_001` | `direct` | `0.333...` | `3333` | `1.0.0` |
| `event_a_10k_001` | `email` | `0.333...` | `3333` | `1.0.0` |

**Total Allocated:** 3333 + 3333 + 3333 = **9999 cents** (1 cent lost to rounding)

---

### Event 2 Allocations (15000 cents)

**Calculation:**
- `allocation_ratio = 1.0 / 3 = 0.333...`
- `allocated_revenue = int(15000 * 0.333...) = int(5000) = 5000`

**Expected Rows:**

| event_id | channel | allocation_ratio | allocated_revenue_cents | model_version |
|----------|---------|------------------|-------------------------|---------------|
| `event_b_15k_002` | `google_search` | `0.333...` | `5000` | `1.0.0` |
| `event_b_15k_002` | `direct` | `0.333...` | `5000` | `1.0.0` |
| `event_b_15k_002` | `email` | `0.333...` | `5000` | `1.0.0` |

**Total Allocated:** 5000 + 5000 + 5000 = **15000 cents** (no rounding loss!)

---

## Complete Expected Output (6 Rows)

**Query to Verify:**
```sql
SELECT
    event_id,
    channel,
    allocation_ratio,
    allocated_revenue_cents,
    model_version,
    tenant_id
FROM attribution_allocations
WHERE tenant_id = 'test_tenant_00000000-0000-0000-0000-000000000001'
  AND model_version = '1.0.0'
ORDER BY event_id, channel;
```

**Expected Result Set:**

| event_id | channel | allocation_ratio | allocated_revenue_cents | model_version | tenant_id |
|----------|---------|------------------|-------------------------|---------------|-----------|
| `event_a_10k_001` | `direct` | `0.333...` | `3333` | `1.0.0` | `test_tenant_...001` |
| `event_a_10k_001` | `email` | `0.333...` | `3333` | `1.0.0` | `test_tenant_...001` |
| `event_a_10k_001` | `google_search` | `0.333...` | `3333` | `1.0.0` | `test_tenant_...001` |
| `event_b_15k_002` | `direct` | `0.333...` | `5000` | `1.0.0` | `test_tenant_...001` |
| `event_b_15k_002` | `email` | `0.333...` | `5000` | `1.0.0` | `test_tenant_...001` |
| `event_b_15k_002` | `google_search` | `0.333...` | `5000` | `1.0.0` | `test_tenant_...001` |

**Total Row Count:** `6` (2 events × 3 channels)

---

## Rounding Policy Analysis

### Integer Truncation (`int()`)

**Behavior:**
```python
int(10000 * 0.333...) = int(3333.333...) = 3333  # Truncates fractional part
```

**Revenue Loss Examples:**

| Revenue (cents) | Per-Channel Allocation | Total Allocated | Lost |
|----------------|------------------------|-----------------|------|
| 10000 | 3333 | 9999 | 1 |
| 10001 | 3333 | 9999 | 2 |
| 10002 | 3334 | 10002 | 0 |
| 15000 | 5000 | 15000 | 0 |
| 100 | 33 | 99 | 1 |
| 1 | 0 | 0 | 1 |

**Observations:**
- ✅ **Deterministic:** Same input → same output (no randomness)
- ⚠️ **Revenue Loss:** Rounding errors accumulate (max loss = num_channels - 1 cents)
- ❌ **Not Production-Ready:** Real attribution should preserve revenue totals

**Acceptable for B0.5.3.6?**
- ✅ **YES** — Deterministic baseline is intentionally simple
- Purpose: Prove E2E pipeline works, not implement production math
- Production-ready attribution (ML-based, revenue-preserving) is future work

---

## Idempotency Test Vector

### First Execution

**Action:** Run `recompute_window` for window `2025-06-01T00:00:00Z` to `2025-06-01T23:59:59.999999Z`

**Expected:**
- 6 rows inserted into `attribution_allocations`
- 1 row inserted into `attribution_recompute_jobs` (status: `succeeded`, run_count: `1`)

---

### Second Execution (Idempotency Proof)

**Action:** Rerun **same** `recompute_window` with **identical parameters**

**Expected:**
- **0 new rows** in `attribution_allocations` (UPSERT updates existing rows)
- **Same values** (3333, 3333, 3333, 5000, 5000, 5000)
- **Same row count** (6 total)
- **Job row updated:** `run_count` increments to `2`, `status` remains `succeeded`

**Assertion:**
```python
# Query allocations before and after rerun
allocations_before = await conn.fetchall(...)
recompute_window.delay(...).get()  # Rerun
allocations_after = await conn.fetchall(...)

assert len(allocations_before) == len(allocations_after) == 6
assert allocations_before == allocations_after  # Exact same rows + values
```

---

## Failure Mode Test Vector

### Induced Failure

**Action:** Call `recompute_window.delay(..., fail=True)`

**Expected:**
- Task raises `ValueError("attribution recompute failure requested")`
- DLQ row inserted into `worker_failed_jobs`:
  ```json
  {
    "task_name": "app.tasks.attribution.recompute_window",
    "exception_class": "ValueError",
    "error_message": "attribution recompute failure requested",
    "correlation_id": "<non-null UUID>",
    "tenant_id": "test_tenant_00000000-0000-0000-0000-000000000001",
    "status": "pending"
  }
  ```
- Job row status set to `failed` in `attribution_recompute_jobs`

**Assertion:**
```python
dlq_row = await conn.fetchone(
    text("SELECT * FROM worker_failed_jobs WHERE task_name = 'app.tasks.attribution.recompute_window' ORDER BY failed_at DESC LIMIT 1")
)
assert dlq_row is not None
assert dlq_row.exception_class == "ValueError"
assert dlq_row.correlation_id is not None  # Non-null correlation
```

---

## E2E Test Template (Pseudocode)

```python
async def test_b0536_attribution_e2e_deterministic_baseline():
    """
    B0.5.3.6: End-to-end attribution recompute with deterministic baseline.

    Proves:
    - Ingest → schedule → task → allocations pipeline works
    - Exact allocation values match expected (deterministic)
    - Idempotency holds (rerun produces same results)
    - Failure mode captures DLQ + correlation
    """
    tenant_id = UUID("test_tenant_00000000-0000-0000-0000-000000000001")
    window_start = "2025-06-01T00:00:00Z"
    window_end = "2025-06-01T23:59:59.999999Z"

    # Setup: Insert test events
    await insert_event(id="event_a_10k_001", revenue_cents=10000, occurred_at="2025-06-01T10:00:00Z")
    await insert_event(id="event_b_15k_002", revenue_cents=15000, occurred_at="2025-06-01T15:00:00Z")

    # Execution 1: First recompute
    result = recompute_window.delay(tenant_id=tenant_id, window_start=window_start, window_end=window_end)
    outcome = result.get(timeout=30)
    assert outcome["status"] == "succeeded"
    assert outcome["event_count"] == 2
    assert outcome["allocation_count"] == 6

    # Verify allocations (exact values)
    allocations = await query_allocations(tenant_id, model_version="1.0.0")
    assert len(allocations) == 6
    assert allocations[0] == {"event_id": "event_a_10k_001", "channel": "direct", "allocated_revenue_cents": 3333}
    assert allocations[1] == {"event_id": "event_a_10k_001", "channel": "email", "allocated_revenue_cents": 3333}
    assert allocations[2] == {"event_id": "event_a_10k_001", "channel": "google_search", "allocated_revenue_cents": 3333}
    assert allocations[3] == {"event_id": "event_b_15k_002", "channel": "direct", "allocated_revenue_cents": 5000}
    assert allocations[4] == {"event_id": "event_b_15k_002", "channel": "email", "allocated_revenue_cents": 5000}
    assert allocations[5] == {"event_id": "event_b_15k_002", "channel": "google_search", "allocated_revenue_cents": 5000}

    # Execution 2: Idempotency proof (rerun)
    allocations_before = await query_allocations(tenant_id, model_version="1.0.0")
    result2 = recompute_window.delay(tenant_id=tenant_id, window_start=window_start, window_end=window_end)
    outcome2 = result2.get(timeout=30)
    allocations_after = await query_allocations(tenant_id, model_version="1.0.0")

    assert outcome2["status"] == "succeeded"
    assert len(allocations_before) == len(allocations_after) == 6
    assert allocations_before == allocations_after  # Exact same values

    # Execution 3: Failure mode proof
    result_fail = recompute_window.delay(tenant_id=tenant_id, window_start=window_start, window_end=window_end, fail=True)
    with pytest.raises(ValueError):
        result_fail.get(propagate=True)

    # Verify DLQ capture
    dlq_row = await query_dlq_latest()
    assert dlq_row.task_name == "app.tasks.attribution.recompute_window"
    assert dlq_row.exception_class == "ValueError"
    assert dlq_row.correlation_id is not None  # Correlation propagated
```

---

## Assertion Checklist

### Correctness Assertions
- [ ] Event count = 2 (events in window)
- [ ] Allocation count = 6 (2 events × 3 channels)
- [ ] Allocation values = [3333, 3333, 3333, 5000, 5000, 5000]
- [ ] Channel ordering = alphabetical (direct, email, google_search)
- [ ] Event ordering = by occurred_at ASC

### Idempotency Assertions
- [ ] Row count unchanged after rerun (6 rows)
- [ ] Allocation values unchanged after rerun (exact match)
- [ ] Job run_count increments (1 → 2)
- [ ] Job status remains "succeeded"

### Failure Mode Assertions
- [ ] Task raises ValueError with expected message
- [ ] DLQ row exists with task_name = "app.tasks.attribution.recompute_window"
- [ ] DLQ row contains exception_class = "ValueError"
- [ ] DLQ row contains correlation_id (non-null)
- [ ] Job status = "failed" in attribution_recompute_jobs

---

## Conclusion

**Gate 3 Status:** ✅ **MET** — Deterministic test vector is specified

**Key Findings:**
- ✅ Exact expected allocations are computable
- ✅ Rounding policy is deterministic (integer truncation)
- ⚠️ Revenue loss is acceptable for baseline (1 cent lost on 10000 input)
- ✅ Idempotency can be asserted via exact value comparison
- ✅ Failure mode includes DLQ + correlation propagation

**Recommendation:** Use this test vector for B0.5.3.6 E2E tests. Revenue-preserving math is future work.

**Next Step:** Validate idempotency invariants at DB schema level in [B0536_IDEMPOTENCY_BASELINE.md](./B0536_IDEMPOTENCY_BASELINE.md).
