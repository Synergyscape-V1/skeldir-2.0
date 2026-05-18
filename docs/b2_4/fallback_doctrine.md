# B2.4 Fallback Doctrine

## Deterministic Truth Sovereignty

Bayesian confidence enriches deterministic attribution and verified revenue truth. It never overrides:

- B2.3 match verdicts.
- Verified revenue records.
- Integer-cents revenue values.
- B2.3 discrepancy classes.
- Deterministic attribution output rows.

Fallback means probabilistic confidence is unavailable or not authoritative. It does not mean deterministic truth failed.

## Fallback Semantics

Allowed fallback states:

| Reason | Meaning | Sampling started | Compute refit lock |
|---|---|---:|---:|
| `insufficient_data` | Eligibility thresholds not met. | No | No |
| `timeout` | Bounded compute exceeded soft/hard time budget. | Yes | Yes |
| `no_convergence` | R-hat threshold failed. | Yes | Yes |
| `insufficient_ess` | ESS threshold failed. | Yes | Yes |
| `divergence` | Divergence count > 0. | Yes | Yes |
| `worker_failure` | Worker crashed or stale-running cleanup recovered task. | Maybe | Yes only if sampling started |
| `artifact_persistence_failure` | Diagnostics may exist but artifact write/hash failed. | Yes | Yes |
| `source_snapshot_changed` | Source hash invalidated before or during fit. | Maybe | No if before sampling |
| `refit_locked` | Recent compute fit blocks refit. | No | Existing lock only |
| `bayesian_not_implemented` | B2.4 not active yet. | No | No |

Cold-start rule: `fallback_only/insufficient_data` is retriable by eligibility threshold crossing, must not set `last_fit_at`, and must not impose a 24-hour compute refit lock.

## Projection Fields

Internal projection fields:

- `confidence_available`.
- `bayesian_convergence_status`.
- `credible_interval_status`.
- `data_completeness_status`.
- `fallback_applied`.
- `fallback_reason`.
- `action_authority`.
- `source_snapshot_hash`.
- `artifact_ref`.
- `artifact_hash`.
- `last_fit_at`.
- `eligibility_retry_after`.

Machine-facing fields use governed reason codes. Internal errors may include stack traces in logs/DLQ only, never in TrustEnvelope projection.

## B2.5 Behavior

B2.5 must:

- Continue deterministic TrustEnvelope construction when deterministic truth exists.
- Mark confidence unavailable with explicit reason.
- Treat `fallback_applied=true` as a confidence-state flag, not a financial-value rewrite.
- Preserve `action_authority=read_only` or `blocked` where confidence is insufficient for later decision surfaces.

## Forbidden Behavior

B2.4 must not:

- Mutate deterministic truth rows during fallback.
- Replace B2.3 verdicts with Bayesian estimates.
- Convert insufficient data into compute failure.
- Emit null fallback reason when fallback applies.
- Hide timeouts or convergence failures behind generic unavailable status.
- Let LLMs invent fallback explanations with numeric claims.
- Expose probabilistic confidence as available without converged diagnostics and artifacts.
