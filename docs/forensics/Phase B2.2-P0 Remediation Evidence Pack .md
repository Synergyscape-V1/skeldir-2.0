# Phase B2.2-P0 Remediation Evidence Pack (Follow-up Corrective Action)

Date: 2026-04-19
Branch at start: `main` (`b50a1ef36`)
Execution branch: `b22-p0-followup-corrective`
Scope: **Context-Robust Hypothesis-Driven B2.2-P0 Follow up Corrective Action Remediation Directive**

## 1. Follow-up Baseline Findings

The previously landed B2.2-P0 state was mechanically converged but architecturally ambiguous for Stripe topology:

- Runtime mounted webhook routes: **5**.
- Runtime OpenAPI webhook operations: **5**.
- Source/bundle/typegen/governance webhook operations: **5**.
- Two Stripe paths were exposed as public topology everywhere:
  - `POST /api/webhooks/stripe/payment_intent_succeeded`
  - `POST /api/webhooks/stripe/payment_intent/succeeded`
- No schema-control mechanism existed to make one Stripe path runtime-only:
  - no `include_in_schema=False` on legacy Stripe alias route,
  - no custom OpenAPI filtering path in `backend/app/main.py`.
- Existing enforcer proved internal equality only, not architectural correctness of the public topology.

## 2. Hypothesis Outcomes (H01-H08)

- `H01` **CONFIRMED**: governance encoded route-first 5-op equality, not architecture-first public topology.
- `H02` **CONFIRMED**: Stripe alias/public distinction was not encoded in runtime schema emission.
- `H03` **CONFIRMED**: source/bundle/typegen surfaces promoted legacy Stripe alias into public SDK topology.
- `H04` **CONFIRMED**: enforcer validated convergence only; it did not validate correct topology law.
- `H05` **CONFIRMED (partially)**: negative controls were non-vacuous for drift, but underfit alias-leak topology risk.
- `H06` **CONFIRMED**: CI was green on wrong invariant (5-op equality).
- `H07` **REFUTED as unresolved necessity**: no authoritative code-path rationale required both Stripe paths as public SDK surface.
- `H08` **CONFIRMED**: correct remediation was not route deletion; it was explicit runtime alias + public topology partition.

## 3. Architectural Decision Implemented

B2.2-P0 public topology is locked to **4 public operations** (one per provider), while retaining one Stripe runtime transport alias:

Public topology (machine-locked):
1. `POST /api/webhooks/shopify/order_create`
2. `POST /api/webhooks/stripe/payment_intent/succeeded`
3. `POST /api/webhooks/paypal/sale_completed`
4. `POST /api/webhooks/woocommerce/order_completed`

Runtime transport-only alias (machine-locked):
- `POST /api/webhooks/stripe/payment_intent_succeeded`

This preserves compatibility transport while preventing alias hardening into public OpenAPI/contracts/typegen.

## 4. Remediations Applied

### 4.1 Runtime schema emission control
- `backend/app/api/webhooks.py`
  - Added `include_in_schema=False` on legacy Stripe alias route:
    - `/webhooks/stripe/payment_intent_succeeded`

### 4.2 Canonical source contract topology
- `api-contracts/openapi/v1/webhooks/stripe.yaml`
  - Removed legacy Stripe alias public operation.
  - Retained only canonical public path:
    - `/api/webhooks/stripe/payment_intent/succeeded`

### 4.3 Bundled artifact and typegen convergence
- Regenerated via canonical scripts:
  - `api-contracts/dist/openapi/v1/webhooks.stripe.bundled.yaml`
  - `frontend/src/types/api/webhooks-stripe.ts`
- Legacy Stripe alias no longer appears in bundled/public type surfaces.

### 4.4 Governance contract hardening
- `contracts-internal/governance/b22_p0_declared_webhook_surface.main.json`
  - Upgraded to topology-aware schema:
    - `required_public_providers`
    - `public_surface_policy`
    - `public_operations` (4 operations)
    - `runtime_transport_aliases` (legacy Stripe alias)

### 4.5 Enforcer invariant correction (correctness, not just equality)
- `scripts/ci/enforce_b22_p0_webhook_surface_lock.py`
  - Enforces exact B2.2 public topology set (4 operations).
  - Enforces approved runtime alias set.
  - Enforces runtime routes = public + aliases.
  - Enforces runtime OpenAPI/source/bundle/typegen = public only.
  - Enforces no public/alias overlap.
  - Enforces contract-scope alias allowlist alignment.

### 4.6 Route fidelity control for runtime-only aliases
- `backend/app/config/contract_scope.yaml`
  - Added `runtime_transport_only_allowlist`:
    - `POST /api/webhooks/stripe/payment_intent_succeeded`
- `tests/contract/test_route_fidelity.py`
  - Honors runtime transport-only allowlist in route->contract mapping to avoid false-positive unmapped route failures while preserving fail-closed controls.

### 4.7 Negative-control expansion (non-vacuous topology testing)
- `backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py`
  - Added/updated controls for:
    - broadened declared public topology,
    - alias promoted into public topology,
    - contract-scope alias allowlist drift,
    - CI wiring drift,
    - semantics allowlist webhook bypass,
    - synthetic forced regression.

### 4.8 Test expectation alignment
- `backend/tests/test_b045_webhooks.py`
  - OpenAPI checks moved to canonical Stripe public path.
  - Explicitly asserts legacy alias is absent from runtime OpenAPI.
- `tests/contract/test_contract_semantics.py`
  - Runtime parity probe moved to canonical Stripe path.

## 5. Falsifiable Local Validation

### 5.1 Enforcer pass on corrected invariant
Command:
- `python scripts/ci/enforce_b22_p0_webhook_surface_lock.py`

Observed result:
- `result=PASS`
- `enforcement=public_topology_runtime_alias_contract_bundle_typegen_webhook_surface_converged`

### 5.2 Enforcer negative controls
Command:
- `pytest backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py -q`

Observed result:
- `7 passed`

### 5.3 Contract/runtime topology and semantics probes
Command:
- `pytest tests/contract/test_route_fidelity.py::test_route_to_contract_mapping tests/contract/test_route_fidelity.py::test_contract_to_route_mapping tests/contract/test_contract_semantics.py::test_p8_runtime_parity_invalid_jwt_vs_invalid_hmac_signature backend/tests/test_b045_webhooks.py::test_openapi_contract_paths_present -q`

Observed result:
- `4 passed`

## 6. Exit Gate Assessment (Pre-Merge Local)

- **Exit Gate 1 - Public Topology Correctness:** PASS (local proof)
- **Exit Gate 2 - Emission-Control and Artifact Integrity:** PASS (local proof)
- **Exit Gate 3 - Correct-Invariant CI Adjudication:** PASS (local proof)

## 7. Protected-Branch Completion Evidence

This section is finalized when the corrective PR is merged to `main` and one full `main` CI run is green:

- PR URL: `<to be populated after PR creation>`
- Merge commit on `main`: `<to be populated after merge>`
- Full green `main` CI run URL: `<to be populated after merge>`

