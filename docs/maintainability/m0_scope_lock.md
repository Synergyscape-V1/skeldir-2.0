# M0 - Scope Lock

**Phase:** M0 - Maintainability Baseline Freeze and Scope Lock
**Baseline SHA:** `a70dc9a4529d6ee8b6ab5cfc64f04069086f6549`
**Effective:** From M0 commit until M7 verdict

## Purpose

This document defines the hard boundary of what is authorized and prohibited
during the M0-M7 maintainability stabilization sequence. It is a CI-consumed
governance input: `scripts/ci/validate_m0_scope_lock.py` enforces these
constraints as a required merge gate.

## Authorized M0 Work

The following changes are authorized during M0 corrective closure:

1. Maintain `docs/maintainability/m0_baseline.md`.
2. Maintain `docs/maintainability/maintainability_issue_register.yaml`.
3. Maintain `docs/maintainability/m0_scope_lock.md`.
4. Maintain canonical completion artifact
   `docs/maintainability/m0_completion_record.md`.
6. Maintain `scripts/ci/validate_m0_scope_lock.py`.
7. Maintain `.github/workflows/m0-maintainability-scope-lock.yml`.
8. Maintain `.github/CODEOWNERS` for M0 policy-file ownership.
9. Maintain branch-protection required-status contract
   `contracts-internal/governance/b03_phase2_required_status_checks.main.json`.
10. Configure GitHub branch protection or equivalent rules so
   `m0-maintainability-scope-lock` is required for `main`.

## Prohibited Work During M0

### B2.4 Implementation Prohibition

The following are unconditionally prohibited during M0:

- Adding `pymc`, `pymc-marketing`, `pymc_marketing`, or `arviz` to dependency
  files.
- Adding Python files containing `pm.Model`, `pm.sample`, `az.rhat`, `az.ess`,
  `az.summary`, or equivalent PyMC/ArviZ convergence diagnostic calls.
- Adding production Bayesian diagnostic or model-fit code under `backend/app/`.
- Adding database migrations for model artifact persistence, Bayesian
  diagnostic storage, or convergence result tables.
- Implementing convergence diagnostics in production or test code.

### B2.3 Semantic Reopening Prohibition

The following are unconditionally prohibited during M0:

- Modifying `match_engine_kernel.py` matching behavior.
- Altering discrepancy classification thresholds.
- Changing `semantic_authority.py` canonicalization or contract behavior.
- Modifying `state_transitions.py` transition logic.
- Altering `extraction_registry.py` provider extraction behavior.
- Changing `batch_engine.py` orchestration semantics.

### Provider-Boundary Behavior-Change Prohibition

The following are unconditionally prohibited during M0:

- Adding new explanation metrics to `provider_boundary.py`.
- Adding new provider-specific imports or SDK integrations.
- Modifying budget reservation, circuit breaker, cache, or distillation
  behavior.
- Adding new LLM fallback narrative behavior.

### Broad CI Refactor Prohibition

The following are unconditionally prohibited during M0:

- Splitting, merging, or restructuring `ci.yml` beyond the M0 enforcement path.
- Removing or weakening existing required CI status checks.
- Renaming existing CI jobs referenced by branch protection rules.

## Allowed M0 Change Surface

Changes during M0 corrective closure are restricted to these paths:

```text
docs/maintainability/**
scripts/ci/validate_m0_scope_lock.py
.github/workflows/m0-maintainability-scope-lock.yml
.github/CODEOWNERS
contracts-internal/governance/b03_phase2_required_status_checks.main.json
```

Any change outside this surface must be explicitly justified in
`docs/maintainability/m0_completion_record.md` and will fail validation unless
it remains inside the validator's allowed path set.

## M0 Artifacts Are CI-Consumed Governance Inputs

The M0 artifacts are not advisory documentation. They are inputs to
`validate_m0_scope_lock.py`, which runs as the required CI status context
`m0-maintainability-scope-lock` on the primary branch merge path.

Canonical completion artifact:

```text
docs/maintainability/m0_completion_record.md
```

## Required CI Status Enforcement

The M0 scope lock is enforced via:

1. **Validator:** `scripts/ci/validate_m0_scope_lock.py`
2. **Workflow:** `.github/workflows/m0-maintainability-scope-lock.yml`
3. **Job name:** `m0-maintainability-scope-lock`
4. **Enforcement:** Required CI status check for merging into `main`.

If this job is removed from required checks, the M0 verdict returns to
`M0_BLOCKED_BY_UNENFORCED_VALIDATOR`.

## Final Clean-Tree Requirement

M0 is complete only when a fresh checkout of `origin/main` has empty
`git status --short` output. Local-only investigation artifacts from prior
workspaces are M1 repo hygiene and do not count as committed baseline state.

## Conditions for Moving to M1

M1 may begin only when all of the following are true:

1. All M0 artifacts are committed to `main`.
2. The M0 validator passes as a required CI status check.
3. `docs/maintainability/m0_completion_record.md` confirms all M0 exit gates
   pass.
4. No B2.4 feature contamination has occurred.
5. No B2.3 semantic module or provider-boundary behavior changed.
6. Validator/workflow governance protection is checked and recorded.
