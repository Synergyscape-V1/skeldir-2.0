# B0.5.3.3 Revenue Ledger Schema Ground Truth

**Generated**: 2025-12-16
**Database**: skeldir_validation (local PostgreSQL)
**Migration Head**: skeldir_foundation@head (revision 202512151410)
**Git Commit**: bf1ebf7 (feat(b0.5.3.2): complete window-scoped idempotency with skeldir_foundation merge)

---

## Schema Extraction Method

```bash
# Migration state query
psql -U app_user -d skeldir_validation -h localhost -p 5432 \
  -c "SELECT version_num FROM alembic_version ORDER BY version_num;"

# Table structure query
psql -U app_user -d skeldir_validation -h localhost -p 5432 \
  -c "\d+ revenue_ledger"

# Column details query
psql -U app_user -d skeldir_validation -h localhost -p 5432 \
  -c "SELECT column_name, data_type, is_nullable, column_default
      FROM information_schema.columns
      WHERE table_name = 'revenue_ledger'
      ORDER BY ordinal_position;"

# Constraint details query
psql -U app_user -d skeldir_validation -h localhost -p 5432 \
  -c "SELECT conname, contype, pg_get_constraintdef(oid) AS definition
      FROM pg_constraint
      WHERE conrelid = 'revenue_ledger'::regclass
      ORDER BY contype, conname;"
```

**Execution Date**: 2025-12-16
**Database Connection**: app_user@localhost:5432/skeldir_validation

---

## Applied Migration Head

```
version_num
--------------
 202512151410
(1 row)
```

**Migration**: `202512151410_add_allocation_model_versioning.py` (skeldir_foundation branch)
**Parent**: `202512151400_merge_skeldir_foundation.py`
**Branch Label**: `skeldir_foundation`

---

## Revenue Ledger Table Structure (Raw psql \d+ Output)

```
                                                      Table "public.revenue_ledger"
        Column         |           Type           | Collation | Nullable |      Default      | Storage | Compression | Stats target | Description
-----------------------+--------------------------+-----------+----------+-------------------+---------+-------------+--------------+-------------
 id                    | uuid                     |           | not null | gen_random_uuid() | plain   |             |              |
 tenant_id             | uuid                     |           | not null |                   | plain   |             |              |
 created_at            | timestamp with time zone |           | not null | now()             | plain   |             |              |
 updated_at            | timestamp with time zone |           | not null | now()             | plain   |             |              |
 revenue_cents         | integer                  |           | not null | 0                 | plain   |             |              |
 is_verified           | boolean                  |           | not null | false             | plain   |             |              |
 verified_at           | timestamp with time zone |           |          |                   | plain   |             |              |
 reconciliation_run_id | uuid                     |           |          |                   | plain   |             |              |
Indexes:
    "revenue_ledger_pkey" PRIMARY KEY, btree (id)
    "idx_revenue_ledger_is_verified" btree (is_verified) WHERE is_verified = true
    "idx_revenue_ledger_tenant_updated_at" btree (tenant_id, updated_at DESC)
Check constraints:
    "ck_revenue_ledger_revenue_positive" CHECK (revenue_cents >= 0)
    "revenue_ledger_revenue_cents_check" CHECK (revenue_cents >= 0)
Foreign-key constraints:
    "revenue_ledger_tenant_id_fkey" FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE
Policies (forced row security enabled):
    POLICY "tenant_isolation_policy"
      USING ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid))
      WITH CHECK ((tenant_id = (current_setting('app.current_tenant_id'::text))::uuid))
Not-null constraints:
    "revenue_ledger_id_not_null" NOT NULL "id"
    "revenue_ledger_tenant_id_not_null" NOT NULL "tenant_id"
    "revenue_ledger_created_at_not_null" NOT NULL "created_at"
    "revenue_ledger_updated_at_not_null" NOT NULL "updated_at"
    "revenue_ledger_revenue_cents_not_null" NOT NULL "revenue_cents"
    "revenue_ledger_is_verified_not_null" NOT NULL "is_verified"
Access method: heap
```

---

## Column Details (Canonical Format)

| column_name           | data_type                    | is_nullable | column_default    |
|-----------------------|------------------------------|-------------|-------------------|
| id                    | uuid                         | NO          | gen_random_uuid() |
| tenant_id             | uuid                         | NO          |                   |
| created_at            | timestamp with time zone     | NO          | now()             |
| updated_at            | timestamp with time zone     | NO          | now()             |
| revenue_cents         | integer                      | NO          | 0                 |
| is_verified           | boolean                      | NO          | false             |
| verified_at           | timestamp with time zone     | YES         |                   |
| reconciliation_run_id | uuid                         | YES         |                   |

**Total Columns**: 8

---

## Constraint Details (Canonical Format)

| conname                              | contype | definition                                                      |
|--------------------------------------|---------|-----------------------------------------------------------------|
| ck_revenue_ledger_revenue_positive   | c       | CHECK ((revenue_cents >= 0))                                    |
| revenue_ledger_revenue_cents_check   | c       | CHECK ((revenue_cents >= 0))                                    |
| revenue_ledger_tenant_id_fkey        | f       | FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE|
| revenue_ledger_created_at_not_null   | n       | NOT NULL created_at                                             |
| revenue_ledger_id_not_null           | n       | NOT NULL id                                                     |
| revenue_ledger_is_verified_not_null  | n       | NOT NULL is_verified                                            |
| revenue_ledger_revenue_cents_not_null| n       | NOT NULL revenue_cents                                          |
| revenue_ledger_tenant_id_not_null    | n       | NOT NULL tenant_id                                              |
| revenue_ledger_updated_at_not_null   | n       | NOT NULL updated_at                                             |
| revenue_ledger_pkey                  | p       | PRIMARY KEY (id)                                                |

**Note**: Constraint types: `c` = CHECK, `f` = FOREIGN KEY, `n` = NOT NULL, `p` = PRIMARY KEY

---

## CRITICAL FINDINGS: Schema Drift Analysis

### Finding 1: allocation_id Column DOES NOT EXIST

**Expected (per evidence pack)**: `allocation_id UUID NOT NULL REFERENCES attribution_allocations(id) ON DELETE CASCADE`

**Actual (ground truth)**: Column does NOT exist in current schema.

**Root Cause**: The migrations that add allocation_id (`202511131250_enhance_revenue_ledger.py` and `202511141302_ledger_allocation_id_not_null.py`) are in the `003_data_governance` branch, which has NOT been merged into `skeldir_foundation@head`.

**Impact**:
- Evidence pack's "circular dependency" claim is **invalid** for current schema
- The revenue_ledger table cannot reference attribution_allocations (no FK exists)
- Tests that insert allocation_id will **fail** with "column does not exist" error

### Finding 2: Canonical Schema Columns DO NOT EXIST

**Expected (per evidence pack)**: Additional columns for B2.2/B2.3:
- transaction_id (VARCHAR(255) NOT NULL UNIQUE)
- order_id (VARCHAR(255))
- state (VARCHAR(50) NOT NULL)
- amount_cents (INTEGER NOT NULL)
- currency (VARCHAR(3) NOT NULL)
- verification_source (VARCHAR(50) NOT NULL)
- verification_timestamp (TIMESTAMPTZ NOT NULL)
- metadata (JSONB)

**Actual (ground truth)**: NONE of these columns exist in current schema.

**Root Cause**: These columns are added by `202511151430_realign_revenue_ledger.py` (003_data_governance branch), which has NOT been applied.

**Impact**:
- Tests that insert these columns will **fail** with "column does not exist" error
- Evidence pack's reference to "canonical schema" is misleading for current DB state

### Finding 3: Minimal Core Schema is Intentional

**Current Schema Intent**: The skeldir_foundation branch implements a **minimal core schema** for B0.5.3 attribution worker validation. It includes:
- Basic revenue tracking fields (revenue_cents, is_verified, verified_at)
- Tenant isolation (tenant_id FK, RLS policy)
- Reconciliation reference (reconciliation_run_id)

**Design Decision**: The skeldir_foundation branch intentionally **excludes**:
- allocation_id FK (avoids circular dependency during B0.5.3 development)
- Canonical revenue ledger columns (deferred to B2.2/B2.3 phases)

**Alignment**: This minimal schema **correctly supports Contract B** (worker ignores ledger), since the worker never reads from or writes to revenue_ledger in B0.5.3.

---

## Migration Provenance

**Applied Migrations** (skeldir_foundation@head lineage):

1. `baseline` → Initial empty state
2. `202511131115_add_core_tables.py` → Creates revenue_ledger with 8 core columns
3. `202511131119_add_materialized_views.py` → Creates MVs
4. `202511131120_add_rls_policies.py` → Enables RLS on revenue_ledger
5. `202511131121_add_grants.py` → Grants privileges
6. `202512120900_add_celery_broker_tables.py` → Celery infrastructure
7. `202512131200_add_worker_failed_jobs.py` → Worker DLQ
8. `202512131530_add_kombu_transport_options.py` → Kombu sequences
9. `202512131600_kombu_schema_alignment.py` → Kombu alignment
10. `202512151200_rename_dlq_canonical.py` → DLQ naming
11. `202512151300_add_attribution_recompute_jobs.py` → Window idempotency table
12. `202512151400_merge_skeldir_foundation.py` → **Merge revision** (establishes branch label)
13. `202512151410_add_allocation_model_versioning.py` → **Current head** (adds model_version to allocations)

**Unapplied Migrations** (003_data_governance branch, NOT in skeldir_foundation):

- `202511131250_enhance_revenue_ledger.py` → Would add allocation_id (nullable)
- `202511141302_ledger_allocation_id_not_null.py` → Would make allocation_id NOT NULL
- `202511151430_realign_revenue_ledger.py` → Would add canonical schema columns

---

## Authoritative Schema Definition

**Source of Truth**: Migration `202511131115_add_core_tables.py` (lines 238-273)

```python
# Create revenue_ledger table
op.execute("""
    CREATE TABLE revenue_ledger (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        created_at timestamptz NOT NULL DEFAULT now(),
        updated_at timestamptz NOT NULL DEFAULT now(),
        revenue_cents INTEGER NOT NULL DEFAULT 0 CHECK (revenue_cents >= 0),
        is_verified boolean NOT NULL DEFAULT false,
        verified_at timestamptz,
        reconciliation_run_id uuid
    )
""")
```

**Indexes**:
- `idx_revenue_ledger_tenant_updated_at` on `(tenant_id, updated_at DESC)`
- `idx_revenue_ledger_is_verified` on `(is_verified) WHERE is_verified = true`

**Constraints**:
- `ck_revenue_ledger_revenue_positive` CHECK `(revenue_cents >= 0)`
- `revenue_ledger_tenant_id_fkey` FK to `tenants(id) ON DELETE CASCADE`

**RLS Policy** (added by `202511131120_add_rls_policies.py`):
- `tenant_isolation_policy`: Enforces tenant_id = current_setting('app.current_tenant_id')

---

## Validation Commands (Reproducibility)

To independently verify this ground truth, execute:

```bash
# 1. Verify migration head
psql -U app_user -d skeldir_validation -c "SELECT version_num FROM alembic_version;"

# 2. Extract full schema
pg_dump -U app_user -d skeldir_validation --schema-only --table=revenue_ledger -h localhost -p 5432

# 3. Verify column count
psql -U app_user -d skeldir_validation -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'revenue_ledger';"

# Expected output: 8
```

---

## Summary

**Ground Truth**: The skeldir_validation database at migration `202512151410` (skeldir_foundation@head) has a **minimal 8-column revenue_ledger table** without:
- allocation_id FK
- Canonical schema columns (transaction_id, order_id, state, etc.)

**Schema Drift**: The evidence pack and tests reference migrations from the 003_data_governance branch that have **not been applied** to the skeldir_foundation branch.

**Remediation Required**:
1. Update evidence pack to reflect actual 8-column schema
2. Fix tests to only insert actual columns (no allocation_id, no canonical columns)
3. Strengthen "ledger untouched" assertions with content equality

**Contract B Validation**: The minimal schema correctly supports Contract B, since the worker never touches revenue_ledger in B0.5.3.
