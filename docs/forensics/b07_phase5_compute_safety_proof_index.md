# B0.7 Phase 5 Compute Safety Proof Index

This index maps each Phase 5 exit gate to executable tests and expected artifacts.

## Completion Criteria (Phase 5)
- Code containing Phase 5 controls/tests is merged to `main`.
- `main` CI is green.
- `b07-p2-runtime-proof` job executed and uploaded artifacts proving:
  - `p3_controls.log`
  - `p5_bayesian.log`
  - `p5_bayesian_runtime_proof.json`
  - `enforce_boundary.log`
- Runtime DB identity checks pass under app runtime principal:
  - `current_user == RUNTIME_USER`
  - `rolsuper == false`

## EG5.1 Kill Switch Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_kill_switch_blocks_without_provider_attempt_non_vacuous`
- Negative control:
  - Same test invokes a second request with `kill_switch=False` and asserts provider invocation occurs.
- Ledger proof:
  - Same test asserts blocked row monetary spend is zero (`LLMApiCall.cost_cents == 0`).
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.2 Breaker Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_breaker_opens_after_three_failures`
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_breaker_open_blocks_without_provider_attempt_non_vacuous`
- Negative control:
  - Same non-vacuous test flips `_breaker_open` to closed and asserts provider invocation occurs.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.3 Hourly Shutoff Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_hourly_shutoff_distinct_from_monthly`
- Non-vacuity evidence:
  - Existing accepted calls precede shutoff block in same test.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.4 Budget Reservation Concurrency Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_reservation_concurrency_safety`
- Non-vacuity evidence:
  - Test asserts mixed accepted/blocked outcomes and validates provider attempt count equals accepted set.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.5 Retry Idempotency Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_retry_idempotency_no_double_debit`
- Non-vacuity evidence:
  - First attempt is forced failure, retry reuses same `api_call_id` with no duplicate reservation row.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.6 Timeout Enforcement Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_timeout_enforced`
- Negative control:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_timeout_non_vacuous_negative_control`
  - Same provider path with relaxed timeout succeeds.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.7 Provider Swap via Config-Only Gate
- Positive proof:
  - `backend/tests/test_b07_p3_provider_controls.py::test_p3_provider_swap_config_only_proof`
- Non-vacuity evidence:
  - Same code path executed twice with only `LLM_PROVIDER_MODEL` env/config change; persisted providers differ.
- Artifact:
  - `artifacts/b07-p2/p3_controls.log`

## EG5.8 Bayesian Worker 5-Minute Timeout Gate
- Static production bound proof:
  - `backend/app/tasks/bayesian.py`
  - `PRODUCTION_BAYESIAN_SOFT_TIME_LIMIT_S=270`
  - `PRODUCTION_BAYESIAN_TIME_LIMIT_S=300`
- Dynamic real-worker mechanism proof (reduced limits):
  - `backend/tests/integration/test_b07_p5_bayesian_timeout_runtime.py::test_b07_p5_bayesian_timeout_contract_real_worker`
  - Runs real worker with test-only `4/5s`, asserts hard timeout outcome, fallback event emitted, and health probe success after kill.
- Artifacts:
  - `artifacts/b07-p2/p5_bayesian.log`
  - `artifacts/b07-p2/p5_bayesian_runtime_proof.json`
  - `artifacts/b07-p2/p5_bayesian_probe.jsonl`
  - `artifacts/b07-p2/p5_bayesian_worker.log`

## EG5.9 Static Boundary Analysis Gate
- Positive proof:
  - `scripts/ci/enforce_boundary.sh`
- Enforcement rule:
  - Fails if `import`/`from` references to `aisuite` or `pymc` appear outside:
    - `backend/app/llm/provider_boundary.py`
    - `backend/app/workers/bayesian.py`
- Recommended CI invocation:
  - `bash scripts/ci/enforce_boundary.sh`
- CI artifact:
  - `artifacts/b07-p2/enforce_boundary.log`

## CI Execution Proof Hooks
- Workflow:
  - `.github/workflows/ci.yml` (`b07-p2-runtime-proof`)
- Required log assertions in artifact verification step:
  - `test_p3_kill_switch_blocks_without_provider_attempt_non_vacuous`
  - `test_p3_provider_swap_config_only_proof`
  - `test_b07_p5_bayesian_timeout_contract_real_worker`
