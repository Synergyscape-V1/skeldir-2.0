# M4 Operational Runbooks

This directory is the successor-safe entry point for Skeldir runtime diagnosis.
Canonical local commands are Make targets that execute through Docker Compose
services. Host-native commands are not local authority unless a runbook labels
them `manual_local_host_debug` or `manual_production_diagnostic`.

## Symptom Index

| Symptom | First command | Runbook | First branch |
| --- | --- | --- | --- |
| failed task | `make ops-dlq-inspect` | [DLQ inspection and replay safety](dlq_inspection_and_replay.md) | Classify retryable, non-replayable, or manual forensics. |
| stuck queue | `make ops-queues` | [Queue topology](queue_topology.md) | Confirm queue ownership, then inspect worker active/reserved/scheduled. |
| worker offline | `make ops-worker-inspect` | [Celery worker diagnosis](celery_worker_diagnosis.md) | If inspect cannot reach the worker, inspect container logs and broker DB. |
| missing match verdict | `make ops-b23-trace` | [B2.3 match diagnosis](b23_match_diagnosis.md) | Check ingress, dispatch, task, verdict, then DLQ. |
| webhook accepted but no downstream task | `make ops-b23-trace` | [Webhook replay](webhook_replay.md) and [B2.3 match diagnosis](b23_match_diagnosis.md) | Check webhook ingress identity before Celery dispatch. |
| webhook rejected | `make ops-webhook-replay-local` | [Webhook replay](webhook_replay.md) | Separate auth failure from payload failure. |
| tenant isolation concern | `make ops-rls-check` | [RLS/GUC verification](rls_guc_verification.md) | Compare current_setting with fixture row visibility. |
| RLS/GUC missing context | `make ops-rls-check` | [RLS/GUC verification](rls_guc_verification.md) | Missing context must be reported beside zero-row behavior. |
| duplicate idempotency issue | `make ops-webhook-replay-local` | [Webhook replay](webhook_replay.md) | Confirm duplicate replay does not create another canonical event. |
| DLQ row present | `make ops-dlq-inspect` | [DLQ inspection and replay safety](dlq_inspection_and_replay.md) | Interpret task args/kwargs and protected truth impact. |
| pooler/transaction context issue | `make ops-rls-check` | [RLS/GUC verification](rls_guc_verification.md) | Treat transaction-local GUC scope as the first suspect. |

## Command Metadata

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

```yaml
command: make ops-rls-check
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: true
mutates_state: false
tenant_scope_required: true
idempotency_sensitive: false
signature_sensitive: false
```

```yaml
command: make ops-b23-trace
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: true
mutates_state: false
tenant_scope_required: true
idempotency_sensitive: false
signature_sensitive: false
```

```yaml
command: make ops-webhook-replay-local
execution_context: container_network_curl
command_class: local_fixture_replay
requires_seeded_fixture: true
mutates_state: local_fixture_only
tenant_scope_required: true
idempotency_sensitive: true
signature_sensitive: true
```

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

## Fixture Contract

`make ops-seed-diagnostics` creates a run-scoped synthetic tenant, a
`worker_failed_jobs` row, a B2.3 ingress/dispatch/verdict chain, an RLS/GUC
positive control, and local signed webhook replay material. The material is
stored under `.tmp/m4_ops/` and is removed by `make ops-clear-diagnostics`.

Required fixture IDs:

| Fixture | Proof |
| --- | --- |
| `m4-dlq-positive` | Seeded `worker_failed_jobs` row with task, queue, error type, retry count, timestamp. |
| `m4-dlq-missing-control` | Explicit not-found diagnostic for unknown task ID. |
| `m4-b23-trace-positive` | Linked ingress -> dispatch -> task -> verdict row. |
| `m4-b23-unknown-control` | Explicit no linked task/verdict diagnostic. |
| `m4-rls-positive` | `current_setting('app.current_tenant_id', true)` equals the fixture tenant and row is visible. |
| `m4-rls-missing-context` | Missing context is reported beside defensive zero-row behavior. |
| `m4-webhook-valid` | Existing Stripe HMAC verifier accepts a local signed fixture. |
| `m4-webhook-tampered` | Tampered signature returns unauthorized. |
| `m4-webhook-duplicate` | Reusing the run-scoped idempotency key does not create another canonical event. |

## Safety Doctrine

Read-only inspection commands must not mutate deterministic truth. Local fixture
replay commands may mutate only rows owned by the synthetic M4 tenant. Production
payload replay is forbidden in M4; a production incident may use these runbooks
for diagnosis, but replay requires a separate operational approval path outside
this repository surface.
