# M6 Completion Record

## Executive Verdict

M6_FAIL.

This record reflects the corrective-action branch state after the independent audit rejection. M6 remains failed until the hardened validator, expanded negative controls, final PR URL, final main SHA, and green protected-main CI evidence are landed back on `main`.

## Selected Path

Path B - Guardrail before B2.4; decomposition before B2.7.

Path B remains valid because current B2.4 design artifacts are LLM-free. Path B is invalid if B2.4 introduces explanation, summary, narrative fallback, provider calls, prompts, LLM cache, LLM validation, LLM audit, provider SDK imports, or `provider_boundary.py` behavior changes.

## Final Main Commit SHA

Not established for the corrective action yet. Current inspected main baseline before this follow-up branch: `ddea968e57a5b426cf893bca30377e7db749d1e3`.

## PR URL

Corrective-action PR has not been opened yet. Prior rejected M6 PR: `https://github.com/Synergyscape-V1/skeldir-2.0/pull/474`.

## CI Workflow URL

Authoritative corrective-action CI is not established yet. Prior rejected main B2.4 dry-run evidence: `https://github.com/Synergyscape-V1/skeldir-2.0/actions/runs/26091153852`.

## Validation Command And Output

Command:

```bash
python scripts/ci/validate_m6_llm_boundary.py --negative-control
```

Expected corrective validator output:

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

## Expanded Negative-Control Evidence

The hardened validator now requires each bad fixture to fail:

| Control | Violation proved |
|---|---|
| M6_NC_ABSOLUTE_IMPORT_PASS | `from app.llm.provider_boundary import SkeldirLLMProvider` from B2.4/Bayesian truth path |
| M6_NC_PACKAGE_IMPORT_PASS | `from app import llm` package import from protected truth path |
| M6_NC_ALIAS_IMPORT_PASS | `import app.llm.provider_boundary as provider_boundary` |
| M6_NC_RELATIVE_IMPORT_PASS | `from ..llm import provider_boundary` resolved to `app.llm.provider_boundary` |
| M6_NC_DYNAMIC_IMPORTLIB_PASS | `importlib.import_module("app.llm.provider_boundary")` |
| M6_NC_DYNAMIC_BUILTIN_IMPORT_PASS | `__import__("app.llm.provider_boundary")` |
| M6_NC_DYNAMIC_EVAL_PASS | `eval(...)` fail-closed in protected truth paths |
| M6_NC_DYNAMIC_EXEC_PASS | `exec(...)` fail-closed in protected truth paths |
| M6_NC_PROVIDER_SDK_TRUTH_PATH_PASS | direct provider SDK import in protected truth path |
| M6_NC_FORBIDDEN_SYMBOL_PASS | direct high-risk boundary symbol reference in protected truth path |
| M6_NC_REVERSE_FLOW_IMPORT_PASS | `backend/app/llm/**` importing Bayesian/truth internals |
| M6_NC_DECISION_MUTATION_PASS | decision record losing the Path B invalidation rule |

## Import-Resolution Hardening Summary

The validator no longer reads only `ast.Import` and absolute `ast.ImportFrom.module`. It resolves `ast.ImportFrom.level` against the repo-relative package name for `backend/app/**`, so relative imports such as `from ..llm import provider_boundary` and `from ...llm.provider_boundary import SkeldirLLMProvider` are treated as `app.llm.*` imports. Unresolved relative imports in protected truth paths fail closed.

Package and alias imports are also expanded. For example, `from app import llm` produces an `app.llm` import target, and `from app.llm import provider_boundary` produces both `app.llm` and `app.llm.provider_boundary`.

## Dynamic Import Detection Summary

Protected truth paths fail validation if they call:

- `importlib.import_module`
- `__import__`
- `eval`
- `exec`

This is intentionally fail-closed. There is no accepted B2.4, Bayesian diagnostic, Trust, reconciliation, revenue-verification, policy, solver, envelope, or MCP truth-path reason to use dynamic import or dynamic code execution during M6.

## Bidirectional Flow Guardrail Summary

The guardrail checks both directions:

- Truth/B2.4 paths -> `app.llm.*`, `provider_boundary.py`, provider SDKs, and high-risk LLM/provider symbols.
- `backend/app/llm/**` -> B2.4, Bayesian, Trust, reconciliation, revenue-verification, policy, solver, envelope, MCP, and `app.tasks.bayesian` internals.

No reverse-flow exceptions are approved during M6.

## Provider SDK Allowlist Summary

Provider SDK imports remain approved only in `backend/app/llm/provider_boundary.py` during M6:

- `aisuite`
- `openai`
- `anthropic`
- `groq`
- `google.generativeai`
- `google.genai`
- `vertexai`
- `cohere`
- `mistralai`

Protected truth paths fail if they import provider SDKs directly.

## Execution Environment Determinism Summary

Host-native execution is advisory. CI on main is authoritative for phase closure.

The validator prints Python version and platform on every run and uses `Path(...).as_posix()` normalization for repo-relative paths. The relative-import negative-control fixture runs in the same CI invocation as the positive validator.

## Decision And Precondition Preservation

`docs/llm/provider_boundary_decision.md` still selects Path B only because B2.4 is LLM-free and still states the automatic Path B invalidation rule. `docs/b2_7/preconditions.md` still blocks B2.7 until provider-boundary decomposition is completed or formally waived.

## Diff Scope Inventory

The corrective action is authorized to change only:

- `scripts/ci/validate_m6_llm_boundary.py`
- `docs/llm/provider_boundary_decision.md`
- `docs/llm/provider_boundary_guardrail.md`
- `docs/maintainability/m6_completion_record.md`
- `docs/maintainability/M6 Remediation Evidence Pack .md`

No Makefile, workflow, governance, or B2.7 precondition change is required unless validation proves drift.

## Non-Implementation Proof

This corrective action must not modify:

- `backend/app/llm/provider_boundary.py`
- `backend/app/bayesian/**`
- `backend/app/tasks/bayesian.py`
- B2.3 match or revenue-verification semantics
- webhook verifier logic
- RLS policies
- prompt templates
- public API routes
- dependency manifests
- frontend/dashboard code
- migrations

The validator continues to reject unauthorized PR diff surfaces when a merge base exists.

## Hypothesis Matrix

| ID | Status | Finding |
|---|---|---|
| H01 | REMEDIATED | Relative imports are resolved using package context and fail closed when unresolved. |
| H02 | REMEDIATED | Dynamic import/code execution mechanisms are banned in protected truth paths. |
| H03 | REMEDIATED | Reverse-flow imports from `backend/app/llm/**` into truth internals are scanned. |
| H04 | REMEDIATED | Negative controls now cover absolute, package, alias, relative, dynamic, provider SDK, symbol, reverse-flow, and decision-mutation violations. |
| H05 | REMEDIATED | Provider SDK imports are treated as an independent protected-truth-path violation. |
| H06 | REMEDIATED | High-risk boundary/provider symbol references are rejected in protected truth paths. |
| H07 | REMEDIATED | Host-native output is advisory; CI on main is authoritative; environment metadata is printed. |
| H08 | PROVEN_BLOCKER | The current main record is not final and must be updated to `M6_PASS` only after corrective merge and green protected-main CI. |

## Root-Cause Findings

| ID | Finding |
|---|---|
| RC01 | PROVEN: The original validator encoded one example rather than the invariant. |
| RC02 | PROVEN: The original AST scan ignored `ImportFrom.level`, dynamic imports, and dynamic code execution. |
| RC03 | PROVEN: The original boundary check was unidirectional. |
| RC04 | PROVEN: The original negative-control success was too narrow to prove evasion resistance. |
| RC05 | REMEDIATED: Execution authority is now documented as CI-on-main, with local host execution advisory only. |
| RC06 | PROVEN_BLOCKER: Final completion evidence remains open until the corrective PR lands and protected-main CI is green. |

## Residual Risk Register

| Risk | Residual state | Owner phase |
|---|---|---|
| `provider_boundary.py` remains physically large | Accepted under Path B because B2.4 is LLM-free; blocked before B2.7 unless formally waived. | B2.7 |
| Future DTO/schema reverse-flow exception may be needed | No exception is approved during M6; any future exception needs decision-record and validator allowlist updates. | Future LLM governance |
| External protected-main CI can fail before repo code executes | M6 cannot pass until authoritative protected-main workflows are green. | M6 closure |

## Exit Gate Table

| Gate | Status | Evidence |
|---|---|---|
| M6-A | REMEDIATED | Relative, package, alias, and absolute imports are detected. |
| M6-B | REMEDIATED | Dynamic import/code execution calls fail closed in protected truth paths. |
| M6-C | REMEDIATED | Guardrail is bidirectional: truth-to-LLM and LLM-to-truth. |
| M6-D | REMEDIATED | Expanded negative controls are listed and implemented. |
| M6-E | REMEDIATED | Path B decision and B2.7 precondition remain intact. |
| M6-F | REMEDIATED | Validator prints Python/platform and states CI on main is authoritative. |
| M6-G | REMEDIATED | Corrective diff remains guardrail/docs-only. |
| M6-H | NOT_CLOSED | Updated validator must run in the B2.4 dry-run lane and protected-main CI must be green. |
| M6-I | NOT_CLOSED | Final record must be updated to `M6_PASS` with final SHA, PR URL, CI URL, and M7 authorization after main CI is green. |

## Next Phase Authorization

M7 may begin: NO.
