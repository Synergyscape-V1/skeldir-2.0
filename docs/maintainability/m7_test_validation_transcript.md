# M7 Test Validation Transcript

## Coordinate

| Field | Value |
| --- | --- |
| validation_time | 2026-05-19T12:21:07-05:00 |
| branch | `codex/m7-b24-readiness` |
| base_sha | `668fb9867ab973023b8ed4b417a5dcf51489146e` |

## M0-M2 Static Validators

Command:

```text
python scripts/ci/validate_m0_scope_lock.py --local-dev
```

Observed result:

```text
VERDICT: M0_SCOPE_LOCK_VALID
Total: 80 | Passed: 80 | Failed: 0
```

Command:

```text
python scripts/ci/validate_m1_local_dev_authority.py --local-dev
```

Observed result:

```text
VERDICT: M1_STATIC_VALID
```

Command:

```text
python scripts/ci/validate_m2_test_feedback_loop.py --local-dev
```

Observed result:

```text
VERDICT: M2_STATIC_VALID
```

## Test Topology

Direct Postgres profile:

```text
make test-db-direct
```

M7 result: CI-bound runtime proof. The M2 validator confirmed the target, marker, workflow wiring, local-safe DSN defaults, and representative B2.3/B2.4 readiness commands. Host-local DB runtime could not start because Docker Desktop was not running.

Pooler profile:

```text
make test-db-pooler
make test-pooler-worker-concurrent
```

M7 result: explicitly classified as non-blocking B2.4 debt unless B2.4 adds transaction-pooler-dependent worker behavior. The M2 validator confirmed `integration_db_pooler`, `pooler_worker_concurrent`, PgBouncer local port, asyncpg statement-cache disablement, and M2 workflow wiring.

External DB rejection:

```text
python scripts/ci/validate_m2_test_feedback_loop.py --local-dev
```

Observed result:

```text
[PASS] default test paths contain no hardcoded external DB URLs
[PASS] external DB smoke target is explicit
```

Append-only isolation:

```text
python scripts/ci/validate_m2_test_feedback_loop.py --local-dev
```

Observed result:

```text
[PASS] append-only isolation doc forbids protected deletion
[PASS] protected truth-table deletion is classified or quarantined
```

Marker taxonomy:

```text
python scripts/ci/validate_m2_test_feedback_loop.py --local-dev
```

Observed result:

```text
Configured and used markers included unit_pure, db_invariant, integration_db_direct, integration_db_pooler, governance, e2e, slow, celery_eager, celery_worker, celery_worker_concurrent, pooler_worker_concurrent, parallel_isolation, append_only_sensitive, rls_guc_sensitive, fail_visible_tenant_context, b23_representative, b24_persistence_readiness, b24_persistence_entry_gate, and requires_external_db.
```

## M5-M7 Validators

Command:

```text
python scripts/ci/validate_m5_b24_readiness_design.py --negative-control
```

Observed result:

```text
M5_NEGATIVE_CONTROL_PASS: docs/b2_4/diagnostic_protocol.md missing required token: ## Diagnostic Metrics
M5_B24_READINESS_VALIDATION_PASS
```

Command:

```text
python scripts/ci/validate_m6_llm_boundary.py --negative-control
```

Observed result:

```text
M6_NEGATIVE_CONTROL_PASS
M6_LLM_BOUNDARY_VALIDATION_PASS
```

Command:

```text
python scripts/ci/validate_m7_b24_readiness.py --negative-control
```

Observed result:

```text
M7_NEGATIVE_CONTROL_PASS
M7_B24_READINESS_VALIDATION_PASS
```

## Unit-Pure Representative Subset

The Git Bash wrapper selected `/usr/bin/python3`, which lacked pytest on this Windows host. The same M2 unit-pure subset was then executed with the repository Python 3.11 environment and equivalent M2 environment variables:

```text
python -m pytest -q -m unit_pure backend/tests/test_m2_test_feedback_loop.py backend/tests/test_m2_corrective_runtime_proofs.py backend/tests/test_channel_normalization.py backend/tests/test_money_primitives.py
```

Observed result:

```text
69 passed, 15 deselected in 0.91s
```
