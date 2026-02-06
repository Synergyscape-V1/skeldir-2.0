# B0.7-P2 Remediation Evidence (Runtime Proof + Redaction + Fail-Fast)

Date: 2026-02-06
Branch: main
Status: Draft (CI artifacts captured)
Target: Continuous runtime proof (broker + worker + DB write) and secrets redaction hardening

## Purpose
Establish a non-vacuous CI runtime chain for LLM task consumption and enforce secrets hygiene before provider enablement.

## Scientific Approach
This document uses falsifiable hypotheses, deterministic probes, and artifact-backed observations. All findings must point to CI artifacts or code paths. Until CI runs, hypotheses remain unverified.

## Hypotheses (H-P2-01..06)
H-P2-01: CI enqueues a real LLM task and the worker consumes it (non-vacuous runtime chain).
H-P2-02: Worker write succeeds under P1 RLS + identity (tenant_id + user_id), and cross-tenant/user reads are denied.
H-P2-03: Celery queue routing includes `llm` and the worker is subscribed to it in the CI proof.
H-P2-04: Centralized redaction prevents canary secrets from leaking to logs (worker + lifecycle logs).
H-P2-05: Provider enablement fails fast at config init if key is missing.
H-P2-06: CI uploads sanitized artifacts that can be audited post-run.

## Probe Design (Deterministic Tests)
1. Runtime chain proof
- Test: `backend/tests/integration/test_b07_p2_runtime_chain_e2e.py`
- Mechanism: enqueue LLM explanation task via `enqueue_llm_task`, poll DB for `llm_api_calls` row by deterministic `request_id`, assert required columns non-null.
- Falsification: fails if task not consumed, DB write blocked, or schema fields missing.

2. RLS/identity enforcement
- Test: `backend/tests/integration/test_b07_p2_runtime_chain_e2e.py`
- Mechanism: attempt reads with wrong tenant/user GUCs and assert zero rows.
- Falsification: returns row under wrong identity.

3. Redaction gate
- Test: `backend/tests/integration/test_b07_p2_runtime_chain_e2e.py`
- Canary: `B07_P2_LOG_CANARY=skeldir_test_secret_123`
- Mechanism: `app.tasks.observability_test.redaction_canary` logs `LLM_PROVIDER_API_KEY=<canary>` and `Bearer <canary>`; assert only redacted tokens appear.
- Falsification: canary appears in logs.

4. Fail-fast provider gate
- Test: `backend/tests/test_b07_p2_provider_enablement.py`
- Mechanism: set `LLM_PROVIDER_ENABLED=true` without key and expect config init failure.
- Falsification: config loads without exception.

## CI Harness (Runtime Oracle)
- Workflow: `.github/workflows/ci.yml`
- Job: `b07-p2-runtime-proof` (B0.7 P2 Runtime Proof)
- Key env:
  - `DATABASE_URL=postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_b07_p2`
  - `B07_P2_RUNTIME_DATABASE_URL=postgresql://app_user:app_user@127.0.0.1:5432/skeldir_b07_p2`
  - `CELERY_BROKER_URL=sqla+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_b07_p2`
  - `CELERY_RESULT_BACKEND=db+postgresql://app_user:app_user@127.0.0.1:5432/skeldir_b07_p2`
  - `SKELDIR_TEST_TASKS=1`

## Evidence Artifacts (Expected Paths)
These artifacts are produced by the CI job and should be attached to the run:
- `artifacts/b07-p2/pytest.log`
- `artifacts/b07-p2/worker.log`
- `artifacts/b07-p2/runtime_db_probe.json`
- `artifacts/b07-p2/redaction_probe.json`

## Observations (CI Run 21759002041 on main)
Run metadata (GitHub Actions API):
- Workflow run ID: `21759002041`
- Head SHA: `6ed5ab11e040df520aae1dcc0c12beac5e9d66f3`
- Trigger: `workflow_dispatch`
- Run start (UTC): 2026-02-06T17:05:16Z
- Conclusion: failure (other jobs failed), but `B0.7 P2 Runtime Proof (LLM + Redaction)` succeeded.

B0.7 P2 job status:
- Job: `B0.7 P2 Runtime Proof (LLM + Redaction)` (job_id: 62777232343)
- Conclusion: success
- Provider enablement unit gate step succeeded.
- Runtime chain proof step succeeded.
- Artifact upload step succeeded.

Artifact presence:
- Artifact `b07-p2-runtime-proof` exists for this run.
- Files inspected:
  - `runtime_db_probe.json`
  - `redaction_probe.json`
  - `worker.log`
  - `pytest.log`

Required confirmations (artifact-backed):
1. Runtime chain proof
- `runtime_db_probe.json` contains:
  - `request_id`: `b07-p2-59dc2d50`
  - `tenant_id`: `59dc2d50-f6ef-4e8b-b4fd-b30f7576c7eb`
  - `user_id`: `3bf78e6a-b56a-4a3f-acc3-c976ac994d36`
  - `provider`: `stub`
  - `distillation_eligible`: `false`
  - `endpoint`: `app.tasks.llm.explanation`

2. RLS enforcement
- `pytest.log` shows `test_b07_p2_runtime_llm_chain_with_redaction` passed with cross-tenant/user read assertions.

3. Redaction
- `redaction_probe.json` reports `canary_present=false`, `redacted_key_present=true`, `redacted_bearer_present=true`.
- `worker.log` shows redacted markers:
  - `LLM_PROVIDER_API_KEY=***`
  - `Authorization: Bearer ***`

4. Fail-fast provider gate
- `pytest.log` shows `test_b07_p2_provider_enablement.py` executed and passed before the runtime chain proof.

5. Artifact audit gate
- CI artifacts uploaded under `b07-p2-runtime-proof`.

## Code Changes (Ground Truth References)
- `backend/app/observability/logging_config.py`:
  - Adds centralized redaction filter for structured JSON logs and exceptions.
- `backend/app/observability/celery_task_lifecycle.py`:
  - Applies redaction filter to raw lifecycle JSON logs.
- `backend/app/core/config.py`:
  - Adds `LLM_PROVIDER_ENABLED` + `LLM_PROVIDER_API_KEY` and fail-fast validation.
- `backend/app/tasks/observability_test.py`:
  - Adds redaction canary task for deterministic log proof.
- `backend/tests/integration/test_b07_p2_runtime_chain_e2e.py`:
  - Runtime chain, RLS, and redaction validation with artifact outputs.
- `backend/tests/test_b07_p2_provider_enablement.py`:
  - Fails fast when provider enabled without key.
- `.github/workflows/ci.yml`:
  - Adds `b07-p2-runtime-proof` job with artifact uploads.

## Exit Gates Mapping
- EG-P2-1 Runtime Consume Gate: `test_b07_p2_runtime_chain_e2e.py` + `runtime_db_probe.json`.
- EG-P2-2 Schema + Identity Gate: `runtime_db_probe.json` + RLS assertions.
- EG-P2-3 No-Leak Redaction Gate: `redaction_probe.json` + `worker.log`.
- EG-P2-4 Fail-Fast Secrets Gate: `test_b07_p2_provider_enablement.py`.
- EG-P2-5 CI Artifact Audit Gate: `b07-p2-runtime-proof` artifact upload.

## Next Evidence Capture Steps
1. Optional: capture checksums for `runtime_db_probe.json`, `redaction_probe.json`, and `worker.log`.
2. If related code changes occur, re-run CI on `main` and refresh this document with new artifacts.
