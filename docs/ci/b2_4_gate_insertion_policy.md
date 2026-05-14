# B2.4 Gate Insertion Policy

B2.4 CI gates must attach through the isolated B2.4 workflow or a future reusable workflow referenced by that lane. They must not be appended to `.github/workflows/ci.yml` and must not edit M0, M1, or M2 workflows.

## Allowed in This Lane

- Metadata-only gate registration.
- Static validation of future convergence gate contracts.
- Dry-run cohort summaries through `scripts/ci/run_ci_governance_cohort.py`.
- Registry and subsumption validation.

## Forbidden in This Lane

- Bayesian runtime implementation.
- Statistical model execution.
- New production convergence diagnostics.
- Provider-boundary behavior changes.
- B2.3 semantic changes.
- Additional DB setup duplication.

## Required Registration

Every future B2.4 gate must add or update an entry in `docs/ci/enforcer_registry.yaml` and `docs/ci/gate_subsumption_matrix.yaml`, including invariant, owner phase, command, local reproduction, failure meaning, DB/Celery/pooler dependencies, default execution, and visibility.

## Dry-Run Proof

`make ci-b24-gate-dry-run` validates that the lane exists, is registered, is feature-clean, and can produce a registry cohort summary without executing B2.4 runtime logic.
