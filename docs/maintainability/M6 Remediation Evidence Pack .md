# M6 Remediation Evidence Pack

## Executive Summary

M6 selects Path B: guardrail before B2.4, decomposition before B2.7. Current B2.4 design artifacts do not touch LLM explanation/provider behavior, so `provider_boundary.py` decomposition is not B2.4-blocking. The remediation adds a static validator, B2.7 precondition lock, CI/governance registration, and decision records that make B2.4 LLM-boundary drift mechanically falsifiable.

## Initial Findings

Current branch before M6 work:

- Branch: `codex/m6-llm-boundary-guardrail`
- Baseline SHA inspected: `f4c733a8b864ec2e38ad6f2ddca0a232075c95d4`
- `backend/app/llm/provider_boundary.py`: 2472 lines, about 100 KB
- Existing B2.4 docs explicitly forbid `app.llm.*` imports, public API routes, MCP tools, frontend/dashboard consumers, and LLM explanation changes.
- Existing CI had `validate-m5-b24-readiness-design`, but no M6 validator.

External context reviewed:

- `M-Skeldir-Context-v3_Post-V9_4.md`: LLMs explain deterministic truth only; Trust API read paths must not import LLM provider modules.
- `Maintainability Audit Nicholas.md`: provider boundary is architecturally sound but near cognitive ceiling.
- `Maintainability Audit Trey.md`: provider boundary is the largest app file and accumulates provider calls, budget, breaker, cache, distillation, and validation.
- `skeldir_maintainability_audit_george.md`: provider boundary needs decomposition, but boundary enforcement is correct.
- `Maintainability Stabilization Linerarly Hierarchical approach.md`: M6 must decide Path A or B after M5; Path B is allowed only if B2.4 does not touch explanation/provider behavior.

## Remediations Made

- Added `docs/llm/provider_boundary_decision.md`.
- Added `docs/llm/provider_boundary_guardrail.md`.
- Added `docs/b2_7/preconditions.md`.
- Added `scripts/ci/validate_m6_llm_boundary.py`.
- Added `make validate-m6-llm-boundary`.
- Registered `validate-m6-llm-boundary` in `docs/ci/enforcer_registry.yaml`.
- Registered the gate in `docs/ci/gate_subsumption_matrix.yaml`.
- Wired `make validate-m6-llm-boundary` into `.github/workflows/b2_4-gate-dry-run.yml`.
- Updated M0/M1 maintainability validators to recognize M6 docs and the M6 validator as allowed maintainability surfaces.
- Added `docs/maintainability/m6_completion_record.md`.

## Decision Evidence

Every B2.4 surface is classified as LLM-free:

| Surface | LLM touchpoint |
|---|---:|
| Diagnostics | NO |
| Fit worker | NO |
| Artifact store | NO |
| Fallback | NO |
| Confidence projection | NO |
| CI gates | NO |
| API exposure during B2.4 | NO |

Path B invalidation rule: any B2.4 explanation, summary, narrative fallback, provider call, prompt, LLM cache, LLM validation, LLM audit, provider SDK import, or `provider_boundary.py` behavior change makes Path A mandatory before B2.4 continues.

## Validation Evidence

Local validation command:

```bash
python scripts/ci/validate_m6_llm_boundary.py --negative-control
```

Expected validator output:

```text
M6_NEGATIVE_CONTROL_PASS: forbidden LLM import in B2.4/truth path
M6_LLM_BOUNDARY_VALIDATION_PASS
```

The positive validation and GitHub Actions evidence are updated after the branch validation run.

## CI And Merge Closure

PR URL: recorded after PR creation.

Main commit SHA: recorded after merge to `main`.

Main CI workflow URL: recorded after protected-branch workflow completion.

Protected-branch conclusion: recorded after GitHub Actions reports green on `main`.

## Non-Implementation Proof

No M6 remediation is authorized to change:

- `backend/app/llm/provider_boundary.py`
- production Bayesian implementation
- `backend/app/tasks/bayesian.py` behavior
- B2.3 match/revenue-verification semantics
- webhook verifier logic
- RLS policies
- LLM provider behavior
- prompt templates
- public API routes
- frontend/dashboard code
- dependency manifests

## Final M7 Authorization

M7 may begin: NO until protected-branch main evidence is appended and `docs/maintainability/m6_completion_record.md` is updated to `M6_PASS`.
