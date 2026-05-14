# RLS/GUC Verification

`app.current_tenant_id` is the Postgres session setting used by tenant-scoped
RLS policies. API sessions and B2.3 worker sessions bind it transaction-locally
through `backend/app/db/session.py`.

## Command

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

Seed and cleanup:

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
command: make ops-clear-diagnostics
execution_context: container_api
command_class: local_fixture_replay
requires_seeded_fixture: true
mutates_state: local_fixture_only
tenant_scope_required: true
idempotency_sensitive: true
signature_sensitive: true
```

## SQL Signal

The required diagnostic signal is:

`current_setting('app.current_tenant_id', true)`

The runbook command prints this value beside seeded row visibility. A zero-row
query without this setting is not a valid health proof.

## Positive Control

Fixture: `m4-rls-positive`.

Expected healthy output:

| Signal | Expected |
| --- | --- |
| `tenant_context` | The seeded tenant UUID. |
| `visible_seeded_dlq_rows` | `1` for the seeded `worker_failed_jobs` row. |
| `status` | `ok`. |

## Missing-Context Negative Control

Fixture: `m4-rls-missing-context`.

Expected output:

| Signal | Expected |
| --- | --- |
| `tenant_context` | Empty or unset value from `current_setting('app.current_tenant_id', true)`. |
| `visible_seeded_dlq_rows` | `0`. |
| `interpretation` | Explicit text saying zero rows are defensive behavior, not proof of health. |

## Direct DB vs Pooler Notes

Direct database sessions keep session settings until reset unless transaction
local binding is used. Transaction-pooler sessions can move work between backend
connections, so operational checks must bind and read the GUC in the same
transaction path. Skeldir's runtime session code uses transaction-local binding
for API and B2.3 sessions; this aligns with the M2 direct/pooler tests.

## Transaction Boundary Warning

If a diagnostic sets tenant context and then opens a new transaction or uses a
different connection, the setting may not apply to the query being interpreted.
Always read `current_setting('app.current_tenant_id', true)` in the same command
output as the data query.

## Do Not Bypass RLS

Do not disable RLS, use superuser bypass behavior, or query tenant tables without
tenant context to "prove" isolation. Missing tenant context can produce defensive
zero rows, but that is only useful when the diagnostic reports the missing GUC
explicitly.
