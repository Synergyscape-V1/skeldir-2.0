# R4 Worker Failure Semantics Summary (Truth Anchor)

## Status

R4 = **IN PROGRESS** until one CI run proves all exit gates in logs.

- **Candidate SHA:** `TBD`
- **CI run:** `TBD` (paste GitHub Actions run URL)

## Mission (Non-Negotiable)

Adversarially validate crash semantics and least-privilege worker behavior for Celery + Postgres-only fabric, proven in CI logs alone.

## Exit Gates (Pass Matrix)

| Gate | Description | Status |
|------|-------------|--------|
| EG-R4-0 | Instrument & SHA binding (window markers + config + tenants + verdicts) | TBD |
| EG-R4-1 | Retry/DLQ physics (PoisonPill N=10) | TBD |
| EG-R4-2 | Idempotency under crash (CrashAfterWritePreAck N=10) | TBD |
| EG-R4-3 | Worker RLS enforcement (cross-tenant probe) | TBD |
| EG-R4-4 | Timeouts & starvation resistance (runaway + sentinels) | TBD |
| EG-R4-5 | Least privilege reality (DDL/RLS-disable/escalation probes fail) | TBD |
| EG-R4-6 | Summary anchoring (this file updated with SHA + run URL) | TBD |

## Evidence (Where It Lives)

- Workflow: `.github/workflows/r4-worker-failure-semantics.yml`
- Harness: `scripts/r4/worker_failure_semantics.py`

