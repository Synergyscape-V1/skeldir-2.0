# Queue Topology

Canonical queue source: `backend/app/core/queues.py`. Celery route authority:
`backend/app/celery_app.py`.

## Command

```yaml
command: make ops-queues
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
idempotency_sensitive: false
signature_sensitive: false
```

Worker inspection:

```yaml
command: make ops-worker-inspect
execution_context: container_celery
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
idempotency_sensitive: false
signature_sensitive: false
```

## Canonical Queues

| Queue | Owning workload | Producer path | Consumer worker | Task names | Expected state | Stuck-queue causes |
| --- | --- | --- | --- | --- | --- | --- |
| `housekeeping` | Health, probes, governance, failure semantics. | `backend/app/tasks/housekeeping.py`, `backend/app/tasks/health.py`, R4/R6 tasks. | Local worker bound by `make worker`. | `app.tasks.housekeeping.ping`, `app.tasks.health.probe`. | Usually idle. | Worker offline, broker DB unavailable, task route defaulting unexpectedly. |
| `maintenance` | Materialized views, privacy and maintenance sweeps. | `backend/app/tasks/maintenance.py`, `backend/app/tasks/matviews.py`, `backend/app/tasks/privacy.py`. | Local worker bound by `make worker`. | `app.tasks.matviews.refresh_all`, `app.tasks.maintenance.*`, `app.tasks.privacy.*`. | Idle except scheduled maintenance. | Long-running refresh, lock timeout, stale DB migration. |
| `llm` | Bounded LLM explanation/investigation tasks only. | `backend/app/tasks/llm.py`. | Local worker bound by `make worker`. | `app.tasks.llm.route`, `app.tasks.llm.explanation`, `app.tasks.llm.investigation`, `app.tasks.llm.budget_optimization`. | Idle unless LLM feature path is enabled. | Provider kill switch, budget guard, audit persistence failure. |
| `attribution` | Deterministic attribution recomputation. | `backend/app/tasks/attribution.py`. | Local worker bound by `make worker`. | `app.tasks.attribution.recompute_window`. | Idle until ingestion follow-up or explicit recompute. | Idempotency conflict, RLS GUC missing, model validation failure. |
| `bayesian` | B2.4 readiness queue, not M4 feature work. | `backend/app/tasks/bayesian.py`. | Dedicated/opt-in worker when enabled. | `app.tasks.bayesian.*`. | Idle in M4. | B2.4 is not active, missing statistical dependencies, feature gate disabled. |
| `bayesian_publisher` | B2.5-P13 C11 fresh fit-dispatch publication. Separated from `bayesian` because its worker authenticates as the dedicated `app_dispatch_publisher` principal, which holds cross-tenant SELECT/UPDATE on the dispatch outbox and nothing else; an ordinary execution worker must not be able to acquire that authority by consuming from the same queue. | `backend/app/tasks/bayesian_publisher.py`. | Dedicated publisher worker, `--concurrency=1`. | `app.tasks.bayesian.publish_due_fit_dispatches`. | Idle in M4. | B2.4 is not active, feature gate disabled, or the publisher DSN is unset. |
| `b23_match_engine` | B2.3 revenue verification and match engine. | `backend/app/api/webhooks.py`, `backend/app/tasks/revenue_verification.py`. | Local worker bound by `make worker`. | `app.tasks.revenue_verification.execute_b23_batch_match_engine`, transition tasks. | Idle unless verified webhook ingress or transition sweep dispatches work. | Missing ingress identity, task dispatch not persisted, DB pool timeout, verdict constraint failure. |

## Local Start And Health

```yaml
command: make worker
execution_context: container_worker
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
idempotency_sensitive: false
signature_sensitive: false
```

Expected healthy output from `make ops-queues`: JSON containing all six queue
names from `backend/app/core/queues.py`. The M4 validator compares this runbook
against that canonical source.

Expected healthy output from `make ops-worker-inspect`: Celery inspect sections
for active, reserved, and scheduled. Empty lists are healthy only when the queue
is expected to be idle and no incident task ID is being traced.

## Safety

Do not add ad hoc queues in runbooks. Queue names must come from
`backend/app/core/queues.py`, and local inspection must stay behind the Make
targets above.
