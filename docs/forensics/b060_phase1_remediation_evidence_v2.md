# B0.6 Phase 1 Remediation Evidence Pack (v2)

Date: 2026-01-27

## SHAs

- Before: `2fc0a5365ebaeffd5f04c38233f7648624099501`
- After: `d95d0fbdb4fb8131869bc735adf243b99df73ec1`

## Context Delta Re-validation

See `docs/forensics/phase1_context_delta_notes.md`.

## Files Changed

- `.env.example`
- `.github/workflows/b0545-convergence.yml`
- `.github/workflows/b06_phase0_adjudication.yml`
- `.github/workflows/ci.yml`
- `backend/app/api/revenue.py`
- `backend/app/core/config.py`
- `backend/app/db/deps.py`
- `backend/app/main.py`
- `backend/app/security/__init__.py`
- `backend/app/security/auth.py`
- `backend/requirements.txt`
- `tests/test_b06_realtime_revenue_v1.py`
- `tests/test_b060_phase1_auth_tenant.py`
- `docs/forensics/phase1_context_delta_notes.md`
- `docs/forensics/b060_phase1_remediation_evidence.md`
- `docs/forensics/b060_phase1_remediation_evidence_v2.md`
- `docs/forensics/INDEX.md`

## Commands Executed

- `git status -sb`
- `git rev-parse HEAD`
- `rg -n "Authorization|B0_6_BEARER_TOKEN|Bearer" backend -g "*.py"`
- `rg -n "jwt|JWT|jose|jwks|pyjwt|oauth2|OAuth2" backend -g "*.py"`
- `rg -n "auth_context|request.state" backend/app -g "*.py"`
- `Get-Content backend/app/core/tenant_context.py`
- `Get-Content backend/app/db/session.py`
- `Get-Content backend/app/main.py`
- `Get-Content .github/workflows/b06_phase0_adjudication.yml`
- `Get-Content .github/workflows/ci.yml | Select-String -Pattern "test_b06_realtime_revenue_v1" -Context 3,3`
- `Get-Content tests/test_b06_realtime_revenue_v1.py`
- `gh run list --branch b060-phase1-auth-tenant --limit 20`
- `gh run view 21411787347 --log --job 61650332306`
- `gh pr view 29 --json state,mergedAt,mergeCommit`

## CI Run Link

- https://github.com/Muk223/skeldir-2.0/actions/runs/21411787347 (B0.6 Phase 0 Adjudication)
- https://github.com/Muk223/skeldir-2.0/actions/runs/21411787347/job/61650332306 (job)

## CI Log Excerpt (Gate P1-F)

```
> B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0516999Z 
 tests/test_b060_phase1_auth_tenant.py::test_missing_token_returns_401 
  B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0532139Z PASSED                        
                                           [ 20%]
> B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0560936Z 
 tests/test_b060_phase1_auth_tenant.py::test_invalid_token_returns_401 
  B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0572129Z PASSED                        
                                           [ 40%]
> B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0601540Z 
 tests/test_b060_phase1_auth_tenant.py::test_missing_tenant_claim_returns_401 
  B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0612406Z PASSED                        
                                           [ 60%]
> B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0645048Z 
 tests/test_b060_phase1_auth_tenant.py::test_valid_token_sets_tenant_and_calls_session 
  B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0657745Z PASSED                        
                                           [ 80%]
> B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.0690896Z 
 tests/test_b060_phase1_auth_tenant.py::test_two_tokens_yield_distinct_tenants 
  B0.6 Phase 0 Adjudication	B0.6 Phase 0 adjudication tests	2026-01-27T19:50:30.4109015Z PASSED                        
                                           [100%]
```
