# B0.5.7-P4 LLM Audit Persistence Evidence Pack

Scope: Prove LLM stub audit persistence under least-privilege runtime identity, with RLS isolation and DLQ failure capture.

## 1. Hypotheses validation (pre-change)

### H-P4-BLOCK-1 (runtime cannot write audit rows)
Status: CONFIRMED (pre-change).

Command:
```sql
-- app_user (runtime) attempt before grants
SELECT set_config('app.current_tenant_id', '2202a213-f896-4ff4-a21d-31c63513b436', false);
INSERT INTO llm_api_calls (
  tenant_id,
  endpoint,
  model,
  input_tokens,
  output_tokens,
  cost_cents,
  latency_ms,
  request_id
) VALUES (
  '2202a213-f896-4ff4-a21d-31c63513b436',
  'app.tasks.llm.route',
  'llm_stub',
  0,
  0,
  0,
  0,
  'req-1'
);
```

Output:
```
set_config
--------------------------------------
2202a213-f896-4ff4-a21d-31c63513b436
(1 row)

ERROR:  permission denied for table llm_api_calls
```

### H-P4-BLOCK-2 (RLS blocks inserts due to missing tenant context)
Status: PLAUSIBLE but not the primary blocker. Tenant GUC is set in:
- `backend/app/db/session.py` (`get_session` sets `app.current_tenant_id`)
- `backend/app/tasks/context.py` (`tenant_task` sets GUC in worker connection)

### H-P4-BLOCK-3 (CI does not exercise stubs under runtime identity)
Status: CONFIRMED.
- Existing CI runs `tests/test_b055_llm_worker_stubs.py` in `ci.yml`, but migrations run under app_user and DB is owned by app_user in CI, masking missing GRANTs.
- No dedicated runtime/admin split gate for LLM audit persistence existed before P4.

### H-P4-BLOCK-4 (stubs write elsewhere)
Status: REFUTED.
- `backend/app/workers/llm.py` writes to `llm_api_calls` + `llm_monthly_costs`, plus `investigations` or `budget_optimization_jobs` for specific stubs.

## 2. Static verification (repo truth)

Write sites:
- `backend/app/workers/llm.py`:
  - `_claim_api_call` inserts into `llm_api_calls` (idempotency guard).
  - `record_monthly_costs` upserts into `llm_monthly_costs`.
  - `run_investigation` inserts into `investigations`.
  - `optimize_budget` inserts into `budget_optimization_jobs`.
- `backend/app/tasks/llm.py` uses `get_session(tenant_id=...)` and `@tenant_task` for tenant GUC.

RLS migrations:
- `alembic/versions/004_llm_subsystem/202512081510_add_llm_rls_policies.py` enables and forces RLS on all LLM tables using `current_setting('app.current_tenant_id', true)::uuid`.

Grants before P4:
- No GRANTs for `llm_api_calls` et al. for app roles (confirmed by migration review).

## 3. Remediation summary (post-change)

Changes:
- New GRANT migration: `alembic/versions/007_skeldir_foundation/202601221200_b057_p4_llm_audit_grants.py`
- LLM tasks allow test-only retry bypass for failure capture: `backend/app/tasks/llm.py` (`retry_on_failure` flag).
- New integration test: `backend/tests/integration/test_b057_p4_llm_audit_persistence.py`
- New CI workflow: `.github/workflows/b057-p4-llm-audit-persistence.yml`

## 4. Runtime verification (post-change, local Dockerized Postgres)

Command (PowerShell, abbreviated):
```powershell
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@localhost:5433/skeldir_b057_p4'
$env:B057_P4_RUNTIME_DATABASE_URL='postgresql://app_user:app_user@localhost:5433/skeldir_b057_p4'
$env:B057_P4_ADMIN_DATABASE_URL='postgresql://migration_owner:migration_owner@localhost:5433/skeldir_b057_p4'
@'
<python script that seeds tenants, starts worker, runs llm route, queries counts, triggers failure, queries worker_failed_jobs>
'@ | python -
```

Output (key lines):
```
TENANT_A a0d08073-832b-4520-baa4-60dd60b78d0d
TENANT_B 23268754-a3ef-46df-b9e1-ad9be3062829
GUC_BEFORE a0d08073-832b-4520-baa4-60dd60b78d0d
COUNT_BEFORE 0
GUC_AFTER a0d08073-832b-4520-baa4-60dd60b78d0d
COUNT_AFTER 1
COUNT_CROSS_TENANT 0
FAILURE_EXCEPTION TimeoutError
DLQ_ROW {'task_name': 'app.tasks.llm.route', 'error_message': '(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class \\'asyncpg.exceptions.ForeignKeyViolationError\\'>: insert or update on table "llm_api_calls" violates foreign key constraint "llm_api_calls_tenant_id_fkey" ...', 'tenant_id': UUID('f3211e98-144f-4e8d-82e8-c2ea316fcfc1')}
```

Interpretation:
- RLS GUC is set and reflected in `current_setting`.
- `llm_api_calls` count increases for the tenant after a Celery-run stub.
- Cross-tenant count remains 0 (RLS enforced).
- Forced FK violation writes a `worker_failed_jobs` row (DLQ capture).

## 5. Integration test evidence (local)

Command:
```powershell
$env:DATABASE_URL='postgresql+asyncpg://app_user:app_user@localhost:5433/skeldir_b057_p4'
$env:B057_P4_RUNTIME_DATABASE_URL='postgresql://app_user:app_user@localhost:5433/skeldir_b057_p4'
$env:B057_P4_ADMIN_DATABASE_URL='postgresql://migration_owner:migration_owner@localhost:5433/skeldir_b057_p4'
pytest -q backend/tests/integration/test_b057_p4_llm_audit_persistence.py
```

Output:
```
2 passed in 7.36s
```

## 6. CI enforcement (P4 gate)

Workflow added:
- `.github/workflows/b057-p4-llm-audit-persistence.yml`

Status:
- CI run queued: https://github.com/Muk223/skeldir-2.0/actions/runs/21254496176
