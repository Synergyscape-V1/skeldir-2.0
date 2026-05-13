# M2 Remediation Evidence Pack

**Phase:** M2 - Test Feedback Loop and Database Topology Stabilization
**Corrective branch:** `codex/m2-corrective-runtime-proof`
**Current corrective status:** `M2_PASS`
**Protected-main runtime proof SHA:** `6a40a4f53fe729ddeb7647fae6c160652c79c1c0`

## Corrective Initial Findings

The prior M2 implementation landed useful topology scaffolding, but the audit
finding is accepted: it did not physically prove the hardest runtime invariants.

| Finding | Corrective impact |
| --- | --- |
| Missing `celery_worker_concurrent` marker/target/workflow step | No proof that real concurrent Celery tasks isolate tenant ContextVars, sessions, and GUCs. |
| Missing `pooler_worker_concurrent` marker/target/workflow step | No proof that worker DB access is safe through transaction-pooled connections. |
| Broker topology proof was static | URL checks did not prove broker absence failure, worker startup, dispatch, or result retrieval. |
| Pooler RLS/GUC proof was thin | Single reset checks did not prove tenant bleed, missing context, concurrent queries, or worker path behavior. |
| Parallel isolation was undefined | Serial-only vs per-worker isolation was not enforced. |
| Test namespace authority was implicit | M2 had no run-scoped namespace contract for queues, tenants, tables, and future xdist workers. |
| B2.4 naming was stale | `b24_persistence_readiness` existed, but the canonical gate is `b24_persistence_entry_gate`. |
| Validator/runtime harness were too shallow | They could pass while the above proof classes were absent. |

## Corrective Remediations

| Area | Remediation |
| --- | --- |
| Marker taxonomy | Added `celery_worker_concurrent`, `pooler_worker_concurrent`, `parallel_isolation`, and `b24_persistence_entry_gate`. |
| Command surface | Added `make test-celery-worker-concurrent`, `make test-pooler-worker-concurrent`, `make test-parallel-isolation`, and `make test-b24-persistence-entry-gate`. |
| Concurrent worker proof | Added real subprocess Celery workers using threaded pools with concurrency greater than one. The tenant A/B tasks use a committed disposable DB barrier; serial execution times out instead of passing. |
| Tenant isolation proof | Added an M2 test-only tenant task that binds tenant authority via `TenantTask`, uses `get_session`, writes to an RLS/forced-RLS test table as a non-superuser runtime role, verifies own visibility, verifies cross-tenant invisibility, and verifies missing authority fails visibly. |
| Pooler worker proof | Added a separate proof path where worker `DATABASE_URL` is `TEST_POOLED_DATABASE_URL` while broker/result remain direct local Postgres. It verifies tenant isolation through PgBouncer transaction pooling. |
| Pooler RLS/GUC controls | Added concurrent pooled SQL controls proving tenant A/B isolation, missing-GUC failure, transaction reset, and concurrent query non-contamination. |
| Broker proof | `make test-broker-topology` now runs URL rejection plus a physical broker-absent negative control and real worker dispatch. |
| Parallel/namespace authority | Added `docs/testing_parallel_isolation.md`; M2 is explicitly serial-only until per-worker DB/schema isolation exists. `SKELDIR_TEST_RUN_ID`, `SKELDIR_TEST_PARALLEL_MODE`, and `PYTEST_XDIST_WORKER` are enforced. |
| B2.4 entry gate | Added `docs/testing_b24_persistence_entry_gate.md`, `b24_persistence_entry_gate`, and `make test-b24-persistence-entry-gate`; the gate allows future B2.4-P0 schema work but blocks Bayesian execution/model behavior. |
| Validator | Strengthened `scripts/ci/validate_m2_test_feedback_loop.py` to fail if the new markers, targets, workflow steps, runtime test bodies, namespace authority, broker proof, pooler worker proof, or canonical B2.4 gate are absent. |
| CI runtime harness | Updated `.github/workflows/m2-test-feedback-loop.yml` and `scripts/ci/run_m2_test_feedback_loop.sh` to run the corrected proof commands on PR and push to `main`. |
| PgBouncer compatibility | Added an env-gated asyncpg statement-cache disable path for transaction-pooler tests: `SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE=1`. |

## Corrective Files Changed

PR #460 M2 runtime proof files:

- `.github/workflows/m2-test-feedback-loop.yml`
- `Makefile`
- `pytest.ini`
- `backend/app/db/session.py`
- `backend/app/tasks/enqueue.py`
- `backend/app/tasks/observability_test.py`
- `backend/tests/conftest.py`
- `backend/tests/test_m2_corrective_runtime_proofs.py`
- `backend/tests/test_m2_test_feedback_loop.py`
- `docs/testing.md`
- `docs/testing_celery_modes.md`
- `docs/testing_db_topology.md`
- `docs/testing_b24_persistence_readiness.md`
- `docs/testing_b24_persistence_entry_gate.md`
- `docs/testing_parallel_isolation.md`
- `scripts/ci/run_m2_test_feedback_loop.sh`
- `scripts/ci/validate_m2_test_feedback_loop.py`

PR #461 primary-branch closure files:

- `.github/workflows/r7-final-winning-state.yml`
- `scripts/r3/ingestion_under_fire.py`
- `scripts/ci/validate_m0_scope_lock.py`
- `scripts/ci/validate_m1_local_dev_authority.py`

## Local Validation

Local static validation:

```text
python -m py_compile backend/app/db/session.py backend/app/tasks/observability_test.py backend/app/tasks/enqueue.py backend/tests/test_m2_corrective_runtime_proofs.py backend/tests/test_m2_test_feedback_loop.py scripts/ci/validate_m2_test_feedback_loop.py
python scripts/ci/validate_m2_test_feedback_loop.py --local-dev
python scripts/guard_no_docker.py
python scripts/ci/validate_m0_scope_lock.py --baseline-sha origin/main
python scripts/ci/validate_m1_local_dev_authority.py --baseline-sha origin/main
python -m pytest -q -m parallel_isolation backend/tests/test_m2_corrective_runtime_proofs.py
```

Local Docker availability hypothesis was validated on 2026-05-13:

```text
docker version
docker compose version
docker compose --env-file .env.local -f docker-compose.local.yml -f docker-compose.test.yml up -d postgres pgbouncer
docker compose --env-file .env.local -f docker-compose.local.yml -f docker-compose.test.yml run --rm migrate
```

The workstation already had a non-Docker listener on `127.0.0.1:5432`, so the
local Docker Postgres proof used `POSTGRES_PORT=55432`; PgBouncer remained on
`127.0.0.1:6432`.

Local Docker-backed runtime validation:

```text
python -m pytest -q -m "integration_db_pooler or celery_worker_concurrent or pooler_worker_concurrent or parallel_isolation or b24_persistence_entry_gate or celery_worker" backend/tests/test_m2_test_feedback_loop.py backend/tests/test_m2_corrective_runtime_proofs.py
```

Result:

```text
7 passed, 9 deselected
```

## Authoritative Main Evidence

Corrective M2 landed on `main` through protected-branch PR flow in two PRs:

- Corrective runtime proof PR: https://github.com/Synergyscape-V1/skeldir-2.0/pull/460
- Main-CI stabilization PR: https://github.com/Synergyscape-V1/skeldir-2.0/pull/461

Authoritative `main` proof at
`6a40a4f53fe729ddeb7647fae6c160652c79c1c0`:

| Workflow | Result | URL |
| --- | --- | --- |
| M0 Maintainability Scope Lock | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892847 |
| M1 Local Development Authority | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892843 |
| M2 Test Feedback Loop | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892851 |
| R7: Final Winning State | success | https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25829892886 |

The complete post-merge `main` workflow set for that SHA completed with no
failed runs.

## Main-CI Stabilization Follow-Up

After PR #460 merged, the first post-merge `main` sweep reached the physical
transition condition but exposed a separate primary-branch blocker:
`R7: Final Winning State` failed twice in `R7 Phase R3c: Ingestion harness`
during `S4_PIIStorm_N1000` with a single transient 5xx/request transport
failure. PR #461 made the R3 harness more resilient to transient transport
failures and ensured failed R3 runs preserve `/tmp/r7_results/r3.json` plus
uvicorn diagnostics instead of exiting before evidence capture.

## Current Verdict

`M2_PASS`
