# Local Database Rebuild Guide (Windows)

**Purpose**: Reproducible instructions for rebuilding the Skeldir local PostgreSQL database from scratch on Windows, achieving parity with CI environment.

**Target Audience**: Developers setting up local environment or recovering from schema corruption.

**Completion Definition**: Following these steps produces a database that passes all B0.5.3.2 window idempotency tests.

---

## Prerequisites

- **PostgreSQL 15+** installed and running locally
- **psql.exe** in PATH
- **Python 3.11+** with backend dependencies installed (`pip install -r backend/requirements.txt`)
- **Alembic** installed (`pip install alembic`)
- **postgres superuser** password known

---

## Quick Start (30-Second Version)

```powershell
# 1. Bootstrap roles and database
.\scripts\bootstrap_local_db.ps1 -DropExisting

# 2. Run migrations (two-step approach)
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
alembic upgrade 202511131121
alembic upgrade skeldir_foundation@head

# 3. Verify schema
psql -U app_user -d skeldir_validation -c "\dt" | findstr "tenants attribution_recompute_jobs"
```

**Expected Result**: Both `tenants` and `attribution_recompute_jobs` tables exist.

---

## Step-by-Step Instructions

### Gate E1: Ground-Truth Diagnosis (Pre-Rebuild)

**Purpose**: Establish baseline understanding of current database state.

```powershell
# Check current database state
psql -U app_user -d skeldir_validation -c "\dt"
psql -U postgres -c "\du" | findstr "app_"

# Check current migration state
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
alembic current
alembic heads -v
```

**Expected Symptoms (if rebuild needed)**:
- Missing tables: `tenants`, `attribution_events`, `attribution_allocations`, `attribution_recompute_jobs`
- Only Celery tables present: `kombu_queue`, `worker_failed_jobs`
- Current revision: `202512151200` (celery_foundation branch only)

---

### Gate E2-E3: Bootstrap Roles and Database

**Purpose**: Create PostgreSQL roles and skeldir_validation database with CI-parity grants.

```powershell
# Run bootstrap script (idempotent - safe to run multiple times)
.\scripts\bootstrap_local_db.ps1

# With clean slate (drops existing database first)
.\scripts\bootstrap_local_db.ps1 -DropExisting
```

**Script Output**:
```
[1/7] Dropping existing skeldir_validation database (if exists)...
[2/7] Creating app_user role...
[3/7] Creating app_rw role...
[4/7] Creating app_ro role...
[5/7] Creating skeldir_validation database...
[6/7] Granting database privileges...
[7/7] Granting schema privileges...
[8/8] Defining custom GUC parameters...

Bootstrap Complete!
```

**Verification**:
```powershell
# Check roles exist
psql -U postgres -c "SELECT rolname FROM pg_roles WHERE rolname IN ('app_user','app_rw','app_ro') ORDER BY rolname;"

# Expected output:
#  rolname
# ----------
#  app_ro
#  app_rw
#  app_user
# (3 rows)
```

---

### Gate R4: Run Migrations (Two-Step Approach)

**Purpose**: Apply skeldir_foundation migrations to create core attribution schema + Celery infrastructure.

**Critical Note**: Due to Alembic multi-head topology, migrations must be run in two steps to resolve cross-branch FK dependencies.

```powershell
# Set environment variable
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"

# Step 1: Upgrade to core_schema parent (creates tenants table)
alembic upgrade 202511131121

# Step 2: Upgrade to skeldir_foundation head (creates celery + attribution tables)
alembic upgrade skeldir_foundation@head
```

**Expected Output** (Step 1):
```
INFO  [alembic.runtime.migration] Running upgrade  -> baseline, Schema Foundation Baseline
INFO  [alembic.runtime.migration] Running upgrade baseline -> 202511131115, Add core tables for B0.3 schema foundation
INFO  [alembic.runtime.migration] Running upgrade 202511131115 -> 202511131119, Add materialized views
INFO  [alembic.runtime.migration] Running upgrade 202511131119 -> 202511131120, Add RLS policies
INFO  [alembic.runtime.migration] Running upgrade 202511131120 -> 202511131121, Add GRANTs for application roles
```

**Expected Output** (Step 2):
```
INFO  [alembic.runtime.migration] Running upgrade  -> 202512120900, Create Celery broker/result tables
INFO  [alembic.runtime.migration] Running upgrade 202512120900 -> 202512131200, Create worker DLQ table
INFO  [alembic.runtime.migration] Running upgrade 202512131200 -> 202512131530, Backfill Kombu SQLA transport sequences
INFO  [alembic.runtime.migration] Running upgrade 202512131530 -> 202512131600, Align kombu_message schema
INFO  [alembic.runtime.migration] Running upgrade 202512131600 -> 202512151200, Rename DLQ to canonical
INFO  [alembic.runtime.migration] Running upgrade 202512151200 -> 202512151300, Create attribution_recompute_jobs table
INFO  [alembic.runtime.migration] Running upgrade 202511131121, 202512151300 -> 202512151400, Merge skeldir_foundation
```

**Verification**:
```powershell
# Check critical tables exist
psql -U app_user -d skeldir_validation -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename IN ('tenants', 'attribution_events', 'attribution_allocations', 'attribution_recompute_jobs', 'kombu_queue', 'worker_failed_jobs') ORDER BY tablename;"

# Expected output (6 rows):
#          tablename
# ----------------------------
#  attribution_allocations
#  attribution_events
#  attribution_recompute_jobs
#  kombu_queue
#  tenants
#  worker_failed_jobs
```

**Verify FK Constraint**:
```powershell
# Confirm attribution_recompute_jobs.tenant_id → tenants.id FK exists
psql -U app_user -d skeldir_validation -c "\d attribution_recompute_jobs" | findstr "Foreign-key"

# Expected output:
# Foreign-key constraints:
#     "attribution_recompute_jobs_tenant_id_fkey" FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
```

---

### Gate R5: Run Behavioral Validation Tests

**Purpose**: Prove window-scoped idempotency enforcement works locally.

**Status**: ⚠️ **BLOCKED** - Event loop timing issue under investigation.

**Known Issue**: Tests fail with `TimeoutError` due to async event loop handling in `_run_async()` helper function. This is a test infrastructure issue, not a schema/migration issue.

```powershell
# Set environment variables
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
$env:PYTHONPATH="C:\Users\ayewhy\II SKELDIR II\backend"

# Run B0.5.3.2 tests (currently failing with TimeoutError)
cd backend
pytest tests/test_b0532_window_idempotency.py -v

# Run B0.5.2 tests (should pass)
pytest tests/test_b052_queue_topology_and_dlq.py -v
```

**Expected Outcome** (when Gate R5 blocker resolved):
- All 4 tests in `test_b0532_window_idempotency.py` pass
- Job identity uniqueness validated
- Derived output repeatability validated

---

## Common Failure Modes

### Failure 1: `relation "tenants" does not exist`

**Symptom**:
```
psycopg2.errors.UndefinedTable: relation "tenants" does not exist
[SQL: CREATE TABLE attribution_recompute_jobs (...tenant_id uuid NOT NULL REFERENCES tenants(id)...)]
```

**Root Cause**: Attempted to run `alembic upgrade celery_foundation@head` or `alembic upgrade skeldir_foundation@head` in single step from empty database. Alembic chooses one migration path and misses the core_schema parent.

**Fix**: Use two-step migration approach (Step 1: `202511131121`, Step 2: `skeldir_foundation@head`)

---

### Failure 2: `role "app_rw" does not exist`

**Symptom**:
```
psycopg2.errors.UndefinedObject: role "app_rw" does not exist
File: alembic/versions/001_core_schema/202511131121_add_grants.py, line 71
```

**Root Cause**: Bootstrap script not run, or roles not created before migrations.

**Fix**: Run `.\scripts\bootstrap_local_db.ps1` before migrations.

---

### Failure 3: `unrecognized configuration parameter "app.current_tenant_id"`

**Symptom**:
```
ERROR: psycopg2.errors.UndefinedObject: unrecognized configuration parameter "app.current_tenant_id"
```

**Root Cause**: Custom GUC `app.current_tenant_id` not defined on database.

**Fix**: Bootstrap script (Step 8) defines this. Re-run bootstrap or manually set:
```powershell
psql -U postgres -d skeldir_validation -c "ALTER DATABASE skeldir_validation SET app.current_tenant_id = '00000000-0000-0000-0000-000000000000';"
```

---

### Failure 4: `RuntimeError: asyncio.run() cannot be called from a running event loop`

**Symptom**:
```
RuntimeError: asyncio.run() cannot be called from a running event loop
File: backend/app/tasks/attribution.py, line 401
```

**Root Cause**: Celery eager mode + pytest-asyncio create nested event loops.

**Fix**: This is the Gate R5 blocker. Requires refactoring `_run_async()` helper in `attribution.py` to properly handle nested event loops.

---

## CI/Local Parity Matrix

| Component | CI | Local (After Rebuild) | Status |
|-----------|----|-----------------------|--------|
| **PostgreSQL Version** | 15-alpine | 15+ | ✅ Parity |
| **Roles** | app_user, app_rw, app_ro | Same (via bootstrap) | ✅ Parity |
| **Database** | skeldir_validation | Same (via bootstrap) | ✅ Parity |
| **Migration Target** | skeldir_foundation@head | Same (two-step) | ✅ Parity |
| **Tables** | 6 core tables | Same | ✅ Parity |
| **Custom GUC** | app.current_tenant_id | Same | ✅ Parity |
| **Test Execution** | pytest (Ubuntu) | pytest (Windows) | ⚠️ Event loop issue |

---

## Canonical Migration Path

**Branch Label**: `skeldir_foundation`

**Upgrade Command**:
```powershell
alembic upgrade 202511131121  # Step 1: Core schema parent
alembic upgrade skeldir_foundation@head  # Step 2: Full foundation
```

**Migration Chain**:
```
Phase 1: Core Schema (baseline → 202511131121)
  - baseline: Empty initial state
  - 202511131115: Core tables (tenants, attribution_events, attribution_allocations)
  - 202511131119: Materialized views
  - 202511131120: RLS policies
  - 202511131121: Role grants

Phase 2: Celery Foundation (202512120900 → 202512151300)
  - 202512120900: Celery broker/result tables
  - 202512131200: Worker DLQ
  - 202512131530: Kombu sequences
  - 202512131600: Kombu schema alignment
  - 202512151200: DLQ canonical naming
  - 202512151300: Attribution recompute jobs (B0.5.3.2)

Phase 3: Merge (202512151400)
  - Structural merge of core_schema + celery_foundation
  - Branch label: skeldir_foundation
```

---

## Troubleshooting

### Check Current Migration State

```powershell
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
alembic current
alembic heads -v
```

### Verify Database Connectivity

```powershell
psql -U app_user -d skeldir_validation -c "SELECT version();"
```

### Reset to Clean Slate

```powershell
# WARNING: Destructive operation - drops all data
.\scripts\bootstrap_local_db.ps1 -DropExisting
$env:DATABASE_URL="postgresql://app_user:app_user@localhost:5432/skeldir_validation"
alembic upgrade 202511131121
alembic upgrade skeldir_foundation@head
```

---

## References

- **Bootstrap Script**: `scripts/bootstrap_local_db.ps1`
- **Merge Revision**: `alembic/versions/007_skeldir_foundation/202512151400_merge_skeldir_foundation.py`
- **B0.5.3.2 Tests**: `backend/tests/test_b0532_window_idempotency.py`
- **Gate R1 Analysis**: See previous Gate R1 report for migration graph ground truth
- **Gate R2 Specification**: See previous Gate R2 report for canonical upgrade target design

---

## Support

If you encounter issues not covered by this guide:
1. Check migration history: `alembic history | head -30`
2. Verify table existence: `psql -U app_user -d skeldir_validation -c "\dt"`
3. Check role grants: `psql -U app_user -d skeldir_validation -c "\dp"`
4. Review bootstrap logs for role/database creation failures

---

**Last Updated**: 2025-12-15
**Maintained By**: Skeldir Backend Team
**Version**: B0.5.3.2 Remediation Directive II
