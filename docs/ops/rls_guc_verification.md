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
query without this setting is not a valid health proof unless the same output
also proves the database role is RLS-applicable.

M4.1 separates two signals:

1. GUC binding: `current_setting('app.current_tenant_id', true)` changes as
   expected for tenant A, tenant B, and missing context.
2. Physical PostgreSQL RLS enforcement: a tenant-unfiltered query against
   `worker_failed_jobs` returns only the row visible to the bound tenant.

## Positive Control

Fixture: `m4-rls-positive`.

Expected healthy output:

| Signal | Expected |
| --- | --- |
| `tenant_context` | The seeded tenant UUID. |
| `visible_seeded_dlq_rows` | `1` for the seeded `worker_failed_jobs` row. |
| `status` | `ok`. |

## Physical RLS Enforcement Control

Fixture: `m4-rls-bare-select-isolation`.

The diagnostic seeds two tenants and two tenant-scoped `worker_failed_jobs`
rows. It then connects through the runtime database URL, not the migration URL,
and runs this query shape:

```sql
SELECT task_id, tenant_id
FROM public.worker_failed_jobs
WHERE task_id IN (<tenant_a_task>, <tenant_b_task>);
```

There is intentionally no `tenant_id = ...` predicate. Expected output:

| Bound context | Expected rows |
| --- | --- |
| tenant A | Exactly the tenant A fixture row. |
| tenant B | Exactly the tenant B fixture row. |
| missing context | Zero fixture rows. |

The command also reports `current_user`, `rolsuper`, `rolbypassrls`,
`relrowsecurity`, `relforcerowsecurity`, and table owner. The proof fails if the
runtime role is superuser, has `BYPASSRLS`, owns the table without forced RLS, or
the table does not have RLS enabled.

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

Do not disable RLS or use superuser bypass behavior. M4's diagnostic does query
without a tenant predicate, but only against synthetic fixture task IDs and only
to prove that PostgreSQL RLS is the physical isolation boundary.
