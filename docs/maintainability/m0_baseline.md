# M0 - Maintainability Baseline Freeze

**Created:** 2026-05-11T19:41:00Z
**Finalized:** 2026-05-12T00:00:00Z
**Phase:** M0 - Maintainability Baseline Freeze and Scope Lock
**Position:** Post-B2.3 (Revenue Verification & Matching), Pre-B2.4 (Bayesian Diagnostics)

## Stabilization Target

This document freezes the post-B2.3 repository state as the authoritative
baseline for pre-B2.4 maintainability stabilization phases M0-M7.

**B2.4 implementation is unauthorized.** No Bayesian model code,
PyMC/PyMC-Marketing/ArviZ dependencies, convergence diagnostics, model
artifact persistence migrations, or production Bayesian behavior may be
introduced until M7 issues a `B2.4_READY` or
`B2.4_READY_WITH_EXPLICIT_DEBT` verdict.

## Primary Branch

| Field | Value |
|---|---|
| Primary branch | `main` |
| Primary branch head at corrective evidence capture | `dffc6cf980b95d33c5d2042457e458657d0b0766` |
| Primary branch HEAD | `dffc6cf980b95d33c5d2042457e458657d0b0766` |
| Primary branch HEAD message | `chore(maintainability): M0 baseline freeze and scope lock (#452)` |
| Remote | `origin` -> `https://github.com/Synergyscape-V1/skeldir-2.0.git` |

## M0 Baseline SHA

The M0 baseline remains the `origin/main` HEAD at stabilization start:

```text
M0_BASELINE_SHA=a70dc9a4529d6ee8b6ab5cfc64f04069086f6549
```

All M0 diff validation compares against this SHA unless the workflow supplies
the PR merge base or push parent as a narrower runtime baseline.

## Initial Working-Tree Status

**Timestamp:** 2026-05-11T19:41:00Z

The original remediation workspace contained two tracked line-ending drifts and
178 untracked local investigation artifacts. Those artifacts were local
workspace entropy only. They were not committed to `main`, and they remain
classified as M1 repo hygiene in `MIR-006`.

## Final Clean-State Confirmation

**Status:** COMPLETE.

Fresh checkout evidence from isolated worktree
`C:\Users\ayewhy\m0-main-closure` at `origin/main`:

```text
$ git status --short --branch
## HEAD (no branch)

$ git status --short

```

The empty `git status --short` output confirms the committed `origin/main`
state is reproducible and not contaminated by the prior local-only dirty
artifacts.

Canonical completion artifact:

```text
docs/maintainability/m0_completion_record.md
```

## M0 CI Enforcement

| Field | Value |
|---|---|
| M0 CI workflow | `.github/workflows/m0-maintainability-scope-lock.yml` |
| M0 CI job name | `m0-maintainability-scope-lock` |
| Required for merge | **YES** - configured as a required status check on `main` |
| Validator script | `scripts/ci/validate_m0_scope_lock.py` |
| Canonical completion artifact | `docs/maintainability/m0_completion_record.md` |

## Explicit Statements

1. **M0 is post-B2.3 and pre-B2.4.** The B2.3 phase (Revenue Verification &
   Matching) is closed. The B2.4 phase (Bayesian Diagnostics) has not begun.
2. **B2.4 implementation is unauthorized.** No statistical computation code,
   PyMC/PyMC-Marketing/ArviZ dependency additions, convergence diagnostic
   implementations, model artifact persistence migrations, or production
   Bayesian behavior may be introduced during M0-M7 stabilization.
3. **B2.3 semantics are closed.** The B2.3 match engine kernel, semantic
   authority, extraction registry, state transitions, and verdict persistence
   are frozen. No semantic changes to these modules are authorized during M0.
4. **The primary branch is `main`.** All stabilization work targets `main` via
   pull request and must pass the M0 scope-lock validator as a required status
   check.
