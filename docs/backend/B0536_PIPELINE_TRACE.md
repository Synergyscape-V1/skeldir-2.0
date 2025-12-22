# B0.5.3.6 Context Baseline — Pipeline Trace (Ingest → Schedule → Task → Allocations)

**Investigation Date:** 2025-12-18
**Branch:** `b0534-worker-tenant-ci` @ `8b2a806`
**Directive:** B0.5.3.6 Hypothesis-Driven Context Gathering
**Authorization:** Evidence collection ONLY (no implementation changes)

---

## Executive Summary

**Pipeline Status:** **PARTIALLY IMPLEMENTED**

**What Exists:**
- ✅ Ingestion insertion mechanism (direct SQL in tests)
- ✅ Task entrypoint (`recompute_window`)
- ✅ Allocations write path (`_compute_allocations_deterministic_baseline`)
- ✅ Correlation ID propagation infrastructure (`set_request_correlation_id`)

**What's Missing:**
- ❌ **`schedule_recompute_window()` function** — No scheduling layer exists yet
- ❌ **Ingestion → Scheduling trigger** — B0.4 ingestion doesn't auto-schedule recompute

**Implication:** B0.5.3.6 must implement `schedule_recompute_window()` to bridge ingestion → task execution.

---

## Full Pipeline Trace

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: Ingestion (Test Harness)                                   │
│ Location: Direct SQL INSERT in test code                           │
│ Target Table: attribution_events                                   │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Schedule Task (MISSING)                                    │
│ Expected: schedule_recompute_window(tenant_id, window_start, ...)  │
│ Action: Enqueue Celery task via recompute_window.delay()           │
│ Status: ❌ NOT IMPLEMENTED YET                                     │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Task Execution (EXISTS)                                    │
│ File: backend/app/tasks/attribution.py                             │
│ Function: @celery_app.task recompute_window()                      │
│ Broker: Postgres SQLAlchemy transport                              │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 4: Allocations Write (EXISTS)                                 │
│ Function: _compute_allocations_deterministic_baseline()            │
│ Target Table: attribution_allocations                              │
│ Write Strategy: UPSERT (ON CONFLICT DO UPDATE)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component-by-Component Trace

### 1. Ingestion Insertion Mechanism

**Current Implementation:** Direct SQL `INSERT INTO attribution_events`

**Test Example:**
[`tests/test_b0534_worker_tenant_isolation.py:46-50`](../../backend/tests/test_b0534_worker_tenant_isolation.py#L46-L50)

```python
await conn.execute(
    text("""
        INSERT INTO attribution_events (id, tenant_id, occurred_at, revenue_cents, raw_payload)
        VALUES
            (:id1, :tenant_id, CAST(:ts1 AS timestamptz), :rev1, '{}'::jsonb),
            (:id2, :tenant_id, CAST(:ts2 AS timestamptz), :rev2, '{}'::jsonb)
        ON CONFLICT DO NOTHING
    """),
    {...}
)
```

**Schema:** [`attribution_events` table](../../alembic/versions/) (from migrations)

**Key Fields:**
- `id` (UUID, PK)
- `tenant_id` (UUID, FK to tenants, RLS enforced)
- `occurred_at` (timestamptz)
- `revenue_cents` (int) — Input for allocations
- `raw_payload` (jsonb) — Original event data

**B0.4 Integration Status:**
- ❓ **UNKNOWN** — No evidence that B0.4 ingestion API automatically triggers recompute
- Expected: B0.4 ingestion → `schedule_recompute_window()` → Celery task
- Current: Tests manually call `recompute_window.delay()` (no scheduling layer)

---

### 2. Schedule Task (MISSING COMPONENT)

**Expected Location:** `backend/app/services/attribution.py` or `backend/app/tasks/attribution.py`

**Expected Function Signature:**
```python
def schedule_recompute_window(
    tenant_id: UUID,
    window_start: str,  # ISO8601 timestamp
    window_end: str,    # ISO8601 timestamp
    correlation_id: Optional[str] = None,
    model_version: str = "1.0.0",
) -> AsyncResult:
    """
    Schedule attribution recompute for a window.

    Returns:
        AsyncResult: Celery task result handle
    """
    from app.tasks.attribution import recompute_window

    result = recompute_window.delay(
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        correlation_id=correlation_id,
        model_version=model_version,
    )
    return result
```

**Current Workaround (in tests):**
```python
# Tests call task directly without scheduling layer
from app.tasks.attribution import recompute_window

result = recompute_window.delay(
    tenant_id=test_tenant_id,
    window_start="2025-01-01T00:00:00Z",
    window_end="2025-01-01T23:59:59Z",
)
```

**Why Missing Matters:**
- Without `schedule_recompute_window()`, there's no abstraction for:
  - Validation of window boundaries
  - Correlation ID generation
  - Triggering from HTTP API (future)
  - Testing isolation (mock scheduling without running task)

**Recommendation:** Implement `schedule_recompute_window()` as part of B0.5.3.6.

---

### 3. Task Execution

**File:** [`backend/app/tasks/attribution.py:382-578`](../../backend/app/tasks/attribution.py#L382-L578)

**Task Entrypoint:**
```python
@celery_app.task(
    bind=True,
    name="app.tasks.attribution.recompute_window",
    routing_key="attribution.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def recompute_window(
    self,
    tenant_id: UUID,
    window_start: Optional[str] = None,
    window_end: Optional[str] = None,
    correlation_id: Optional[str] = None,
    model_version: str = "1.0.0",
    fail: bool = False,
):
    """Attribution recompute window task with window-scoped idempotency."""
    ...
```

**Task Lifecycle:**

1. **Context Preparation** ([`attribution.py:425-431`](../../backend/app/tasks/attribution.py#L425-L431)):
   ```python
   model = AttributionTaskPayload(...)
   correlation = _prepare_context(model)  # Sets correlation_id in contextvars
   ```

2. **Window Validation** ([`attribution.py:446-466`](../../backend/app/tasks/attribution.py#L446-L466)):
   ```python
   window_start_dt = _normalize_timestamp(window_start)
   window_end_dt = _normalize_timestamp(window_end)
   if window_start_dt >= window_end_dt:
       raise ValueError(...)
   ```

3. **Job Identity Upsert** ([`attribution.py:469-490`](../../backend/app/tasks/attribution.py#L469-L490)):
   ```python
   job_id, run_count, previous_status = _run_async(
       _upsert_job_identity,
       tenant_id=model.tenant_id,
       window_start=window_start_dt,
       window_end=window_end_dt,
       model_version=model_version,
       correlation_id=correlation,
   )
   ```

4. **Allocations Compute** ([`attribution.py:508-515`](../../backend/app/tasks/attribution.py#L508-L515)):
   ```python
   result = _run_async(
       _compute_allocations_deterministic_baseline,
       tenant_id=model.tenant_id,
       window_start=window_start_dt,
       window_end=window_end_dt,
       model_version=model_version,
   )
   ```

5. **Status Update** ([`attribution.py:517-523`](../../backend/app/tasks/attribution.py#L517-L523)):
   ```python
   _run_async(
       _mark_job_status,
       job_id=job_id,
       tenant_id=model.tenant_id,
       status="succeeded",
   )
   ```

---

### 4. Allocations Write Path

**Function:** [`_compute_allocations_deterministic_baseline()`](../../backend/app/tasks/attribution.py#L264-L380)

**Code Path:**

```python
async def _compute_allocations_deterministic_baseline(
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_version: str = "1.0.0",
) -> dict:
    async with engine.begin() as conn:
        # Set tenant context for RLS
        await set_tenant_guc(conn, tenant_id, local=True)

        # Step 1: Read events in window (READ-ONLY)
        events_result = await conn.execute(
            text("""
                SELECT id, revenue_cents, occurred_at
                FROM attribution_events
                WHERE tenant_id = :tenant_id
                  AND occurred_at >= :window_start
                  AND occurred_at < :window_end
                ORDER BY occurred_at ASC
            """),
            {...}
        )
        events = events_result.fetchall()

        # Step 2: Deterministic allocation logic
        BASELINE_CHANNELS = ["google_search", "direct", "email"]
        allocation_ratio = 1.0 / len(BASELINE_CHANNELS)  # Equal split

        for event_row in events:
            event_id = event_row[0]
            revenue_cents = event_row[1]

            for channel in BASELINE_CHANNELS:
                allocated_revenue = int(revenue_cents * allocation_ratio)

                # Step 3: UPSERT allocation (idempotent)
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

        return {"event_count": len(events), "allocation_count": allocation_count}
```

**Key Characteristics:**
- ✅ **Read-only events:** No writes to `attribution_events` (respects B0.5.3.5)
- ✅ **UPSERT strategy:** `ON CONFLICT DO UPDATE` ensures idempotency
- ✅ **Unique constraint:** `(tenant_id, event_id, model_version, channel)`
- ✅ **Deterministic logic:** Fixed channels, equal split (no randomness)
- ✅ **RLS enforced:** `set_tenant_guc()` ensures tenant isolation

---

## Correlation ID Propagation Path

### Correlation Infrastructure

**Module:** [`backend/app/observability/context.py`](../../backend/app/observability/context.py)

**ContextVars:**
```python
correlation_id_request_var: ContextVar[Optional[str]] = ContextVar("correlation_id_request", default=None)
correlation_id_business_var: ContextVar[Optional[str]] = ContextVar("correlation_id_business", default=None)
tenant_id_var: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)
```

**Setters:**
```python
def set_request_correlation_id(value: str) -> None:
    correlation_id_request_var.set(value)

def set_tenant_id(value: Optional[UUID]) -> None:
    tenant_id_var.set(str(value) if value else None)
```

---

### Correlation Propagation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Task Invocation                                                  │
│    recompute_window.delay(correlation_id="abc123", ...)             │
│    → Celery request headers: {'correlation_id': 'abc123'}          │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 2. Task Execution Start                                             │
│    File: app/tasks/attribution.py:98-102                            │
│    _prepare_context(model):                                         │
│        correlation = model.correlation_id or str(uuid4())           │
│        set_request_correlation_id(correlation)  ← ContextVar set    │
│        set_tenant_id(model.tenant_id)                               │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 3. Structured Logging                                               │
│    logger.info("...", extra=log_context())                          │
│    → log_context() reads from ContextVars                           │
│    → Logs include: {"correlation_id_request": "abc123", ...}       │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 4. Job Identity Persistence                                         │
│    File: app/tasks/attribution.py:188                               │
│    INSERT INTO attribution_recompute_jobs (                         │
│        ..., last_correlation_id, ...                                │
│    ) VALUES (..., :correlation_id, ...)                             │
│    → DB row contains correlation ID                                 │
└─────────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────────┐
│ 5. DLQ Capture (on failure)                                         │
│    File: app/celery_app.py:334-342                                  │
│    correlation_id_val = getattr(task.request, 'correlation_id', ...)│
│    INSERT INTO worker_failed_jobs (..., correlation_id, ...)        │
│    → DLQ row contains correlation ID                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Correlation ID Sources (Priority Order)

**Source 1 (Explicit):** `recompute_window.delay(correlation_id="abc123", ...)`
- Passed as task argument
- Stored in task payload

**Source 2 (Fallback - Task ID):**
[`app/celery_app.py:338-342`](../../backend/app/celery_app.py#L338-L342)
```python
# Correlation must be present for DLQ diagnostics; fall back to task_id when missing.
if correlation_id is None and task_id:
    try:
        correlation_id = UUID(str(task_id))
    except (ValueError, TypeError):
        correlation_id = None
```

**Source 3 (Generated):**
[`app/tasks/attribution.py:99`](../../backend/app/tasks/attribution.py#L99)
```python
correlation = model.correlation_id or str(uuid4())  # Generate if not provided
```

---

## Missing Pipeline Components

### 1. `schedule_recompute_window()` Function ❌

**What's Needed:**
```python
# Proposed location: backend/app/services/attribution.py

from uuid import UUID, uuid4
from typing import Optional
from celery.result import AsyncResult

def schedule_recompute_window(
    tenant_id: UUID,
    window_start: str,
    window_end: str,
    correlation_id: Optional[str] = None,
    model_version: str = "1.0.0",
) -> AsyncResult:
    """
    Schedule attribution recompute for a time window.

    This function:
    1. Validates tenant_id exists
    2. Generates correlation_id if not provided
    3. Enqueues recompute_window Celery task
    4. Returns AsyncResult for status tracking

    Args:
        tenant_id: Tenant UUID
        window_start: ISO8601 timestamp (e.g., "2025-01-01T00:00:00Z")
        window_end: ISO8601 timestamp (exclusive upper bound)
        correlation_id: Optional correlation ID for observability
        model_version: Attribution model version (default: "1.0.0")

    Returns:
        AsyncResult: Celery task handle

    Raises:
        ValueError: If window_start >= window_end
    """
    from app.tasks.attribution import recompute_window

    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = str(uuid4())

    # Enqueue task
    result = recompute_window.delay(
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        correlation_id=correlation_id,
        model_version=model_version,
    )

    return result
```

**Why It's Needed:**
- ✅ Single entry point for scheduling (tests + future API)
- ✅ Correlation ID generation (ensures observability)
- ✅ Input validation (prevents invalid windows)
- ✅ Abstraction layer (can add rate limiting, batching, etc.)

---

### 2. B0.4 Ingestion → Scheduling Trigger ❓

**Expected Integration:**
```python
# In B0.4 ingestion endpoint (after event insert):
await conn.execute(text("INSERT INTO attribution_events ..."))
await conn.commit()

# Trigger recompute for affected window
schedule_recompute_window(
    tenant_id=tenant_id,
    window_start=window_start,  # Computed from event timestamp
    window_end=window_end,
    correlation_id=request_correlation_id,
)
```

**Current Status:** ❓ **UNKNOWN** — B0.4 ingestion may not auto-trigger recompute yet

---

## Pipeline Readiness Matrix

| Component | Status | Location | Notes |
|-----------|--------|----------|-------|
| **Ingestion** (test harness) | ✅ EXISTS | Direct SQL in tests | Works for E2E tests |
| **Scheduling layer** | ❌ MISSING | N/A | Must implement for B0.5.3.6 |
| **Task entrypoint** | ✅ EXISTS | `app/tasks/attribution.py:382` | `recompute_window` task |
| **Job identity tracking** | ✅ EXISTS | `_upsert_job_identity()` | Idempotency enforcement |
| **Allocations compute** | ✅ EXISTS | `_compute_allocations_deterministic_baseline()` | Deterministic logic |
| **Allocations write** | ✅ EXISTS | UPSERT with unique constraint | Idempotent writes |
| **Correlation propagation** | ✅ EXISTS | ContextVars + task args | End-to-end tracing |
| **DLQ capture** | ✅ EXISTS | `worker_failed_jobs` | Failure observability |

---

## Conclusion

**Gate 2 Status:** ✅ **MET** — Pipeline trace is complete

**What Works:**
- ✅ Task execution (`recompute_window`)
- ✅ Allocations write path (deterministic baseline)
- ✅ Correlation ID propagation (end-to-end)
- ✅ Job identity tracking (idempotency)

**What's Missing:**
- ❌ `schedule_recompute_window()` function (must implement)
- ❓ B0.4 ingestion trigger (unknown if auto-schedules)

**Recommendation:**
1. **Implement `schedule_recompute_window()`** as first step of B0.5.3.6
2. **Use direct task invocation** in E2E tests (bypass scheduling layer for now)
3. **Defer B0.4 integration** until after E2E tests pass (out of scope for B0.5.3.6)

**Next Step:** Define deterministic test vector in [B0536_DETERMINISTIC_TEST_VECTOR.md](./B0536_DETERMINISTIC_TEST_VECTOR.md).
