# B0.5.7-P5 Full-Chain E2E Integration Evidence

Status: FINAL

## Objective
Prove the canonical full-chain path under least-privilege + RLS:
webhook -> persistence -> downstream tasks -> matview refresh.

## Canonical Route Selection (P5)
Chosen route: `POST /api/webhooks/shopify/order_create`

Rationale:
- Uses `_handle_ingestion(...)` which schedules downstream tasks via `_schedule_downstream_tasks`.
- Includes deterministic signature validation and PII stripping middleware.
- Avoids the Stripe contract route which currently bypasses downstream scheduling.

Source:
- `backend/app/api/webhooks.py` (`shopify_order_create`, `_handle_ingestion`, `_schedule_downstream_tasks`)

## Chain Mapping (EG-P5.1)
Route -> persistence -> tasks -> matview refresh:
1. FastAPI route:
   - `backend/app/api/webhooks.py: shopify_order_create`
2. Tenant resolution + signature validation:
   - `backend/app/api/webhooks.py: tenant_secrets`
   - `backend/app/core/tenant_context.py: get_tenant_with_webhook_secrets`
   - `backend/app/webhooks/signatures.py: verify_shopify_signature`
3. Persistence (idempotent ingestion):
   - `backend/app/api/webhooks.py: _handle_ingestion`
   - `backend/app/ingestion/event_service.py: ingest_with_transaction -> EventIngestionService.ingest_event`
   - Writes `public.attribution_events` with RLS.
4. Downstream tasks enqueued:
   - `backend/app/api/webhooks.py: _schedule_downstream_tasks`
   - Celery chain:
     - `app.tasks.attribution.recompute_window`
     - `app.tasks.matviews.refresh_all_for_tenant`
5. Attribution recompute (deterministic baseline):
   - `backend/app/tasks/attribution.py: recompute_window`
   - Writes `public.attribution_recompute_jobs` and `public.attribution_allocations`
6. Matview refresh:
   - `backend/app/tasks/matviews.py: matview_refresh_all_for_tenant`
   - `backend/app/matviews/executor.py: refresh_all_for_tenant`
7. Matview dependency:
   - `mv_allocation_summary` depends on `attribution_allocations` + `attribution_events`
   - `alembic/versions/003_data_governance/202511161110_fix_mv_allocation_summary_left_join.py`

## Matview Dependency Chosen (EG-P5.5)
Matview: `mv_allocation_summary`

Why:
- Directly reflects allocations computed by `recompute_window`.
- Deterministic: `total_allocated_cents == event_revenue_cents` when allocations succeed.

Dependency path:
- Base tables: `attribution_allocations`, `attribution_events`
- View definition: `alembic/versions/003_data_governance/202511161110_fix_mv_allocation_summary_left_join.py`

## CI Topology (EG-P5.2)
Workflow:
- `.github/workflows/b057-p5-full-chain.yml`

Topology:
- Postgres service
- Admin identity: `migration_owner` (migrations + tenant seed)
- Runtime identity: `app_user` (API + worker + tests)
- API started via Uvicorn
- Worker started via Celery (queues: attribution, maintenance)

## Canonical Test (EG-P5.3–EG-P5.6)
Test file:
- `backend/tests/integration/test_b057_p5_full_chain_e2e.py`

Assertions:
- Webhook accepted (HTTP 200) and persisted in `attribution_events`.
- Downstream task executed (`attribution_recompute_jobs.status == succeeded`).
- Allocations created for the event in `attribution_allocations`.
- Matview refreshed (`mv_allocation_summary` row exists and balances).
- RLS isolation:
  - Cross-tenant reads return 0 for `attribution_events` and `attribution_allocations`.
  - No-tenant context reads return 0 for the same tables.

Anti-flake:
- Explicit polling with bounded timeouts for recompute + allocations + matview row.
- Timeout diagnostics captured to `artifacts/b057-p5/timeout_diagnostics.json`.

## Artifacts (EG-P5.7)
Expected CI artifacts uploaded by workflow:
- `artifacts/b057-p5/api.log`
- `artifacts/b057-p5/worker.log`
- `artifacts/b057-p5/pytest.log`
- `artifacts/b057-p5/db_probe.json`
- `artifacts/b057-p5/timeout_diagnostics.json` (on failure)

## CI Evidence (Final)
- Commit SHA: 97264f05f5d87f668e5d4c916da5364c539a833c
- GitHub Actions run URL: https://github.com/Muk223/skeldir-2.0/actions/runs/21339028148
- Workflow: `b057-p5-full-chain`

## Empirical Results
Test status:
- `backend/tests/integration/test_b057_p5_full_chain_e2e.py` PASSED (1 test, 7.75s)

DB probe (artifact `db_probe.json`):
- attribution_recompute_jobs: status=succeeded, run_count=1
- mv_allocation_summary: total_allocated_cents=1050, event_revenue_cents=1050, is_balanced=true, drift_cents=0
- RLS isolation:
  - tenant-scoped counts: events=1, allocations=3
  - no-tenant counts: events=0, allocations=0

Metrics deltas (artifact `metrics_delta.json`):
- events_ingested_total: +1
- celery_task_success_total (recompute_window): +1
- celery_task_success_total (refresh_all_for_tenant): +1
- matview_refresh_total (mv_allocation_summary, success): +1

Truthful scrape targets:
- API metrics surface contains API + broker-truth gauges (no `celery_task_success_total`).
- Worker metrics surface contains task metrics (`celery_task_success_total` present).

Cardinality/privacy lint (artifact `metrics_lint.json`):
- API label keys: queue, state, le (no violations)
- Worker label keys: task_name, view_name, outcome, le (no violations)
- No tenant_id labels, no UUID-like values detected.

Structured log validation:
- `api.log` contains `event_ingested` and `ingestion_followup_tasks_enqueued` with tenant_id.
- `worker.log` contains lifecycle records for recompute + matview tasks and matview refresh markers.

Artifacts captured:
- `api.log`
- `worker.log`
- `exporter.log`
- `pytest.log`
- `db_probe.json`
- `metrics_api_before.txt`
- `metrics_api_after.txt`
- `metrics_worker_before.txt`
- `metrics_worker_after.txt`
- `metrics_delta.json`
- `metrics_lint.json`

## Notes
- No claims of local execution.
- This evidence pack is authoritative only after a CI run on `main`.
