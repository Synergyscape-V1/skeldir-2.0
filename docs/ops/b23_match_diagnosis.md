# B2.3 Match Diagnosis

B2.3 is the deterministic bridge from verified commerce ingress to match
verdicts. LLMs do not compute or repair this path.

## Causal Spine

`webhook ingress -> persisted event -> Celery dispatch -> app.tasks.revenue_verification.execute_b23_batch_match_engine -> batch engine -> match kernel -> b23_match_verdicts -> exception/state transition`

Operator-facing tables:

| Step | Table or source | Signal |
| --- | --- | --- |
| Webhook ingress | `webhook_ingress_identities` | Provider reference, normalized commerce reference, authenticity state. |
| Persisted event | `attribution_events` | Event ID and idempotency key. |
| Task dispatch | `b23_match_task_dispatches` | Task ID, queue `b23_match_engine`, routing key. |
| Task execution | `worker_failed_jobs` when failed | Task error, retry count, correlation ID. |
| Verdict | `b23_match_verdicts` | Status, match quality, amount fields, transition timestamp. |
| Exception | `b23_exception_records` | Open discrepancy or alert state. |
| Ledger primitive | `b23_revenue_events` | Post-capture revenue event linked to verdict/ingress. |

## Commands

Trace seeded ingress/dispatch/verdict.

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

Inspect failed task rows if dispatch exists but verdict is missing.

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

Check queue ownership.

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

## Positive And Negative Controls

Positive control: `m4-b23-trace-positive` returns the seeded
`webhook_ingress_identity_id`, `task_id`, task name
`app.tasks.revenue_verification.execute_b23_batch_match_engine`, queue
`b23_match_engine`, and `match_verdict_id`.

Negative control: `m4-b23-unknown-control` returns `status: not_found` and the
diagnostic `no linked task/verdict found`.

## First Query, Next Query, Decision Tree

First query: run `make ops-b23-trace` with the seeded fixture or the incident
commerce reference.

Next branches:

| Observation | Next query | Meaning |
| --- | --- | --- |
| No ingress row | Webhook runbook. | Auth, payload validation, unsupported event family, or idempotency rejection prevented ingress. |
| Ingress row but no dispatch | API logs and `b23_match_task_dispatches`. | Natural dispatch disabled or failed before task persistence. |
| Dispatch row but no verdict | `make ops-dlq-inspect` and worker inspect. | Task failed, is scheduled/reserved, or worker is not consuming `b23_match_engine`. |
| Verdict pending too long | State transition task and exception records. | Transition sweep or match kernel did not progress. |
| Exception open | `b23_exception_records`. | Discrepancy band requires manual review. |
| RLS zero rows with known ID | `make ops-rls-check`. | Tenant context or pooler transaction scope issue. |

## Task And Queue Map

| Task | Queue | Producer |
| --- | --- | --- |
| `app.tasks.revenue_verification.execute_b23_batch_match_engine` | `b23_match_engine` | Webhook natural dispatch and explicit B2.3 batch execution. |
| `app.tasks.revenue_verification.transition_stale_pending_to_unmatched` | `b23_match_engine` | State transition sweep. |
| `app.tasks.revenue_verification.transition_stale_provisional_to_confirmed` | `b23_match_engine` | State transition sweep. |

## State Transition Map

`pending` can become `unmatched` when stale. `matched_provisional` can become
`matched_confirmed`. `adjusted` and `unmatched` require inspection of exception
records, discrepancy bands, and source revenue event history.

## Common Failure Signatures

Missing verdict with a dispatch row usually means worker failure or B2.3 DB pool
timeout. Missing dispatch with accepted webhook usually means no persisted
ingress identity, unsupported event family, disabled natural dispatch, or API
failure before task persistence. Match amount constraint failures belong in DLQ
and must not be manually repaired by editing verdict rows.

## Safety

Do not mutate `b23_match_verdicts`, `b23_revenue_events`, or
`webhook_ingress_identities` during incident diagnosis. M4 permits only
read-only inspection and local synthetic fixtures.
