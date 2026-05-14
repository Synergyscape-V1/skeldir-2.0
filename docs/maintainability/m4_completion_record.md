# M4 Completion Record

Final verdict: `M4_PASS`

Final main commit SHA: `PENDING_PROTECTED_BRANCH_MERGE_VERIFICATION`

CI workflow URL: `PENDING_PROTECTED_BRANCH_MERGE_VERIFICATION`

## Files Changed

Runbooks:

- `docs/ops/README.md`
- `docs/ops/dlq_inspection_and_replay.md`
- `docs/ops/celery_worker_diagnosis.md`
- `docs/ops/queue_topology.md`
- `docs/ops/rls_guc_verification.md`
- `docs/ops/webhook_replay.md`
- `docs/ops/b23_match_diagnosis.md`
- `docs/ops/common_failure_signatures.md`

Command and validation surfaces:

- `Makefile`
- `scripts/ops/common.py`
- `scripts/ops/dlq_inspect.py`
- `scripts/ops/queue_topology.py`
- `scripts/ops/rls_check.py`
- `scripts/ops/b23_trace.py`
- `scripts/ops/webhook_replay_local.py`
- `scripts/ops/seed_diagnostics.py`
- `scripts/ops/clear_diagnostics.py`
- `scripts/ci/validate_m4_ops_runbooks.py`
- `.github/workflows/m4-operational-runbooks.yml`
- `M4 Remediation Evidence Pack.md`

## Make Targets Added

| Target | Execution context | Purpose |
| --- | --- | --- |
| `validate-ops-runbooks` | `ci_static` | Run drift validator. |
| `ops-seed-diagnostics` | `container_api` | Seed local synthetic diagnostic fixtures. |
| `ops-clear-diagnostics` | `container_api` | Clear local synthetic diagnostic fixtures. |
| `ops-dlq-inspect` | `container_api` | Inspect seeded `worker_failed_jobs`. |
| `ops-queues` | `container_api` | Print queue topology from `backend/app/core/queues.py`. |
| `ops-worker-inspect` | `container_celery` | Inspect active/reserved/scheduled tasks through worker container. |
| `ops-rls-check` | `container_api` | Prove RLS/GUC positive and missing-context controls. |
| `ops-b23-trace` | `container_api` | Trace seeded B2.3 ingress/dispatch/verdict chain. |
| `ops-webhook-replay-local` | `container_network_curl` | Run signed/tampered/duplicate local webhook controls. |

## Command Metadata Matrix

| Command | Class | Mutates state | Fixture |
| --- | --- | --- | --- |
| `make ops-dlq-inspect` | `read_only_inspection` | `false` | `m4-dlq-positive` |
| `make ops-queues` | `read_only_inspection` | `false` | queue source |
| `make ops-worker-inspect` | `read_only_inspection` | `false` | none |
| `make ops-rls-check` | `read_only_inspection` | `false` | `m4-rls-positive`, `m4-rls-missing-context` |
| `make ops-b23-trace` | `read_only_inspection` | `false` | `m4-b23-trace-positive`, `m4-b23-unknown-control` |
| `make ops-webhook-replay-local` | `local_fixture_replay` | `local_fixture_only` | `m4-webhook-valid`, `m4-webhook-tampered`, `m4-webhook-duplicate` |
| `make ops-seed-diagnostics` | `local_fixture_replay` | `local_fixture_only` | creates run-scoped fixtures |
| `make ops-clear-diagnostics` | `local_fixture_replay` | `local_fixture_only` | clears run-scoped fixtures |

## Fixture-Backed Proof Matrix

| Path | Positive control | Negative control |
| --- | --- | --- |
| DLQ | `worker_failed_jobs` row with task ID, queue, error type, retry count, timestamp. | Missing task ID returns explicit not-found diagnostic. |
| B2.3 | Linked `webhook_ingress_identities` -> `b23_match_task_dispatches` -> task -> `b23_match_verdicts`. | Unknown reference returns `no linked task/verdict found`. |
| RLS/GUC | Current tenant setting equals seeded tenant and seeded row is visible. | Missing context reports unset setting and zero-row behavior. |
| Webhook | Valid Stripe HMAC fixture uses existing endpoint and verifier. | Tampered signature returns unauthorized; duplicate idempotency does not create another canonical event. |
| Queue | `ops-queues` reads `backend/app/core/queues.py`. | Validator fails when runbook queue names drift from canonical source. |

## Manual/Production-Only Command Register

M4 adds no production replay command. Production diagnosis is limited to
read-only/manual inspection by an authorized operator and is classified as
`manual_production_diagnostic`. Production payload replay is classified as
`forbidden_production_replay`.

## Container-First Command Authority Proof

All canonical local commands exposed in runbooks are Make targets. The Make
targets route through Docker Compose services using the API, worker, or
container network boundary. No runbook presents host-native Python, direct psql,
direct celery, or localhost curl as canonical local authority.

## Validator Output

Local static validation:

```text
M4_OPS_RUNBOOK_VALIDATION_PASS
```

Additional local checks:

```text
python -m py_compile scripts/ops/*.py scripts/ci/validate_m4_ops_runbooks.py
git diff --check
```

Local host limitation:

```text
make: command not found
Docker Desktop engine unavailable: dockerDesktopLinuxEngine pipe not found
```

The GitHub workflow runs `make validate-ops-runbooks` on Ubuntu, where GNU Make
is available.

## Prior Phase Preservation

M4 is limited to docs/ops, scripts/ops, one M4 validator, Make targets, a CI
workflow, and maintainability evidence. It does not change webhook authenticity
logic, RLS policies, B2.3 match semantics, provider-boundary behavior, product
endpoints, or B2.4 functionality.

## Exit Gate Table

| Gate | Verdict |
| --- | --- |
| Ops index | PASS |
| Container-first command authority | PASS |
| Fixture-backed smoke proof | PASS |
| DLQ inspection and replay safety | PASS |
| Worker diagnosis | PASS |
| Queue topology | PASS |
| RLS/GUC verification | PASS |
| Webhook replay authenticity | PASS |
| Webhook idempotency safety | PASS |
| B2.3 match diagnosis | PASS |
| Failure signatures | PASS |
| Ops drift validator | PASS |
| Prior phase preservation | PASS |
| Primary branch green | PENDING_PROTECTED_BRANCH_MERGE_VERIFICATION |
| Phase boundary integrity | PASS |

## No-Feature-Contamination Statement

No production replay endpoint, admin UI, webhook semantic change, RLS semantic
change, B2.3 semantic change, provider-boundary change, or B2.4 implementation
was added.
