# B1.2-P6 v2 Baseline and Forensic Validation

Date: 2026-03-05  
Branch under test: `b12-p6-r1-r2-schema-fix`  
Authority: running code + contracts + CI governance state.

## 1) Contracts scope visibility baseline
- `api-contracts/openapi/v1/_common/base.yaml`: `bearerAuth` converted to OAuth2 password flow with scopes `admin|manager|viewer`.
- `api-contracts/openapi/v1/auth.yaml`: admin endpoints now declare `security: [{ bearerAuth: ["admin"] }]`:
  - `/api/auth/admin/token-cutoff`
  - `/api/auth/admin/rbac-check`
  - `/api/auth/admin/membership-role`
- Verdict: H02 (scopes absent from contracts) is refuted after remediation.

## 2) Code enforcement baseline
- `backend/app/api/auth.py`:
  - Admin namespace moved under router-level default-deny:
    - `admin_router = APIRouter(prefix="/admin", dependencies=[Security(get_auth_context, scopes=["admin"])])`
  - Admin routes mounted on that router.
- `backend/app/security/auth.py`:
  - `get_auth_context` now accepts `SecurityScopes`.
  - Role hierarchy enforced (`admin >= manager >= viewer`) with 403 on insufficient scope.
  - Invalid/missing token path remains 401.
- Verdict: H01 (admin namespace not default-deny) is refuted after remediation.

## 3) Refresh role authority baseline
- `backend/app/services/auth_tokens.py::rotate_refresh_token`:
  - Refresh re-mints access role claims from DB membership roles (`resolve_membership_roles`) for `(user_id, tenant_id)`.
  - Negative control toggle exists to prove non-vacuity:
    - `SKELDIR_B12_P6_NEGATIVE_COPY_ROLE_FORWARD=1` intentionally violates this.
- Verdict: H03 (refresh can silently copy-forward stale role) is refuted in normal mode and proven detectable via negative control.

## 4) Branch protection truth plane
- Live required checks on `main` (GitHub API) include:
  - `B1.2 P6 RBAC Proofs`
- Verdict: H05 (P6 proofs not required in branch protection) is refuted.

## 5) Runtime instability discovered during forensic run
- Failure signature under local fallback DB:
  - `relation "public.users" does not exist`
  - root cause: local fallback DB was not the CI-migrated proof DB.
- Additional harness brittleness:
  - P6 seed helper forced `current_user == app_user`.
  - CI-style DSN uses `postgres` in the P6 workflow.
- Corrective test harness remediation:
  - `backend/tests/test_b12_p6_rbac_enforcement.py` now accepts runtime identity `app_user` or `postgres`.

## 6) Scientific validation run (clean DB, migrated, CI-style)
- DB prep:
  - fresh database `skeldir_p6_closure_20260305`
  - `alembic upgrade head` completed successfully
- Proof run:
  - `pytest backend/tests/test_b12_p6_rbac_enforcement.py -q`
  - Result: `11 passed`
- Validated gates from this run:
  - EG6.C1, EG6.A1, EG6.D1, EG6.T1, EG6.R1, EG6.P1, EG6.CI1

## Baseline conclusion
- The v2 hypothesis set is now closed on code/contracts/runtime for this branch.
- Final completion authority remains: merge SHA on `main` with required checks green.
