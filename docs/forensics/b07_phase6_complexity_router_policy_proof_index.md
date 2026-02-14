# B0.7 Phase 6 Complexity Router & Policy Proof Index

This index maps Phase 6 exit gates to executable gates and CI artifacts.

## Scope
- Branch authority: `main`
- Runtime authority: `.github/workflows/ci.yml` job `b07-p2-runtime-proof`
- Artifact root: `artifacts/b07-p2`

## EG6.0 Scorer Non-Vacuity & Margin Alignment
- Tests:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg60_scorer_non_vacuous_and_margin_alignment`
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg60_negative_control_constant_scorer_fails`
- Artifact:
  - `artifacts/b07-p2/p6_router_tests.log`

## EG6.1 Determinism
- Test:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg61_determinism_and_mutation_control`
- Artifact:
  - `artifacts/b07-p2/p6_router_tests.log`

## EG6.2 Config Policy Mapping
- Test:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg62_config_policy_mapping_and_fail_closed`
- Artifact:
  - `artifacts/b07-p2/p6_policy_swap_proof.log`

## EG6.3 Choke Point Enforcement
- Runtime choke-point proof:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg63_chokepoint_enforcement_via_worker_paths`
- Static negative-control proof:
  - `backend/tests/test_b07_p0_provider_boundary_enforcement.py::test_provider_dependency_scanner_rejects_direct_call_pattern`
- Enforcement scanner:
  - `scripts/ci/enforce_llm_provider_boundary.py`
- Artifact:
  - `artifacts/b07-p2/p6_router_tests.log`

## EG6.4 Threshold Binding (1-3 cheap, 8-10 premium)
- Test:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg64_threshold_binding_with_negative_control`
- Artifact:
  - `artifacts/b07-p2/p6_policy_swap_proof.log`

## EG6.5 Budget-Pressure Downgrade
- Test:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg65_budget_pressure_downgrade_and_negative_control`
- Artifact:
  - `artifacts/b07-p2/p6_policy_swap_proof.log`

## EG6.6 Ledger Persistence
- Test:
  - `backend/tests/test_b07_p6_complexity_router.py::test_eg66_ledger_persistence_across_success_failure_blocked_cached`
- Ledger fields asserted:
  - `complexity_score`, `complexity_bucket`, `chosen_tier`, `chosen_provider`, `chosen_model`, `policy_id`, `policy_version`, `routing_reason`
- Artifact:
  - `artifacts/b07-p2/p6_ledger_persistence_proof.log`

## EG6.7 CI Runtime Proof + Identity Parity
- CI runtime identity assertions:
  - `current_user == RUNTIME_USER`
  - `rolsuper == false`
- CI required logs (fail if missing):
  - `p6_router_tests.log`
  - `p6_policy_swap_proof.log`
  - `p6_ledger_persistence_proof.log`
- Checksum manifest:
  - `artifacts/b07-p2/manifest.sha256`

## Required Artifact Set
- `artifacts/b07-p2/p6_router_tests.log`
- `artifacts/b07-p2/p6_policy_swap_proof.log`
- `artifacts/b07-p2/p6_ledger_persistence_proof.log`
- `artifacts/b07-p2/manifest.sha256`
