# B0.5.7-P6 CI Enforcement + Governance Cleanup Evidence

Status: DRAFT (requires CI run link update after merge)

## Objective
Enforce production-truth constraints in CI for B0.5.7:
- E2E runs under least-privilege runtime identity with deterministic identity assertion.
- E2E run is non-optional (part of canonical CI workflow).
- Redis references removed/quarantined; CI fails on new Redis references.
- Forensics INDEX governance enforced and updated for Phase 6.

## Investigation A — CI topology and required workflows
Command:
```
Get-ChildItem -Name .github/workflows
```
Output:
```
.gitkeep
b0541-view-registry.yml
b0542-refresh-executor.yml
b0543-matview-task-layer.yml
b0545-convergence.yml
b057-p3-webhook-ingestion-least-privilege.yml
b057-p4-llm-audit-persistence.yml
b057-p5-full-chain.yml
channel_governance_ci.yml
ci.yml
contract-artifacts.yml
contract-enforcement.yml
contract-publish.yml
contract-validation.yml
contracts.yml
empirical-validation.yml
mock-contract-validation.yml
phase-gates.yml
r0-preflight-validation.yml
r1-contract-runtime.yml
r1-validation.yml
r2-data-truth-hardening.yml
r3-ingestion-under-fire.yml
r4-worker-failure-semantics.yml
r5-context-gathering.yml
r5-remediation.yml
r6-worker-resource-governance.yml
r7-final-winning-state.yml
schema-deploy-production.yml
schema-drift-check.yml
schema-validation.yml
workflow-yaml-lint.yml
```

Canonical CI workflow (by convention): `ci.yml`.

Triggers in canonical CI:
```
Select-String -Path .github/workflows/ci.yml -Pattern '^on:' -Context 0,6
```
Output:
```
.github\workflows\ci.yml:3:on:
.github\workflows\ci.yml:4:  push:
.github\workflows\ci.yml:5:    branches: [main, develop]
.github\workflows\ci.yml:6:  pull_request:
.github\workflows\ci.yml:7:    branches: [main, develop]
.github\workflows\ci.yml:8:  workflow_dispatch:
```

B0.5.7 E2E workflow (prior P5) triggers:
```
Select-String -Path .github/workflows/b057-p5-full-chain.yml -Pattern '^on:' -Context 0,6
```
Output:
```
.github\workflows\b057-p5-full-chain.yml:3:on:
.github\workflows\b057-p5-full-chain.yml:4:  pull_request:
.github\workflows\b057-p5-full-chain.yml:5:  push:
.github\workflows\b057-p5-full-chain.yml:6:    branches: [main]
.github\workflows\b057-p5-full-chain.yml:7:  workflow_dispatch:
```

Conclusion: The canonical merge-gating workflow is assumed to be `ci.yml`. Branch protection is not visible locally; required-check configuration must ensure `CI` is enforced.

## Investigation B — DB identity in CI (runtime vs migrations)
Command:
```
Select-String -Path .github/workflows/b057-p5-full-chain.yml -Pattern 'MIGRATION_|RUNTIME_|DATABASE_URL|DB_SUPER|DB_NAME|DB_HOST|DB_PORT'
```
Output:
```
.github\workflows\b057-p5-full-chain.yml:27:      DB_NAME: skeldir_b057_p5
.github\workflows\b057-p5-full-chain.yml:28:      DB_HOST: 127.0.0.1
.github\workflows\b057-p5-full-chain.yml:29:      DB_PORT: "5432"
.github\workflows\b057-p5-full-chain.yml:30:      DB_SUPERUSER: postgres
.github\workflows\b057-p5-full-chain.yml:31:      DB_SUPERPASS: postgres
.github\workflows\b057-p5-full-chain.yml:33:      MIGRATION_USER: migration_owner
.github\workflows\b057-p5-full-chain.yml:34:      MIGRATION_PASS: migration_owner
.github\workflows\b057-p5-full-chain.yml:35:      RUNTIME_USER: app_user
.github\workflows\b057-p5-full-chain.yml:36:      RUNTIME_PASS: app_user
.github\workflows\b057-p5-full-chain.yml:38:      DATABASE_URL: postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/skeldir_b057_p5
.github\workflows\b057-p5-full-chain.yml:39:      B057_P5_RUNTIME_DATABASE_URL: postgresql://app_user:app_user@127.0.0.1:5432/skeldir_b057_p5
.github\workflows\b057-p5-full-chain.yml:40:      B057_P5_ADMIN_DATABASE_URL: postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir_b057_p5
.github\workflows\b057-p5-full-chain.yml:41:      MIGRATION_DATABASE_URL: postgresql://migration_owner:migration_owner@127.0.0.1:5432/skeldir_b057_p5
```

Finding: Workflow separates migration owner from runtime user, but lacks an explicit runtime identity assertion in CI.

## Investigation C — Redis dependency sweep
Command:
```
rg -n "redis://|REDIS|redis\b" . --no-messages
```
Output (abridged):
```
scripts/ci/enforce_postgres_only.py:19:REDIS_PATTERN = re.compile(r"(redis://|\bredis\b|\bREDIS\b)", re.IGNORECASE)
backend/tests/test_b051_celery_foundation.py:217:    assert "redis" not in broker and "redis" not in backend
backend/validation/evidence/runtime/configuration_complete.txt:10:   - pkgs.redis (task queue)
backend/validation/evidence/runtime/configuration_complete.txt:35:   - redis-server (PID 2)
backend/validation/evidence/runtime/configuration_complete.txt:43:- redis-cli PING ? PONG
backend/validation/evidence/runtime/nix_baseline.txt:24:- pkgs.redis (required for task queue)
artifacts_vt_run3/.../nix_baseline.txt:24:- pkgs.redis (required for task queue)
artifacts_vt_run3/.../configuration_complete.txt:10:   - pkgs.redis (task queue)
docs/forensics/archive/... (multiple historical references)
docs/forensics/backend/B0.5.1_Foundation_Forensic_Assessment.md:11: ... Procfile ... empirical-validation.yml ... replit.nix includes Redis
```

Classification:
- Allowed evidence/history: `docs/forensics/**`, `backend/validation/evidence/**`, `artifacts_vt_run3/**`.
- Active dependency to remove: `Procfile` (redis-server), `replit.nix` (pkgs.redis), `empirical-validation.yml` (redis service).

## Investigation D — Governance / INDEX truth check
Command:
```
rg -n "pending|local-uncommitted|ci-pending" docs/forensics/INDEX.md
```
Output:
```
8:| Hygiene | docs/forensics/evidence_hygiene_remediation_evidence.md | Evidence hygiene remediation proof pack | PR #15 / fa5d30c | pending |
13:| B055 Phase 3 v2 | docs/forensics/b055_phase3_remediation_v2_integrity_evidence.md | Phase 3 integrity remediation evidence pack | PR #17 / 93b58be | pending |
22:| B0.5.6 Phase 0 | docs/forensics/b056_phase0_worker_observability_drift_inventory_evidence.md | Worker observability drift inventory (context-gathering) | pending | pending |
69:| B055 | docs/forensics/evidence/b055/b055_phase3_worker_stubs_evidence.md | Phase 3 worker stubs + ORM audit evidence | PR #17 / f03b8bc | pending |
```
Finding: placeholders exist outside B0.5.7 scope. B0.5.7 Phase 3–5 rows already have commit + CI links. Phase 6 row must be added with real commit + CI run link after merge.

## Remediation Summary (implemented)
- Added canonical CI job `b057-p6-e2e` with least-privilege runtime assertion and P5 full-chain test execution.
- Added governance guardrails job in CI to enforce Postgres-only dependencies and INDEX governance rules.
- Removed Redis service from `empirical-validation.yml` and updated process/port checks.
- Removed Redis from `Procfile` and `replit.nix`.
- Added CI scripts:
  - `scripts/ci/enforce_postgres_only.py`
  - `scripts/ci/enforce_forensics_index.py`
- Added Phase 6 evidence pack and INDEX row (commit + CI run link to be updated post-merge).

## CI Evidence (EG-P6.1/EG-P6.2/EG-P6.3)
- Commit SHA: UPDATE_AFTER_MERGE
- CI Run URL: UPDATE_AFTER_CI
- Workflow: `CI` (`b057-p6-e2e` job)

## Branch Protection Note
Branch protection is not visible locally. Ensure the GitHub required checks include the `CI` workflow so the new `b057-p6-e2e` job is unskippable.