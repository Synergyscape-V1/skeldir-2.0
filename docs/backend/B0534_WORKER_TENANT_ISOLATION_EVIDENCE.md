B0.5.3.4 Worker-Scoped Tenant Isolation Evidence Pack (Draft for CI)

Scope: Close the worker-scoped tenant isolation gap (beyond API-level checks) with falsifiable tests and minimal hardening.

What changed
- Tenant GUC scoping: All worker DB transactions now call `SET LOCAL app.current_tenant_id` (via `set_tenant_guc(..., local=True)`) inside `_upsert_job_identity`, `_mark_job_status`, and allocation compute paths. This prevents pooled-connection leakage of a prior tenant_id.
- DLQ correlation hardening: Celery failure signal now falls back to `task_id` as a correlation UUID when `request.correlation_id` is absent, ensuring DLQ rows always carry correlation metadata.
- New CI-targeted tests in `backend/tests/test_b0534_worker_tenant_isolation.py`:
  - `test_allocations_and_jobs_are_tenant_scoped`: runs recompute for two tenants and proves RLS prevents cross-tenant reads of allocations and recompute jobs.
  - `test_retry_idempotent_and_event_id_non_null`: runs recompute twice for the same window and asserts no duplicate allocations, no NULL event_ids, and run_count == 2.
  - `test_concurrent_recompute_converges_without_duplicates`: concurrent recompute invocations converge to a single canonical allocation set (distinct count == total, no duplication, run_count >= 2).
  - `test_missing_tenant_context_captured_in_dlq_with_correlation`: deliberate missing tenant_id raises ValueError, lands in `worker_failed_jobs` with `error_type=validation_error` and non-null correlation_id.

How tenant context propagates (worker path)
- `@tenant_task` still sets contextvars; DB-facing paths now set the tenant GUC per transaction (`SET LOCAL ...`) so every read/write is scoped even if the connection is reused from the pool.
- Using `SET LOCAL` means the tenant_id resets after each transaction commit, eliminating session-level residue that could bleed into the next task.

Why GUC leakage is prevented
- Session-level GUC setting was removed in favor of per-transaction `SET LOCAL`, and every worker transaction (jobs + allocations) now performs this call before RLS-protected operations. Even with pooled connections, the GUC value is confined to the current transaction and cannot persist to later tasks.

Idempotency key correctness under retry
- Unique index `(tenant_id, event_id, model_version, channel)` combined with non-null event_ids (asserted in tests) keeps retries idempotent. Tests assert total allocations == distinct allocations and event_id IS NOT NULL after repeat and concurrent execution.

Execution plan for CI (closure bar)
1) Run `pytest backend/tests/test_b0534_worker_tenant_isolation.py -q` in CI with DATABASE_URL set (per Gate C).  
2) Capture pytest summary showing the four tests passing.  
3) Attach logs demonstrating DLQ row insertion with `correlation_id` present.  
4) Link CI job/run ID in the B0.5.3.4 execution summary once green.

Residual risks / TODO
- Materialized view refresh paths are not covered here; if they reuse pooled connections they should also call `SET LOCAL` before tenant-scoped work.  
- Concurrency test uses Celery eager mode with thread executors; a follow-up with a real worker process could further derisk connection reuse semantics.  
- RLS for `worker_failed_jobs` is assumed from prior migration; if CI reveals gaps, add an explicit policy assertion alongside the new DLQ test.
