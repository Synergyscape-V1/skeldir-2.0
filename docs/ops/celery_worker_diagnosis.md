# Celery Worker Diagnosis

Skeldir workers use the Postgres Celery broker/backend from `.env.local`:
`sqla+postgresql://...` for broker and `db+postgresql://...` for result backend.
Canonical local worker commands run through Docker Compose.

## Commands

Start the local worker.

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

Inspect active, reserved, and scheduled tasks through the worker container.

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

Inspect API and worker logs through the canonical topology.

```yaml
command: make logs
execution_context: container_worker
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
idempotency_sensitive: false
signature_sensitive: false
```

Cross-check failed task persistence.

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

## Queue Binding

The local worker command in `docker-compose.local.yml` binds:

`housekeeping,maintenance,llm,attribution,b23_match_engine`

If a task is queued but not consumed, first verify that its queue appears in
[queue topology](queue_topology.md), then run `make ops-worker-inspect`.

## Task Correlation

Use this order:

1. `task_id` from `worker_failed_jobs` or `b23_match_task_dispatches`.
2. `task_name`, especially `app.tasks.revenue_verification.execute_b23_batch_match_engine`.
3. `queue`, then worker binding.
4. `correlation_id`, then API/webhook logs.
5. `tenant_id`, then [RLS/GUC verification](rls_guc_verification.md).

## Broker And Backend Checks

The broker and result backend are Postgres-backed. A worker can be idle because
the queue is empty, because the wrong queue is bound, because broker DB access is
unavailable, or because a task is reserved but blocked in execution. Treat
`active`, `reserved`, and `scheduled` as different states:

| State | Meaning | Next step |
| --- | --- | --- |
| active | Worker has started executing the task. | Inspect logs and task timeout. |
| reserved | Worker has received but not started it. | Check prefetch and concurrency. |
| scheduled | Retry or ETA is pending. | Check retry/backoff and expected delay. |
| absent | Task not known to worker inspect. | Check queue topology and broker rows. |

## Restart Safety

Safe restart conditions:

| Condition | Reason |
| --- | --- |
| No active tasks and no reserved task for the incident queue. | Lowest duplicate-processing risk. |
| Failure is already persisted to `worker_failed_jobs`. | You can diagnose before restarting. |
| Idempotency key is known and protected by DB uniqueness. | Duplicate dispatch should not duplicate truth. |

Unsafe restart conditions:

| Condition | Risk |
| --- | --- |
| Active B2.3 match or attribution task with unknown idempotency key. | Duplicate financial processing. |
| Reserved task backlog with `acks_late` behavior. | Re-delivery may happen after worker loss. |
| Missing tenant context in task kwargs or DLQ. | RLS zero rows or cross-tenant investigation risk. |
| Webhook signature or idempotency incident unresolved. | Restart does not repair authenticity or duplicate root cause. |

## Common Failure Signatures

`OperationalError` or connection timeout means inspect Postgres service and
broker DSN. `MissingTenantContextError` means tenant context propagation failed.
Repeated `IntegrityError` on idempotency constraints usually means duplicate
dispatch is being handled by the database and should be investigated through the
webhook runbook, not retried blindly. A B2.3 task failure persisted to DLQ means
switch to [B2.3 match diagnosis](b23_match_diagnosis.md) after inspecting the
DLQ row.
