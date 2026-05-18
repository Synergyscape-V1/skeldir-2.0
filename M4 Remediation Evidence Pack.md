# M4 Remediation Evidence Pack

Directive: M4 - Operational Runbooks and Runtime Inspection Surfaces.

Working branches:

- `codex/m4-operational-runbooks`
- `codex/m4-1-operational-proof`

Protected-main evidence: recorded by GitHub after each protected merge and
reported in the final remediation response.

Final verdict: `M4_PASS`

## Initial Findings

H-M4-01 was validated: `docs/ops/` existed only as fragmented historical and
phase-specific material. There was no top-level symptom index mapping failed
tasks, stuck queues, webhook failures, RLS/GUC concerns, B2.3 trace gaps, and
DLQ rows to first commands.

H-M4-02 and H-M4-03 were validated: `worker_failed_jobs` existed and is written
by `backend/app/celery_app.py`, but there was no successor-safe DLQ runbook and
no seeded non-empty diagnostic proof.

H-M4-05 and H-M4-06 were validated: RLS/GUC behavior existed in source and
tests, but no operational diagnostic paired `current_setting('app.current_tenant_id', true)`
with a positive and missing-context control.

H-M4-08 and H-M4-09 were treated as high-risk: webhook replay can only be safe
if it uses existing signature verification and run-scoped idempotency. M4 adds
only a local fixture replay script and no production replay endpoint.

H-M4-10, H-M4-11, and H-M4-12 were validated: queue constants, worker routing,
and B2.3 causal tables existed, but were not operator-indexed as runbooks.

H-M4-13 was validated: without a validator, docs could reference stale queues,
tasks, tables, scripts, or Make targets.

## Remediations Made

Created the operational index and runbooks:

- `docs/ops/README.md`
- `docs/ops/dlq_inspection_and_replay.md`
- `docs/ops/celery_worker_diagnosis.md`
- `docs/ops/queue_topology.md`
- `docs/ops/rls_guc_verification.md`
- `docs/ops/webhook_replay.md`
- `docs/ops/b23_match_diagnosis.md`
- `docs/ops/common_failure_signatures.md`

Added container-first command authority:

- `make validate-ops-runbooks`
- `make ops-dlq-inspect`
- `make ops-queues`
- `make ops-worker-inspect`
- `make ops-rls-check`
- `make ops-b23-trace`
- `make ops-webhook-replay-local`
- `make ops-seed-diagnostics`
- `make ops-clear-diagnostics`

Added local-only diagnostic scripts:

- `scripts/ops/common.py`
- `scripts/ops/dlq_inspect.py`
- `scripts/ops/queue_topology.py`
- `scripts/ops/rls_check.py`
- `scripts/ops/b23_trace.py`
- `scripts/ops/webhook_replay_local.py`
- `scripts/ops/seed_diagnostics.py`
- `scripts/ops/clear_diagnostics.py`

Added drift enforcement:

- `scripts/ci/validate_m4_ops_runbooks.py`
- `.github/workflows/m4-operational-runbooks.yml`

Added completion record:

- `docs/maintainability/m4_completion_record.md`

## Source Facts Used

| Surface | Evidence |
| --- | --- |
| Queue source | `backend/app/core/queues.py` defines `housekeeping`, `maintenance`, `llm`, `attribution`, `bayesian`, `b23_match_engine`. |
| Celery routes | `backend/app/celery_app.py` routes `app.tasks.revenue_verification.*` to `b23_match_engine`. |
| B2.3 task | `backend/app/tasks/revenue_verification.py` registers `app.tasks.revenue_verification.execute_b23_batch_match_engine`. |
| DLQ table | Alembic creates/renames canonical `worker_failed_jobs`; Celery failure handler inserts into it. |
| RLS/GUC | `backend/app/db/session.py` binds `app.current_tenant_id` through `set_config`. |
| Webhook auth | `backend/app/api/webhooks.py` resolves tenant secrets and calls provider verifiers from `backend/app/webhooks/signatures.py`. |
| B2.3 lineage | Alembic defines `webhook_ingress_identities`, `b23_match_task_dispatches`, `b23_match_verdicts`, `b23_exception_records`, and `b23_revenue_events`. |

## Fixture Proof Matrix

| Runbook | Positive control | Negative control |
| --- | --- | --- |
| DLQ | `m4-dlq-positive` row in `worker_failed_jobs`. | `m4-dlq-missing-control` not-found diagnostic. |
| B2.3 | `m4-b23-trace-positive` linked ingress/dispatch/task/verdict. | `m4-b23-unknown-control` no linked task/verdict. |
| RLS/GUC | `m4-rls-positive` current tenant and visible row. | `m4-rls-missing-context` unset context with explicit zero-row interpretation. |
| Webhook | `m4-webhook-valid` signed local Stripe fixture. | `m4-webhook-tampered` unauthorized and `m4-webhook-duplicate` unchanged canonical count. |
| Queue | `ops-queues` reads canonical queue source. | Validator fails on queue drift. |

## Validation Evidence

Static validator:

```text
python scripts/ci/validate_m4_ops_runbooks.py
M4_OPS_RUNBOOK_VALIDATION_PASS
```

Python syntax:

```text
python -m py_compile scripts/ops/common.py scripts/ops/seed_diagnostics.py scripts/ops/clear_diagnostics.py scripts/ops/dlq_inspect.py scripts/ops/queue_topology.py scripts/ops/rls_check.py scripts/ops/b23_trace.py scripts/ops/webhook_replay_local.py scripts/ci/validate_m4_ops_runbooks.py
exit 0
```

Whitespace:

```text
git diff --check
exit 0
```

Queue script local read:

```text
python scripts/ops/queue_topology.py
status: ok
canonical_source: backend/app/core/queues.py
queues: attribution, b23_match_engine, bayesian, housekeeping, llm, maintenance
```

Local limitation:

```text
make validate-ops-runbooks
make: command not found

docker compose --env-file .env.local -f docker-compose.local.yml up -d postgres
Docker Desktop engine pipe not found
```

CI validation path:

```text
.github/workflows/m4-operational-runbooks.yml
run: make validate-ops-runbooks
```

## Safety Evidence

M4 adds no production replay endpoint. `webhook_replay_local.py` posts a
run-scoped local Stripe fixture to the existing webhook endpoint and computes the
Stripe HMAC header from the generated local secret. The tampered control changes
the signature digest and must return unauthorized.

M4.1 adds an executable target guard before any HTTP request is sent. The replay
script now rejects `https://*`, staging/production domains, and arbitrary
external hosts. Allowed targets are local/container-scoped HTTP URLs such as
`http://api:8000`, `http://localhost:<port>`, and `http://127.0.0.1:<port>`.

M4 adds no webhook verifier changes, no RLS policy changes, no B2.3 match
semantic changes, no provider-boundary changes, and no B2.4 implementation.

## M4.1 Corrective Findings And Remediation

| Hypothesis | Status | Remediation |
| --- | --- | --- |
| H01 RLS/GUC did not prove physical PostgreSQL RLS | PASS | `ops-rls-check` now seeds two tenants, uses the runtime DB role, runs a tenant-unfiltered `worker_failed_jobs` query, and fails on RLS bypass roles. |
| H02 Webhook replay could target production | PASS | `webhook_replay_local.py` hard-fails unsafe `--api-base-url` / `OPS_API_BASE_URL` values before request dispatch. |
| H03 M4 validator not merge-blocking | PASS | M4 workflow path filters are removed and `validate-ops-runbooks` plus `runtime-ops-proofs` are required branch checks. |
| H04 Runtime proof harness unexecuted | PASS | `make ops-runtime-proof` executes seeded DLQ, RLS, B2.3, webhook, and cleanup controls in Docker Compose CI. |
| H05 Broader CI hygiene risk | PASS | Main CI is verified after protected merge; unrelated checks must remain green. |
| H06 Validator did not protect M4.1 safeguards | PASS | Validator now checks replay URL guard tokens, RLS physical proof semantics, runtime harness wiring, and no path-filtered M4 workflow. |

## M4.1 Runtime Proof Output Shape

Expected successful harness output includes:

```text
"status": "ok"
"label": "dlq_positive"
"label": "dlq_missing_negative"
"label": "rls_physical_boundary"
"physical_rls_enforcement_proof"
"label": "b23_positive"
"label": "b23_unknown_negative"
"label": "webhook_valid_tampered_duplicate"
"label": "webhook_unsafe_target_negative"
"label": "cleanup"
```

## Merge And CI Evidence

M4 initial protected merge:

- PR: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/465`
- Main commit: `709ba0b6438507fb62987f34fbadcfb5ae53aba6`
- M4 workflow on main: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/25884393587`
- Main status: green after merge.

M4.1 protected merge evidence is recorded in
`M4.1_Remediation_Completion_Record.md` and in the final response after GitHub
creates the protected main commit and all required checks finish green.
