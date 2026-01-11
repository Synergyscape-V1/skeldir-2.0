B0.5.3.5 Worker Read-Only Ingestion Proof (Draft for CI)

Scope: Prove attribution workers cannot mutate ingestion inputs (`attribution_events`, `dead_events`) while preserving ingestion/API write ability.

What changed
- DB guardrail: New trigger function `fn_block_worker_ingestion_mutation` raises `ingestion tables are read-only in worker context (table=…)` when `app.execution_context = 'worker'` attempts INSERT/UPDATE/DELETE on `attribution_events` or `dead_events` (migration `202512171700_worker_ingestion_readonly.py`).
- Worker context marking: `tenant_task` sets `app.execution_context='worker'` (SET LOCAL) alongside the tenant GUC so worker transactions are identifiable at the DB layer.
- CI tests (`tests/test_b0535_worker_readonly_ingestion.py`):
  - Gate 0: Asserts `current_user == settings.DATABASE_URL.username` while `app.execution_context='worker'` is set (proves same session/role as worker).
  - Gate 1: In worker context, INSERT/UPDATE/DELETE against `attribution_events` and `dead_events` all fail with the guardrail error message.
  - Gate 2: Static posture check scans `backend/app/tasks/**` and `backend/app/workers/**` for ingestion-table writes and fails on any hit.

Execution plan for CI
1) Run `pytest backend/tests/test_b0535_worker_readonly_ingestion.py -q` (added as R5-7 in B0.5.3.3 job).  
2) Capture pytest summary showing the two dynamic tests + static scan passing (`4 passed`).  
3) Link CI run ID and include the guard error signature in the adjudication note once green.

Notes / Boundaries
- Guardrail triggers are scoped to `app.execution_context='worker'` so ingestion/API paths remain writable.
- Existing B0.5.3.3/B0.5.3.4 proofs remain part of the same job to ensure no regression.
