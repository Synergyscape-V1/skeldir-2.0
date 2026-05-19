# M6 Completion Record

## Executive Verdict

M6_CONDITIONAL.

This record is the branch evidence state for the M6 implementation. The final verdict becomes M6_PASS only after the M6 branch is merged to `main`, protected-branch CI is green on `main`, and this record is updated with final main closure evidence.

## Selected Path

Path B - Guardrail before B2.4; decomposition before B2.7.

## Final Main Commit SHA

Final main SHA is recorded in `docs/maintainability/M6 Remediation Evidence Pack .md` after protected-branch merge closure.

## PR URL

The PR URL is recorded in `docs/maintainability/M6 Remediation Evidence Pack .md` after publication.

## CI Workflow URLs

CI workflow URLs are recorded in `docs/maintainability/M6 Remediation Evidence Pack .md` after GitHub Actions completes.

## Validation Command And Output

Command:

```bash
python scripts/ci/validate_m6_llm_boundary.py --negative-control
```

Expected output:

```text
M6_NEGATIVE_CONTROL_PASS: forbidden LLM import in B2.4/truth path
M6_LLM_BOUNDARY_VALIDATION_PASS
```

## Negative-Control Evidence

The validator creates a temporary fixture under `backend/app/bayesian/m6_bad_import.py` containing:

```python
from app.llm.provider_boundary import SkeldirLLMProvider
```

It then runs the import-boundary scan against the fixture root and requires failure before the real repository can pass.

## B2.4 LLM Touchpoint Matrix

| Surface | LLM touchpoint | Status |
|---|---:|---|
| B2.4 diagnostics | NO | REFUTED as LLM-touching |
| B2.4 fit worker | NO | REFUTED as LLM-touching |
| B2.4 artifact store | NO | REFUTED as LLM-touching |
| B2.4 fallback | NO | REFUTED as LLM-touching |
| B2.4 confidence projection | NO | REFUTED as LLM-touching |
| B2.4 CI gates | NO | REFUTED as LLM-touching |
| B2.4 API exposure, if any later | NO during B2.4 | REFUTED as current B2.4 surface |

## Provider Import Boundary Policy

Provider SDK imports are approved only in `backend/app/llm/provider_boundary.py` during M6. `app.llm.*` imports are forbidden from Bayesian, Trust API, MCP trust-tool, reconciliation, revenue-verification, policy, solver, and envelope-generation paths.

## B2.7 Precondition Evidence

`docs/b2_7/preconditions.md` blocks B2.7 until provider-boundary decomposition is completed or formally waived with owner, reason, expiry/review date, allowed changes, CI guardrails, and LLM-free truth-path proof.

## Diff Scope Inventory

M6 changes are limited to:

- `.github/workflows/b2_4-gate-dry-run.yml`
- `Makefile`
- `docs/b2_7/preconditions.md`
- `docs/ci/enforcer_registry.yaml`
- `docs/ci/gate_subsumption_matrix.yaml`
- `docs/llm/provider_boundary_decision.md`
- `docs/llm/provider_boundary_guardrail.md`
- `docs/maintainability/m6_completion_record.md`
- `docs/maintainability/M6 Remediation Evidence Pack .md`
- `scripts/ci/validate_m6_llm_boundary.py`

## Non-Implementation Proof

M6 does not modify:

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

The validator checks these constraints in PR diff mode when a merge base is available.

## Hypothesis Matrix

| ID | Status | Finding |
|---|---|---|
| H01 | REFUTED | Current B2.4 artifacts contain no explanation, summary, narrative fallback, prompt, provider call, LLM cache, LLM validation, or provider-boundary behavior. |
| H02 | REMEDIATED | Path B selected and guarded because B2.4 is LLM-free. |
| H03 | PARTIAL | `provider_boundary.py` remains physically overloaded, but B2.4 does not depend on extending it. |
| H04 | REMEDIATED | M6 validator adds active import-boundary protection for B2.4/truth paths and provider SDK imports. |
| H05 | REMEDIATED | `docs/b2_7/preconditions.md` blocks B2.7 until decomposition or waiver. |
| H06 | REMEDIATED | Decision record includes Path B invalidation rule. |
| H07 | REMEDIATED | `make validate-m6-llm-boundary` provides machine-falsifiable validation with a negative control. |
| H08 | REMEDIATED | M6 avoids provider-boundary decomposition implementation and provider behavior changes. |
| H09 | REMEDIATED | Validator is registered in CI governance and wired into the B2.4 dry-run lane. |
| H10 | PARTIAL | Main closure evidence awaits protected-branch merge and final CI completion. |

## Root-Cause Findings

| ID | Finding |
|---|---|
| RC01 | PROVEN: `provider_boundary.py` is architecturally correct but physically overloaded. |
| RC02 | PROVEN: B2.4 is LLM-free by design but lacked a hard M6 guard before this remediation. |
| RC03 | PARTIAL: Forward Trust API/MCP plans create pressure to route explanation through truth paths, so M6 blocks those imports. |
| RC04 | PROVEN: Decomposition is valuable but premature for B2.4 while B2.4 stays LLM-free. |
| RC05 | PROVEN: M5 had a validator, but there was no M6 LLM-boundary validator in the B2.4 dry-run lane. |
| RC06 | REMEDIATED: M6 explicitly treats narrative fallback, explanation confidence, summary, insight, assistant, prompts, and provider behavior as Path B invalidators in B2.4 contexts. |

## Residual Risk Register

| Risk | Residual state | Owner phase |
|---|---|---|
| `provider_boundary.py` remains large | Accepted under Path B because B2.4 is LLM-free; blocked before B2.7 unless waived. | B2.7 |
| Existing non-B2.4 explanation API imports LLM modules | Allowed as pre-existing explanation surfaces; not authority for Trust API or Bayesian paths. | LLM governance |
| Final main evidence not present in this branch record | Must be closed after protected-branch CI passes on `main`. | M6 closure |

## Exit Gate Table

| Gate | Status | Evidence |
|---|---|---|
| M6-A | PASS | Decision selects Path B with evidence from B2.4 docs. |
| M6-B | PASS | Touchpoint matrix classifies B2.4 surfaces as LLM-free. |
| M6-C | PASS | Static validator rejects bad B2.4 `app.llm.provider_boundary` import. |
| M6-D | PASS | Path B invalidation rule exists. |
| M6-E | PASS | B2.7 precondition exists. |
| M6-F | PASS | Diff scope excludes provider, B2.4 implementation, API, dependency, frontend, RLS, webhook, and B2.3 behavior changes. |
| M6-G | PASS | Validator has negative control and CI wiring. |
| M6-H | CONDITIONAL | Final main SHA, PR URL, and main CI URL require post-merge closure update. |

## Next Phase Authorization

M7 may begin: NO until M6-H is closed on `main`.
