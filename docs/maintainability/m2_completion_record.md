# M2 Completion Record

Final verdict: `M2_PASS`

Corrective M2 is landed on `main` with the concurrent-worker, pooler-worker,
broker, parallel-isolation, namespace, and B2.4 entry-gate proof surface
executing in protected-branch CI.

## Main Commit and Workflow Evidence

Runtime proof `main` SHA:
`6a40a4f53fe729ddeb7647fae6c160652c79c1c0`

Pull requests:

- https://github.com/Synergyscape-V1/skeldir-2.0/pull/460
- https://github.com/Synergyscape-V1/skeldir-2.0/pull/461

Post-merge `main` workflow evidence at the runtime proof SHA:

| Workflow | Result | URL |
| --- | --- | --- |
| M0 Maintainability Scope Lock | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892847 |
| M1 Local Development Authority | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892843 |
| M2 Test Feedback Loop | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892851 |
| R7: Final Winning State | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892886 |

The full workflow set for that `main` SHA completed with no failed runs.

## Corrected Marker Taxonomy

Configured in `pytest.ini`: `unit_pure`, `db_invariant`,
`integration_db_direct`, `integration_db_pooler`, `governance`, `e2e`, `slow`,
`celery_eager`, `celery_worker`, `celery_worker_concurrent`,
`pooler_worker_concurrent`, `parallel_isolation`, `append_only_sensitive`,
`rls_guc_sensitive`, `fail_visible_tenant_context`, `b23_representative`,
`b24_persistence_entry_gate`, `b24_persistence_readiness`, and
`requires_external_db`.

## Corrected Command Surface

M2 now includes `make test-celery-worker-concurrent`,
`make test-pooler-worker-concurrent`, `make test-parallel-isolation`, and
`make test-b24-persistence-entry-gate` in addition to the original M2 targets.

## Corrective Proofs Installed

| Gate | Corrective proof |
| --- | --- |
| Concurrent worker tenant isolation | Real subprocess Celery workers with threaded pools and concurrency greater than one dispatch tenant A/B tasks through local Postgres broker/result backend. A committed disposable DB barrier makes serial execution fail instead of pass. |
| Pooler worker concurrency | Worker DB sessions use `TEST_POOLED_DATABASE_URL` through PgBouncer while broker/result remain direct local Postgres. |
| Broker cold/warm-start | Broker-absent negative control plus subprocess worker dispatch/result retrieval. |
| Pooler RLS/GUC coverage | Tenant bleed, missing context, concurrent tenant query, transaction reset, and worker-path pooler controls. |
| Serial/parallel isolation | M2 is serial-only, enforced through `SKELDIR_TEST_PARALLEL_MODE=serial-only` and `PYTEST_XDIST_WORKER == master`. |
| Test namespace authority | `SKELDIR_TEST_RUN_ID` scopes queues, probe tables, and runtime test markers. |
| B2.4 persistence entry gate | Canonical `b24_persistence_entry_gate` doc/marker/target blocks Bayesian runtime behavior until schema substrate exists. |
| Validator adequacy | Validator fails if corrected markers, targets, workflow steps, runtime tests, namespace authority, pooler controls, or B2.4 entry gate are absent. |
| Runtime harness adequacy | M2 workflow runs the corrected proof commands on PR and push/main. |
| Phase boundary | No B2.4 Bayesian execution/model code, no B2.3 semantic changes, and no provider-boundary behavior changes are intended. |

## Local Docker Runtime Evidence

Docker Desktop and Docker Compose are available locally as of 2026-05-13. The
local topology was started with `docker-compose.local.yml` plus
`docker-compose.test.yml`, migrations were applied, and the corrective M2
runtime subset passed against local Docker Postgres and PgBouncer.

Because this workstation has another local listener on `127.0.0.1:5432`, the
Docker Postgres host port was remapped to `55432` for local validation.
PgBouncer remained on `6432`.

Validated command:

```text
python -m pytest -q -m "integration_db_pooler or celery_worker_concurrent or pooler_worker_concurrent or parallel_isolation or b24_persistence_entry_gate or celery_worker" backend/tests/test_m2_test_feedback_loop.py backend/tests/test_m2_corrective_runtime_proofs.py
```

Result:

```text
7 passed, 9 deselected
```

## Main-CI Stabilization Follow-Up

The first post-PR #460 `main` sweep proved the corrective branch had physically
transitioned to `main`, but `R7: Final Winning State` failed twice in
`R7 Phase R3c: Ingestion harness` during `S4_PIIStorm_N1000` with a single
transient 5xx/request transport failure. PR #461 made the R3 harness retry
transient HTTP failures more robustly and preserve failed-run diagnostics before
exit. The subsequent `main` run at
`6a40a4f53fe729ddeb7647fae6c160652c79c1c0` passed M0, M1, M2, R7, and the
remaining workflow set.

## No-Contamination Statement

No B2.4 Bayesian execution/model code was introduced. No B2.3 production
semantics were changed to make M2 pass. No provider-boundary behavior was
modified. The PR #461 follow-up touched only R7/R3 CI harness behavior and the
M0/M1 validator allowlists needed to permit that narrow primary-CI repair.
