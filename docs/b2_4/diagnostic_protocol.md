# B2.4 Diagnostic Protocol

## Fit Request Identity

Every fit request is identified by:

- `tenant_id`: UUID and RLS boundary.
- `correlation_id`: UUID propagated through logs/tasks.
- `model_type`: governed enum, initially `bayesian_attribution_confidence`.
- `model_version`: semantic implementation version.
- `source_window_start` and `source_window_end`: inclusive/exclusive UTC timestamps.
- `source_snapshot_hash`: SHA-256 over canonical source snapshot.
- `requested_at`: UTC timestamp.
- `requested_by`: internal producer id, not user PII.

Forbidden identity states:

- Missing tenant.
- Missing source snapshot hash.
- Null source window.
- Ambiguous model version.
- Any durable PII in the request.

## Required Source Substrate

Inputs must come from deterministic B2.1/B2.3 substrates:

- Attribution event identities, timestamps, channel, model allocation outputs, and integer-cents revenue.
- B2.3 revenue event identities, provider, match verdict id, discrepancy class, confirmed/unmatched/provisional state, and integer-cents verified revenue.
- Deterministic implementation version markers where available.

No model may sample directly from raw PII, webhook payloads containing PII, or LLM-generated summaries.

## Eligibility Check Outputs

Eligibility runs before sampling. It returns:

- `eligible`: boolean.
- `eligibility_status`: `eligible`, `insufficient_data`, `unsupported_model_type`, `source_window_empty`, `source_snapshot_unstable`.
- `minimum_event_count_required`.
- `minimum_matched_revenue_event_count_required`.
- `observed_event_count`.
- `observed_matched_revenue_event_count`.
- `eligibility_retry_after`.
- `compute_refit_lock_consumed`: always false unless sampling starts.

Governed minimums for initial B2.4 implementation:

- At least 200 attribution events in the source window.
- At least 30 verified matched revenue events.
- At least 3 contributing channels with non-zero deterministic allocation.
- At least 14 days of covered source window unless a later model version justifies a different threshold.

Cold-start rule: `fallback_only/insufficient_data` must not set `last_fit_at` and must not consume the 24-hour compute refit lock. It may set a short eligibility retry backoff and must be unlocked by event-driven threshold crossing.

Future gates:

- B24-COLD-G1 proves insufficient data does not set `sampling_started_at`.
- B24-COLD-G2 proves insufficient data does not set `last_fit_at`.
- B24-COLD-G3 proves insufficient data does not consume the 24-hour compute refit lock.
- B24-COLD-G4 proves threshold crossing re-enqueues eligibility.

## Lifecycle Statuses

Allowed statuses:

- `eligibility_checked`
- `queued`
- `running`
- `converged`
- `fallback_only`
- `failed`
- `aborted`

Allowed fallback reasons:

- `insufficient_data`
- `timeout`
- `no_convergence`
- `insufficient_ess`
- `divergence`
- `worker_failure`
- `artifact_persistence_failure`
- `source_snapshot_changed`
- `refit_locked`
- `unsupported_model_type`
- `bayesian_not_implemented`

Forbidden status combinations:

- `converged` with `fallback_applied=true`.
- `converged` with null R-hat, ESS, divergence count, or artifact ref.
- `fallback_only/insufficient_data` with `sampling_started_at`.
- `fallback_only/insufficient_data` with `last_fit_at`.
- `failed` for pre-sampling insufficiency.
- Null `fallback_reason` when `fallback_applied=true`.

## Diagnostic Metrics

Persisted metrics:

- `r_hat_max`: maximum R-hat across parameters; pass threshold `< 1.01`.
- `ess_min`: minimum effective sample size across parameters; pass threshold `> 400`.
- `divergences`: count; pass threshold `0`.
- `hdi_probability`: expected `0.95` unless model version says otherwise.
- `credible_interval_status`: `available`, `unavailable`, `failed_diagnostics`, `not_applicable`, or `suppressed`.
- `sample_count`.
- `chain_count`.
- `tune_count`.
- `runtime_ms`.
- `timeout_seconds`.
- `diagnostic_payload`: JSONB with parameter-level details and ArviZ summary metadata.

Convergence requires all pass thresholds and an artifact write. Partial diagnostic success is not convergence.

## Error Classes

Future `app.bayesian.exceptions` classes:

- `BayesianEligibilityError`
- `BayesianSourceSnapshotError`
- `BayesianComputeTimeout`
- `BayesianNoConvergence`
- `BayesianInsufficientEss`
- `BayesianDivergenceFailure`
- `BayesianArtifactPersistenceError`
- `BayesianWorkerLifecycleError`
- `BayesianDependencyUnavailable`

Internal errors may be specific; external projection must use governed reason codes and must not expose stack traces.

## B2.5 Projection Behavior

B2.4 projects internal confidence metadata, not public endpoints. B2.5 sees:

- `bayesian_convergence_status`.
- `credible_interval_status`.
- `data_completeness_status`.
- `fallback_applied`.
- `fallback_reason`.
- `action_authority`.
- `source_snapshot_hash`.
- `artifact_ref` and `artifact_hash` when available.

If confidence is unavailable, B2.5 must expose unavailable confidence explicitly and continue deterministic TrustEnvelope construction where deterministic truth is valid.

## Negative Controls Expected in B2.4

- Insufficient data produces `fallback_only/insufficient_data`, no compute lock.
- Timeout produces explicit timeout fallback and deterministic projection.
- Failed R-hat blocks convergence.
- Failed ESS blocks convergence.
- Divergence count > 0 blocks convergence.
- Missing artifact hash blocks convergence.
- LLM imports in Bayesian path fail static validation.
