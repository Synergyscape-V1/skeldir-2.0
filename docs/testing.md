# Skeldir Testing Authority

M2 defines the developer feedback loop as layered topology proof, not a single `pytest` invocation.

## Required Local Commands

| Command | Scope | Infrastructure |
| --- | --- | --- |
| `make test-unit-pure` | `unit_pure` | none |
| `make test-db-invariant` | `db_invariant` | local direct Postgres |
| `make test-db-direct` | `integration_db_direct` | local direct Postgres |
| `make test-db-pooler` | `integration_db_pooler` | local PgBouncer transaction pooler |
| `make test-fail-visible-tenant-context` | `fail_visible_tenant_context` | local or pure boundary tests |
| `make test-celery-eager` | `celery_eager` | no worker proof claimed |
| `make test-celery-worker` | `celery_worker` | local Postgres broker/result backend |
| `make test-broker-topology` | broker URL and rejection controls | local Postgres only |
| `make test-b23-representative` | `b23_representative` | local direct Postgres |
| `make test-b24-persistence-readiness` | `b24_persistence_readiness` | schema audit/blocker |
| `make test-governance` | `governance` | static validator |
| `make test-external-db-smoke` | `requires_external_db` | opt-in only |
| `make test` | safe default | M2 validator plus pure unit loop |

## Marker Taxonomy

The canonical markers are `unit_pure`, `db_invariant`, `integration_db_direct`, `integration_db_pooler`, `governance`, `e2e`, `slow`, `celery_eager`, `celery_worker`, `append_only_sensitive`, `rls_guc_sensitive`, `fail_visible_tenant_context`, `b23_representative`, `b24_persistence_readiness`, and `requires_external_db`.

Default tests must not infer external infrastructure. External DB smoke requires `SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true` and is never part of `make test`.

## Latency Budgets

Targets are: pure unit <= 60s, DB invariant <= 3m, direct DB representative <= 5m, pooler representative <= 5m, B2.4 readiness <= 60s, and M2 CI <= 10m. Runtime durations are written to `artifacts/m2/runtime_durations.ndjson`.
