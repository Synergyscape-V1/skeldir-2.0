# M6 Remediation Evidence Pack

## Executive Summary

M6 remains in corrective action after independent audit rejection. The original M6 work correctly selected Path B, but the validator was too narrow: it did not resolve relative imports, did not fail closed on dynamic imports, did not check reverse-flow coupling from LLM modules into truth internals, and proved only one absolute-import negative control.

This iteration hardens the guardrail without reopening the accepted Path B decision and without implementing B2.4 or decomposing `provider_boundary.py`.

## Initial Corrective Findings

Current inspected `main` baseline:

- Branch: `main`
- Rejected M6 baseline SHA before corrective hardening: `ddea968e57a5b426cf893bca30377e7db749d1e3`
- Hardened validator landing SHA: `d7c62766e69a104f8b756231e14484cde7be2baf`
- Corrective PR: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/475`
- Prior rejected M6 PR: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/474`
- Prior status: `M6_REJECT`

Accepted facts retained:

- Path B is directionally valid because B2.4 design artifacts are LLM-free.
- B2.7 precondition documentation exists.
- M6 did not modify provider behavior, B2.4 implementation, public API routes, prompts, dependencies, migrations, frontend code, webhook verifier logic, RLS policies, or B2.3 semantics.
- The M6 validator is registered in governance and wired into the B2.4 dry-run lane.

Rejected validator gaps:

- Relative import evasion remained open.
- Dynamic import and dynamic code execution evasion remained open.
- Reverse-flow LLM-to-truth coupling remained unchecked.
- Provider SDK truth-path imports were not called out as an independent violation channel.
- Negative controls covered only a single absolute import.
- Completion evidence remained non-final.

## Remediations Made In This Iteration

- Replaced `scripts/ci/validate_m6_llm_boundary.py` with a hardened static validator.
- Added package-context resolution for `ast.ImportFrom.level`.
- Expanded import target extraction for package imports and aliased imports.
- Added fail-closed checks for `importlib.import_module`, `__import__`, `eval`, and `exec` in protected truth paths.
- Added reverse-flow scanning from `backend/app/llm/**` into Bayesian, Trust, reconciliation, revenue-verification, policy, solver, envelope, MCP, and Bayesian task internals.
- Added provider SDK truth-path violation reporting.
- Added high-risk provider-boundary symbol reference checks in protected truth paths.
- Added Python version and platform output for CI environment evidence.
- Added multi-vector negative controls for absolute, package, alias, relative, dynamic, provider SDK, symbol, reverse-flow, and decision-mutation violations.
- Updated `docs/llm/provider_boundary_decision.md` with reverse-flow policy and provider SDK truth-path policy.
- Updated `docs/llm/provider_boundary_guardrail.md` with the expanded machine-enforcement contract.
- Updated `docs/maintainability/m6_completion_record.md` with corrective findings, expanded controls, CI authority doctrine, and M6-A through M6-I gate status.

## Validator Authority Model

Host-native execution is advisory. CI on `main` is authoritative for M6 closure.

The validator remains a Class A pure static validator: no DB, Celery, pooler, network, provider SDK, or secret dependency. It uses repo-relative path normalization and prints:

```text
M6_ENVIRONMENT: python=<version> platform=<platform>
```

## Expanded Negative-Control Output

Expected output from:

```bash
python scripts/ci/validate_m6_llm_boundary.py --negative-control
```

```text
M6_ENVIRONMENT: python=<version> platform=<platform>
M6_NC_ABSOLUTE_IMPORT_PASS
M6_NC_PACKAGE_IMPORT_PASS
M6_NC_ALIAS_IMPORT_PASS
M6_NC_RELATIVE_IMPORT_PASS
M6_NC_DYNAMIC_IMPORTLIB_PASS
M6_NC_DYNAMIC_BUILTIN_IMPORT_PASS
M6_NC_DYNAMIC_EVAL_PASS
M6_NC_DYNAMIC_EXEC_PASS
M6_NC_PROVIDER_SDK_TRUTH_PATH_PASS
M6_NC_FORBIDDEN_SYMBOL_PASS
M6_NC_REVERSE_FLOW_IMPORT_PASS
M6_NC_DECISION_MUTATION_PASS
M6_NEGATIVE_CONTROL_PASS
M6_LLM_BOUNDARY_VALIDATION_PASS
```

## Decision Evidence

Path B remains selected:

```text
Guardrail before B2.4; decomposition before B2.7.
```

Every current B2.4 surface remains classified as LLM-free:

| Surface | LLM touchpoint |
|---|---:|
| Diagnostics | NO |
| Fit worker | NO |
| Artifact store | NO |
| Fallback | NO |
| Confidence projection | NO |
| CI gates | NO |
| API exposure during B2.4 | NO |

Path B invalidation rule remains active: any B2.4 explanation, summary, narrative fallback, provider call, prompt, LLM cache, LLM validation, LLM audit, provider SDK import, or `provider_boundary.py` behavior change makes Path A mandatory before B2.4 continues.

## Non-Implementation Proof

This corrective iteration is limited to validator and documentation surfaces. It does not modify:

- `backend/app/llm/provider_boundary.py`
- `backend/app/bayesian/**`
- `backend/app/tasks/bayesian.py`
- B2.3 match/revenue-verification semantics
- webhook verifier logic
- RLS policies
- prompt templates
- public API routes
- dependency manifests
- frontend/dashboard code
- migrations

## CI And Merge Closure

Corrective-action PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/475`.

Final evidence PR URL: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/476`.

Hardened validator main SHA: `d7c62766e69a104f8b756231e14484cde7be2baf`.

Authoritative M6 main CI evidence:

- B2.4 Gate Dry Run with hardened M6 validator passed: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26103636329`
- Main aggregate CI passed: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26103635288`
- `b11-p6-end-to-end-closure-pack` passed after OIDC recovery: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26103635286`
- `b11-p1-control-plane-adjudication` passed after OIDC recovery: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26103635120`
- `b11-p4-db-provider-ci-audit-adjudication` passed after OIDC recovery: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26103634226`

Additional CI evidence remediation:

- `Proof Pack (EG-5)` on PR #476 repeatedly failed because GitHub's run-jobs REST endpoint returned `HTTP 502` for the large CI run.
- `scripts/phase_gates/generate_value_trace_proof_pack.py` now retries GitHub API calls and falls back to commit check-runs for VALUE gate job URLs while preserving same-run artifact IDs.
- M0 scope-lock governance now explicitly allows that exact proof-pack generator path as an evidence-generation surface.
- Local reproduction against PR run `26104708396` passed from a temporary working directory:

  ```text
  EG-5 PASS: proof pack matches GITHUB_SHA and GITHUB_RUN_ID
  ```

Protected-branch conclusion: M6 passes. The hardened M6 guardrail is on `main`, the M6-specific lane passed, aggregate main CI passed, and the previously blocked AWS OIDC workflows now pass.

## Final M7 Authorization

M7 may begin: YES.
