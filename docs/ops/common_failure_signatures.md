# Common Failure Signatures

Each signature lists the first safe command and the next operational branch.

## Safety

Do not treat a zero-row result, empty queue, or idempotent duplicate response as
proof by itself. Each branch below pairs the command with expected output and
the next diagnostic check.

| Signature | Symptom | Likely cause | First command | Expected output | Next branch | Related runbook | command_class | execution_context |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| database unavailable | API or worker logs show connection timeout. | Postgres container down, wrong DSN, pool exhaustion. | `make health` | Readiness fails or reports DB unhealthy. | Start `make dev`, inspect migrations. | [Celery worker diagnosis](celery_worker_diagnosis.md) | read_only_inspection | container_api |
| migration mismatch | Table or column missing in diagnostics. | Alembic head not applied. | `make migrate` | Migration reaches head. | Rerun failed diagnostic. | [RLS/GUC verification](rls_guc_verification.md) | read_only_inspection | container_api |
| tenant GUC missing | `current_setting` empty. | Session did not bind tenant context. | `make ops-rls-check` | Negative control reports missing context and zero rows. | Inspect `backend/app/db/session.py` path. | [RLS/GUC verification](rls_guc_verification.md) | read_only_inspection | container_api |
| RLS denied / zero rows | Known row not visible. | Wrong tenant or missing GUC. | `make ops-rls-check` | Positive control sees one seeded row; negative sees zero. | Verify tenant ID and transaction boundary. | [RLS/GUC verification](rls_guc_verification.md) | read_only_inspection | container_api |
| webhook signature invalid | 401 from webhook endpoint. | Bad HMAC/RSA header, missing tenant key, wrong secret. | `make ops-webhook-replay-local` | Tampered control returns unauthorized. | Separate tenant lookup from signature construction. | [Webhook replay](webhook_replay.md) | local_fixture_replay | container_network_curl |
| idempotency duplicate | Replay accepted but no new event. | Duplicate key handled by DB/service idempotency. | `make ops-webhook-replay-local` | Duplicate control count is unchanged after second replay. | Trace existing event and dispatch. | [Webhook replay](webhook_replay.md) | duplicate_detection_probe | container_network_curl |
| Celery broker unavailable | Worker cannot inspect or logs broker errors. | Postgres broker DSN unavailable. | `make ops-worker-inspect` | Inspect fails or returns no worker response. | Check Postgres service and worker logs. | [Celery worker diagnosis](celery_worker_diagnosis.md) | read_only_inspection | container_celery |
| worker not consuming queue | Task dispatch exists but no active/reserved/scheduled task. | Wrong queue binding or worker offline. | `make ops-queues` | Queue source includes incident queue. | Run worker inspect and logs. | [Queue topology](queue_topology.md) | read_only_inspection | container_api |
| task failed and persisted to DLQ | `worker_failed_jobs` row exists. | Task exception after retry. | `make ops-dlq-inspect` | Seeded row returns task ID, queue, error, retry count, timestamp. | Classify replayability and root cause. | [DLQ inspection](dlq_inspection_and_replay.md) | read_only_inspection | container_api |
| B2.3 match verdict missing | Webhook accepted but no verdict. | No ingress, no dispatch, worker failure, or match kernel failure. | `make ops-b23-trace` | Positive fixture returns linked ingress/dispatch/verdict. | Follow B2.3 decision tree. | [B2.3 match diagnosis](b23_match_diagnosis.md) | read_only_inspection | container_api |
| state transition stale/pending | Verdict remains `pending` or provisional past expected window. | Transition task not running or exception path open. | `make ops-b23-trace` | Trace shows verdict status and transition timestamp. | Inspect transition tasks and exceptions. | [B2.3 match diagnosis](b23_match_diagnosis.md) | read_only_inspection | container_api |
| pooler transaction context issue | Direct DB works, pooler path returns zero rows. | GUC not bound inside same transaction. | `make ops-rls-check` | Current setting appears in same output as row count. | Reproduce through M2 pooler tests. | [RLS/GUC verification](rls_guc_verification.md) | read_only_inspection | container_api |

## Command Metadata

```yaml
command: make health
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
idempotency_sensitive: false
signature_sensitive: false
```

```yaml
command: make migrate
execution_context: container_api
command_class: read_only_inspection
requires_seeded_fixture: false
mutates_state: false
tenant_scope_required: false
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
