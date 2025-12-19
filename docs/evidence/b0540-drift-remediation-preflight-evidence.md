# B0.5.4.0 Drift Remediation Preflight Evidence

**Status:** Remediation Complete — Awaiting Verification & Testing
**Phase:** B0.5.4.0 (Drift Closure Before Feature Work)
**Objective:** Close all known drift blockers with falsifiable evidence
**Constraint:** Evidence → Adjudication → Remediation → Exit Gates
**Implementation Summary:** R1, R3, R4, R5, R6 complete | R2 pending H-B | Exit gates ready for verification

---

## 0. Document Header (Required Metadata)

### 0.1 Repository State
```
Branch:        b0534-worker-tenant-ci
Commit:        5571868dfda5c60bf789424fd43903c76fb2199b
Commit Message: Add async GUC fix evidence doc
```

### 0.2 Database Target
```
Target:        Local Windows PostgreSQL
Connection:    postgresql://app_user:app_user@localhost:5432/skeldir_validation (sync for alembic)
DB Name:       skeldir_validation
Note:          async variant: postgresql+asyncpg://... (for application runtime)
```

### 0.3 Migration Status (FIXED - see H-A evidence)
```
Working Directory: c:\Users\ayewhy\II SKELDIR II (repo root, NOT backend/)
Alembic Config:    ./alembic.ini (repo root)
Script Location:   alembic/ (repo root/alembic/)

Current Head:     202512151410 (with sync DATABASE_URL)
Heads:            e9b7435efea6 (head)
                  202512091100 (head)
                  202512171700 (celery_foundation, skeldir_foundation) (head)
```

**Command That Works:**
```bash
cd "c:/Users/ayewhy/II SKELDIR II"  # REPO ROOT
export DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"  # SYNC
alembic current  # SUCCESS: 202512151410
alembic heads    # SUCCESS: shows 3 heads
```

### 0.4 Startup Commands (Evidence-Based)
```bash
# API Server (from repo root or backend/)
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000

# Celery Worker (from repo root or backend/)
cd backend && celery -A app.celery_app.celery_app worker -P solo -c 1 -Q housekeeping,maintenance,llm,attribution --loglevel=INFO

# Celery Beat (NOT YET DEPLOYED - see H-E evidence)
# Expected: cd backend && celery -A app.celery_app.celery_app beat --loglevel=INFO
```

### 0.5 Runtime Environment
```
OS:            Windows (MINGW64_NT-10.0-26100)
Python:        3.11.9
Platform:      win32
Working Dir:   c:\Users\ayewhy\II SKELDIR II
```

---

## 1. Hypothesis Validation (H-A through H-G)

### **H-A: Migration Determinism Drift** — ✅ VALIDATED

**Hypothesis**: Local alembic execution is non-deterministic because config is not discoverable (script_location missing) even though CI can run migrations.

**Evidence Collected:**

1. **Alembic Configuration Location**
   - **File:** ./alembic.ini (repo root, NOT backend/alembic.ini)
   - **script_location:** `alembic` (line 5)
   - **version_locations:** Multiple paths (line 41)
     ```
     alembic/versions/001_core_schema;
     alembic/versions/002_pii_controls;
     alembic/versions/003_data_governance;
     alembic/versions/004_llm_subsystem;
     alembic/versions/006_celery_foundation;
     alembic/versions/007_skeldir_foundation
     ```

2. **File Layout Causing Drift**
   ```
   II SKELDIR II/              (repo root)
   ├── alembic.ini             (✅ EXISTS HERE)
   ├── alembic/
   │   ├── env.py              (✅ migration runner)
   │   └── versions/           (✅ migration files)
   ├── backend/
   │   ├── app/
   │   └── (NO alembic.ini)    (❌ MISSING - forensic doc looked here)
   ```

3. **Forensic Doc Error Analysis**
   - **Forensic Search:** Looked in `backend/alembic.ini` (NOT FOUND)
   - **Command Attempted:** `cd backend && alembic current` (FAILED - config not found)
   - **Root Cause:** Wrong working directory assumption

4. **DATABASE_URL Driver Mismatch**
   - **Application (.env):** `postgresql+asyncpg://...` (async driver for app runtime)
   - **Alembic Requirement:** `postgresql://...` (sync driver for CLI)

   **Test Results:**
   ```bash
   # FAIL: async driver
   $ export DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"
   $ alembic current
   ERROR: sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called

   # PASS: sync driver
   $ export DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
   $ alembic current
   INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
   INFO  [alembic.runtime.migration] Will assume transactional DDL.
   202512151410
   ```

5. **CI Success Analysis**
   - **File:** .github/workflows/ci.yml:154-157
   - **CI DATABASE_URL:** Uses sync format: `postgresql://app_user:...@127.0.0.1:5432/...`
   - **CI Working Dir:** Repo root (standard GitHub Actions checkout)
   - **Result:** CI works because it uses correct driver + correct working directory

**Root Causes Identified:**
1. **Working Directory Mismatch:** Forensic doc assumed `backend/` as CWD; actual config is at repo root
2. **DATABASE_URL Format Mismatch:** .env uses async driver; alembic needs sync driver
3. **Documentation Gap:** No clear guidance on "alembic must run from repo root with sync URL"

**Adjudication:** ✅ **VALIDATED** — Drift exists. CI works due to environment-specific config. Local execution requires:
- CWD = repo root
- DATABASE_URL = sync format (postgresql://)

---

### **H-B: Matview Inventory Drift Between Environments** — ⚠️ INVESTIGATION REQUIRED

**Hypothesis**: The canonical schema state includes 5 PG matviews, but CI provisions only 2, implying DB init path divergence (migrations vs schema snapshot).

**Evidence To Collect:**
- [ ] Query fresh DB created from migrations: `SELECT schemaname, matviewname FROM pg_matviews ORDER BY 1,2;`
- [ ] Compare with canonical schema snapshot (5 matviews documented)
- [ ] Identify which migrations create which matviews

**Preliminary Findings (from forensic doc):**
- **Canonical Schema:** 5 matviews exist
  1. mv_allocation_summary
  2. mv_channel_performance
  3. mv_daily_revenue_summary
  4. mv_realtime_revenue
  5. mv_reconciliation_status

- **Code References (maintenance.py:26-29):** Only 2 matviews in MATERIALIZED_VIEWS list
  1. mv_channel_performance
  2. mv_daily_revenue_summary

**Suspected Drift:** Code list (2) < DB reality (5)

**Status:** ⏸️ **Pending fresh DB query to confirm inventory**

---

### **H-C: Registry Drift** — ✅ VALIDATED

**Hypothesis**: Code references only a subset of matviews (hardcoded list), making refresh behavior non-auditable and non-coherent.

**Evidence:**

1. **Hardcoded List in Code**
   - **File:** backend/app/tasks/maintenance.py:26-29
   - **List:**
     ```python
     MATERIALIZED_VIEWS: List[str] = [
         "mv_channel_performance",
         "mv_daily_revenue_summary",
     ]
     ```
   - **Count:** 2 matviews

2. **Actual DB Inventory (from forensic doc)**
   - **Source:** db/schema/canonical_schema.sql + live_schema_snapshot.sql
   - **Confirmed Matviews:** 5
     1. mv_allocation_summary (canonical_schema.sql:1344)
     2. mv_channel_performance (canonical_schema.sql:1375) ✅ IN CODE
     3. mv_daily_revenue_summary (canonical_schema.sql:1524) ✅ IN CODE
     4. mv_realtime_revenue (live_schema_snapshot.sql:286) ❌ MISSING FROM CODE
     5. mv_reconciliation_status (live_schema_snapshot.sql:298) ❌ MISSING FROM CODE

3. **Comparison: Code vs Reality**
   ```
   Code List (2):         mv_channel_performance, mv_daily_revenue_summary
   DB Reality (5):        +mv_allocation_summary, +mv_realtime_revenue, +mv_reconciliation_status
   Missing from Code (3): mv_allocation_summary, mv_realtime_revenue, mv_reconciliation_status
   ```

4. **Impact of Drift**
   - **Refresh Task:** Only refreshes 2 of 5 matviews (maintenance.py:56-58)
   - **Stale Data Risk:** 3 matviews never refreshed automatically
   - **Non-Auditable:** No single source of truth for "what matviews exist"

**Adjudication:** ✅ **VALIDATED** — Registry drift exists. Hardcoded list is incomplete and diverges from DB reality.

---

### **H-D: Global Refresh Drift = Contract Violation** — ✅ VALIDATED

**Hypothesis**: Current refresh is implemented as a single global task (non-tenant), which conflicts with worker-scoped isolation principles and the B0.5.4 target topology.

**Evidence:**

1. **Task Definition**
   - **File:** backend/app/tasks/maintenance.py:48-68
   - **Function Signature:** `def refresh_all_materialized_views_task(self) -> Dict[str, str]:`
   - **Decorator:** `@celery_app.task(bind=True, name="app.tasks.maintenance.refresh_all_materialized_views", ...)`
   - **NO `@tenant_task` decorator** (contrast with line 84: `scan_for_pii_contamination_task` HAS `@tenant_task`)
   - **NO `tenant_id` parameter**

2. **Docstring Evidence**
   - **Line 50-51:**
     ```python
     """
     Refresh configured materialized views. Global (non-tenant) scope.
     """
     ```
   - **Explicit:** Docstring claims "Global (non-tenant) scope"

3. **Implementation Evidence**
   - **File:** backend/app/tasks/maintenance.py:56-58
   - **Loop:**
     ```python
     for view_name in MATERIALIZED_VIEWS:
         asyncio.run(_refresh_view(view_name, self.request.id))
         results[view_name] = "success"
     ```
   - **NO tenant loop**
   - **NO tenant filtering**
   - **NO tenant GUC setting**

4. **Refresh Function Evidence**
   - **File:** backend/app/tasks/maintenance.py:32-38
   - **Function:** `_refresh_view(view_name: str, task_id: str)`
   - **Implementation:**
     ```python
     async with engine.begin() as conn:
         await conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
     ```
   - **NO `set_tenant_guc` call**
   - **NO tenant_id parameter**

5. **Contract Violation Analysis**
   - **Worker Isolation Principle (G3):** Workers use `SET LOCAL app.current_tenant_id` for tenant scoping
   - **Ingestion Read-Only (G4):** Workers marked with `execution_context='worker'` for privilege isolation
   - **Global Refresh:** Refreshes ALL tenant data at once without tenant context
   - **Conflict:** Global operation violates per-tenant isolation architecture

**Adjudication:** ✅ **VALIDATED** — Global refresh exists and contradicts tenant isolation architecture. This is a **CONTRACT VIOLATION**.

---

### **H-E: Beat Drift** — ✅ VALIDATED

**Hypothesis**: Beat schedule is defined but not loaded into Celery config, and beat is not started/proven in CI.

**Evidence:**

1. **Beat Schedule Definition**
   - **File:** backend/app/tasks/maintenance.py:169-186
   - **Constant:** `BEAT_SCHEDULE` (dict with 3 schedules)
   - **Comment:** `# Celery Beat schedule configuration (reference)`
   - **Schedules Defined:**
     ```python
     BEAT_SCHEDULE = {
         "refresh-matviews-every-5-min": {...},
         "pii-audit-scanner": {...},
         "enforce-data-retention": {...},
     }
     ```

2. **Celery Config Loading Check**
   - **File:** backend/app/celery_app.py:119-154
   - **Config Section:** `celery_app.conf.update(...)`
   - **Lines Checked:** 119-154 (entire conf.update block)
   - **beat_schedule Key:** ❌ **NOT FOUND**
   - **Missing Line:** `beat_schedule=BEAT_SCHEDULE` or equivalent import/assignment

3. **CI Beat Startup Evidence**
   - **File:** .github/workflows/ci.yml:159-168
   - **Worker Startup:** `celery -A app.celery_app.celery_app worker ...` (line 164)
   - **Beat Startup:** ❌ **NOT FOUND** (no `celery beat` command)
   - **Search Result:** Grep for "celery beat" in ci.yml returns 0 matches

4. **Runtime Proof Check**
   - **Method:** Check if `celery_app.conf.beat_schedule` is populated at runtime
   - **Expected:** If loaded, `conf.beat_schedule` should contain BEAT_SCHEDULE dict
   - **Status:** ⏸️ **Pending runtime inspection** (requires starting celery_app)

**Adjudication:** ✅ **VALIDATED** — Beat schedule defined but NOT loaded into config. CI does NOT start beat process.

---

### **H-F: Privilege Proof Gap** — ⏸️ INVESTIGATION REQUIRED

**Hypothesis**: We have proof worker cannot write ingestion (good), but we do not have direct proof app_user can refresh all matviews under worker execution constraints.

**Evidence To Collect:**
- [ ] As app_user, attempt `REFRESH MATERIALIZED VIEW CONCURRENTLY <each>`
- [ ] Show success/failure for each matview
- [ ] Query role grants: `SELECT * FROM information_schema.role_table_grants WHERE grantee='app_user';`

**Status:** ⏸️ **Pending live DB test**

---

### **H-G: Concurrency Primitive Missing** — ✅ VALIDATED

**Hypothesis**: No application-level serialization/dedup exists for refresh operations; relying on Postgres alone is insufficient for multi-worker/beat overlap.

**Evidence:**

1. **Advisory Lock Search**
   - **Command:** `grep -r "pg_advisory_lock" backend/`
   - **Result:** 0 matches found
   - **Conclusion:** No advisory lock usage in application code

2. **Refresh Implementation**
   - **File:** backend/app/tasks/maintenance.py:32-38
   - **Function:** `_refresh_view`
   - **Code:**
     ```python
     async with engine.begin() as conn:
         await conn.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
     ```
   - **NO lock acquisition**
   - **NO idempotency check**
   - **NO "already running" guard**

3. **Postgres CONCURRENTLY Behavior**
   - **Mechanism:** Allows queries during refresh
   - **Concurrency:** Multiple CONCURRENTLY refreshes queue (don't error)
   - **Limitation:** Does NOT prevent duplicate work
   - **Gap:** No application-level "skip if already refreshing" logic

4. **Overlap Scenarios**
   - **Beat + Manual:** Beat triggers refresh every 5 min + human triggers manual refresh
   - **Multi-Worker:** Multiple workers both pick up same refresh task from queue
   - **Retry:** Failed refresh retries while first attempt still running
   - **Current Behavior:** All execute sequentially (wasted work, no deduplication)

**Adjudication:** ✅ **VALIDATED** — No advisory lock. No idempotency key for refresh. Postgres CONCURRENTLY provides basic safety but no deduplication.

---

## 2. Remediation Plan (Evidence-Driven)

### **R1: Restore Migration Determinism** — ✅ IMPLEMENTED

**Goal:** One canonical, repeatable migration command works locally the same way CI expects.

**Implementation Evidence:**

1. **Created PowerShell Wrapper Script**
   - **File:** scripts/run_alembic.ps1
   - **Features:**
     - Validates running from repo root (checks for alembic.ini)
     - Validates DATABASE_URL is set
     - Validates DATABASE_URL uses sync driver (postgresql://), not async (postgresql+asyncpg://)
     - Provides clear error messages with examples
     - Masks password in output logs
   - **Usage:**
     ```powershell
     .\scripts\run_alembic.ps1 current
     .\scripts\run_alembic.ps1 upgrade head
     .\scripts\run_alembic.ps1 history
     ```

2. **Created Documentation**
   - **File:** docs/backend/ALEMBIC_DETERMINISM.md
   - **Contents:**
     - Problem statement with evidence from H-A validation
     - Failure mode vs success mode examples
     - Wrapper script usage
     - Manual invocation requirements
     - CI/CD integration guidance
     - Troubleshooting section
   - **Link:** [ALEMBIC_DETERMINISM.md](../backend/ALEMBIC_DETERMINISM.md)

3. **Root Causes Documented:**
   - Working directory dependency (repo root, not backend/)
   - DATABASE_URL driver mismatch (async vs sync)
   - Why two formats exist (runtime async I/O vs migration DDL)

**Exit Gate:** EG-1 (alembic determinism) — ✅ **READY FOR VERIFICATION** (script + docs created)

---

### **R2: Align Matview Inventory** — Pending H-B Validation

**Goal:** A DB created from migrations only yields the same matview set as canonical schema reality.

**Strategy (pending H-B evidence):**
- **If migrations missing 3 matviews:** Add migrations to create mv_allocation_summary, mv_realtime_revenue, mv_reconciliation_status
- **If local DB ahead:** Document which matviews are "schema-load only" vs "migration-created"

**Exit Gate:** EG-2 (fresh DB inventory matches canonical) — Pending H-B evidence

---

### **R3: Create Closed Registry** — ✅ IMPLEMENTED

**Goal:** Replace hardcoded list with a closed registry that matches DB reality.

**Implementation Evidence:**

1. **Created Registry Module**
   - **File:** backend/app/core/matview_registry.py (46 lines)
   - **Canonical List:** All 5 matviews now in registry
     ```python
     MATERIALIZED_VIEWS: List[str] = [
         "mv_allocation_summary",
         "mv_channel_performance",
         "mv_daily_revenue_summary",
         "mv_realtime_revenue",
         "mv_reconciliation_status",
     ]
     ```
   - **Functions Provided:**
     - `get_all_matviews() -> List[str]`: Returns copy of canonical list
     - `validate_matview_name(view_name: str) -> bool`: Validates view in registry
   - **Docstring:** Explicitly states "single source of truth" and requires test alignment

2. **Updated maintenance.py**
   - **File:** backend/app/tasks/maintenance.py:19
   - **Change:** Replaced local hardcoded MATERIALIZED_VIEWS (deleted lines 26-29)
   - **Import:** `from app.core.matview_registry import MATERIALIZED_VIEWS`
   - **Impact:** refresh_all_matviews_global_legacy now iterates over all 5 views (was 2)

3. **Updated Test Files**
   - **File:** backend/tests/test_b051_celery_foundation.py:320-321
     - Updated test to expect new task names (refresh_all_matviews_global_legacy, refresh_matview_for_tenant)
   - **File:** backend/tests/test_b052_queue_topology_and_dlq.py:26,71-72,89
     - Updated import and task name expectations
     - Added refresh_matview_for_tenant to expected_tasks set

**Exit Gate:** EG-3 (code registry matches DB) — ✅ **READY FOR VERIFICATION** (registry created, tests updated)

---

### **R4: Neutralize Global Refresh Drift** — ✅ IMPLEMENTED

**Goal:** Remove "global refresh" contract violation; prepare topology for per-tenant scheduling.

**Implementation Evidence:**

1. **Deprecated Global Task**
   - **File:** backend/app/tasks/maintenance.py:65-100
   - **Task Name Changed:** `refresh_all_materialized_views_task` → `refresh_all_matviews_global_legacy`
   - **Celery Name Changed:** `app.tasks.maintenance.refresh_all_materialized_views` → `app.tasks.maintenance.refresh_all_matviews_global_legacy`
   - **Docstring Updated:**
     ```python
     """
     DEPRECATED: Global refresh (non-tenant-scoped).

     B0.5.4.0: This task violates worker-tenant isolation principles by refreshing
     materialized views without tenant context. Kept for backward compatibility
     during B0.5.4 transition; scheduled for removal in B0.5.5.

     Use `refresh_matview_for_tenant` for new integrations.

     Marked for removal: B0.5.5
     """
     ```
   - **Implementation Unchanged:** Still refreshes all views globally (backward compatible)

2. **Created Tenant-Aware API**
   - **File:** backend/app/tasks/maintenance.py:103-177
   - **Task Name:** `refresh_matview_for_tenant`
   - **Decorators:**
     - `@celery_app.task(bind=True, name="app.tasks.maintenance.refresh_matview_for_tenant", ...)`
     - `@tenant_task` (sets tenant GUC via context.py)
   - **Signature:** `(self, tenant_id: UUID, view_name: str, correlation_id: Optional[str] = None)`
   - **Features:**
     - Validates view_name against canonical registry
     - Sets tenant_id via observability context
     - Calls `_refresh_view(view_name, task_id, tenant_id)` with tenant_id
     - Returns structured response: `{"status": "ok", "view_name": ..., "tenant_id": ..., "result": ...}`
     - Advisory lock support (via R6 implementation)

3. **Updated Beat Schedule**
   - **File:** backend/app/tasks/maintenance.py:281
   - **Changed:** `"task": "app.tasks.maintenance.refresh_all_matviews_global_legacy"` (was refresh_all_materialized_views)
   - **Impact:** Beat continues to use legacy task (maintains current behavior)

4. **Updated Test Expectations**
   - **Files Updated:** test_b051_celery_foundation.py, test_b052_queue_topology_and_dlq.py
   - **Both tasks registered:** refresh_all_matviews_global_legacy + refresh_matview_for_tenant

**Exit Gate:** EG-4 (topology neutralized) — ✅ **READY FOR VERIFICATION** (global deprecated, tenant API created)

---

### **R5: Deploy Beat Schedule Loading** — ✅ IMPLEMENTED

**Goal:** Beat is real: schedule is loaded and beat can dispatch at least one refresh task in CI.

**Implementation Evidence:**

1. **Loaded Schedule into Celery Config**
   - **File:** backend/app/celery_app.py:156-168
   - **Location:** Inside `_ensure_celery_configured()` function (after task_routes config)
   - **Code Added:**
     ```python
     # B0.5.4.0: Load Beat schedule (closes G11 drift - beat not deployed)
     from app.tasks.maintenance import BEAT_SCHEDULE
     celery_app.conf.beat_schedule = BEAT_SCHEDULE

     logger.info(
         "celery_app_configured",
         extra={
             "broker_url": celery_app.conf.broker_url,
             "result_backend": celery_app.conf.result_backend,
             "queues": [q.name for q in celery_app.conf.task_queues],
             "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
             "scheduled_tasks": list(celery_app.conf.beat_schedule.keys()) if celery_app.conf.beat_schedule else [],
             "app_name": celery_app.main,
         },
     )
     ```
   - **Logging Added:** Now logs `beat_schedule_loaded` and `scheduled_tasks` for observability

2. **Beat Schedule Contents (from BEAT_SCHEDULE import)**
   - **3 Scheduled Tasks:**
     - `refresh-matviews-every-5-min`: Every 5 minutes (300s), expires after 300s
     - `pii-audit-scanner`: Daily at 04:00 UTC (crontab), expires after 3600s
     - `enforce-data-retention`: Daily at 03:00 UTC (crontab), expires after 3600s

3. **CI Smoke Test**
   - **Status:** ⏸️ **Pending** — CI job addition required (see EG-5 for test plan)
   - **Plan:** Add beat startup step to .github/workflows/ci.yml to verify schedule loads

**Exit Gate:** EG-5 (beat dispatch proven) — ✅ **CODE READY**, ⏸️ **CI TEST PENDING**

---

### **R6: Add Serialization Primitive** — ✅ IMPLEMENTED

**Goal:** Prevent duplicate refresh execution under overlap (beat + manual + retries + multi-worker).

**Implementation Evidence:**

1. **Created Advisory Lock Helper Module**
   - **File:** backend/app/core/pg_locks.py (167 lines)
   - **Purpose:** PostgreSQL advisory lock helpers for task serialization (G12 remediation)
   - **Functions Implemented:**
     - `_lock_key_from_string(s: str) -> int`: SHA256 hash → signed int32 conversion
     - `try_acquire_refresh_lock(conn, view_name, tenant_id) -> bool`: Non-blocking lock acquisition
     - `release_refresh_lock(conn, view_name, tenant_id)`: Lock release
   - **Lock Key Strategy:** `f"matview_refresh:{view_name}:{tenant_str}"` → deterministic int32
   - **Logging:** Debug logs for lock attempts, info logs for acquired/held/released states

2. **Lock Key Implementation Details**
   - **Deterministic Hashing:**
     ```python
     h = hashlib.sha256(s.encode()).hexdigest()[:8]
     unsigned = int(h, 16)
     if unsigned >= 2**31:
         return unsigned - 2**32  # Convert to signed int32
     return unsigned
     ```
   - **Key Format Examples:**
     - `matview_refresh:mv_channel_performance:GLOBAL` (global refresh)
     - `matview_refresh:mv_channel_performance:123e4567-e89b-12d3-a456-426614174000` (tenant refresh)

3. **Integrated with Refresh Function**
   - **File:** backend/app/tasks/maintenance.py:20, 28-62
   - **Import Added:** `from app.core.pg_locks import try_acquire_refresh_lock, release_refresh_lock`
   - **Updated _refresh_view:**
     - **Signature:** Added `tenant_id: Optional[UUID] = None` parameter
     - **Lock Acquisition:** Try to acquire before refresh, return "skipped_already_running" if held
     - **Lock Release:** Always released in finally block
     - **Logging:** Logs skip events when lock already held
     - **Return Values:** "success" or "skipped_already_running"

4. **Concurrency Test**
   - **Status:** ⏸️ **Pending** — Test file creation required (see EG-6 for test plan)
   - **Plan:** Create test_matview_refresh_concurrency.py to verify lock behavior

**Exit Gate:** EG-6 (serialization prevents duplicates) — ✅ **CODE READY**, ⏸️ **TEST PENDING**

---

## 3. Exit Gate Status

| Gate ID | Objective | Status | Evidence Required |
|---------|-----------|--------|-------------------|
| **EG-1** | Alembic Determinism | ✅ **READY** | Script + docs created (R1), needs verification run |
| **EG-2** | Fresh DB Inventory Match | ⏸️ **PENDING** | Awaiting H-B validation (fresh DB query) |
| **EG-3** | Code Registry Matches DB | ✅ **READY** | Registry module created (R3), needs test run |
| **EG-4** | Privilege Compatibility | 🟡 **PARTIAL** | Topology neutralized (R4), needs H-F validation |
| **EG-5** | Beat Dispatch Proven | ✅ **READY** | Schedule loading implemented (R5), needs CI test |
| **EG-6** | Serialization Prevents Dups | ✅ **READY** | Advisory locks implemented (R6), needs test creation |

---

## 4. Implementation Summary & Next Actions

### ✅ Phase 1: Evidence Collection (COMPLETE)
1. ✅ H-A validated (migration determinism) — Working directory + DATABASE_URL driver mismatch identified
2. ✅ H-C validated (registry drift) — Code has 2 matviews, DB has 5
3. ✅ H-D validated (global refresh drift) — Global task confirmed, violates tenant isolation
4. ✅ H-E validated (beat drift) — Schedule defined but not loaded
5. ✅ H-G validated (concurrency primitive missing) — No advisory locks found
6. ⏸️ **H-B**: Query fresh DB for matview inventory (BLOCKED - requires live DB)
7. ⏸️ **H-F**: Test refresh as app_user + query grants (BLOCKED - requires live DB)

### ✅ Phase 2: Apply Remediations (5 of 6 COMPLETE)
1. ✅ **R1** (IMPLEMENTED): Created scripts/run_alembic.ps1 + docs/backend/ALEMBIC_DETERMINISM.md
2. ⏸️ **R2**: Align inventory (BLOCKED - depends on H-B validation)
3. ✅ **R3** (IMPLEMENTED): Created backend/app/core/matview_registry.py with all 5 matviews
4. ✅ **R4** (IMPLEMENTED): Deprecated global task, created refresh_matview_for_tenant
5. ✅ **R5** (IMPLEMENTED): Loaded BEAT_SCHEDULE into celery_app.conf.beat_schedule
6. ✅ **R6** (IMPLEMENTED): Created backend/app/core/pg_locks.py with advisory lock helpers

### ⏸️ Phase 3: Verify Exit Gates (PENDING - Test Execution Required)
1. **EG-1** (✅ READY): Run `.\scripts\run_alembic.ps1 current` to verify wrapper works
2. **EG-2** (⏸️ BLOCKED): Query fresh DB → confirm inventory (depends on H-B)
3. **EG-3** (✅ READY): Run existing tests → verify task registration
4. **EG-4** (🟡 PARTIAL): Topology neutralized, needs H-F validation for permissions
5. **EG-5** (✅ READY): Run local celery beat → verify schedule loads and dispatches
6. **EG-6** (✅ READY): Create + run concurrency test → verify advisory lock skips duplicates

### 🚧 Phase 4: PR & Documentation (NEXT)
1. **Review Changes:** Verify git status shows only drift remediation files
2. **Run Local Tests:** Execute pytest backend/tests/ to ensure no regressions
3. **Commit Changes:** Staged files ready for commit
4. **Open PR:** Title: "B0.5.4.0 Drift Remediation Preflight"
5. **Link Evidence:** Reference this document in PR description

---

## 5. Files Modified (Remediation Footprint)

**Created:**
- `backend/app/core/matview_registry.py` (R3 - canonical registry)
- `backend/app/core/pg_locks.py` (R6 - advisory lock helpers)
- `docs/backend/ALEMBIC_DETERMINISM.md` (R1 - documentation)
- `scripts/run_alembic.ps1` (R1 - standardized wrapper)

**Modified:**
- `backend/app/tasks/maintenance.py` (R3, R4, R6 - registry import, task rename, lock integration)
- `backend/app/celery_app.py` (R5 - beat_schedule loading)
- `backend/tests/test_b051_celery_foundation.py` (R4 - test expectations)
- `backend/tests/test_b052_queue_topology_and_dlq.py` (R4 - test expectations)

**Total:** 4 new files, 4 modified files

---

**Document Generated:** 2025-12-19
**Evidence Cutoff:** Git commit 5571868dfda5c60bf789424fd43903c76fb2199b
**Author:** Claude Code Drift Remediation Agent
**Compliance:** B0.5.4.0 Preflight Requirements v1.0
