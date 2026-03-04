# B1.2-P6 State Baseline (Pre-Remediation Snapshot)

Scope: authority was current `main` runtime at P6 start; prior writeups treated as hypotheses.

## 1) Where Roles Live
- Role catalog + tenant membership role assignments live in auth substrate tables:
  `public.roles`, `public.tenant_memberships`, `public.tenant_membership_roles`.
- Canonical schema sources:
  - `alembic/versions/007_skeldir_foundation/202602271430_b12_p2_auth_substrate.py`
  - `backend/app/models/auth_substrate.py`

## 2) Where Tokens Are Minted/Refreshed
- Access/refresh token issuance path:
  - login endpoint: `backend/app/api/auth.py` -> `issue_login_token_pair(...)`
  - refresh endpoint: `backend/app/api/auth.py` -> `rotate_refresh_token(...)`
- Prior to P6 remediation, access token minting did not query tenant membership roles and did not guarantee stable `role`/`roles` claims for issued tokens.

## 3) Where Revocation Is Enforced
- Revocation check execution:
  - verifier dependency: `backend/app/security/auth.py` (`get_auth_context`, `assert_access_token_active`)
  - substrate reads/writes: `backend/app/services/auth_revocation.py`
  - kill-switch table: `public.auth_user_token_cutoffs`
- Mutation path existed (`upsert_tokens_invalid_before`) but was not wired to role mutation flows at baseline because no role-mutation endpoint was present.

## 4) Route Classification Audit (JWT vs Non-JWT)
- JWT/Bearer route family:
  - `api-contracts/openapi/v1/auth.yaml` (`bearerAuth`) + FastAPI auth router (`backend/app/api/auth.py`)
- Non-JWT webhook family remains explicit and separate:
  - `api-contracts/openapi/v1/webhooks/*.yaml` uses `tenantKeyAuth`
  - runtime enforcement is tenant-key + provider HMAC (`backend/app/api/webhooks.py`)

## 5) Hot-Path I/O Baseline
- Baseline risk at P6 start:
  - RBAC claim extraction path was not centralized as a reusable dependency guard.
  - No explicit CI gate asserted role checks remained DB-free on request hot path.
- P6 remediation adds a dedicated zero-role-DB-read proof test and merge-blocking CI check.
