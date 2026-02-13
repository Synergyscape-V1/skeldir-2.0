# B0.7 Phase 5 Compute Safety Proof Index

This index maps each Phase 5 exit gate to executable tests, CI enforcement points, and auditable artifacts.

## Adjudication Baseline (main)
- Merge commit: `b928e67a89264178bc15a29fa3f5cd9ba380a455` (PR #84)
- Main CI run: https://github.com/Muk223/skeldir-2.0/actions/runs/21995773671
- Phase 5 execution job: `B0.7 P2 Runtime Proof (LLM + Redaction)` (job `63555250970`)

## CI Contradiction Resolution (H5.1)
For run `21995773671`, Phase 5 gates did execute in `b07-p2-runtime-proof`:
- Step 17: `Enforce compute boundaries (EG5.9 static analysis)`
- Step 18: `EG5.9 non-vacuity self-test (boundary guard must fail on violation)`
- Step 20: `Run B0.7 P3 provider controls gate`
- Step 21: `Run B0.7 P5 Bayesian timeout runtime gate`
- Step 25: `Upload B0.7 P2 artifacts`
- Step 26: `Upload Phase 5 compute safety artifact bundle`

## Completion Criteria (Phase 5)
- Code containing Phase 5 controls/tests is merged to `main`.
- `main` CI is green.
- `b07-p2-runtime-proof` executes and uploads artifacts proving:
  - `artifacts/b07-p2/enforce_boundary.log`
  - `artifacts/b07-p2/enforce_boundary_selftest.log`
  - `artifacts/b07-p2/p3_controls.log`
  - `artifacts/b07-p2/p5_bayesian.log`
  - `artifacts/b07-p2/p5_bayesian_worker.log`
  - `artifacts/b07-p2/p5_bayesian_probe.jsonl`
  - `artifacts/b07-p2/p5_bayesian_runtime_proof.json`
  - `artifacts/b07-p2/manifest.sha256`
- Runtime DB identity checks pass under app runtime principal:
  - `current_user == RUNTIME_USER`
  - `rolsuper == false`

## EG5.1 Kill Switch Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_kill_switch_blocks_without_provider_attempt_non_vacuous`
- Negative control:
  - Same test invokes second request with `kill_switch=False` and asserts provider invocation occurs.
- Ledger proof:
  - Same test asserts blocked row spend is zero: `LLMApiCall.cost_cents == 0` and `LLMApiCall.cost_usd == 0`.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.2 Breaker Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_breaker_opens_after_three_failures`
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_breaker_open_blocks_without_provider_attempt_non_vacuous`
- Negative control:
  - Non-vacuous test flips `_breaker_open` closed and provider path is invoked.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.3 Hourly Shutoff Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_hourly_shutoff_distinct_from_monthly`
- Non-vacuity evidence:
  - Accepted calls occur before shutoff block in same test.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.4 Budget Reservation Concurrency Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_reservation_concurrency_safety`
- Non-vacuity evidence:
  - Mixed accepted/blocked outcomes and provider-attempt count equals accepted set.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.5 Retry Idempotency Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_retry_idempotency_no_double_debit`
- Non-vacuity evidence:
  - Forced failure + retry reuses same `api_call_id` and no duplicate reservation row.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.6 Timeout Enforcement Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_timeout_enforced`
- Negative control:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_timeout_non_vacuous_negative_control`.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.7 Provider Swap via Config-Only Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_provider_swap_config_only_proof`
- Non-vacuity evidence:
  - Same code path with config-only `LLM_PROVIDER_MODEL` change persists provider change (`openai` -> `anthropic`).
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.8 Bayesian Worker 5-Minute Timeout Gate
- Static production bound proof:
  - `backend/app/tasks/bayesian.py`
  - `PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S=270`
  - `PRODUCTION_BAYESIAN_TIME_LIMIT_S=300`
- Dynamic real-worker mechanism proof (reduced limits):
  - `backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py::test_b07_p5_bayesian_timeout_contract_real_worker`
  - Real worker with test-only `4/5s`; asserts hard timeout, deterministic fallback event, and post-kill health probe success.
- Artifacts:
  - `artifacts/b07-p2/p5_bayesian.log`
  - `artifacts/b07-p2/p5_bayesian_worker.log`
  - `artifacts/b07-p2/p5_bayesian_probe.jsonl`
  - `artifacts/b07-p2/p5_bayesian_runtime_proof.json`

## EG5.9 Static Boundary Analysis Gate
- Enforcement script:
  - `scripts/ci/enforce_boundary.sh`
- Runtime scan scope:
  - `backend/app/**/*.py`
- Allowlist boundaries:
  - LLM boundary: `backend/app/llm/provider_boundary.py`
  - Bayesian boundaries: `backend/app/tasks/bayesian.py`, `backend/app/workers/bayesian.py`
- Blocked import classes outside allowlist:
  - Provider SDKs: `aisuite`, `openai`, `anthropic`, `mistralai`, `google.generativeai`, `vertexai`
  - Bayesian SDKs: `pymc`
  - HTTP transports: `httpx`, `requests`, `aiohttp`, `urllib3`
  - Dynamic import bypass: `importlib.import_module(...)` and `__import__(...)` for provider/Bayesian SDKs
- Non-vacuity proof:
  - CI self-test step injects temporary forbidden import and asserts guard failure:
    - `.github/workflows/ci.yml` step `EG5.9 non-vacuity self-test (boundary guard must fail on violation)`
- Artifacts:
  - `artifacts/b07-p2/enforce_boundary.log`
  - `artifacts/b07-p2/enforce_boundary_selftest.log`

## EG5.Z Evidence Pack Integrity
- CI manifest generation:
  - `.github/workflows/ci.yml` step `Build B0.7 P2 artifact manifest`
  - Generates `artifacts/b07-p2/manifest.sha256` from top-level artifact files.
- Stable artifact bundle:
  - Existing: `b07-p2-runtime-proof`
  - Dedicated Phase 5 mirror: `phase5-compute-safety-proof`

## CI Execution Proof Hooks
- Workflow:
  - `.github/workflows/ci.yml` (`b07-p2-runtime-proof`)
- Required named-test log assertions:
  - `test_p3_kill_switch_blocks_without_provider_attempt_non_vacuous`
  - `test_p3_provider_swap_config_only_proof`
  - `test_b07_p5_bayesian_timeout_contract_real_worker`
- Required artifact existence assertions:
  - `enforce_boundary.log`, `enforce_boundary_selftest.log`, `p3_controls.log`, `p5_bayesian.log`, `p5_bayesian_worker.log`, `p5_bayesian_probe.jsonl`, `p5_bayesian_runtime_proof.json`, `manifest.sha256`
