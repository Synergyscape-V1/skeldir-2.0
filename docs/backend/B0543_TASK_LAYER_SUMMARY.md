# B0543 Task Layer Summary (Matview Task Wrapper)

## Candidate Completion SHA (C)

edd965bb9c3801da44f7f53fd31551c80626a848

## CI Evidence

- CI_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20681544928
- CI_JOB_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20681544928/job/59376449091
- R7_RUN_URL: not run for edd965bb9c3801da44f7f53fd31551c80626a848

## Pre-Remediation Hypothesis Verdict

- H-B0543-REM-1 (Outcome strategy incomplete): VALIDATED
  - Evidence: `RefreshOutcome` only defines SUCCESS/SKIPPED_LOCK_HELD/FAILED and no task-level strategy mapping exists in a dedicated wrapper (see `backend/app/matviews/executor.py:30-166`). Current maintenance task only raises on FAILED (`backend/app/tasks/maintenance.py:136-168`) and has no extensible mapping.
- H-B0543-REM-2 (DLQ schema incompatibility / correlation_id loss): REFUTED
  - Evidence: DLQ schema includes `correlation_id` and JSONB payload columns (`alembic/versions/006_celery_foundation/202512131200_worker_dlq.py:50-74`), and the canonical table is renamed to `worker_failed_jobs` (`alembic/versions/006_celery_foundation/202512151200_rename_dlq_to_canonical.py:33-65`). DLQ insert writes `task_kwargs` and `correlation_id` (`backend/app/celery_app.py:542-570`).
- H-B0543-REM-3 (DLQ suppression via non-raising semantics): VALIDATED
  - Evidence: DLQ persistence is only in `@signals.task_failure` (`backend/app/celery_app.py:345-589`); tasks must raise to reach DLQ.
- H-B0543-REM-4 (NotRegistered risk): VALIDATED
  - Evidence: task discovery uses explicit `include=[...]` without a matview module (`backend/app/celery_app.py:163-170`).
- H-B0543-REM-5 (Metrics not emitted in worker context): VALIDATED
  - Evidence: metrics are defined but no matview-specific counters/histograms exist in `backend/app/observability/metrics.py:1-53`, and task wrapper does not yet emit them.
- H-B0543-REM-6 (R6 governance regression): REFUTED (baseline fuses exist)
  - Evidence: global R6 fuses are configured in `backend/app/celery_app.py:146-154` with defaults in `backend/app/core/config.py:62-101`.

## Files Changed (Commit C)

- `backend/app/tasks/matviews.py`
- `backend/app/observability/metrics.py`
- `backend/app/celery_app.py`
- `backend/tests/test_b051_celery_foundation.py`
- `backend/tests/test_b052_queue_topology_and_dlq.py`
- `backend/tests/test_b0543_matview_task_layer.py`
- `docs/backend/B0543_TASK_LAYER_SUMMARY.md`
- `scripts/r2/static_audit_allowlist.json` (R2 static audit allowlist for R5 probe cleanup)
- `.github/workflows/b0543-matview-task-layer.yml`

## Wrapper API + Outcome Strategy

- Task wrappers (Celery-facing, executor-only):
  - `app.tasks.matviews.refresh_single`
  - `app.tasks.matviews.refresh_all_for_tenant`
- Strategy mapping:
  - `RefreshOutcome.SUCCESS` -> `TaskOutcomeStrategy.SUCCESS`
  - `RefreshOutcome.SKIPPED_LOCK_HELD` -> `TaskOutcomeStrategy.SILENT_SKIP`
  - `RefreshOutcome.FAILED` -> `TaskOutcomeStrategy.DEAD_LETTER`
  - Unmapped outcomes raise `UnmappedOutcomeError` (fail-fast).

## Metrics & Observability

- New metrics in `backend/app/observability/metrics.py`:
  - `matview_refresh_total{view_name,outcome,strategy}`
  - `matview_refresh_duration_seconds{view_name,outcome}`
  - `matview_refresh_failures_total{view_name,error_type}`
- Task logs include `view_name`, `tenant_id`, `correlation_id`, `schedule_class`, `strategy`, and executor `result`.

Local verification (metrics):

```
$env:DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"; pytest backend/tests/test_b0543_matview_task_layer.py -q
...
assert b"matview_refresh_total" in metrics_payload
assert b"matview_refresh_duration_seconds" in metrics_payload
```

Captured output (metrics excerpt):

```
METRICS_EXCERPT_START
matview_refresh_total{outcome="SUCCESS",strategy="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_created{outcome="SUCCESS",strategy="SUCCESS",view_name="mv_allocation_summary"} 1.7673034559294152e+09
matview_refresh_duration_seconds_bucket{le="0.01",outcome="SUCCESS",view_name="mv_allocation_summary"} 0.0
matview_refresh_duration_seconds_bucket{le="0.05",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="0.1",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="0.25",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="0.5",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="1.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="2.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="5.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="10.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="30.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="60.0",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_bucket{le="+Inf",outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_count{outcome="SUCCESS",view_name="mv_allocation_summary"} 1.0
matview_refresh_duration_seconds_sum{outcome="SUCCESS",view_name="mv_allocation_summary"} 0.025
matview_refresh_duration_seconds_created{outcome="SUCCESS",view_name="mv_allocation_summary"} 1.7673034559294152e+09
METRICS_EXCERPT_END
```

## DLQ Compatibility

- Schema supports correlation/payload: `alembic/versions/006_celery_foundation/202512131200_worker_dlq.py:50-74`
- Canonical table rename: `alembic/versions/006_celery_foundation/202512151200_rename_dlq_to_canonical.py:33-65`
- DLQ insert persists `task_kwargs` and `correlation_id`: `backend/app/celery_app.py:542-570`

Local verification (DLQ correlation persistence):

```
$env:DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"; pytest backend/tests/test_b0543_matview_task_layer.py -q
...
SELECT correlation_id, task_kwargs FROM worker_failed_jobs WHERE task_name = 'app.tasks.matviews.refresh_single' ...
assert str(row[0]) == correlation_id
assert str(row[1].get("correlation_id")) == correlation_id
```

Captured output (DLQ proof):

```
DLQ_PROOF_START
(UUID('7a6ea2b7-5641-4393-a3c5-81c8d09a3e0e'), {'tenant_id': '96d9f9aa-1b2b-46fd-924e-329d0dbc5c05', 'view_name': 'mv_allocation_summary', 'correlation_id': '7a6ea2b7-5641-4393-a3c5-81c8d09a3e0e'})
DLQ_PROOF_END
```

## Evidence Checklist (Exit Gates)

- EG-B0543-1 Registration Gate: LOCALLY VERIFIED
  - Evidence: `backend/app/celery_app.py:163-185`, `backend/tests/test_b051_celery_foundation.py:317-326`, `backend/tests/test_b052_queue_topology_and_dlq.py:64-83`.
- EG-B0543-2 Delegation Gate: LOCALLY VERIFIED
  - Evidence: `backend/app/tasks/matviews.py` delegates to executor only; no refresh SQL in tasks.
- EG-B0543-3 Strategy Gate: LOCALLY VERIFIED
  - Evidence: `_OUTCOME_STRATEGY_MAP` + `UnmappedOutcomeError` in `backend/app/tasks/matviews.py:36-74`; tests in `backend/tests/test_b0543_matview_task_layer.py:34-60`.
- EG-B0543-4 DLQ Schema Gate: LOCALLY VERIFIED
  - Evidence: `alembic/versions/006_celery_foundation/202512131200_worker_dlq.py:50-74`.
- EG-B0543-5 Observability Gate: LOCALLY VERIFIED
  - Evidence: `backend/app/observability/metrics.py:54-75`, test asserts metric names via `generate_latest()` in `backend/tests/test_b0543_matview_task_layer.py:69-95`.
- EG-B0543-6 DLQ Persistence Gate: LOCALLY VERIFIED
  - Evidence: `backend/app/celery_app.py:345-589` DLQ handler; failure test in `backend/tests/test_b0543_matview_task_layer.py:98-152` verifies correlation_id persistence.
- EG-B0543-7 Governance Gate: LOCALLY VERIFIED
  - Evidence: global R6 limits in `backend/app/celery_app.py:146-154` with defaults `backend/app/core/config.py:62-101`; matview tasks do not override.

CI/R7 evidence bound to commit C via the URLs above.
