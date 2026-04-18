# Phase B2.2-P0 Remediation Evidence Pack

Date: 2026-04-18  
Branch at start: `main`  
Scope: **B2.2-P0 Runtime/Contract Authority Convergence + Declared Surface Lock**

## 1. Initial Findings (Validated)

Authoritative pre-remediation drift (from runtime + contract inventory):
- Mounted runtime webhook operations: **5**
- Runtime-generated OpenAPI webhook operations: **5**
- Source + bundled webhook contract operations: **15**
- Drift class: **10 declared-but-unmounted webhook operations**

Validated blockers at phase start:
- `H01`/`H03`/`H04`/`H05`: split truth across runtime, source contracts, bundles, and generated types.
- `H02`: webhook drift tolerated because checks were not fail-closed for webhook exclusivity.
- `H06`: existing runtime checks proved partial correctness, not full authority-chain identity.
- `H07`: no webhook-specific declared surface lock artifact and no dedicated enforcer.

## 2. Remediation Implemented

### 2.1 Canonical Declared Surface (machine-checkable)
Added canonical governance artifact:
- `contracts-internal/governance/b22_p0_declared_webhook_surface.main.json`

Declared webhook surface locked to exactly:
1. `POST /api/webhooks/shopify/order_create`
2. `POST /api/webhooks/stripe/payment_intent_succeeded`
3. `POST /api/webhooks/stripe/payment_intent/succeeded`
4. `POST /api/webhooks/paypal/sale_completed`
5. `POST /api/webhooks/woocommerce/order_completed`

### 2.2 Source Contract Convergence
Pruned webhook source contracts to mounted authority only:
- `api-contracts/openapi/v1/webhooks/shopify.yaml`
- `api-contracts/openapi/v1/webhooks/stripe.yaml`
- `api-contracts/openapi/v1/webhooks/paypal.yaml`
- `api-contracts/openapi/v1/webhooks/woocommerce.yaml`

### 2.3 Artifact + Typegen Convergence
Regenerated bundled contracts and frontend generated types:
- `api-contracts/dist/openapi/v1/webhooks.*.bundled.yaml`
- `frontend/src/types/api/webhooks-*.ts`
- `frontend/src/types/api/index.ts`

### 2.4 Merge-blocking Proof Harness Hardening
Added B2.2-P0 enforcer:
- `scripts/ci/enforce_b22_p0_webhook_surface_lock.py`

Added non-vacuous negative controls:
- `backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py`

Strengthened route fidelity to fail-closed on webhook drift:
- `tests/contract/test_route_fidelity.py`
- New merge-blocking marker: `webhook_contract_drift_is_merge_blocking`

Removed webhook semantic skip bypass:
- `tests/contract/semantics_skip_allowlist.yaml` -> `bundles: {}`

Enabled webhook semantic execution under deterministic auth fixture (no DB dependency):
- `tests/contract/test_contract_semantics.py`

Wired enforcer into required CI context (`Contract Semantic Drift Gate`):
- `.github/workflows/ci.yml`
- Added steps:
  - `python scripts/ci/enforce_b22_p0_webhook_surface_lock.py`
  - `pytest backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py -q`

## 3. Post-Remediation Authority Convergence

Post-remediation operation identity is exact across all surfaces:

- Runtime mounted routes: **5**
- Runtime OpenAPI: **5**
- Source webhook contracts: **5**
- Bundled webhook artifacts: **5**
- Generated frontend webhook types: **5**

No declared-unmounted operations remain in canonical B2.2 webhook scope.

## 4. Non-Vacuous Validation Evidence

### 4.1 Enforcer positive proof
Command:
- `python scripts/ci/enforce_b22_p0_webhook_surface_lock.py`

Result:
- `result=PASS`
- `enforcement=declared_runtime_contract_bundle_typegen_webhook_surface_converged`

### 4.2 Enforcer negative controls (fail as designed)
Command:
- `pytest backend/tests/test_b22_p0_webhook_surface_lock_enforcer.py -q`

Result:
- `5 passed`
- Includes synthetic and structural failures:
  - forced regression path
  - missing CI wiring
  - declared surface drift injection
  - webhook allowlist bypass injection

### 4.3 Route-fidelity webhook exclusivity proof
Command:
- `pytest tests/contract/test_route_fidelity.py::test_contract_to_route_mapping -q`

Result:
- `passed`
- Webhook declared/unmounted drift is now merge-blocking.

### 4.4 Runtime semantic conformance including webhook bundles
Command:
- `pytest tests/contract/test_contract_semantics.py -q`

Result:
- `21 passed, 1 skipped`
- Webhook bundles executed and passed without allowlist exemption.

## 5. Exit Gate Status

- **EG-P0-1 Runtime/Declared Surface Identity:** PASS
- **EG-P0-2 Artifact Convergence:** PASS
- **EG-P0-3 Merge-Blocking Adjudication:** PASS (wired into required `Contract Semantic Drift Gate`)

## 6. Merge + Main CI Evidence

### 6.1 Authority-convergence landing on `main`
- PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/347`
- Merge timestamp (UTC): `2026-04-18T22:43:30Z`
- Merge commit SHA on `main`: `a93ddf8296f6d1a68571cfa8304a4a6e9468a25e`
- Main CI run URL for this merge commit: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24615568708`
- Observed result on this first post-merge run: one failing job (`B1.5 P3 Runtime Route Binding and Review Enforcement`) caused by brittle YAML string mutation in a negative-control test after allowlist normalization to `bundles: {}`.

### 6.2 Post-merge CI stabilization (no B2.2 surface change)
- Follow-up PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/348`
- Follow-up merge timestamp (UTC): `2026-04-18T23:15:24Z`
- Follow-up merge commit SHA on `main`: `0a98d2e40a5a01c06f64e463596a21b0d0d5e38d`
- Follow-up change scope: `backend/tests/test_b15_p3_runtime_route_binding_enforcer.py` only, making skip-allowlist regression injection YAML-structural instead of brittle text append.
- Authoritative main CI run URL (full-green proof): `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24616087341`
- CI outcome: `status=completed`, `conclusion=success`.
- Merge-commit check-run summary (`0a98d2e...`): `106` completed, `0` failures, `0` pending.

### 6.3 Completion Statement
Protected-branch workflow evidence now includes:
- initial B2.2-P0 authority convergence merge to `main`,
- post-merge CI stabilization,
- at least one full-green `main` CI execution on the landed code path.
