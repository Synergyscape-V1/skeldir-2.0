# Phase B2.2-P1 Remediation Evidence Pack

Date: 2026-04-19
Execution branch: `main`
Scope: **Phase B2.2-P1 - Authenticity Semantics Closure + Tenant Secret Authority Preservation**

## 1. Initial Findings (Validated from `main`)

1. PayPal authenticity on `main` was still a local HMAC shortcut:
- `verify_paypal_signature` used HMAC over a canonical envelope instead of provider-correct asymmetric verification.
- Governance and CI enforced that HMAC envelope model, so checks were green for the wrong invariant.

2. Tenant authority chain was present and sound:
- `X-Skeldir-Tenant-Key` -> hash lookup -> server-side tenant material resolution remained fail-closed.
- Unknown tenant and bad signature paths already shared constant-work auth structure.

3. PayPal trust-anchor semantics were incomplete:
- `cert_url` format checks existed, but no certificate retrieval/cache/expiry + asymmetric verification path existed.
- No SSRF-resilient cert retrieval controls were encoded as merge-blocking invariants.

## 2. Remediation Implemented

## 2.1 Provider-correct PayPal authenticity semantics
- File: `backend/app/webhooks/signatures.py`
- Replaced PayPal HMAC model with PayPal self-verification model:
  - Required envelope: `transmission_id`, `transmission_time`, `transmission_sig`, `auth_algo`, `cert_url`.
  - Canonical message: `transmission_id|transmission_time|tenant_authoritative_webhook_id|crc32(raw_body_decimal)`.
  - Signature primitive: RSA PKCS#1 v1.5 + SHA-256 (`SHA256withRSA` class).
  - Fail-closed on malformed envelope, stale timestamp, bad base64 signature, wrong algo, invalid cert/trust path, verification failure.

## 2.2 Tenant-authoritative PayPal webhook authority preservation
- File: `backend/app/api/webhooks.py`
- Preserved server-authoritative ingress chain and constant-work auth shape.
- Kept PayPal verification material server-resolved from tenant authority (`paypal_webhook_secret`), interpreted as expected PayPal webhook authority ID.
- Optional `PayPal-Webhook-Id` header now acts as a consistency assertion only; provider correctness does not rely on request-derived webhook identity.

## 2.3 Trust-anchor + SSRF controls for cert retrieval
- File: `backend/app/webhooks/signatures.py`
- Added bounded, fail-closed cert trust path:
  - HTTPS-only URL enforcement.
  - Host suffix allowlist (`paypal.com`, `paypalobjects.com`).
  - No URL credentials, no query, no fragment, port restricted to `443`.
  - DNS resolution guard requiring globally routable IPs only.
  - Redirect suppression (`follow_redirects=False`) and host consistency checks.
  - Response max size bound.
  - Bounded fetch timeouts and bounded in-memory cert cache with expiry.

## 2.4 Governance/enforcer invariant correction
- Files:
  - `contracts-internal/governance/b22_p1_authenticity_semantics.main.json`
  - `scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py`
  - `backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py`
- Corrected lock semantics from `hmac_sha256_canonical_envelope` to `rsa_sha256_canonical_message_crc32`.
- Added merge-blocking assertions for:
  - asymmetric primitive requirement,
  - cert-fetch trust policy and boundedness flags,
  - tenant-authoritative webhook ID source,
  - PayPal OpenAPI required/optional header contract semantics.

## 2.5 Contract + generated type convergence
- Files:
  - `api-contracts/openapi/v1/webhooks/paypal.yaml`
  - `api-contracts/dist/openapi/v1/webhooks.paypal.bundled.yaml`
  - `frontend/src/types/api/webhooks-paypal.ts`
- `PAYPAL-WEBHOOK-ID` changed to optional in API contract/types; required auth headers remain enforced.

## 2.6 Non-vacuous proof harness updates
- Files:
  - `backend/tests/helpers/paypal_signature.py` (new)
  - `backend/tests/test_b22_p1_authenticity_semantics.py`
  - `backend/tests/test_b045_webhooks.py`
  - `backend/tests/test_b046_integration.py`
  - `backend/tests/test_b12_p8_error_contract_normalization.py`
- Added real asymmetric PayPal test signing/cert fixture and moved PayPal tests off HMAC shortcut assumptions.
- Added bounded fail-closed test for cert-fetch failure path.

## 3. Falsifiable Validation Performed

## 3.1 Enforcer / contract locks
- `python scripts/ci/enforce_b22_p0_webhook_surface_lock.py` -> PASS
- `python scripts/ci/enforce_b22_p1_authenticity_semantics_lock.py` -> PASS

## 3.2 B2.2-P1 auth semantics and lock negative controls
- `pytest backend/tests/test_b22_p1_authenticity_semantics_lock_enforcer.py -q` -> `7 passed`
- `pytest backend/tests/test_b22_p1_authenticity_semantics.py -q` -> `11 passed`

## 3.3 Auth path adversarial normalization checks
- `pytest backend/tests/test_b12_p8_error_contract_normalization.py -q` -> `14 passed`
- `pytest backend/tests/test_b045_webhooks.py -q` -> `12 passed`
- `pytest backend/tests/test_b046_integration.py -q` -> `8 passed`

## 4. Exit Gate Assessment (B2.2-P1)

1. Exit Gate 1 - Provider-correct PayPal authenticity closure: **PASS (local proof)**
- PayPal no longer uses local HMAC secret verification.
- Asymmetric signature verification + canonical CRC32 message + cert trust path now enforced.

2. Exit Gate 2 - Tenant authority and pre-persistence trust boundary: **PASS (local proof)**
- Server-authoritative tenant-key resolution preserved.
- Wrong/missing tenant and bad signature cases remain fail-closed with no authoritative persistence.

3. Exit Gate 3 - Trust-anchor / SSRF / boundedness closure: **PASS (local proof)**
- Cert retrieval path has explicit SSRF-resistant constraints and bounded runtime behavior.
- Bounded fail-closed cert-fetch test added and passing.

4. Exit Gate 4 - Correct-invariant CI adjudication + mainline closure: **IN PROGRESS**
- Correct invariant is encoded in governance + enforcer + tests.
- Protected-branch merge and authoritative green `main` run evidence recorded below after merge.

## 5. Protected Branch Delivery Evidence

- PR URL: `TBD`
- PR head SHA: `TBD`
- Merge commit on `main`: `TBD`
- Green `main` CI run URL: `TBD`
- Required checks status: `TBD`

This section is finalized only after authoritative protected-branch merge and post-merge green `main` adjudication.
