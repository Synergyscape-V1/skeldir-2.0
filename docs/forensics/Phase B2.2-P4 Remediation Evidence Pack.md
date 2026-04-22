# Phase B2.2-P4 Remediation Evidence Pack

Date: 2026-04-22  
Branch basis: `main`  
Directive: Idempotent ACK Semantics + Webhook-Orchestration Side-Effect Isolation

## 1) Initial findings (falsifiable)

- H01 validated: `backend/app/ingestion/event_service.py` exposed `ingest_with_transaction(...)-> Dict[str, Any]` and downgraded typed ingestion state into mapping keys.
- H02 validated: `backend/app/api/webhooks.py` orchestration gate used `result.get("is_duplicate")` on the webhook path.
- H03 validated: `scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py` and `scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py` enforced the dict-based duplicate gate token.
- H04 validated: governance claimed `IngestionDecision` but runtime boundary exported dict.
- H07 validated: `backend/app/main.py` contained webhook-specific protocol branching in global `RequestValidationError` handler.
- Runtime behavior before refactor remained mostly correct (duplicate row suppression and ACK outcomes), but architecture/enforcement were misaligned with required typed-boundary law.

## 2) Remediations implemented

- `backend/app/ingestion/event_service.py`
  - Added typed runtime boundary object `IngestionTransactionResult` (`@dataclass(frozen=True)`).
  - Changed `ingest_with_transaction()` return type from `Dict[str, Any]` to `IngestionTransactionResult`.
  - Removed dict serialization seam from success and race-duplicate paths.
  - Preserved deterministic duplicate state via `decision: IngestionDecision` and `is_duplicate` property.

- `backend/app/api/webhooks.py`
  - Replaced orchestration dict lookups with typed attribute access:
    - `result.status`
    - `result.session_id`
    - `result.is_duplicate`
    - `result.event_id`
    - `result.channel`
    - `result.error_type` / `result.error`
  - Downstream scheduling gate is now explicitly:
    - `if event_timestamp and session_id and not result.is_duplicate:`

- `backend/app/main.py`
  - Removed webhook-specific protocol ownership from global validation middleware.
  - `RequestValidationError` handler now delegates to FastAPI default handler without `/api/webhooks/*` routing logic.

- `scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py`
  - Rewired enforcement to require typed boundary usage.
  - Added checks for `IngestionTransactionResult` and typed return annotation.
  - Added forbidden checks for `result.get("is_duplicate")` and `result["is_duplicate"]`.
  - Added contract checks for forbidden boundary shapes.

- `scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py`
  - Updated required webhook gate token to typed `not result.is_duplicate`.
  - Added forbidden dict duplicate-access tokens.

- `scripts/ci/enforce_b14_p3_attribution_locality.py`
  - Removed stale dict-token expectation (`session_id = result.get("session_id")`).
  - Enforced typed runtime accessor token (`session_id = result.session_id`).
  - Replaced stale event-service payload token check with typed session property checks.

- `contracts-internal/governance/b22_p4_idempotent_ack_orchestration.main.json`
  - Version bump `1.1.0 -> 1.2.0`.
  - Added typed transaction contract field:
    - `ingestion_transaction_result_type: "IngestionTransactionResult"`
  - Added forbidden boundary shape policy:
    - `dict`, `typed_dict`, `tuple`, `list`.

- Compatibility updates (non-architectural behavior preserved)
  - Updated ingestion-wrapper consumers to typed access in:
    - `backend/tests/test_b043_ingestion.py`
    - `backend/tests/test_b043_ingestion_backup.py`
    - `backend/tests/integration/test_b14_p3_attribution_locality_runtime.py`
    - `backend/tests/integration/test_b14_p4_retention_deletion_runtime.py`
    - `backend/tests/integration/test_b14_p5_export_log_artifact_no_leak_runtime.py`
    - `backend/tests/integration/test_b14_p7_e2e_privacy_system_proofs.py`
    - `scripts/r2/runtime_scenario_suite.py`

## 3) Local falsifiable validation

- `python scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py` -> PASS
- `python scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py` -> PASS
- `pytest backend/tests/test_b22_p2_post_auth_privacy_boundary_enforcer.py -q` -> 5 passed
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py -q` -> 5 passed
- `pytest backend/tests/test_b043_ingestion.py::test_transaction_wrapper_success backend/tests/test_b043_ingestion.py::test_transaction_wrapper_error -q` -> 2 passed
- `pytest backend/tests/test_b12_p8_error_contract_normalization.py::test_eg83_paypal_hmac_failure_variants_share_non_leaky_problem_contract backend/tests/test_b12_p8_error_contract_normalization.py::test_eg8cf_paypal_constant_work_unknown_key_and_known_bad_signature_both_invoke_compute backend/tests/test_b12_p8_error_contract_normalization.py::test_eg8route_stripe_alias_and_canonical_auth_failures_are_equivalent -q` -> 3 passed
- `pytest backend/tests/test_b22_p4_idempotent_ack_orchestration.py -q` -> 4 skipped locally (authoritative DB proof harness not provisioned in local run)

## 4) Exit gate status after remediation

- Exit Gate 1 (Typed Boundary Closure): PASS locally by code + enforcer proof.
- Exit Gate 2 (Duplicate Suppression Integrity): preserved; full authoritative proof delegated to CI runtime DB harness.
- Exit Gate 3 (ACK Protocol Stability): preserved (targeted normalization tests passed; malformed webhook behavior remains route-owned).
- Exit Gate 4 (Auth Precedence): preserved (targeted auth failure normalization tests passed).
- Exit Gate 5 (Non-Regression): typed wrapper consumers updated; ingestion compatibility tests pass locally.
- Exit Gate 6 (CI + Governance Correctness): PASS locally for enforcer surfaces; protected-branch workflow evidence captured in section 5.

## 5) Protected-branch workflow evidence (finalized)

- Repository: `Synergyscape-V1/skeldir-2.0`
- Branch: `main`
- PR merged: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/371`
- Merge commit on `main`: `cb07a0b44afa26a7c491a8d2483dc3ea03353587`
- Merge timestamp (UTC): `2026-04-22T15:06:55Z`
- Main CI (fresh manual full run on merged SHA): `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24790632408`
- Main CI result: `completed/success` (head SHA `cb07a0b44afa26a7c491a8d2483dc3ea03353587`)
- Protected-check convergence on PR head: all required checks green before merge.

Falsifiable completion claim:
- Typed runtime boundary closure is merged on protected `main`.
- Required protected checks were green at merge.
- Full `CI` workflow run on merged `main` SHA completed green once.
