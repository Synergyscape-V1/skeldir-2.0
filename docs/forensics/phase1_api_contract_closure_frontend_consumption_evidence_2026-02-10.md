# Phase 1 Evidence Pack - API Contract Closure + Frontend Consumption Gate (B0.1/B0.2)

Date: 2026-02-10  
Branch: `fix/phase1-contract-consumption`  
Base commit at branch creation: `5006ab7`  
Scope: Empirical validation of Phase 1 remediation status and gate outcomes.

## Superseding Status (Authoritative)
This document contains an initial pre-remediation snapshot and a later post-remediation update.
The **authoritative final status** is:

- Phase 1 remediation is asserted on `main`.
- Required Phase 1 checks are configured as merge-blocking in `main` branch protection.
- `main` CI is globally green after forensic remediation of unrelated red jobs.
- Main-branch run evidence exists for:
  - `Validate Contracts`
  - `Frontend Contract Consumption Gate`
  - `Mock Usability Gate`
  - `Phase 1 Negative Controls`
  - `Phase 1 Runtime Conformance`

Authoritative references:
- Merge PR: `https://github.com/Muk223/skeldir-2.0/pull/66`
- Merge PR (runtime conformance gate addition): `https://github.com/Muk223/skeldir-2.0/pull/68`
- Merge PR (global main CI remediation): `https://github.com/Muk223/skeldir-2.0/pull/70`
- Main run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656`
- Main run (post-PR68): `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998`
- Main run (post-PR70, globally green): `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093`
- Branch protection API evidence:
  - `gh api repos/Muk223/skeldir-2.0/branches/main/protection`

## Executive Verdict
The hypothesis "Phase 1 is fully and completely completed" is **validated**.

What is validated:
- Phase 1 remediations are merged to `main` with merge-blocking required checks.
- Required Phase 1 checks are green in `main` branch context.
- Non-vacuous negative controls are demonstrated in CI.
- Dedicated runtime conformance gate exists and is required.
- `main` CI run is globally green (`success`) after forensic closure of unrelated failing jobs.

## Canonical Contract Artifact (A)
The canonical contract artifact is: `api-contracts/dist/openapi/v1/*.bundled.yaml` produced by `scripts/contracts/bundle.sh` and consumed by `.github/workflows/ci.yml` jobs `validate-contracts`, `frontend-contract-consumption`, and `mock-usability-gate`.

Evidence:
- `scripts/contracts/bundle.sh:2`
- `scripts/contracts/bundle.sh:10`
- `scripts/contracts/bundle.sh:82`
- `.github/workflows/ci.yml:61`
- `.github/workflows/ci.yml:132`
- `.github/workflows/ci.yml:172`

## Remediations Implemented

### 1) Frontend consumption gate (typegen + compile)
- Added deterministic type generation script from canonical bundles:
  - `scripts/contracts/generate_frontend_types.sh`
- Added contract-only compile entrypoint:
  - `frontend/tsconfig.contract-gate.json`
  - `frontend/src/contract-consumption-gate.ts`
  - `frontend/package.json:8` (`contract:compile`)
- Added CI job to enforce:
  - bundle -> typegen -> `git diff --exit-code -- frontend/src/types/api` -> compile
  - `.github/workflows/ci.yml:132`

### 2) Runtime contract conformance tightening
- Reduced broad skip behavior and narrowed operation/security skipping:
  - `tests/contract/test_contract_semantics.py:80`
  - `tests/contract/test_contract_semantics.py:133`
  - `tests/contract/test_contract_semantics.py:142`
- Updated allowlist policy to keep explicit deferred bundles:
  - `tests/contract/semantics_skip_allowlist.yaml:5`

### 3) API runtime alignment for frontend-critical contract surfaces
- Wired missing routers:
  - `backend/app/main.py:69`
  - `backend/app/main.py:70`
- Added reconciliation endpoints:
  - `backend/app/api/reconciliation.py`
- Added export endpoints:
  - `backend/app/api/export.py`
- Added contract health aliases:
  - `backend/app/api/health.py:219`
  - `backend/app/api/health.py:236`
  - `backend/app/api/health.py:267`
  - `backend/app/api/health.py:273`
- Added auth verify endpoint and adjusted auth behavior:
  - `backend/app/api/auth.py:134`
- Fixed realtime response optional numeric contract mismatch:
  - `backend/app/services/realtime_revenue_response.py:47`

### 4) Mock usability gate
- Added CI job that starts Prism from canonical bundle artifacts and validates response bodies:
  - `.github/workflows/ci.yml:172`
- Fixed health smoke request to include required correlation header:
  - `.github/workflows/ci.yml:216`
  - `.github/workflows/ci.yml:217`

## Exit Gate Results (Empirical)

### EG1.1 - OpenAPI Closure Gate (lint + breaking + canonical bundle)
Status: **Partially validated (local/workflow static), not fully validated on main CI**

Validated:
- Canonical bundling path and deterministic command are present in CI.
- `validate-contracts` job includes validation and breaking-change detection.

Evidence:
- `.github/workflows/ci.yml:61`
- `.github/workflows/ci.yml:150`
- `scripts/contracts/bundle.sh`

Not yet validated:
- Green CI execution evidence on `main` with run links/artifacts.

### EG1.2 - Runtime Contract Conformance Gate (real API vs OpenAPI)
Status: **Validated locally for Phase 1 target bundles**

Command:
- `pytest tests/contract/test_contract_semantics.py -q` (with `DATABASE_URL` set in shell)

Observed result:
- `9 passed, 7 skipped`
- Passed bundles include: `attribution`, `auth`, `export`, `health`, `reconciliation`, `revenue`
- Skips are explicit deferred areas (`llm-*`, `webhooks.*`)

Evidence files:
- `tests/contract/test_contract_semantics.py`
- `tests/contract/semantics_skip_allowlist.yaml`

Not yet validated:
- CI execution proof on `main` with required-check enforcement metadata.

### EG1.3 - Frontend Consumption Gate (typegen + compile)
Status: **Validated locally; CI wiring present; not validated on main**

Validated locally:
- Contract compile command succeeds:
  - `npx --yes -p typescript@5.6.3 tsc -p frontend/tsconfig.contract-gate.json --noEmit`

Workflow wiring present:
- `.github/workflows/ci.yml:132`
- Uses canonical bundle and typegen before compile:
  - `.github/workflows/ci.yml:150`
  - `.github/workflows/ci.yml:154`

Not yet validated:
- Required-check status on `main` and remote compile failure proof against deliberate schema drift.

### EG1.4 - Mock Usability Gate (B0.2 operationalization)
Status: **Validated locally; CI wiring present; not validated on main**

Validated locally:
- Prism mock smoke passed for:
  - `GET /api/attribution/revenue/realtime`
  - `GET /api/health` (with `X-Correlation-ID`)
- Required fields validated in response bodies.

Workflow wiring present:
- `.github/workflows/ci.yml:172`
- `.github/workflows/ci.yml:216`

Not yet validated:
- CI run link proving gate executes and passes on `main`.

## Hypothesis Matrix Outcomes (requested H1.*)

### H1.1 - Frontend contract consumption not merge-blocking
Result: **Refuted in code, unvalidated in branch-protection enforcement**
- CI job now explicitly enforces typegen + compile.
- Merge-blocking status in GitHub branch protection is not locally verifiable.

### H1.2 - Contract semantics pass/skip debt masks drift
Result: **Partially validated**
- Skip debt remains for deferred bundles (`llm-*`, `webhooks.*`).
- Frontend-critical bundles targeted by Phase 1 now execute and pass locally.

### H1.3 - OpenAPI closure incomplete for frontend-critical endpoints/errors
Result: **Substantially addressed for Phase 1 targets**
- Runtime/API alignment implemented for health/auth/reconciliation/export/realtime response shape.
- Local semantics pass indicates improved closure on these surfaces.

### H1.4 - Canonical bundle-of-record mismatch with frontend generation
Result: **Refuted**
- Frontend type generation source points to `api-contracts/dist/openapi/v1/*.bundled.yaml`.

### H1.5 - Mockability not operationally useful
Result: **Refuted for required smoke set**
- Prism returns usable schema-aligned payloads for attribution revenue and health.

## Current Worktree State
Worktree is still dirty and uncommitted by design in this iteration.  
Unrelated file intentionally left untouched per instruction:
- `frontend/D2_COMPOSITE_COMPONENT_SYSTEM_CONTEXT.md`

## Required Finalization Steps to Claim Full Phase 1 PASS
1. Commit Phase 1 changes on `fix/phase1-contract-consumption`.
2. Push branch and open PR to `main`.
3. Capture CI run links showing green `validate-contracts`, `frontend-contract-consumption`, `mock-usability-gate`, and contract semantics execution context.
4. Capture branch-protection evidence that these contexts are required/merge-blocking.
5. Add negative-control CI proof snippets:
   - backend response drift without OpenAPI update fails runtime semantics,
   - OpenAPI/type drift fails frontend contract compile gate,
   - breaking OpenAPI change fails `oasdiff`.

## Post-Remediation Update (2026-02-10)

The previously unvalidated items are now remediated as follows.

### A) Changes committed and pushed to `main`
- Phase 1 commits:
  - `019884115` (`phase1: enforce contract consumption gates and negative controls`)
  - `a0d16c6b5` (`phase1: harden oasdiff negative-control assertion`)
- PR merged to `main`:
  - `https://github.com/Muk223/skeldir-2.0/pull/66`
- Main head after merge:
  - `08afccd0a`

### B) Main-branch CI run links for required Phase 1 checks
- Main push CI run:
  - `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656`
- Required Phase 1 checks in that run:
  - Validate Contracts: `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656/job/63137439721` (pass)
  - Frontend Contract Consumption Gate: `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656/job/63137898096` (pass)
  - Mock Usability Gate: `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656/job/63137898350` (pass)
  - Phase 1 Negative Controls: `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656/job/63137898122` (pass)

Note: the overall workflow still has unrelated failing jobs; however, the required Phase 1 checks above are green.

### C) Merge-blocking enforcement in production branch context (`main`)
- Branch protection now includes Phase 1 checks as required status checks:
  - `B0.7 P2 Runtime Proof (LLM + Redaction)`
  - `Celery Foundation B0.5.1`
  - `Validate Contracts`
  - `Frontend Contract Consumption Gate`
  - `Mock Usability Gate`
  - `Phase 1 Negative Controls`
  - `Phase 1 Runtime Conformance`
- Evidence (GitHub API response):
  - `gh api repos/Muk223/skeldir-2.0/branches/main/protection`
  - strict mode: `true`

### D) Non-vacuous negative controls demonstrated in remote CI context
- Dedicated CI job:
  - `.github/workflows/ci.yml` -> `Phase 1 Negative Controls`
- Script:
  - `scripts/contracts/run_negative_controls.sh`
- Controls proven:
  - Runtime response drift induces contract/runtime failure (intentional backend mutation).
  - Frontend type drift induces compile failure (intentional TypeScript mismatch).
  - Intentional OpenAPI breaking mutation is detected by `oasdiff`.
- PR run proof:
  - `https://github.com/Muk223/skeldir-2.0/actions/runs/21873789946/job/63137000474` (pass)
- Main run proof:
  - `https://github.com/Muk223/skeldir-2.0/actions/runs/21874004656/job/63137898122` (pass)

## Post-Remediation Update II (2026-02-10) - Runtime Conformance Gate Authority on `main`

Hypothesis addressed:
- "Dedicated `Phase 1 Runtime Conformance` job is required for exit-gate authority, and current runtime checks are not merge-blocking."

Forensic result:
- A dedicated CI job was added in `.github/workflows/ci.yml`:
  - job id: `phase1-runtime-conformance`
  - display name: `Phase 1 Runtime Conformance`
  - command: `pytest tests/contract/test_contract_semantics.py -q`
- Change was merged to `main`:
  - PR: `https://github.com/Muk223/skeldir-2.0/pull/68`
  - merge commit: `62b93e9653a567be9b84b1e19d9a04220564494c`
- `main` branch protection required checks now include `Phase 1 Runtime Conformance`:
  - Evidence: `gh api repos/Muk223/skeldir-2.0/branches/main/protection/required_status_checks`
  - required contexts include:
    - `Validate Contracts`
    - `Frontend Contract Consumption Gate`
    - `Mock Usability Gate`
    - `Phase 1 Negative Controls`
    - `Phase 1 Runtime Conformance`
- `main` run proof (production branch context):
  - Run: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998`
  - Required Phase 1 context outcomes in that run:
    - `Validate Contracts`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998/job/63144028401` (success)
    - `Frontend Contract Consumption Gate`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998/job/63144262072` (success)
    - `Mock Usability Gate`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998/job/63144262031` (success)
    - `Phase 1 Negative Controls`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998/job/63144261986` (success)
    - `Phase 1 Runtime Conformance`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21875741998/job/63144261983` (success)

Conclusion:
- The hypothesis is refuted. Runtime conformance is now an explicit, dedicated, merge-blocking required check on `main`, and it has passing `main`-branch execution evidence.

## Post-Remediation Update III (2026-02-10) - Global `main` CI Green Closure

Hypothesis addressed:
- "CI on `main` is not globally green; therefore completion authority is incomplete."

Scientific method:
- Baseline observation: previous `main` CI runs had `conclusion=failure` while required Phase 1 checks were green.
- Root-cause isolation: extracted failing jobs and traced shared failure signatures from job logs.
- Controlled remediation: patched only failing cause-classes, re-ran CI in PR context, then asserted on `main`.
- Validation: confirmed globally green `main` CI run after merge.

Root causes identified:
- CI migration policy mismatch: multiple jobs ran Alembic under `CI=true` without `MIGRATION_DATABASE_URL`, violating `alembic/env.py` strict CI contract.
- Mock gate race: health Prism endpoint probe executed before readiness on some runs.
- Backend test environment gap: `Test Backend` lacked deterministic Postgres service+migrations.
- Phase gate strictness mismatch: `SCHEMA_GUARD` raw SQL marker missing in a B0.7 P4 integration seed.

Remediations merged:
- PR: `https://github.com/Muk223/skeldir-2.0/pull/70`
- Merge commit: `7b34b0cbc9351b3e9f737ca51d48758a0803fb12`
- Files:
  - `.github/workflows/ci.yml`
  - `.github/workflows/b0542-refresh-executor.yml`
  - `.github/workflows/b0543-matview-task-layer.yml`
  - `scripts/ci/zero_drift_v3_2.sh`
  - `scripts/guard_no_docker.py`
  - `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`

Main-branch proof:
- `main` CI run after PR #70 merge:
  - `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093`
  - workflow conclusion: `success` (globally green)
- Phase 1 required checks in that run:
  - `Validate Contracts`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093/job/63149184872` (success)
  - `Frontend Contract Consumption Gate`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093/job/63149397164` (success)
  - `Mock Usability Gate`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093/job/63149397295` (success)
  - `Phase 1 Negative Controls`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093/job/63149397107` (success)
  - `Phase 1 Runtime Conformance`: `https://github.com/Muk223/skeldir-2.0/actions/runs/21877158093/job/63149397114` (success)

Conclusion:
- The hypothesis is refuted.
- Completion authority now includes both:
  - merge-blocking Phase 1 gate success on `main`, and
  - globally green CI on `main`.
