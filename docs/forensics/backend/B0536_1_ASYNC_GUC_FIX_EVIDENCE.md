# B0.5.3.6.1 — Async GUC Fix Evidence

- CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/20349542847 (workflow `CI`, job `Celery Foundation B0.5.1`)
- Commit: 8879b2ab094cb80d95d2ac852abc65d9d0b9c79b (branch `b0534-worker-tenant-ci`)

## Gate 0 — Root cause validated (cross-loop GUC setter)
- Prior run (20349469357, job 58470036410) failed with `RuntimeError: Task ... got Future ... attached to a different loop` from `_set_tenant_guc_global` and `RuntimeError: Cannot run the event loop while another loop is running` during `_run_async`. This matched the hypothesis that per-call `asyncio.run`/`run_until_complete` bound the asyncpg pool to one loop then reused it from another.
- Fix: Introduced a dedicated worker event loop running in a background thread and route all sync→async bridges through `asyncio.run_coroutine_threadsafe`, eliminating per-call loop creation.

## Gate 2–4 — Proof of readiness, deterministic output, idempotency
- Readiness handshake: `test_b051_celery_foundation.py` published ping `f6000f6f-8695-48cb-95dc-aaa69b5fcb04` via `send_task` → result backend SUCCESS in 10s; DSN/queue identities logged (`queues=['housekeeping','maintenance','llm','attribution']`).
- Pytest summary (Celery job): `====================== 21 passed, 127 warnings in 15.71s =======================`.
- B0536 E2E: `tests/test_b0536_attribution_e2e.py::test_b0536_attribution_e2e_true_worker PASSED`. Test asserts:
  - Execution A: 6 deterministic allocations (channels direct/email/google_search, integer truncation of 10 000/15 000 cents).
  - Execution B: rerun yields identical 6 rows (unique key `(tenant_id,event_id,model_version,channel)` UPSERT).
  - Execution C: induced failure writes `worker_failed_jobs` row with matching `correlation_id`.

## Gate 5 — Security coherence
- Worker ingest tables remain read-only; no ingestion mutations introduced. Existing B0.5.3.5 tests run in the B0.5.3.3 job remain green.

## What changed
- Added async/sync-safe tenant GUC helpers; worker-side bridges now reuse a single long-lived loop thread with `run_coroutine_threadsafe` (no `run_until_complete` on ad-hoc loops).
- Tenant GUC and allocation paths keep `SET LOCAL` semantics; no change to allocation UPSERT strategy or ingestion table immutability.

