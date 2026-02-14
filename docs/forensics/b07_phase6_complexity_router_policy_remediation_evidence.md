# B0.7 Phase 6 Complexity Router & Policy Remediation Evidence

## Scope and Authority
- Scope: Phase 6 minimum-viable complexity routing and policy enforcement at the LLM provider choke point.
- Branch target: `main`.
- Runtime authority job: `.github/workflows/ci.yml` job `b07-p2-runtime-proof`.
- Companion proof index: `docs/forensics/b07_phase6_complexity_router_policy_proof_index.md`.

## Executive Findings
- H6.1 (router absent/not invoked at choke point): **Refuted**. Routing now executes inside `backend/app/llm/provider_boundary.py` before claim/provider dispatch.
- H6.2 (deterministic scorer vacuous): **Refuted**. Non-vacuity fixture gate with negative control added in `backend/tests/test_b07_p6_complexity_router.py`.
- H6.3 (policy not config-driven): **Refuted**. Routing policy path is config-driven via `LLM_COMPLEXITY_POLICY_PATH`.
- H6.4 (threshold binding unenforced): **Refuted**. Explicit threshold gate and tamper negative control implemented.
- H6.5 (budget-pressure downgrade missing): **Refuted**. Downgrade semantics implemented and tested; reason persisted as routing reason.
- H6.6 (ledger persistence incomplete): **Remediated**. Router decision fields are persisted in `llm_api_calls` at claim path and remain available across call outcomes.
- H6.7 (CI proofs vacuous/bypassable): **Partially remediated locally, fully enforced in CI wiring**. Required Phase 6 logs and named-test checks were added to CI.

## Implementations and Remediations

### 1) Deterministic Complexity Router (provider-agnostic, policy-driven)
- Added: `backend/app/llm/complexity_router.py`
  - `complexity_score(prompt, feature, context) -> float [0,1]`
  - `bucket(score) -> int [1..10]`
  - `route_request(...) -> RoutingDecision`
  - Deterministic proxies: canonical payload length, message count, structured-output markers, reasoning markers, context size, feature class.
  - No RNG/time-based logic.
- Added policy artifact: `backend/app/llm/policies/complexity_router_policy.json`
  - Mandatory bands:
    - bucket `1-3` -> `cheap`
    - bucket `4-7` -> `standard`
    - bucket `8-10` -> `premium`
  - Tier->provider/model mapping is data-only.
  - Budget pressure downgrade policy:
    - pressure threshold and critical threshold
    - deterministic downgrade order

### 2) Enforced at Single LLM Choke Point
- Updated: `backend/app/llm/provider_boundary.py`
  - Router invoked at start of `complete(...)` before `_claim(...)`.
  - Selected model now derives from routing decision (`chosen_provider:chosen_model`) instead of ad hoc prompt model fallback.
  - Budget state snapshot is read and passed to router for downgrade semantics.
  - Routing decision is attached to `_claim(...)` and persisted.

### 3) Config-Driven Policy (fail-closed)
- Updated: `backend/app/core/config.py`
  - Added setting: `LLM_COMPLEXITY_POLICY_PATH`.
  - Validation enforces non-empty path.
- Router fails closed on:
  - missing policy file
  - malformed JSON/object
  - missing `policy_id`/`policy_version`
  - missing tier mappings/provider/model fields

### 4) Ledger Persistence (auditable economics)
- Updated ORM: `backend/app/models/llm.py`
  - Added columns:
    - `complexity_score`
    - `complexity_bucket`
    - `chosen_tier`
    - `chosen_provider`
    - `chosen_model`
    - `policy_id`
    - `policy_version`
    - `routing_reason`
  - Added constraints:
    - score range `[0,1]`
    - bucket range `[1,10]`
    - tier enum in `cheap|standard|premium`
- Added migration:
  - `alembic/versions/007_skeldir_foundation/202602141200_b07_p6_complexity_router_fields.py`
  - Adds columns and DB constraints to `llm_api_calls`.

### 5) Non-Vacuous Test Gates (EG6.*)
- Added test module: `backend/tests/test_b07_p6_complexity_router.py`
  - EG6.0 scorer non-vacuity + fixture distribution checks.
  - EG6.0 negative control: constant scorer injection must fail gate conditions.
  - EG6.1 determinism and mutation control.
  - EG6.2 policy swap from config-only plus fail-closed missing policy.
  - EG6.4 threshold binding plus policy-tamper negative control.
  - EG6.5 budget-pressure downgrade plus “remove downgrade” negative control.
  - EG6.3 runtime worker-path choke-point traversal assertion.
  - EG6.6 ledger field persistence assertions across success/failure/blocked/cached.
- Added fixture vectors:
  - `backend/tests/fixtures/b07_p6_complexity_vectors_v1.json` (12 vectors).

### 6) Choke-Point Static Guard Hardening
- Updated scanner: `scripts/ci/enforce_llm_provider_boundary.py`
  - Existing forbidden-provider import checks retained.
  - Added detection for direct provider SDK call patterns:
    - `.chat.completions.create(...)`
    - `.responses.create(...)`
    - `.messages.create(...)`
- Added negative-control fixture:
  - `backend/tests/fixtures/forbidden_direct_provider_call_fixture.txt`
- Extended test:
  - `backend/tests/test_b07_p0_provider_boundary_enforcement.py::test_provider_dependency_scanner_rejects_direct_call_pattern`

### 7) CI Enforcement and Artifactization
- Updated CI job `b07-p2-runtime-proof` in `.github/workflows/ci.yml`:
  - Added Phase 6 gate execution and logs:
    - `artifacts/b07-p2/p6_router_tests.log`
    - `artifacts/b07-p2/p6_policy_swap_proof.log`
    - `artifacts/b07-p2/p6_ledger_persistence_proof.log`
  - Added required-file assertions and named-test grep assertions.
  - Added manifest generation:
    - `artifacts/b07-p2/manifest.sha256`

## Evidence Map (File-Level)
- Router implementation: `backend/app/llm/complexity_router.py`
- Policy artifact: `backend/app/llm/policies/complexity_router_policy.json`
- Choke-point enforcement: `backend/app/llm/provider_boundary.py`
- Config surface: `backend/app/core/config.py`
- Ledger schema model: `backend/app/models/llm.py`
- Migration: `alembic/versions/007_skeldir_foundation/202602141200_b07_p6_complexity_router_fields.py`
- Gate tests: `backend/tests/test_b07_p6_complexity_router.py`
- Non-vacuity fixtures: `backend/tests/fixtures/b07_p6_complexity_vectors_v1.json`
- Static boundary guard: `scripts/ci/enforce_llm_provider_boundary.py`
- Guard negative-control fixture: `backend/tests/fixtures/forbidden_direct_provider_call_fixture.txt`
- Guard tests: `backend/tests/test_b07_p0_provider_boundary_enforcement.py`
- CI workflow wiring: `.github/workflows/ci.yml`

## Local Execution Evidence
- Executed and passing:
  - `pytest -q backend/tests/test_b07_p6_complexity_router.py -k "eg60 or eg61 or eg62 or eg64 or eg65"`
  - `pytest -q backend/tests/test_b07_p0_provider_boundary_enforcement.py`
  - `python -m py_compile backend/app/llm/complexity_router.py backend/app/llm/provider_boundary.py backend/app/models/llm.py backend/tests/test_b07_p6_complexity_router.py scripts/ci/enforce_llm_provider_boundary.py`
- Not fully executable in local environment:
  - DB-backed Phase 6 tests for EG6.3/EG6.6 encountered external runtime DB auth mismatch in local context.
  - These are wired into CI runtime DB job for authoritative execution under runtime identity checks.

## Residual Risks and Controls
- Risk: local-only validation cannot prove runtime identity parity.
  - Control: CI `b07-p2-runtime-proof` already enforces runtime user and non-superuser assertions.
- Risk: policy drift could alter band economics unintentionally.
  - Control: threshold-binding tests with tamper negative control and policy version/id persistence.
- Risk: direct SDK bypass patterns may evolve.
  - Control: static scanner is now explicit on direct call patterns and can be extended as signatures evolve.

## Completion Status Against Phase 6 Objective
- Deterministic non-vacuous router: **Implemented**
- Enforced at single choke point: **Implemented**
- Policy-driven provider/model selection: **Implemented**
- Economic routing + budget-pressure downgrade: **Implemented**
- Ledger persistence of routing metadata: **Implemented**
- CI proof wiring with required artifacts and manifest: **Implemented**

