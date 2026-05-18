# B2.4 Readiness Substrate

## Purpose

M5 freezes the B2.4 implementation substrate before statistical code begins. B2.4 is a bounded probabilistic confidence substrate over deterministic B2.1 attribution and B2.3 revenue-verification truth. It is not a new financial truth source and it is not a public API phase.

Maturity mode: Design Partner Mode. B2.4 may create internal confidence metadata and persisted artifacts after implementation starts, but external activation waits for later TrustEnvelope phases.

## Module Home

The canonical future production package is `backend/app/bayesian/`.

Required future submodules:

| Module | Responsibility |
|---|---|
| `backend/app/bayesian/model_spec.py` | Versioned model-type definitions, governed fit thresholds, model configuration identity, and deterministic source-window declaration. |
| `backend/app/bayesian/fit_worker.py` | Celery-facing orchestration wrapper that loads source snapshots, calls the sampler, persists lifecycle transitions, and emits fallback metadata. |
| `backend/app/bayesian/diagnostics.py` | R-hat, ESS, divergence, HDI, sample-count, timeout, and convergence-status evaluation over sampler outputs. |
| `backend/app/bayesian/artifact_store.py` | Artifact reference creation, hash validation, storage-backend dispatch, and resolver contracts. |
| `backend/app/bayesian/fallback.py` | Deterministic fallback reason mapping and B2.5 projection shape for unavailable confidence. |
| `backend/app/bayesian/api_projection.py` | Internal projection into `contracts/internal/b2_4_confidence_metadata.schema.json`; no FastAPI router. |
| `backend/app/bayesian/exceptions.py` | Typed exceptions for eligibility, compute, diagnostics, artifact persistence, and worker lifecycle failures. |

`backend/app/tasks/bayesian.py` remains the Celery task surface. During B2.4 it should become a thin task adapter that delegates to `app.bayesian.fit_worker`. Statistical code must not live directly in `app/tasks/bayesian.py`.

## Existing Stub Classification

The current `backend/app/tasks/bayesian.py` is scaffold and reusable infrastructure only.

Reusable:

- `QUEUE_BAYESIAN` binding and task-route proof surface.
- Soft/hard bounded-compute contracts.
- Health probe concept.
- Resource-contention probes used to reason about worker topology.
- Structured tenant and correlation logging pattern.

Must be replaced or bypassed for real B2.4:

- `run_mcmc_inference` resource simulation.
- Fallback payload named as `deterministic_last_touch`.
- Any implication that CPU sleep loops are convergence logic.
- Lack of source snapshot identity, fit persistence, artifact refs, and diagnostics.

## Allowed Imports

Future `backend/app/bayesian/` modules may import:

- `app.attribution.strategy_kernel` and attribution semantics for deterministic source surfaces.
- `app.revenue_verification.semantic_authority` read-side types and B2.3 verdict identity.
- `app.core.money`, `app.core.queues`, `app.core.config`, and tenant-context utilities.
- SQLAlchemy session/model layers through existing repository patterns.
- PyMC and ArviZ only after B2.4 implementation authorizes dependency installation.

## Forbidden Imports

B2.4 Bayesian substrate must not import:

- `app.llm.*` or provider SDKs.
- FastAPI routers or public API dependencies.
- Webhook verifier modules.
- Frontend/dashboard code.
- Direct external MCP/tool adapters.
- Non-Postgres brokers, event buses, or non-relational stores.

## Consumer Surfaces

Primary consumers:

- B2.5 TrustEnvelope builder, through internal confidence metadata only.
- B2.7 explanation layer, only after validated deterministic/Bayesian outputs exist; LLMs do not calculate.
- B5.1 Bayesian TrustEnvelope enrichment.

Non-consumers during B2.4:

- Public FastAPI endpoints.
- Dashboard/frontend components.
- MCP tools.
- LLM provider boundary.

## Source Substrates

B2.4 consumes deterministic source rows from:

- B2.1 attribution events and deterministic attribution outputs.
- B2.3 verified revenue events, match dispatches, verdicts, exception records, and state transitions.

The source snapshot must be identified by `source_snapshot_hash`, computed from tenant id, model type, source window, deterministic row identities, deterministic version fields, and canonical serialized source data. The hash is required before sampling and is persisted with every fit and artifact.

## Worker Lifecycle

Future lifecycle:

```text
eligibility_checked
  -> fallback_only / insufficient_data
  -> queued
  -> running
  -> converged
  -> aborted
  -> failed
  -> fallback_only
```

Rules:

- `insufficient_data` is an eligibility outcome, not a compute failure.
- `queued` records task identity and source snapshot identity.
- `running` records `sampling_started_at` and consumes the compute refit lock.
- `converged` requires R-hat < 1.01, ESS > 400, divergences == 0, successful HDI generation, and persisted artifacts.
- `aborted` covers governed cancellation, stale-running cleanup, or hard timeout after cleanup.
- `failed` covers compute, diagnostics, persistence, or worker failures after sampling started.
- `fallback_only` always preserves deterministic truth and emits explicit reason metadata.

Timeouts:

- Soft timeout persists `fallback_only/timeout` if the worker can still write.
- Hard timeout is recovered by stale-running cleanup and persisted as `aborted/stale_running_timeout` or `fallback_only/worker_failure`.

Retries:

- Eligibility failure uses `eligibility_retry_backoff`, not compute refit lock.
- Compute failure uses governed retry count and then `fallback_only`.
- Stale-running cleanup must be idempotent by fit id and task id.

## Future Implementation Sequence

P0: Add design-to-code placeholders and enums only if required by test registration; no PyMC installation.

P1: Add migrations for `bayesian_model_fits` and `bayesian_artifacts`, RLS, constraints, indexes, canonical schema reflection, and static schema validators.

P2: Implement source snapshot extraction and eligibility checks with cold-start negative controls.

P3: Introduce PyMC and ArviZ through declared dependencies and lockfiles; implement bounded fit orchestration and diagnostic evaluation.

P4: Persist artifacts, run real Celery worker proofs, add convergence/failure negative controls, and project internal confidence metadata for B2.5.

## B2.4 Must Not Do

B2.4 must not mutate deterministic source rows, redesign B2.3, calculate financial truth through an LLM, create public endpoints, route through dashboard code, clone statistical dependencies manually, or treat unavailable confidence as zero confidence.
