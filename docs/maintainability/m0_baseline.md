# M0 — Maintainability Baseline Freeze

**Created:** 2026-05-11T19:41:00Z
**Phase:** M0 — Maintainability Baseline Freeze and Scope Lock
**Position:** Post-B2.3 (Revenue Verification & Matching), Pre-B2.4 (Bayesian Diagnostics)

---

## Stabilization Target

This document freezes the post-B2.3 repository state as the authoritative baseline for pre-B2.4 maintainability stabilization phases M0–M7.

**B2.4 implementation is unauthorized.** No Bayesian model code, PyMC/PyMC-Marketing/ArviZ dependencies, convergence diagnostics, model artifact persistence migrations, or production Bayesian behavior may be introduced until M7 issues a `B2.4_READY` or `B2.4_READY_WITH_EXPLICIT_DEBT` verdict.

---

## Primary Branch

| Field | Value |
|---|---|
| Primary branch | `main` |
| Primary branch HEAD | `a70dc9a4529d6ee8b6ab5cfc64f04069086f6549` |
| Primary branch HEAD message | `docs: close B2.3-P6 final evidence status (#451)` |
| Remote | `origin` → `https://github.com/Synergyscape-V1/skeldir-2.0.git` |

## Current Working Branch

| Field | Value |
|---|---|
| Current branch | `codex/b23-p6-natural-webhook-dispatch` |
| Current HEAD | `545f3b9d9bdc02909b49e187980874c0fa4bb1f6` |
| Remote tracking | `origin` → `https://github.com/Synergyscape-V1/skeldir-2.0.git` |

## M0 Baseline SHA

The M0 baseline is defined as `origin/main` HEAD at stabilization start:

```
M0_BASELINE_SHA=a70dc9a4529d6ee8b6ab5cfc64f04069086f6549
```

All M0 diff validation compares against this SHA.

---

## Initial Working-Tree Status

**Timestamp:** 2026-05-11T19:41:00Z

### Tracked Modified Files (2)

| File | Classification |
|---|---|
| `backend/validation/evidence/database/b0_3_summary.json` | Cosmetic — CRLF/LF line-ending drift |
| `backend/validation/evidence/database/phase2_b03/phase2_b03_summary.json` | Cosmetic — CRLF/LF line-ending drift |

### Untracked Items (178)

**Classification: Dirty-State Entropy (H03)**

The repository root contains 178 untracked items. These fall into the following categories:

| Category | Count | Examples | Disposition |
|---|---|---|---|
| CI artifact dumps (`.json`, `.tsv`) | ~95 | `tmp_b23_p2_main_check_runs.json` | M1/Deferred — repo hygiene |
| PR body drafts (`.md`) | ~25 | `tmp_pr_body_b23_p6_natural_dispatch.md` | M1/Deferred — repo hygiene |
| CI run artifact directories | ~20 | `tmp_b17_p6_final_artifacts/` | M1/Deferred — repo hygiene |
| Forensic evidence directories | ~15 | `docs/forensics/evidence/b11_p4_tmp/` | M1/Deferred — repo hygiene |
| Schema/validation artifacts | ~10 | `tmp_schema_authority_449/` | M1/Deferred — repo hygiene |
| Investigation artifacts | ~8 | `.tmp_artifacts/`, `.tmp_b11_scan/` | M1/Deferred — repo hygiene |
| Miscellaneous logs | ~5 | `tmp_log_b0545.txt` | M1/Deferred — repo hygiene |

**Assessment:** None of these items block M0. They represent accumulated investigation/CI artifacts from B0.5–B2.3 phases. They are classified as M1-deferred repo hygiene (issue `MIR-006` in the register).

---

## Final Clean-State Confirmation

**Status:** PENDING — M0 artifacts not yet committed.

Final clean state will be confirmed when:

1. M0 artifacts are committed to a branch.
2. `git status --short` shows no untracked/modified items within the M0 change surface.
3. The M0 validator passes in CI.

This field will be updated in the M0 validation report upon completion.

---

## M0 CI Enforcement

| Field | Value |
|---|---|
| M0 CI workflow | `.github/workflows/m0-maintainability-scope-lock.yml` |
| M0 CI job name | `m0-maintainability-scope-lock` |
| Required for merge | **YES** — must be configured as a required status check on `main` |
| Validator script | `scripts/ci/validate_m0_scope_lock.py` |

---

## Explicit Statements

1. **M0 is post-B2.3 and pre-B2.4.** The B2.3 phase (Revenue Verification & Matching) is closed. The B2.4 phase (Bayesian Diagnostics) has not begun.

2. **B2.4 implementation is unauthorized.** No statistical computation code, PyMC/PyMC-Marketing/ArviZ dependency additions, convergence diagnostic implementations, model artifact persistence migrations, or production Bayesian behavior may be introduced during M0–M7 stabilization.

3. **B2.3 semantics are closed.** The B2.3 match engine kernel, semantic authority, extraction registry, state transitions, and verdict persistence are frozen. No semantic changes to these modules are authorized during stabilization.

4. **The primary branch is `main`.** All stabilization work targets `main` via pull request and must pass the M0 scope-lock validator as a required status check.
