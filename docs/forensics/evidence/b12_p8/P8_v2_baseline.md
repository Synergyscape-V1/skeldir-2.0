# B1.2-P8 v2 Corrective Baseline (Pre-Remediation)

Date: 2026-03-08  
Branch base: `origin/main` @ `059f8a539`  
Work branch: `p8-corrective-v2-main`

## Scope
This baseline validates or refutes H01-H05 before any corrective implementation.

## H01 - Webhook auth early-returns on unknown tenant key before signature compute
Status: **Validated**

Evidence:
- Webhook dependency/verification split:
  - `tenant_secrets` resolves API key and may raise before route handler signature verification in [backend/app/api/webhooks.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\api\webhooks.py):78 and :83-85.
  - Route handlers call `verify_*_signature` only after dependency success in [backend/app/api/webhooks.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\api\webhooks.py):258, :294, :342, :541, :576.
  - Unknown key raises in [backend/app/core/tenant_context.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\core\tenant_context.py):66-67.
- Runtime control-flow probe:
  - unknown key -> `verify_calls=0`
  - known key + bad signature -> `verify_calls=1`
  - Artifact: `docs/forensics/evidence/b12_p8/runtime/p8_v2_control_flow_baseline.json`

## H02 - Current parity tests do not fully exercise production control flow
Status: **Validated**

Evidence:
- Existing P8 tests use dependency overrides/monkeypatching that bypass live tenant-secret resolution and real dependency choreography:
  - `app.dependency_overrides[webhooks_api.tenant_secrets]` in multiple tests.
  - `monkeypatch.setattr(webhooks_api, "get_tenant_with_webhook_secrets", ...)`.
- Artifacts:
  - [backend/tests/test_b12_p8_error_contract_normalization.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\tests\test_b12_p8_error_contract_normalization.py)
  - [tests/contract/test_contract_semantics.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\tests\contract\test_contract_semantics.py)
  - `docs/forensics/evidence/b12_p8/runtime/p8_v2_monkeypatch_inventory.txt`

## H03 - No bounded pre-crypto body-size policy
Status: **Validated**

Evidence:
- No webhook/body-size cap enforcement found in app code (`Content-Length`, 413, max-bytes policy absent).
- Webhook and PII middleware both read full request body:
  - [backend/app/api/webhooks.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\api\webhooks.py):257, :292, :341, :540, :575
  - [backend/app/middleware/pii_stripping.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\middleware\pii_stripping.py):144

## H04 - P8 check not proven required in live branch protection
Status: **Validated**

Evidence:
- Live branch-protection contexts for `main` do **not** include `B1.2 P8 Error Contract Proofs` (nor `B1.2 P7 Worker Coherence Proofs`).
- Artifact: `docs/forensics/evidence/b12_p8/runtime/p8_v2_main_required_status_checks.json`
- The repo governance contract lists P8 as expected, but live protection is behind contract:
  - [contracts-internal/governance/b03_phase2_required_status_checks.main.json](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\contracts-internal\governance\b03_phase2_required_status_checks.main.json):18

## H05 - Header/422 leak proofs are missing or non-merge-blocking
Status: **Partially validated**

Findings:
- `WWW-Authenticate` on sampled 401 responses is currently absent (no parameter leakage observed).
  - Artifact: `docs/forensics/evidence/b12_p8/runtime/p8_v2_runtime_baseline_samples.json`
- Auth-header malformed cases sampled return 401 ProblemDetails, not 422 pointer dumps.
  - Artifact: `docs/forensics/evidence/b12_p8/runtime/p8_v2_runtime_baseline_samples.json`
- Business-validation 422 pointer surface exists after valid webhook auth (Shopify route example).
  - 422 `application/json` body with FastAPI `detail[].loc` pointer.
  - Artifact: `docs/forensics/evidence/b12_p8/runtime/p8_v2_422_shopify_baseline.json`

## Auth Failure Emitter Map (Current)
JWT plane:
- `unauthorized_auth_error()` / `forbidden_auth_error()` in [backend/app/security/auth.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\security\auth.py):81-98, invoked by token parse/claims/scope checks.
- Global normalizer in [backend/app/main.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\main.py):98-126 for `AuthError` and raw 401/403 `HTTPException`.

Webhook/HMAC plane:
- `tenant_secrets` dependency in [backend/app/api/webhooks.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\api\webhooks.py):78-85.
- Secret lookup/unknown key raise in [backend/app/core/tenant_context.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\core\tenant_context.py):36-77.
- Vendor signature checks in [backend/app/webhooks/signatures.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\webhooks\signatures.py):11-65.
- Route-level unauthorized raises after signature check in [backend/app/api/webhooks.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\api\webhooks.py):258-259, :294-295, :342-343, :541-542, :576-577.

RBAC deny plane:
- Scope enforcement raises forbidden in [backend/app/security/auth.py](c:\Users\ayewhy\II SKELDIR II\.tmp\p8-main\backend\app\security\auth.py):171-179.

## Baseline Conclusion
P8 v2 corrective work is required. The highest-severity confirmed gaps are:
1. Webhook existence-oracle control-flow asymmetry (H01).
2. Missing pre-crypto bounded-input policy (H03).
3. Live branch-protection required-check mismatch for P8 (H04).
4. Business-validation 422 pointer exposure after valid auth on at least one webhook route (H05 partial).
