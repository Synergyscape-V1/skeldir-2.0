# M2 Completion Record

Final verdict: `M2_BLOCKED_BY_PRIMARY_BRANCH_NOT_GREEN`

This record is updated by the M2 remediation branch. It may not be changed to `M2_PASS` until the remediation lands on `main` and required checks are green.

## Summary

M2 installed the marker taxonomy, command surface, topology URL authority matrix, transaction-pooler compose profile, static validator, runtime harness, fast disposable DB scripts, append-only isolation rules, skeleton quarantine, fail-visible tenant-context boundary, B2.3 representative path, and B2.4 persistence readiness guard.

## Files Changed

See git diff for the authoritative file list.

## Marker Taxonomy

Configured in `pytest.ini`: `unit_pure`, `db_invariant`, `integration_db_direct`, `integration_db_pooler`, `governance`, `e2e`, `slow`, `celery_eager`, `celery_worker`, `append_only_sensitive`, `rls_guc_sensitive`, `fail_visible_tenant_context`, `b23_representative`, `b24_persistence_readiness`, `requires_external_db`.

## Command Surface

`make test` is the safe default. M2-specific targets cover pure unit, DB invariant, direct DB, pooler DB, fail-visible tenant context, Celery eager, Celery worker, broker topology, B2.3 representative, B2.4 persistence readiness, governance, E2E, and opt-in external DB smoke.

## Topology URL Authority

Documented in `docs/testing_topology_url_authority.md`; enforced by `scripts/testing/assert_topology_urls.py` and `scripts/ci/validate_m2_test_feedback_loop.py`.

## Proof Status

| Gate | Status |
| --- | --- |
| M1 dependency closure | Superseded by M2 workflow prerequisite that runs M1 bootstrap |
| External DB elimination | Static validator installed; hardcoded default-test Neon DSNs removed |
| Direct Postgres proof | `integration_db_direct` subset installed |
| Transaction-pooler proof | PgBouncer transaction profile and `integration_db_pooler` subset installed |
| Fail-visible tenant context | `MissingTenantContextError` boundary installed and tested |
| Broker topology | Local Postgres broker/result backend validation installed |
| Fast disposable isolation | Template/disposable DB scripts installed with duration artifacts |
| Append-only isolation | Trigger/RLS proof and static protected-deletion classifier installed |
| Skeleton closure | Legacy skeletons quarantined with M2 issue IDs |
| Celery mode clarity | `celery_eager` and `celery_worker` markers documented and tested |
| B2.3 representative path | `b23_match_verdicts` local schema proof installed |
| B2.4 persistence readiness | Blocked by enforced readiness guard until schema exists |
| Phase boundary | Validator blocks B2.4 dependencies and B2.3/provider-boundary semantic surfaces |
| Primary branch green | Pending |

## Latency Measurements

Runtime measurements are written to `artifacts/m2/runtime_durations.ndjson` by `scripts/ci/run_m2_test_feedback_loop.sh`.

## CI Workflow URL

Pending until pushed and executed on GitHub Actions.

## No-Contamination Statement

No B2.4 Bayesian implementation was added. No Bayesian runtime dependency was added. B2.3 semantic production files and `provider_boundary.py` are not part of the intended M2 surface.

## Deferred Items

M3: broad CI rationalization. M4: operational runbooks. M5/M6: later-phase non-test-substrate work.
