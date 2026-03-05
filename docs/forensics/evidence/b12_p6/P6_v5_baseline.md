# B1.2-P6 v5 Baseline

## Scope and method
- Branch baseline captured from `origin/main` at commit `5f116178679f54242cb62f71f3beb39fa3452d40`.
- Contract inventory source: `api-contracts/openapi/v1/**/*.yaml` parsed operation-by-operation.
- Runtime inventory source: `app.openapi()` from `backend/app/main.py`.

## 1) Contract inventory: operation security declarations (current)
Contract inventory (`45` operations total) shows monolithic `bearerAuth` for JWT families, `tenantKeyAuth` for webhook contracts, and security-empty refresh/login and selected health routes.

| File | Method | Path | Security |
| --- | --- | --- | --- |
| attribution.yaml | GET | /api/attribution/revenue/realtime | `[{"bearerAuth":[]}]` |
| attribution.yaml | GET | /api/attribution/channels | `[{"bearerAuth":[]}]` |
| attribution.yaml | GET | /api/attribution/explain/{entity_type}/{entity_id} | `[{"bearerAuth":[]}]` |
| attribution.yaml | POST | /api/attribution/platform-connections | `[{"bearerAuth":[]}]` |
| attribution.yaml | GET | /api/attribution/platform-connections/{platform} | `[{"bearerAuth":[]}]` |
| attribution.yaml | POST | /api/attribution/platform-credentials | `[{"bearerAuth":[]}]` |
| auth.yaml | POST | /api/auth/login | `[]` |
| auth.yaml | POST | /api/auth/refresh | `[]` |
| auth.yaml | POST | /api/auth/logout | `[{"bearerAuth":[]}]` |
| auth.yaml | GET | /api/auth/verify | `[{"bearerAuth":[]}]` |
| auth.yaml | POST | /api/auth/admin/token-cutoff | `[{"bearerAuth":["admin"]}]` |
| auth.yaml | GET | /api/auth/admin/rbac-check | `[{"bearerAuth":["admin"]}]` |
| auth.yaml | POST | /api/auth/admin/membership-role | `[{"bearerAuth":["admin"]}]` |
| export.yaml | GET | /api/export/revenue | `[{"bearerAuth":[]}]` |
| export.yaml | GET | /api/export/csv | `[{"bearerAuth":[]}]` |
| export.yaml | GET | /api/export/json | `[{"bearerAuth":[]}]` |
| export.yaml | GET | /api/export/excel | `[{"bearerAuth":[]}]` |
| health.yaml | GET | /api/health | `[]` |
| health.yaml | GET | /api/health/detailed | `[{"bearerAuth":[]}]` |
| health.yaml | GET | /api/health/ready | `[]` |
| health.yaml | GET | /api/health/live | `[]` |
| llm-budget.yaml | POST | /api/budget/optimize | `[{"bearerAuth":[]}]` |
| llm-budget.yaml | GET | /api/budget/recommendations/{job_id} | `[{"bearerAuth":[]}]` |
| llm-explanations.yaml | GET | /api/v1/explain/{entity_type}/{entity_id} | `[{"bearerAuth":[]}]` |
| llm-investigations.yaml | POST | /api/investigations | `[{"bearerAuth":[]}]` |
| llm-investigations.yaml | GET | /api/investigations/{investigation_id}/status | `[{"bearerAuth":[]}]` |
| reconciliation.yaml | GET | /api/reconciliation/status | `[{"bearerAuth":[]}]` |
| reconciliation.yaml | GET | /api/reconciliation/platform/{platform_id} | `[{"bearerAuth":[]}]` |
| reconciliation.yaml | POST | /api/reconciliation/sync | `[{"bearerAuth":[]}]` |
| revenue.yaml | GET | /api/v1/revenue/realtime | `[{"bearerAuth":[]}]` |
| webhooks/paypal.yaml | POST | /api/webhooks/paypal/sale_completed | `[{"tenantKeyAuth":[]}]` |
| webhooks/paypal.yaml | POST | /api/webhooks/paypal/payment/capture/completed | `[{"tenantKeyAuth":[]}]` |
| webhooks/paypal.yaml | POST | /api/webhooks/paypal/payment/sale/refunded | `[{"tenantKeyAuth":[]}]` |
| webhooks/shopify.yaml | POST | /api/webhooks/shopify/order_create | `[{"tenantKeyAuth":[]}]` |
| webhooks/shopify.yaml | POST | /api/webhooks/shopify/orders/paid | `[{"tenantKeyAuth":[]}]` |
| webhooks/shopify.yaml | POST | /api/webhooks/shopify/refunds/create | `[{"tenantKeyAuth":[]}]` |
| webhooks/shopify.yaml | POST | /api/webhooks/shopify/checkouts/update | `[{"tenantKeyAuth":[]}]` |
| webhooks/stripe.yaml | POST | /api/webhooks/stripe/charge/succeeded | `[{"tenantKeyAuth":[]}]` |
| webhooks/stripe.yaml | POST | /api/webhooks/stripe/payment_intent_succeeded | `[{"tenantKeyAuth":[]}]` |
| webhooks/stripe.yaml | POST | /api/webhooks/stripe/payment_intent/succeeded | `[{"tenantKeyAuth":[]}]` |
| webhooks/stripe.yaml | POST | /api/webhooks/stripe/charge/refunded | `[{"tenantKeyAuth":[]}]` |
| webhooks/woocommerce.yaml | POST | /api/webhooks/woocommerce/order/created | `[{"tenantKeyAuth":[]}]` |
| webhooks/woocommerce.yaml | POST | /api/webhooks/woocommerce/order/updated | `[{"tenantKeyAuth":[]}]` |
| webhooks/woocommerce.yaml | POST | /api/webhooks/woocommerce/order_completed | `[{"tenantKeyAuth":[]}]` |
| webhooks/woocommerce.yaml | POST | /api/webhooks/woocommerce/order/refunded | `[{"tenantKeyAuth":[]}]` |

## 2) Runtime OpenAPI inventory (`app.openapi()`)
- Total runtime operations: `34`.
- Operations with missing `security`: `16`.
- Missing-security list includes:
  - `POST /api/auth/login`
  - `POST /api/auth/refresh`
  - `GET /health/live`, `GET /health`, `GET /api/health`, `GET /api/health/ready`, `GET /api/health/live`, `GET /health/ready`, `GET /health/worker`, `GET /metrics`, `GET /`
  - webhook ingress operations (`/api/webhooks/...`) currently render with no `security` in runtime OpenAPI.
- Runtime scheme usage currently:
  - `bearerAuth: []` on 15 operations.
  - `bearerAuth: ["admin"]` on 3 admin operations.

## 3) Token-type endpoint typing (current)
- Access JWT endpoints (runtime dependency path): `Depends(get_auth_context)` or `Security(get_auth_context, scopes=...)`.
  - Present in `backend/app/api/auth.py`, `attribution.py`, `revenue.py`, `reconciliation.py`, `export.py`, `platforms.py`, `health.py`.
- Refresh endpoint:
  - `POST /api/auth/refresh` consumes refresh token from request body (`RefreshRequest.refresh_token`) and calls `rotate_refresh_token(...)`.
  - No dedicated refresh bearer security scheme is declared in runtime OpenAPI.
- Webhook endpoints:
  - Tenant API key/HMAC validated in `backend/app/api/webhooks.py` using `tenant_secrets(...)`.
  - Runtime OpenAPI currently does not emit `tenantKeyAuth` on these routes.

## 4) Empty-role -> viewer fallback location
- Viewer fallback is implemented in role normalization:
  - `backend/app/services/auth_tokens.py`:
    - `_normalize_role_codes(...)` returns `ordered or ["viewer"]`.
    - `resolve_membership_roles(...)` always returns normalized role list, therefore empty membership-role result becomes `["viewer"]`.
- Refresh mint path:
  - `rotate_refresh_token(...)` calls `resolve_membership_roles(...)` and mints access token claims from that result.
  - Current behavior allows viewer fallback even when membership roles are empty.

## 5) Branch protection required checks (enforcement plane truth)
From GitHub branch protection API for `main`:
- `B0.7 P2 Runtime Proof (LLM + Redaction)`
- `Celery Foundation B0.5.1`
- `Validate Contracts`
- `Frontend Contract Consumption Gate`
- `Mock Usability Gate`
- `Phase 1 Negative Controls`
- `Phase 1 Runtime Conformance`
- `B0.6 Phase 2 Adjudication`
- `Phase Gates (B0.3)`
- `Phase 8 Regression Gate (Full Physics)`
- `b11-p2-secret-chokepoint-gate`
- `b11-p2-readiness-gate`
- `b11-p4-static-and-runtime-gate`
- `b11-p4-ci-audit-gate`
- `JWT Tenant Context Invariants`
- `B1.2 P6 RBAC Proofs`

## Baseline conclusions
- `H01` validated: contract plane currently overloads `bearerAuth`; no explicit access-vs-refresh bearer scheme separation.
- `H02` validated: runtime OpenAPI has non-webhook non-public routes with no security declarations, and webhook routes with missing emitted security.
- `H03` validated: JWT-protected baseline routes (logout/verify and broad JWT family) still show empty scopes.
- `H04` validated: refresh role resolution path currently defaults empty roles to viewer via `_normalize_role_codes`.
