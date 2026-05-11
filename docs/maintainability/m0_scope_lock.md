# M0 — Scope Lock

**Phase:** M0 — Maintainability Baseline Freeze and Scope Lock
**Baseline SHA:** `a70dc9a4529d6ee8b6ab5cfc64f04069086f6549`
**Effective:** From M0 commit until M7 verdict

---

## Purpose

This document defines the hard boundary of what is authorized and prohibited during the M0–M7 maintainability stabilization sequence. It is a CI-consumed governance input — the `validate_m0_scope_lock.py` validator enforces these constraints as a required merge gate.

---

## Authorized M0 Work

The following changes are authorized during M0:

1. **Create** `docs/maintainability/m0_baseline.md` — baseline freeze artifact.
2. **Create** `docs/maintainability/maintainability_issue_register.yaml` — normalized audit findings.
3. **Create** `docs/maintainability/m0_scope_lock.md` — this document.
4. **Create** `docs/maintainability/m0_validation_report.md` — validation evidence.
5. **Create** `scripts/ci/validate_m0_scope_lock.py` — policy-as-code validator.
6. **Create** `.github/workflows/m0-maintainability-scope-lock.yml` — CI enforcement workflow.
7. **Inspect** any repository file for classification purposes.
8. **Classify** audit findings into the issue register without remediating them.

---

## Prohibited Work During M0

### B2.4 Implementation Prohibition

The following are **unconditionally prohibited** during M0:

- Adding `pymc`, `pymc-marketing`, `pymc_marketing`, or `arviz` to any dependency file (`requirements.txt`, `requirements-dev.txt`, `setup.py`, `setup.cfg`, `pyproject.toml`, `Pipfile`).
- Adding Python files containing `pm.Model`, `pm.sample`, `az.rhat`, `az.ess`, `az.summary`, or equivalent PyMC/ArviZ convergence diagnostic API calls.
- Adding production Bayesian diagnostic or model-fit code under `backend/app/`.
- Adding database migrations for model artifact persistence, Bayesian diagnostic storage, or convergence result tables.
- Implementing convergence diagnostics (R-hat, ESS, divergences) in production or test code.

### B2.3 Semantic Reopening Prohibition

The following are **unconditionally prohibited** during M0:

- Modifying the behavior of `match_engine_kernel.py` matching logic.
- Altering discrepancy classification thresholds.
- Changing `semantic_authority.py` canonicalization or contract behavior.
- Modifying `state_transitions.py` transition logic.
- Altering `extraction_registry.py` provider extraction behavior.
- Changing `batch_engine.py` orchestration semantics.

### Provider-Boundary Behavior-Change Prohibition

The following are **unconditionally prohibited** during M0:

- Adding new explanation metrics to `provider_boundary.py`.
- Adding new provider-specific imports or SDK integrations.
- Modifying budget reservation, circuit breaker, cache, or distillation behavior.
- Adding new LLM fallback narrative behavior.

### Broad CI Refactor Prohibition

The following are **unconditionally prohibited** during M0:

- Splitting, merging, or restructuring `ci.yml` beyond the M0 enforcement path.
- Removing or weakening existing required CI status checks.
- Renaming existing CI jobs that are referenced by branch protection rules.

---

## Allowed M0 Change Surface

Changes during M0 are restricted to these paths:

```
docs/maintainability/**
scripts/ci/validate_m0_scope_lock.py
.github/workflows/m0-maintainability-scope-lock.yml
```

Any change outside this surface must be explicitly justified in `m0_validation_report.md`.

---

## M0 Artifacts Are CI-Consumed Governance Inputs

The M0 artifacts (`m0_baseline.md`, `maintainability_issue_register.yaml`, `m0_scope_lock.md`) are not advisory documentation. They are inputs to the `validate_m0_scope_lock.py` policy-as-code validator, which runs as a required CI status check on the primary branch merge path.

---

## Required CI Status Enforcement

The M0 scope lock is enforced via:

1. **Validator:** `scripts/ci/validate_m0_scope_lock.py`
2. **Workflow:** `.github/workflows/m0-maintainability-scope-lock.yml`
3. **Job name:** `m0-maintainability-scope-lock`
4. **Enforcement:** Must be configured as a required status check for merging into `main`.

If this job cannot be made required, the M0 verdict is `M0_BLOCKED_BY_UNENFORCED_VALIDATOR`.

---

## Final Clean-Tree Requirement

M0 is not complete until the working tree within the M0 change surface is clean. Untracked items outside the M0 surface are classified as deferred repo hygiene (issue `MIR-006`) and do not block M0 completion.

---

## Conditions for Moving to M1

M1 may begin only when all of the following are true:

1. All M0 artifacts are committed to the primary branch.
2. The M0 validator passes as a required CI status check.
3. The M0 validation report confirms all exit gates pass.
4. No B2.4 feature contamination has occurred.
5. The issue register covers Nicholas, Trey, and George audit findings.
6. All B2.4-entry blockers are identified with rationale.
7. All deferred issues have documented reasons.
