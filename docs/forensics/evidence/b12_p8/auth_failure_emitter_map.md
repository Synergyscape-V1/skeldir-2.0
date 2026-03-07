# B1.2-P8 Auth Failure Emitter Map

Authority snapshot:
- Branch target: `main`
- Local adjudicated SHA: `130e7b7f292c1ab177772a5a3c754da5d786f4d9`

Canonical normalizer entrypoint:
- `AuthError` handler in [`backend/app/main.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\main.py:98)
- Problem payload builder in [`backend/app/api/problem_details.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\problem_details.py:42)
- Full static callsite inventory (emitters + handlers + security modality declarations): [`p8_static_auth_emitters.txt`](C:\Users\ayewhy\II SKELDIR II\docs\forensics\evidence\b12_p8\runtime\p8_static_auth_emitters.txt)

## Emitter Inventory

1. JWT dependency / token verification / claims / revocation
- Emitters: [`backend/app/security/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\security\auth.py:128), [`backend/app/security/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\security\auth.py:295), [`backend/app/security/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\security\auth.py:432)
- Canonical emit call: `raise unauthorized_auth_error()` / `raise forbidden_auth_error()`
- Normalized output: `application/problem+json`, stable keys, stable code taxonomy.

2. RBAC deny path
- Emitters: [`backend/app/security/rbac.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\security\rbac.py:49), [`backend/app/security/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\security\auth.py:177)
- Canonical emit call: `raise forbidden_auth_error()`
- Normalized output: canonical `403` ProblemDetails.

3. Auth API route-level failures
- Emitters: [`backend/app/api/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\auth.py:124), [`backend/app/api/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\auth.py:141), [`backend/app/api/auth.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\auth.py:200)
- Canonical emit call: `raise unauthorized_auth_error()` / `raise forbidden_auth_error()`
- Normalized output: canonical 401/403 ProblemDetails.

4. Webhook/HMAC signature and tenant-key failures
- Emitters: [`backend/app/api/webhooks.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\webhooks.py:82), [`backend/app/api/webhooks.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\webhooks.py:259), [`backend/app/api/webhooks.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\api\webhooks.py:577)
- Canonical emit call: `raise unauthorized_auth_error()`
- Removed leak surfaces: `vendor`, `invalid_signature`, `invalid_tenant_key` JSON payloads are no longer emitted as 401 bodies.

5. Tenant-key resolution dependency
- Emitters: [`backend/app/core/tenant_context.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\core\tenant_context.py:51), [`backend/app/core/tenant_context.py`](C:\Users\ayewhy\II SKELDIR II\backend\app\core\tenant_context.py:67)
- Canonical emit call: `raise unauthorized_auth_error()`
- Normalized output: canonical 401 ProblemDetails.
