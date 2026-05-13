# M2 Remediation Evidence Pack

**Phase:** M2 - Test Feedback Loop and Database Topology Stabilization  
**Branch:** `codex/m2-test-feedback-loop-stabilization`  
**PR:** https://github.com/Synergyscape-V1/skeldir-2.0/pull/458  
**Validated remediation branch head:** `7894b5a2c9866800367c5feee88d8e61617469fd`  
**Implementation main merge commit:** `9656025f911517c6b4702e6e474ea92f282fe64d`  
**Current status:** `M2_PASS`.

## Initial Findings

| ID | Finding | M2 impact |
| --- | --- | --- |
| H-M2-01 | Default test paths contained hardcoded Neon/prod-adjacent database URLs and cloud-looking fallbacks. | Default tests could silently use non-local infrastructure. |
| H-M2-02/H-M2-03 | Direct Postgres tests existed, but no local transaction-pooler profile or pooler-specific RLS/GUC proof existed. | Direct DB success could be overread as topology proof. |
| H-M2-04 | Missing tenant context could degrade into raw RLS zero-row behavior without an application/session-layer failure. | Domain code could treat missing GUC as legitimate empty truth. |
| H-M2-05 | URL purpose was implicit across direct, pooled, migration, test, external smoke, broker, and result backend DSNs. | Developers could conflate migration/runtime/pooler/external URLs. |
| H-M2-06/H-M2-12 | Celery eager and real-worker evidence were ambiguous. | Task-logic tests could be mistaken for broker/worker topology proof. |
| H-M2-08/H-M2-09 | Append-only constraints were active, but isolation strategy was not explicit or speed-measured. | Cleanup could rely on forbidden protected-table deletion or shared-state accumulation. |
| H-M2-10/H-M2-11 | Skeleton tests and phase-coded filenames substituted for marker taxonomy. | Green pytest output could overstate actual coverage. |
| H-M2-13 | No single local B2.3 representative command existed. | Successors lacked a focused B2.3 feedback loop. |
| H-M2-14 | B2.4 Bayesian diagnostic persistence readiness was unconfirmed. | B2.4 could begin without schema evidence or an enforced blocker. |
| Governance conflict | Legacy zero-container guard rejected the M2-required container-first topology artifacts until narrowly allowlisted. | Branch CI initially failed phase gates despite M1/M2 requiring containerized local proof. |

## Remediations Made

| Area | Remediation |
| --- | --- |
| Marker taxonomy | Added `unit_pure`, `db_invariant`, `integration_db_direct`, `integration_db_pooler`, `governance`, `e2e`, `slow`, `celery_eager`, `celery_worker`, `append_only_sensitive`, `rls_guc_sensitive`, `fail_visible_tenant_context`, `b23_representative`, `b24_persistence_readiness`, and `requires_external_db` to `pytest.ini`. |
| Command surface | Added M2 Make targets for pure unit, DB invariant, direct DB, pooler DB, fail-visible tenant context, Celery eager, Celery worker, broker topology, B2.3 representative, B2.4 persistence readiness, governance, E2E, opt-in external DB smoke, and safe default `make test`. |
| Pooler topology | Added `docker-compose.test.yml` with local PgBouncer transaction pooling behind local Postgres; M2 CI starts it with the M1 local topology. |
| Runtime harness | Added `.github/workflows/m2-test-feedback-loop.yml` and `scripts/ci/run_m2_test_feedback_loop.sh`; the workflow runs M1 bootstrap first, then M2 validator and representative command surface. |
| Static validator | Added `scripts/ci/validate_m2_test_feedback_loop.py` to enforce artifacts, markers, Make targets, topology URL authority, external DB rejection, pooler profile, append-only isolation, Celery mode clarity, B2.3 path, B2.4 readiness blocker, and phase-boundary integrity. |
| Topology URL authority | Added `docs/testing_topology_url_authority.md` and `scripts/testing/assert_topology_urls.py`; default tests reject external DB/broker hosts, and external DB smoke requires explicit opt-in. |
| Fail-visible tenant context | Added `MissingTenantContextError` and tenant-context assertions in `backend/app/db/session.py`; M2 tests distinguish raw RLS zero-row fallback from application/session trust failure. |
| Append-only isolation | Added `docs/testing_append_only_isolation.md`, disposable/template DB helper scripts, append-only proof tests, and protected deletion/truncation classifier coverage. |
| Celery modes | Added `docs/testing_celery_modes.md`; M2 separates eager task-logic checks from real worker/broker checks and validates Postgres-backed broker/result backend URLs. |
| Skeleton closure | Quarantined legacy skeleton/vacuous tests with explicit M2 issue IDs instead of counting them as real default coverage. |
| B2.3 representative path | Added `b23_representative` proof coverage and Make target for a local B2.3 representative subset. |
| B2.4 readiness | Added `docs/testing_b24_persistence_readiness.md`; because canonical B2.4 persistence is not confirmed, M2 blocks B2.4 readiness through validator guardrails rather than implementing B2.4. |
| M0/M1 compatibility | Updated M0/M1 validators and `scripts/guard_no_docker.py` narrowly so M2-required artifacts do not trip earlier phase guards while B2.4/provider-boundary/B2.3 semantic protections remain active. |

## Files Changed

Primary M2 artifacts:

- `.github/workflows/m2-test-feedback-loop.yml`
- `docker-compose.test.yml`
- `docs/testing.md`
- `docs/testing_db_topology.md`
- `docs/testing_append_only_isolation.md`
- `docs/testing_celery_modes.md`
- `docs/testing_topology_url_authority.md`
- `docs/testing_b24_persistence_readiness.md`
- `docs/maintainability/m2_completion_record.md`
- `scripts/ci/validate_m2_test_feedback_loop.py`
- `scripts/ci/run_m2_test_feedback_loop.sh`
- `scripts/testing/assert_topology_urls.py`
- `scripts/testing/create_test_template_db.sh`
- `scripts/testing/create_disposable_test_db.sh`
- `backend/tests/test_m2_test_feedback_loop.py`
- `backend/app/db/session.py`
- `pytest.ini`
- `Makefile`

Additional touched files quarantine skeleton tests, remove/quarantine external DSNs, classify append-only cleanup, and preserve compatibility with M0/M1/legacy phase guards.

## Validation Evidence

Local validation performed:

```text
python scripts/guard_no_docker.py
python scripts/ci/enforce_postgres_only.py
python scripts/ci/validate_m0_scope_lock.py --baseline-sha origin/main
python scripts/ci/validate_m1_local_dev_authority.py --baseline-sha origin/main
python scripts/ci/validate_m2_test_feedback_loop.py --baseline-sha origin/main
python -m py_compile scripts/guard_no_docker.py scripts/ci/validate_m2_test_feedback_loop.py backend/tests/test_m2_test_feedback_loop.py
python -m pytest -q -m governance backend/tests/test_m2_test_feedback_loop.py backend/tests/test_channel_normalization.py backend/tests/test_money_primitives.py
python -m pytest -q -m unit_pure backend/tests/test_m2_test_feedback_loop.py backend/tests/test_channel_normalization.py backend/tests/test_money_primitives.py
python -m pytest -q -m fail_visible_tenant_context
python -m pytest -q -m celery_eager
python scripts/testing/assert_topology_urls.py --expect-rejection
```

Local Docker-backed direct/pooler/broker execution was not available on this workstation because Docker Desktop was not running. The authoritative container execution proof is therefore GitHub Actions.

Authoritative PR validation:

```text
PR: https://github.com/Synergyscape-V1/skeldir-2.0/pull/458
Branch head: 7894b5a2c9866800367c5feee88d8e61617469fd
Main merge commit: 9656025f911517c6b4702e6e474ea92f282fe64d
m0-maintainability-scope-lock: pass
m1-local-dev-authority: pass
m2-test-feedback-loop: pass
Broad PR check matrix: pass
M2 workflow run for final branch head: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25800183619/job/75787768480
Main CI run for final branch head: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25800183583
Post-merge main M2 workflow: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25801300938
Post-merge main CI workflow: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25801300937
Post-merge main R7 final-winning-state workflow: https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25801300916
Post-merge main validation sweep: 31 push-triggered workflows for 9656025f911517c6b4702e6e474ea92f282fe64d completed successfully; non_green=0.
```

## Exit Gate Status

| Gate | Status |
| --- | --- |
| M1 enforcement dependency | Pass: M2 workflow executes M1 bootstrap prerequisite and M1 check is green. |
| External DB elimination | Pass on branch: default paths reject unapproved external DB URLs. |
| Topology URL authority | Pass on branch: matrix exists and validator enforces it. |
| Broker topology | Pass on branch CI: local Postgres broker/result backend proof and negative control are installed. |
| Marker taxonomy | Pass on branch. |
| Pure unit loop | Pass on branch. |
| DB invariant/direct/pooler loops | Pass in M2 GitHub Actions topology. |
| Pooler RLS/GUC controls | Pass in M2 proof subset. |
| Fail-visible tenant context | Pass on branch. |
| Fast disposable isolation | Pass: helper scripts and duration artifact collection installed. |
| Append-only isolation | Pass: protected cleanup rules and negative controls installed. |
| Skeleton closure | Pass: known skeletons quarantined with M2 issue IDs. |
| Celery mode clarity | Pass: eager and worker modes marked and documented separately. |
| B2.3 representative path | Pass on branch. |
| B2.4 persistence readiness | Pass as enforced blocker: readiness remains blocked until schema substrate exists. |
| M2 validator | Pass. |
| Runtime proof harness | Pass. |
| Phase boundary integrity | Pass: no B2.4 implementation, no provider-boundary behavior change, no B2.3 semantic reopening. |
| Primary branch green | Pass: PR #458 merged to `main` at `9656025f911517c6b4702e6e474ea92f282fe64d`; post-merge main workflows completed successfully. |

## Current Verdict

`M2_PASS`

M2 landed on `main` through PR #458, and the resulting `main` workflow set for merge commit `9656025f911517c6b4702e6e474ea92f282fe64d` completed green.
