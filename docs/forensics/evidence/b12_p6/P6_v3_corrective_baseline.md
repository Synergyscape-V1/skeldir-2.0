# B1.2-P6 v3 Corrective Baseline

Date: 2026-03-05  
Branch: `b12-p6-r1-r2-schema-fix` (PR #170 open)  
Authority: repository code + local validator runs + PR CI logs.

## 1) Scope enforcement implementation (current state)
- `backend/app/security/auth.py` currently enforces scopes via role-precedence logic:
  - `ROLE_PRECEDENCE = ("admin", "manager", "viewer")`
  - `_ROLE_PRECEDENCE_INDEX` rank arithmetic in `_enforce_required_scopes(...)`.
- This confirms H01: precedence evaluator remains in verifier path.

## 2) Current minted claims and enforcement source
- Minting path:
  - `backend/app/services/auth_tokens.py::issue_login_token_pair`
  - `backend/app/services/auth_tokens.py::rotate_refresh_token`
- Current access JWT claims include:
  - `role` (single primary role)
  - `roles` (role list)
  - no `scopes` claim.
- Enforcement currently derives authorization from `role/roles` + precedence, not fat scope membership.
- This confirms H02: fat scope embedding is absent.

## 3) OpenAPI reflection truth for admin routes
- Verified via `app.openapi()`:
  - `/api/auth/admin/token-cutoff` -> `security: [{"bearerAuth":["admin"]}]`
  - `/api/auth/admin/rbac-check` -> `security: [{"bearerAuth":["admin"]}]`
  - `/api/auth/admin/membership-role` -> `security: [{"bearerAuth":["admin"]}]`
- Router-level scope intent is correctly reflected in OpenAPI.

## 4) Why CI fails now
- PR #170 required check failure is `B1.2 P6 RBAC Proofs`.
- Failing assertion is in `test_eg6a1_admin_namespace_routes_are_default_deny_scoped`.
- Root cause:
  - route-lint traverses `route.dependant` and misses router-level dependency attachment in CI runtime model.
  - Result is false violations despite OpenAPI proving `["admin"]`.
- This confirms H03.

## 5) Integration mapping validator status (C3)
- Local direct run:
  - `python scripts/governance/validate_integration_mappings.py`
  - result: `ALL C3 VALIDATIONS PASSED`.
- In PR CI history, C3 failures observed earlier were tied to failed/canceled workflow graph states during red runs, not a reproducible OAuth2 schema mismatch on current head.
- Current evidence refutes a deterministic C3 schema incompatibility at this SHA.

## 6) Refresh downgrade behavior (current test policy)
- `backend/tests/test_b12_p6_rbac_enforcement.py::test_eg6r1_refresh_after_downgrade_db_authoritative`
  - currently allows either:
    - `200` with downgraded token, or
    - `401`.
- This confirms H04: test is permissive and does not hard-encode UX requirement (`refresh_status == 200` for valid refresh token).

## Baseline verdict
- H01: supported
- H02: supported
- H03: supported
- H04: supported
- H05: refuted at current head (C3 passes locally; CI C3 break not reproducible as mapping-schema mismatch)
