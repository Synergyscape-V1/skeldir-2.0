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

## 2.7 Mainline CI stabilization required for protected-branch closure
- File: `backend/tests/test_b0567_integration_truthful_scrape_targets.py`
- After landing PR #354, `main` CI failed on `Backend Integration (B0567)` due to scrape-timing nondeterminism in
  `test_t71_task_metrics_delta_on_exporter` (`duration_count` delta occasionally observed before second update was exported).
- Remediation:
  - Replaced single immediate post-task scrape with bounded polling (`10s` max, `200ms` interval).
  - Kept strict assertions (`success>=1`, `failure>=1`, `duration_count>=2`) and fail-closed timeout assertion payload.
- This stabilized required protected-branch CI behavior on `main` without changing production auth semantics.

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

## 3.4 Post-merge CI stabilization check
- `pytest -vv backend/tests/test_b0567_integration_truthful_scrape_targets.py::test_t71_task_metrics_delta_on_exporter` -> `1 passed`

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

4. Exit Gate 4 - Correct-invariant CI adjudication + mainline closure: **PASS**
- Correct invariant is encoded in governance + enforcer + tests.
- Provider-correct remediation landed on `main` via protected branch PR #354.
- A subsequent unrelated `main` CI failure (`B0567` scrape-timing nondeterminism) was remediated and landed via protected branch PR #355.
- Final `main` merge commit has authoritative all-green run set and zero failed check-runs (evidence below).

## 5. Protected Branch Delivery Evidence

1. Provider-correct PayPal remediation landing
- PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/354`
- PR head SHA: `a3b295bdb12b879c12ad4f00e2993c8f6f762d02`
- Merge commit on `main`: `a4e091613a918ef2220e1cff6b6d0916e2a235bf`
- Merge timestamp: `2026-04-19T19:33:52Z`

2. Initial post-merge `main` adjudication for PR #354
- Failing workflow run (unrelated nondeterministic test): `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24637347717`
- Failing job: `Backend Integration (B0567)` (`test_t71_task_metrics_delta_on_exporter`)

3. Stabilization landing for green-main closure
- PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/355`
- PR head SHA: `e1a3641fe720035ef77c941d907bc816c89afa94`
- Merge commit on `main`: `11f7b94df075e3c1f7b9cb60e2939f9cb3456d30`
- Merge timestamp: `2026-04-19T20:52:16Z`

4. Authoritative green `main` evidence on final merged state (`11f7b94`)
- CI workflow run (green): `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24638867065`
- `Backend Integration (B0567)` job (green): `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/24638867065/job/72039174440`
- Full commit run-set query shows 20/20 workflows `completed/success` for commit `11f7b94`.
- Check-runs summary on commit `11f7b94`: `total_check_runs=106`, `failed_count=0`.
