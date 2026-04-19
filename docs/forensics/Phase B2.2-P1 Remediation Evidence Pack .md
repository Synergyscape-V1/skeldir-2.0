# Phase B2.2-P1 Remediation Evidence Pack

Date: 2026-04-19  
Execution branch: `b22-p0-followup-corrective`  
Scope: **Phase B2.2-P1 - Authenticity Semantics Closure + Tenant Secret Authority Preservation**

## 1. Initial Findings (Validated from Code)

1. PayPal authenticity was weaker than other providers:
- Runtime accepted PayPal using a simplified `hmac(secret, raw_body)` compare against `PayPal-Transmission-Sig`.
- No required envelope semantics (`transmission_id`, `transmission_time`, `webhook_id`, `auth_algo`, `cert_url`) were enforced.

2. Tenant secret authority chain already existed and remained valid:
- `X-Skeldir-Tenant-Key` -> hashed lookup -> server-side tenant secret resolution.
- Dummy-secret constant-work behavior existed for auth failure parity.

3. Merge-blocking P1 policy lock did not exist:
- No dedicated B2.2-P1 governance contract/enforcer in CI.
- Existing CI enforced B2.2-P0 topology lock, not P1 authenticity semantics closure.

## 2. Remediation Implemented

### 2.1 PayPal provider-grade local semantics (no hot-path remote dependency)
- File: `backend/app/webhooks/signatures.py`
- Replaced simplified PayPal raw-body HMAC compare with canonical envelope verification:
  - Required fields: `transmission_id`, `transmission_time`, `transmission_sig`, `webhook_id`, `auth_algo`, `cert_url`
  - Timestamp tolerance: 300 seconds
  - Auth algo allowlist: `HMAC-SHA256`/`SHA256`/`SHA-256`
  - Cert URL constraints: `https` + host suffix in `paypal.com` or `paypalobjects.com`
  - Canonical signature law:
    - `HMAC-SHA256(secret, "{transmission_id}|{transmission_time}|{webhook_id}|{sha256(raw_body)}")`

### 2.2 Runtime ingress auth envelope wiring
- File: `backend/app/api/webhooks.py`
- Added PayPal auth headers to the dependency surface:
  - `PayPal-Transmission-Id`
  - `PayPal-Transmission-Time`
  - `PayPal-Transmission-Sig`
  - `PayPal-Webhook-Id`
  - `PayPal-Auth-Algo`
  - `PayPal-Cert-Url`
- Added deterministic envelope serialization and passed that envelope to verifier while preserving:
  - server-authoritative tenant-key -> tenant-secret resolution
  - fail-closed unauthorized behavior
  - constant-work path for known-bad-signature vs unknown-tenant with complete envelopes

### 2.3 Contract semantics update
- Files:
  - `api-contracts/openapi/v1/webhooks/paypal.yaml`
  - `api-contracts/dist/openapi/v1/webhooks.paypal.bundled.yaml`
  - `frontend/src/types/api/webhooks-paypal.ts`
- Updated PayPal webhook contract headers to required for P1 semantics.

### 2.4 Machine-checkable governance lock
- New governance contract:
  - `contracts-internal/governance/b22_p1_authenticity_semantics.main.json`
- New CI enforcer:
  - `scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py`
- New non-vacuous enforcer tests:
  - `backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py`

### 2.5 Adversarial/runtime proof expansion
- Updated:
  - `backend/tests/test_b045_webhooks.py`
  - `backend/tests/test_b046_integration.py`
  - `backend/tests/test_b12_p8_error_contract_normalization.py`
- Added:
  - `backend/tests/test_b22_p1_authenticity_semantics.py`
- Added/covered P1-critical negatives:
  - missing required PayPal auth header -> 401
  - stale PayPal transmission timestamp -> 401
  - tampered PayPal webhook_id -> 401
  - forged PayPal signature -> 401
  - unknown/wrong tenant key -> canonical 401
  - Stripe alias and canonical route auth-failure equivalence
  - constant-work invocation parity for PayPal bad-signature vs unknown-tenant

### 2.6 CI merge-blocking wiring
- File: `.github/workflows/ci.yml`
- Added to `Contract Semantic Drift Gate`:
  - `python scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py`
  - `pytest backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py -q`
  - `pytest backend/tests/test_b22_p1_authenticity_semantics.py -q`
  - targeted P1 auth-normalization tests from `test_b12_p8_error_contract_normalization.py`

## 3. Falsifiable Validation Performed

### 3.1 Local policy/enforcer checks
- `python scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py` -> PASS
- `python scripts/ci/enforce_b22_p0_webhook_surface_lock.py` -> PASS (non-regression)

### 3.2 New/updated test surfaces
- `pytest backend/tests/test_b22_p1_authenticity_semantics.py -q` -> `7 passed`
- `pytest backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py -q` (with repo root + backend in `PYTHONPATH`) -> `6 passed`
- `pytest backend/tests/test_b12_p8_error_contract_normalization.py -q` -> `14 passed`
- `pytest backend/tests/test_b045_webhooks.py -q` -> `12 passed`
- `pytest backend/tests/test_b046_integration.py -q` -> `8 passed`

## 4. Exit Gate Assessment (P1)

1. **EG-P1-1 Per-provider authenticity gate**: PASS (local)
- Shopify/WooCommerce/Stripe semantics preserved.
- PayPal moved from simplified raw-body HMAC to explicit provider envelope semantics with adversarial coverage.

2. **EG-P1-2 Tenant secret authority gate**: PASS (local)
- Server-authoritative tenant-key resolution preserved.
- Wrong/missing tenant key and cross-tenant misuse fail closed.

3. **EG-P1-3 Latency compatibility gate**: PASS (local)
- No blocking remote dependency added to PayPal auth path.
- Bounded verifier measurement added (`test_b22_p1_paypal_verifier_latency_is_bounded_for_hot_path`) with passing p95 bound.

4. **Merge-blocking adversarial proof gate**: PASS (local)
- P1 enforcer + non-vacuous negative controls added and wired into CI.

## 5. Protected-Branch Delivery Evidence

- PR URL: `TBD`
- PR head commit: `TBD`
- Merge commit on `main`: `TBD`
- Post-merge full `main` CI run URL: `TBD`
- Post-merge CI conclusion: `TBD`

This section is finalized after protected-branch merge and authoritative post-merge CI adjudication.
