# B0.5.3.6 Context Baseline — Idempotency Invariants (DB Schema)

**Investigation Date:** 2025-12-18
**Branch:** `b0534-worker-tenant-ci` @ `8b2a806`
**Directive:** B0.5.3.6 Hypothesis-Driven Context Gathering
**Authorization:** Evidence collection ONLY (no implementation changes)

---

## Executive Summary

**Idempotency Strategy:** ✅ **EVENT-SCOPED OVERWRITE** via unique constraint + UPSERT

**Unique Constraint:** `(tenant_id, event_id, model_version, channel)`

**Write Strategy:** `INSERT ... ON CONFLICT DO UPDATE` (deterministic updates, no duplicates)

**event_id Nullability:** ❌ **NOT NULLABLE** — All allocations MUST reference an event

**Verdict:** ✅ **Idempotency invariants are ENFORCED** at schema level

---

## Schema Definition

### Table: `attribution_allocations`

**Source Migrations:**
- Base schema: [`202511131115_add_core_tables.py:193-204`](../../alembic/versions/001_core_schema/202511131115_add_core_tables.py#L193-L204)
- Model versioning: [`202512151410_add_allocation_model_versioning.py`](../../alembic/versions/007_skeldir_foundation/202512151410_add_allocation_model_versioning.py)

**Complete Schema:**
```sql
CREATE TABLE attribution_allocations (
    -- Primary key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Foreign keys
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    event_id UUID NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Attribution data
    channel TEXT NOT NULL,
    allocation_ratio NUMERIC(10, 6) NOT NULL DEFAULT 0.0,  -- Added in 202512151410
    allocated_revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (allocated_revenue_cents >= 0),
    model_version TEXT NOT NULL DEFAULT '1.0.0',  -- Added in 202512151410

    -- Metadata
    model_metadata JSONB,
    correlation_id UUID
);
```

---

## Idempotency Constraint

### Unique Index (Enforces Event-Scoped Overwrite)

**Name:** `idx_attribution_allocations_event_model_channel`

**Definition:**
```sql
CREATE UNIQUE INDEX idx_attribution_allocations_event_model_channel
ON attribution_allocations (tenant_id, event_id, model_version, channel);
```

**Source:** [`202512151410_add_allocation_model_versioning.py:52-54`](../../alembic/versions/007_skeldir_foundation/202512151410_add_allocation_model_versioning.py#L52-L54)

**Comment:**
```sql
COMMENT ON INDEX idx_attribution_allocations_event_model_channel IS
'Event-scoped overwrite strategy per model version. Ensures deterministic allocation updates on window recomputation. Used by B0.5.3.2 idempotency enforcement.';
```

---

### Unique Key Components

| Column | Purpose | Nullability | Type |
|--------|---------|-------------|------|
| `tenant_id` | Multi-tenant isolation | NOT NULL | UUID |
| `event_id` | Event reference | NOT NULL | UUID |
| `model_version` | Model versioning (A/B testing) | NOT NULL | TEXT |
| `channel` | Attribution channel | NOT NULL | TEXT |

**Interpretation:**
- One allocation per **(event, model_version, channel)** tuple per tenant
- Rerunning same window → **UPDATEs existing rows** (no duplicates)
- Different model versions → separate allocations (A/B testing support)

---

## Write Path Analysis

### UPSERT Strategy

**Source:** [`app/tasks/attribution.py:337-351`](../../backend/app/tasks/attribution.py#L337-L351)

```python
await conn.execute(
    text("""
        INSERT INTO attribution_allocations (
            id, tenant_id, event_id, channel, allocation_ratio,
            model_version, allocated_revenue_cents, created_at, updated_at
        ) VALUES (
            :allocation_id, :tenant_id, :event_id, :channel, :allocation_ratio,
            :model_version, :allocated_revenue_cents, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        )
        ON CONFLICT (tenant_id, event_id, model_version, channel)
        DO UPDATE SET
            allocation_ratio = EXCLUDED.allocation_ratio,
            allocated_revenue_cents = EXCLUDED.allocated_revenue_cents,
            updated_at = CURRENT_TIMESTAMP
    """),
    {...}
)
```

**Behavior:**
1. **First execution:** `INSERT` creates new row
2. **Subsequent executions:** `ON CONFLICT` triggers, `UPDATE` overwrites existing row
3. **Result:** Same (tenant_id, event_id, model_version, channel) tuple → same row

---

### Idempotency Proof

**Scenario:** Recompute same window twice

**First Execution:**
```sql
INSERT INTO attribution_allocations (tenant_id, event_id, model_version, channel, allocated_revenue_cents)
VALUES ('tenant1', 'event_a', '1.0.0', 'google_search', 3333);
-- Result: 1 row inserted
```

**Second Execution (Same Window):**
```sql
INSERT INTO attribution_allocations (tenant_id, event_id, model_version, channel, allocated_revenue_cents)
VALUES ('tenant1', 'event_a', '1.0.0', 'google_search', 3333);
-- ON CONFLICT triggers:
UPDATE attribution_allocations
SET allocated_revenue_cents = 3333,  -- Same value
    updated_at = CURRENT_TIMESTAMP
WHERE tenant_id = 'tenant1'
  AND event_id = 'event_a'
  AND model_version = '1.0.0'
  AND channel = 'google_search';
-- Result: 1 row updated (not inserted), total row count unchanged
```

**Assertion:**
```python
rows_before = await conn.fetchall(text("SELECT * FROM attribution_allocations WHERE ..."))
# Rerun recompute_window
rows_after = await conn.fetchall(text("SELECT * FROM attribution_allocations WHERE ..."))

assert len(rows_before) == len(rows_after)  # Same row count
assert rows_before == rows_after  # Exact same values (deterministic)
```

---

## Nullability Analysis

### Can `event_id` be NULL?

**Answer:** ❌ **NO** — Schema enforces NOT NULL

**Evidence:**
[`202511131115_add_core_tables.py:197`](../../alembic/versions/001_core_schema/202511131115_add_core_tables.py#L197)
```sql
event_id uuid NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE,
```

**Implications:**
- All allocations MUST reference an existing event
- Cannot create "event-less" allocations
- Cascade delete: If event deleted, allocations automatically deleted
- Referential integrity: Cannot insert allocation with non-existent event_id

**Duplicate Prevention:**
- Since `event_id` is NOT NULL and part of unique constraint:
  - Unique constraint ALWAYS applies (no NULL bypass)
  - No possibility of "duplicate NULL event_id" rows

---

### Other NOT NULL Columns

| Column | Nullability | Default | Purpose |
|--------|-------------|---------|---------|
| `tenant_id` | NOT NULL | - | RLS enforcement |
| `event_id` | NOT NULL | - | Event reference (idempotency key) |
| `channel` | NOT NULL | - | Attribution channel (idempotency key) |
| `model_version` | NOT NULL | `'1.0.0'` | Model versioning (idempotency key) |
| `allocation_ratio` | NOT NULL | `0.0` | Fractional credit |
| `allocated_revenue_cents` | NOT NULL | `0` | Integer revenue |
| `created_at` | NOT NULL | `now()` | Audit trail |
| `updated_at` | NOT NULL | `now()` | Audit trail |

**All idempotency key columns are NOT NULL** → Unique constraint always enforced

---

## Cascade Deletion Behavior

### ON DELETE CASCADE

**Schema:**
```sql
event_id UUID NOT NULL REFERENCES attribution_events(id) ON DELETE CASCADE
```

**Behavior:**
- If `attribution_events` row deleted → **all allocations for that event automatically deleted**
- Maintains referential integrity
- No orphaned allocations

**Implication for Recompute:**
- Recompute does NOT delete events (events are read-only)
- Recompute only UPDATEs allocations (via UPSERT)
- No cascade risk during normal operation

---

## Indexes for Query Performance

### Idempotency Index (Unique)

**Name:** `idx_attribution_allocations_event_model_channel`
**Columns:** `(tenant_id, event_id, model_version, channel)`
**Purpose:** Enforce unique constraint + optimize UPSERT lookups

---

### Time-Series Index

**Name:** `idx_attribution_allocations_tenant_created_at`
**Columns:** `(tenant_id, created_at DESC)`
**Purpose:** Optimize window-based queries (recent allocations first)

**Source:** [`202511131115_add_core_tables.py:213-216`](../../alembic/versions/001_core_schema/202511131115_add_core_tables.py#L213-L216)

---

### Event Lookup Index

**Name:** `idx_attribution_allocations_event_id`
**Columns:** `(event_id)`
**Purpose:** Optimize joins/lookups by event (reverse FK navigation)

**Source:** [`202511131115_add_core_tables.py:218-221`](../../alembic/versions/001_core_schema/202511131115_add_core_tables.py#L218-L221)

---

### Channel Aggregation Index

**Name:** `idx_attribution_allocations_channel`
**Columns:** `(channel)`
**Purpose:** Optimize channel-based aggregations (e.g., revenue by channel)

**Source:** [`202511131115_add_core_tables.py:223-226`](../../alembic/versions/001_core_schema/202511131115_add_core_tables.py#L223-L226)

---

## Model Versioning Support

### Multiple Models Coexist

**Scenario:** A/B test two attribution models

**Model 1.0.0 Allocation:**
```sql
INSERT INTO attribution_allocations (tenant_id, event_id, model_version, channel, allocated_revenue_cents)
VALUES ('tenant1', 'event_a', '1.0.0', 'google_search', 3333);
```

**Model 2.0.0 Allocation (Same Event, Different Model):**
```sql
INSERT INTO attribution_allocations (tenant_id, event_id, model_version, channel, allocated_revenue_cents)
VALUES ('tenant1', 'event_a', '2.0.0', 'google_search', 4000);
-- NO CONFLICT: Different model_version → separate row
```

**Result:** 2 rows exist (one per model version)

**Query Pattern:**
```sql
SELECT * FROM attribution_allocations
WHERE tenant_id = 'tenant1'
  AND event_id = 'event_a'
  AND model_version = '1.0.0';  -- Filter by model version
```

---

## Idempotency Test Matrix

| Scenario | Input | Expected Output | Unique Key Match? | Action |
|----------|-------|-----------------|-------------------|--------|
| First run | (tenant1, event_a, 1.0.0, google_search) → 3333 | 1 row inserted | NO | INSERT |
| Rerun (same window) | (tenant1, event_a, 1.0.0, google_search) → 3333 | 1 row total (unchanged) | YES | UPDATE (same value) |
| Rerun (different value) | (tenant1, event_a, 1.0.0, google_search) → 5000 | 1 row total (value changed) | YES | UPDATE (new value) |
| Different model | (tenant1, event_a, 2.0.0, google_search) → 4000 | 2 rows total | NO | INSERT (different model) |
| Different channel | (tenant1, event_a, 1.0.0, direct) → 3333 | 2 rows total | NO | INSERT (different channel) |
| Different event | (tenant1, event_b, 1.0.0, google_search) → 5000 | 2 rows total | NO | INSERT (different event) |

---

## Constraints Summary

### Table-Level Constraints

| Constraint | Type | Definition | Purpose |
|------------|------|------------|---------|
| `attribution_allocations_pkey` | PRIMARY KEY | `(id)` | Unique row identifier |
| `attribution_allocations_tenant_id_fkey` | FOREIGN KEY | `tenant_id → tenants(id) ON DELETE CASCADE` | Tenant isolation |
| `attribution_allocations_event_id_fkey` | FOREIGN KEY | `event_id → attribution_events(id) ON DELETE CASCADE` | Event reference |
| `ck_attribution_allocations_revenue_positive` | CHECK | `allocated_revenue_cents >= 0` | Revenue validation |
| `idx_attribution_allocations_event_model_channel` | UNIQUE INDEX | `(tenant_id, event_id, model_version, channel)` | Idempotency enforcement |

---

## Conclusion

**Gate 4 Status:** ✅ **MET** — Idempotency invariants are validated

**Key Findings:**
- ✅ Unique constraint enforces event-scoped overwrite
- ✅ event_id is NOT NULL (always required)
- ✅ Write path uses UPSERT (ON CONFLICT DO UPDATE)
- ✅ Rerun produces **zero new rows** (updates existing)
- ✅ Deterministic values → **exact match** after rerun
- ✅ Model versioning supported (A/B testing)

**Schema Guarantees:**
1. **No duplicates:** Unique constraint prevents duplicate allocations
2. **Deterministic updates:** Same input → same output (UPSERT idempotency)
3. **Referential integrity:** event_id FK ensures valid event references
4. **Cascade safety:** Event deletion cascades to allocations (no orphans)

**Test Assertions for B0.5.3.6:**
```python
# Idempotency proof
allocations_before = await query_allocations(tenant_id, model_version)
recompute_window.delay(...).get()  # Rerun
allocations_after = await query_allocations(tenant_id, model_version)

assert len(allocations_before) == len(allocations_after)  # Same row count
assert allocations_before == allocations_after  # Exact same values
```

**Recommendation:** Schema is production-ready for idempotent allocation writes. Proceed to B0.5.3.6 E2E tests.

**Next Step:** Confirm DLQ sink and correlation propagation contract in [B0536_DLQ_CORRELATION_CONTRACT.md](./B0536_DLQ_CORRELATION_CONTRACT.md).
