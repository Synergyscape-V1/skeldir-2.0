# M6 LLM Provider Boundary Decision

## Selected Path

Selected path: Path B - Guardrail before B2.4; decomposition before B2.7.

## Rationale

B2.4 is a bounded Bayesian confidence substrate over deterministic attribution and B2.3 revenue-verification truth. Current B2.4 design artifacts classify the phase as internal confidence metadata and artifact persistence work, not explanation-layer work. The design explicitly excludes public API routes, MCP tools, frontend/dashboard consumers, and LLM provider-boundary changes during B2.4.

`backend/app/llm/provider_boundary.py` remains the single LLM choke-point and is physically overloaded. Current inspection shows it contains provider calls, budget reservation/settlement, circuit-breaker behavior, semantic cache handling, timeout handling, output validation, audit writes, and distillation persistence behind the retained `SkeldirLLMProvider` facade. That is a real maintainability risk, but B2.4 does not need to extend explanation behavior. Full decomposition is therefore deferred until B2.7 unless B2.4 introduces an LLM touchpoint.

## B2.4 Touchpoint Classification

| Surface | Evidence | LLM touchpoint |
|---|---|---|
| B2.4 diagnostics | `docs/b2_4/diagnostic_protocol.md` defines R-hat, ESS, divergences, HDI, lifecycle status, and source snapshot requirements over deterministic source rows. It forbids LLM-generated summaries as model inputs. | NO |
| B2.4 fit worker | `docs/b2_4/b2_4_readiness_substrate.md` places future orchestration under `backend/app/bayesian/fit_worker.py` with `backend/app/tasks/bayesian.py` as a thin Celery adapter. | NO |
| B2.4 artifact store | `docs/b2_4/model_artifact_persistence_requirements.md` defines persisted fit/artifact refs, hashes, diagnostics, storage backend, resolver, and RLS/GUC expectations. | NO |
| B2.4 fallback | `docs/b2_4/fallback_doctrine.md` defines deterministic confidence-unavailable reason codes and explicitly forbids LLM-invented fallback explanations with numeric claims. | NO |
| B2.4 confidence projection | `contracts/internal/b2_4_confidence_metadata.schema.json` defines internal confidence metadata. It is not a public explanation schema. | NO |
| B2.4 CI gates | `docs/b2_4/b2_4_ci_gate_strategy.md` places gates in the M3 B2.4 dry-run lane and names LLM-import exclusion as static validation. | NO |
| B2.4 API exposure, if any later | Current B2.4 docs state no FastAPI router or public endpoint during B2.4. Later API exposure must stay deterministic and cannot import provider modules. | NO |

Because every current B2.4 surface is LLM-free, Path B is valid.

## Decision Rule

B2.4 may proceed after M7 only as an LLM-free Bayesian confidence substrate. It may add deterministic/statistical diagnostics, source snapshot identity, artifact persistence, fallback reason codes, and internal confidence metadata. It may not add explanation-layer behavior.

## Invalidation Rule

If B2.4 introduces or modifies LLM-facing explanation, summary, narrative fallback, provider calls, prompts, LLM cache, LLM validation, LLM audit, provider SDK imports, or `backend/app/llm/provider_boundary.py` behavior, Path B is invalid. Path A facade-preserving decomposition becomes mandatory before B2.4 may continue.

## Allowed LLM Import Locations

Application imports from `app.llm.*` are allowed only in existing LLM/explanation surfaces:

- `backend/app/llm/**`
- `backend/app/workers/llm.py`
- `backend/app/services/llm_authority_contract.py`
- `backend/app/api/attribution.py`
- `backend/app/api/budget.py`
- `backend/app/api/investigations.py`

These allowances do not authorize new B2.4 explanation behavior.

## Forbidden Import Locations

`app.llm.*`, `backend.app.llm.*`, `SkeldirLLMProvider`, and `provider_boundary.py` imports are forbidden from:

- `backend/app/bayesian/**`
- `backend/app/tasks/bayesian.py`
- `backend/app/trust/**`
- `backend/app/reconciliation/**`
- `backend/app/revenue_verification/**`
- `backend/app/policy/**`
- `backend/app/policies/**`
- `backend/app/solver/**`
- `backend/app/envelope/**`
- `backend/app/mcp/**`
- Trust API, MCP trust-tool, TrustEnvelope, policy, solver, and envelope-generation paths wherever they appear.

## Provider SDK Import Policy

Provider SDK imports are allowed only inside `backend/app/llm/provider_boundary.py` unless a later decomposition phase explicitly moves that responsibility behind the retained `SkeldirLLMProvider` facade and updates this decision. The M6 validator treats these provider SDK module names as controlled:

- `aisuite`
- `openai`
- `anthropic`
- `groq`
- `google.generativeai`
- `google.genai`
- `vertexai`
- `cohere`
- `mistralai`

Provider SDK imports are also a forbidden truth-path channel. Bayesian, Trust, reconciliation, revenue-verification, policy, solver, envelope, and MCP truth paths may not import provider SDKs directly even if they avoid `app.llm.*`.

## Reverse-Flow Import Policy

`backend/app/llm/**` must not import B2.4, Bayesian diagnostic, Trust, reconciliation, revenue-verification, policy, solver, envelope-generation, MCP, or `app.tasks.bayesian` implementation internals. The LLM layer is downstream explanation infrastructure; it must not become structurally coupled back into deterministic or statistical truth construction.

No reverse-flow exceptions are approved during M6. Stable read-only DTO/schema exceptions require an explicit future decision-record update and validator allowlist entry.

## Effect on B2.4

B2.4 remains blocked from importing LLM provider modules, adding provider SDK imports, adding prompts, adding LLM cache/budget/breaker behavior, adding fallback narration, or modifying `provider_boundary.py`. The M6 static validator is wired into the B2.4 dry-run lane to reject drift before implementation begins.

The guardrail rejects absolute imports, package imports, aliased imports, relative imports, dynamic import mechanisms, provider SDK imports, and high-risk provider-boundary symbol references in protected truth paths.

## Effect on B2.7

B2.7 cannot begin until provider-boundary decomposition is completed or formally waived under `docs/b2_7/preconditions.md`. The default expected decomposition target is:

- `llm/budget.py`
- `llm/cache.py`
- `llm/circuit_breaker.py`
- `llm/provider_call.py`
- `llm/validation.py`
- `llm/audit.py`
- retained `SkeldirLLMProvider` facade

## Effect on Trust API and MCP Paths

Trust API read paths, MCP trust tools, TrustEnvelope builders, policy evaluators, solver kernels, reconciliation kernels, match-engine paths, Bayesian diagnostics, and envelope-generation code must remain LLM-free. LLMs may explain deterministic or bounded-probabilistic facts only after those facts are produced and validated by deterministic/statistical paths.

## Non-Implementation Boundary

M6 does not implement provider-boundary decomposition, B2.4 Bayesian behavior, public API routes, prompt templates, dependency changes, frontend work, webhook behavior, B2.3 semantics, or RLS changes. Its only executable remediation is a static guardrail.

## Maturity Mode

Design Partner Mode. B2.4 may later create internal confidence metadata and persisted artifacts after M7 authorization, but external activation and explanations remain downstream phases.

## End-User Value Test

M6 passes only if a future engineer cannot quietly route B2.4 confidence, TrustEnvelope truth, or MCP trust reads through the LLM provider boundary. The user-facing value is reduced regression risk: Bayesian confidence can be built without diluting deterministic financial truth or making explanation text authoritative.
