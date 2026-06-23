# CI Governance

This directory is the M3 CI governance surface. The registry and matrix are executable inputs to CI, not passive documentation.

## Command Surface

- `make validate-ci-governance` runs the full M3 validator.
- `make ci-topology` validates required-context and M0/M1/M2 topology mapping.
- `make ci-enforcer-registry-check` verifies every `scripts/ci/*.py` is registered or utility-classified.
- `make ci-gate-subsumption-check` verifies gate dispositions.
- `make ci-b24-gate-dry-run` validates the isolated B2.4 insertion lane without feature implementation.
- `make ci-metrics` emits current active complexity metrics.
- `make ci-cohort-summary` emits a structured dry-run summary for the contract governance cohort.

## Executable Artifacts

- `docs/ci/enforcer_registry.yaml`
- `docs/ci/gate_subsumption_matrix.yaml`
- `scripts/ci/validate_m3_ci_governance.py`
- `scripts/ci/run_ci_governance_cohort.py`
- `.github/actions/setup-postgres-ci/action.yml`
- `.github/workflows/m3-ci-governance.yml`
- `.github/workflows/b2_4-gate-dry-run.yml`

## Execution Cohorts

- `b2-4-dry-run`: 16 registered gate(s)
- `contract-governance`: 25 registered gate(s)
- `db-backed-governance`: 18 registered gate(s)
- `m0-m1-m2-preservation`: 3 registered gate(s)
- `static-governance`: 43 registered gate(s)
- `utility-only`: 3 registered gate(s)

## Failure Visibility

The cohort runner emits `gate_id`, script path, protected invariant, failed command, local reproduction command, first diagnostic command, and failure meaning for every selected gate. CI remains visible at the workflow/job cohort level while failures remain attributable to a concrete gate.
