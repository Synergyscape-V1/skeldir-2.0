# B0.5.4.2 Refresh Executor Summary (Draft)

Candidate Completion SHA: PENDING
CI_RUN_URL: PENDING
R7_RUN_URL: PENDING

## Pre-Remediation Hypothesis Verdicts

H-B0542-REM-1 (Session locks used for refresh) — VALIDATED
- Evidence: `B0542_CONTEXT_EVIDENCE_PACK_local_windows.md:55-113`.
- Remediation: replace session locks with `pg_try_advisory_xact_lock` and remove manual unlock.

H-B0542-REM-2 (Int32 lock key collision risk) — VALIDATED
- Evidence: `B0542_CONTEXT_EVIDENCE_PACK_local_windows.md:55-65`.
- Remediation: adopt two-int xact lock keys derived from view_name and tenant_id independently.

H-B0542-REM-3 (No unified executor path) — VALIDATED
- Evidence: `B0542_CONTEXT_EVIDENCE_PACK_local_windows.md:83-99`.
- Remediation: introduce a single executor module and route maintenance tasks through it.

H-B0542-REM-4 (No standardized RefreshResult schema) — VALIDATED
- Evidence: `B0542_CONTEXT_EVIDENCE_PACK_local_windows.md:136-144`.
- Remediation: implement a unified RefreshResult schema with structured outcome fields.

## Files Changed

- `backend/app/core/pg_locks.py`
- `backend/app/matviews/executor.py`
- `backend/app/tasks/maintenance.py`
- `backend/tests/test_b0542_refresh_executor.py`
- `backend/test_eg6_serialization.py`
- `scripts/ci/zero_drift_v3_2.sh`
- `.github/workflows/b0542-refresh-executor.yml`
- `docs/backend/B0542_REFRESH_EXECUTOR_SUMMARY.md`

## Executor API

- `backend/app/matviews/executor.py`:
  - `refresh_single(view_name, tenant_id, correlation_id) -> RefreshResult`
  - `refresh_single_async(view_name, tenant_id, correlation_id) -> RefreshResult`
  - `refresh_all_for_tenant(tenant_id, correlation_id) -> list[RefreshResult]`
  - `refresh_all_for_tenant_async(tenant_id, correlation_id) -> list[RefreshResult]`

## Locking Semantics

- Xact-scoped locks via `pg_try_advisory_xact_lock(key1, key2)` (no manual unlock).
- Lock keys are two int32 values derived independently from `view_name` and `tenant_id|GLOBAL`.
- Lock acquisition is non-blocking; second caller returns `SKIPPED_LOCK_HELD`.

## Evidence Checklist (GATE-2A/2B/2C)

- GATE-2A: `backend/tests/test_b0542_refresh_executor.py::test_b0542_gate_2a_serialization_lock`
- GATE-2B: `backend/tests/test_b0542_refresh_executor.py::test_b0542_gate_2b_lock_key_correctness`
- GATE-2C: `backend/tests/test_b0542_refresh_executor.py::test_b0542_gate_2c_executor_api_and_order`
