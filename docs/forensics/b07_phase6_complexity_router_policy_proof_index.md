# B0.7 Phase 6 Complexity Router & Policy Proof Index

## Clean-Room Evidence Authority
- Branch: `main`
- Merge commit: `5d05ed3c92550dcad9e17b7afb9b557012d5b0e7` (PR `#86`)
- CI run (post-merge, push on `main`): `22010204304`
- CI workflow: `CI`
- Runtime proof job: `B0.7 P2 Runtime Proof (LLM + Redaction)` (`63602436011`)
- Uploaded artifact bundle: `b07-p2-runtime-proof` (`Artifact ID 5508733616`)
- Artifact zip digest (from CI upload step): `970b2486cb1c61f910779c97ca11886fd8258a11abc72e1f9afb8e6e7808b3b6`

This index is derived only from the clean-room run above.

## Exit Gate Mapping (EG6.0-EG6.7)
### EG6.0 Scorer Non-Vacuity & Margin Alignment
- `backend/tests/test_b07_p6_complexity_router.py::test_eg60_scorer_non_vacuous_and_margin_alignment`
- `backend/tests/test_b07_p6_complexity_router.py::test_eg60_negative_control_constant_scorer_fails`
- Evidence log: `artifacts/b07-p2/p6_router_tests.log`

### EG6.1 Determinism Gate
- `backend/tests/test_b07_p6_complexity_router.py::test_eg61_determinism_and_mutation_control`
- Evidence log: `artifacts/b07-p2/p6_router_tests.log`

### EG6.2 Config Policy Mapping Gate
- `backend/tests/test_b07_p6_complexity_router.py::test_eg62_config_policy_mapping_and_fail_closed`
- Evidence log: `artifacts/b07-p2/p6_policy_swap_proof.log`

### EG6.3 Choke Point Enforcement Gate
- Runtime choke-point traversal: `backend/tests/test_b07_p6_complexity_router.py::test_eg63_chokepoint_enforcement_via_worker_paths`
- Static negative control: `backend/tests/test_b07_p0_provider_boundary_enforcement.py::test_provider_dependency_scanner_rejects_direct_call_pattern`
- Static scanner: `scripts/ci/enforce_llm_provider_boundary.py`
- Evidence log: `artifacts/b07-p2/p6_router_tests.log`

### EG6.4 Threshold Binding Gate
- `backend/tests/test_b07_p6_complexity_router.py::test_eg64_threshold_binding_with_negative_control`
- Evidence log: `artifacts/b07-p2/p6_policy_swap_proof.log`

### EG6.5 Budget-Pressure Downgrade Gate
- `backend/tests/test_b07_p6_complexity_router.py::test_eg65_budget_pressure_downgrade_and_negative_control`
- Evidence log: `artifacts/b07-p2/p6_policy_swap_proof.log`

### EG6.6 Ledger Persistence Gate
- `backend/tests/test_b07_p6_complexity_router.py::test_eg66_ledger_persistence_across_success_failure_blocked_cached`
- Persisted fields proven in test: `complexity_score`, `complexity_bucket`, `chosen_tier`, `chosen_provider`, `chosen_model`, `policy_id`, `policy_version`, `routing_reason`
- Evidence log: `artifacts/b07-p2/p6_ledger_persistence_proof.log`

### EG6.7 CI Runtime Proof + Identity Parity Gate
- CI runtime identity step: `Assert runtime identity (least-privilege)`
- Runtime proof gate steps executed in-job:
  - `Run B0.7 P6 router non-vacuity + choke-point gate`
  - `Run B0.7 P6 policy mapping and downgrade gate`
  - `Run B0.7 P6 ledger persistence gate`
  - `Build B0.7 P2 artifact manifest`
  - `Upload B0.7 P2 artifacts`

## Required Artifact Set + Checksums
- `artifacts/b07-p2/p6_router_tests.log`
  - sha256: `85492c3419b0be7ecf2eec88118aad8b5e871064e99dda5a411fac2d5e2962d3`
- `artifacts/b07-p2/p6_policy_swap_proof.log`
  - sha256: `b5cdf87ae4c02ea30fe3173c587790633e680ee5d83e01def95aea08a8839bdd`
- `artifacts/b07-p2/p6_ledger_persistence_proof.log`
  - sha256: `addd117a2930b1f9e73dd0555bc061f181063b1485f22780d78712aecd2f9e5b`
- `artifacts/b07-p2/manifest.sha256`
  - sha256 (as listed inside artifact manifest): `d193c41eea3fa739dac5bdf8f6f6429de8508a894efb25ab9ef015439fb00264`

## Artifact Layout
- Root: `artifacts/b07-p2`
- Full proof bundle name: `b07-p2-runtime-proof`
- Artifact URL: `https://github.com/Muk223/skeldir-2.0/actions/runs/22010204304/artifacts/5508733616`
