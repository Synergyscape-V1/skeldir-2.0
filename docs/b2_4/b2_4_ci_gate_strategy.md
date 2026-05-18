# B2.4 CI Gate Strategy

## Strategy

B2.4 gates attach through the M3-created B2.4 insertion lane. They must not expand `.github/workflows/ci.yml`, alter M0/M1/M2 workflows, or create unregistered validators.

Current M5 gate:

- `validate-m5-b24-readiness-design`: static design validator.

Future B2.4 gate cohort:

- `b24-static-contracts`.
- `b24-schema-persistence`.
- `b24-cold-start`.
- `b24-worker-runtime`.
- `b24-convergence-diagnostics`.
- `b24-artifact-integrity`.
- `b24-negative-controls`.

## Future Validator Names

| Validator | Lane | Merge blocking |
|---|---|---|
| `validate_m5_b24_readiness_design.py` | M5 static design | Yes for M5. |
| `validate_b24_schema_contract.py` | DB schema/static migration | Yes when P1 begins. |
| `validate_b24_cold_start_semantics.py` | Static + DB-backed | Yes. |
| `validate_b24_artifact_integrity.py` | DB-backed artifact resolver | Yes. |
| `validate_b24_worker_lifecycle.py` | Real Celery/Postgres worker | Yes after worker implementation. |
| `validate_b24_convergence_diagnostics.py` | Bounded statistical runtime | Merge-blocking for minimal deterministic fixtures; heavier sampling nightly. |
| `validate_b24_llm_exclusion.py` | Static import/path scan | Yes. |

## Negative Controls

Required negative controls:

- Missing required M5 section fails validation.
- Insufficient data cannot consume compute refit lock.
- R-hat >= 1.01 blocks convergence.
- ESS <= 400 blocks convergence.
- Divergences > 0 block convergence.
- Missing artifact hash/ref blocks convergence.
- Cross-tenant artifact ref resolution fails under RLS.
- LLM imports from Bayesian path fail.
- Public route addition for B2.4 fails until owning API phase.

## DB-Backed Gates

Future DB gates must prove:

- `bayesian_model_fits` and `bayesian_artifacts` fields and constraints.
- RLS enabled and GUC-bound under runtime identity.
- Composite indexes for tenant/time lookup.
- Reversible migration and canonical schema reflection.
- Artifact hash/ref uniqueness and resolver tenant guard.

## Worker Runtime Gates

Future worker gates must run against Postgres broker/backend only and prove:

- `queued -> running -> converged`.
- Soft timeout emits fallback.
- Hard timeout/stale-running cleanup persists final state.
- Retry limit produces deterministic fallback.
- Health probe remains available after timeout.
- `QUEUE_BAYESIAN` remains isolated.

## Branch Protection and Required Contexts

M5 uses the existing `B2.4 Gate Dry Run` workflow context and extends it with the M5 static design command. If future branch protection needs a distinct context, add it through `docs/ci/enforcer_registry.yaml`, `docs/ci/gate_subsumption_matrix.yaml`, and the required-status-check contract, not by ad hoc workflow edits.

## M3 Insertion Lane Usage

All B2.4 validators must:

- Register in `docs/ci/enforcer_registry.yaml`.
- Register disposition in `docs/ci/gate_subsumption_matrix.yaml`.
- Use the isolated `.github/workflows/b2_4-gate-dry-run.yml` or a future B2.4 reusable workflow referenced by the same lane.
- Provide local reproduction command and first diagnostic command.
- Classify DB/Celery/pooler dependencies.

## Avoiding CI Sprawl

Do not add B2.4 commands to unrelated phase workflows. Do not duplicate database setup blocks. Do not create one workflow per tiny validator. Cohort validators should summarize failures while preserving clear gate IDs and negative-control evidence.
