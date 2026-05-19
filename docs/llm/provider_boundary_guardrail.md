# M6 Provider Boundary Guardrail

## Canonical Authority

The canonical M6 decision is `docs/llm/provider_boundary_decision.md`. This guardrail document restates the operational rule for implementers and CI owners.

## Path B Guardrail

B2.4 is allowed to proceed only as LLM-free Bayesian confidence work. During B2.4, do not add:

- explanation metrics in `backend/app/llm/provider_boundary.py`
- provider-specific imports outside `backend/app/llm/provider_boundary.py`
- new budget, cache, circuit-breaker, validation, audit, or provider-call behavior
- prompt templates or prompt routing
- LLM fallback narrative behavior
- Trust API or MCP truth paths that import `app.llm.*`

## Machine Enforcement

`scripts/ci/validate_m6_llm_boundary.py --negative-control` enforces the guardrail. It validates the decision record, B2.7 precondition, provider SDK import policy, forbidden `app.llm` import paths, CI/governance registration, and PR diff non-implementation constraints when a GitHub merge base is available.

The validator resolves package-relative imports using repo-relative package context and uses OS-neutral path normalization. It fail-closes unresolved relative imports in protected truth paths, bans `importlib.import_module`, `__import__`, `eval`, and `exec` in protected truth paths, rejects provider SDK imports outside the approved provider boundary, and rejects reverse-flow imports from `backend/app/llm/**` into B2.4, Bayesian, Trust, reconciliation, revenue-verification, policy, solver, envelope, MCP, or Bayesian task internals.

The negative control suite creates temporary bad fixtures and requires each class to fail before positive validation may pass. It covers absolute imports, package imports, aliased imports, relative imports, dynamic imports, built-in dynamic imports, `eval`, `exec`, provider SDK truth-path imports, forbidden symbol references, reverse-flow imports, and decision-record mutation.

## Invalidation

If any B2.4 change needs explanation, summary, narrative fallback, provider calls, prompts, LLM cache, LLM validation, LLM audit, provider SDK imports, or `provider_boundary.py` behavior, Path B is invalid. Stop B2.4 and execute or formally authorize Path A decomposition first.
