# DLQ Inspection and Replay Safety

`worker_failed_jobs` is the canonical Celery failed-task persistence table. It
contains task identity, queue, worker, tenant context, args/kwargs snapshots,
error classification, traceback, retry count, status, correlation ID, and
failure timestamp.

## Commands

Seed the local positive controls first.

```yaml
command: make ops-seed-diagnostics
execution_context: container_api
command_class: local_fixture_replay
requires_seeded_fixture: false
mutates_state: local_fixture_only
tenant_scope_required: false
idempotency_sensitive: true
signature_sensitive: true
```

Inspect the seeded DLQ row.

```yaml
command: make ops-dlq-inspect
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: true
mutates_state: false
tenant_scope_required: true
idempotency_sensitive: false
signature_sensitive: false
```

Clear only the local synthetic fixture rows.

```yaml
command: make ops-clear-diagnostics
execution_context: container_api
command_class: local_fixture_replay
requires_seeded_fixture: true
mutates_state: local_fixture_only
tenant_scope_required: true
idempotency_sensitive: true
signature_sensitive: true
```

## Positive And Negative Controls

Positive control: `make ops-dlq-inspect` must return `status: found` for
`m4-dlq-positive-*` with task ID, task name, queue `b23_match_engine`,
`error_type`, `retry_count`, `failed_at`, and `correlation_id`.

Negative control: the script's missing-control path returns `status: not_found`
and the diagnostic text `no worker_failed_jobs row matched task_id under the
seeded tenant context`. That output is a valid negative result only because it
names the tenant scope and searched task ID.

## Field Interpretation

| Field | Meaning | First branch |
| --- | --- | --- |
| `task_id` | Celery execution identity. | Use it for worker inspect and B2.3 dispatch correlation. |
| `task_name` | Fully qualified task, for example `app.tasks.revenue_verification.execute_b23_batch_match_engine`. | Confirm route in `backend/app/celery_app.py`. |
| `queue` | Queue that should own consumption. | Cross-check [queue topology](queue_topology.md). |
| `tenant_id` | RLS scope for tenant tasks. | If missing on tenant work, inspect task envelope propagation. |
| `task_args` / `task_kwargs` | Serialized invocation context. | Treat as forensic context, not an approved replay payload. |
| `error_type` / `exception_class` | Failure class. | Separate validation, transient DB, permission, and code defects. |
| `traceback` | Worker-side stack trace. | Use first application frame for source location. |
| `retry_count` / `failed_at` | Retry history and age. | High retry count plus fresh timestamp suggests active retry churn. |

## Replayability Classification

`read_only_inspection`: always allowed for local and production diagnosis.

`local_fixture_replay`: allowed only for synthetic M4 fixture rows produced by
`make ops-seed-diagnostics`.

`duplicate_detection_probe`: allowed only when a run-scoped idempotency key is
used and the expected result is no additional canonical event.

`manual_production_diagnostic`: read-only production SQL or queue inspection
performed by an authorized operator in the production runbook environment.

`forbidden_production_replay`: any production replay of provider payloads, task
args, or B2.3 financial truth from `worker_failed_jobs`.

## Non-Replayable Failure Classes

Do not replay from DLQ when the row involves webhook authenticity, provider
signature material, protected B2.3 match verdicts, attribution financial truth,
tenant context ambiguity, PII stripping uncertainty, or append-only ledger
mutation. Use the row to diagnose cause, then repair through the original
authentic ingress or a separately approved manual remediation.

## Safety Warnings

`task_args` and `task_kwargs` can contain enough context to mutate deterministic
truth if reused blindly. They are forensic signals only. M4 adds no production
replay endpoint, no production replay Make target, and no authorization to
delete or rewrite append-only truth tables.

Escalate manually when the same task ID appears repeatedly, the tenant context
is absent for tenant-scoped work, the traceback indicates auth/RLS bypass risk,
or the failure touches `b23_match_verdicts`, `b23_revenue_events`,
`webhook_ingress_identities`, or `attribution_events`.
