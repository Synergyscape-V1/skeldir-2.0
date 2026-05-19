# B2.7 Preconditions

## Hard Precondition

B2.7 cannot begin until the LLM provider boundary is decomposed behind the retained `SkeldirLLMProvider` facade or a formal waiver is approved.

## Required Decomposition Evidence

The default decomposition must separate these responsibilities before explanation-layer expansion:

- `llm/budget.py`
- `llm/cache.py`
- `llm/circuit_breaker.py`
- `llm/provider_call.py`
- `llm/validation.py`
- `llm/audit.py`
- retained `SkeldirLLMProvider` facade

Completion evidence must include regression checks proving existing provider behavior, budget accounting, cache replay, circuit-breaker behavior, output validation, audit writes, timeout handling, and distillation persistence remain facade-compatible.

## Waiver Requirements

A waiver is valid only if it records:

- owner
- reason decomposition is deferred
- expiry or review date
- exact explanation/provider changes allowed
- static CI guardrails that remain active
- proof that Trust API, MCP tools, TrustEnvelope truth paths, Bayesian diagnostics, reconciliation kernels, policy evaluators, solver kernels, and envelope-generation paths remain LLM-free

No open-ended waiver is valid.

## B2.4 Interaction

Path B from M6 allows B2.4 to proceed only while B2.4 remains LLM-free. If B2.4 introduces explanation/provider behavior, this precondition accelerates: decomposition or formal waiver is required before B2.4 continues, not merely before B2.7 starts.
