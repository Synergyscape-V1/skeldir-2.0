#!/usr/bin/env python3
"""Validate B2.4-P7 diagnostic semantics and interval conditionality."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
DIAGNOSTICS = BAYESIAN_PACKAGE / "diagnostics.py"
INTERVALS = BAYESIAN_PACKAGE / "intervals.py"
RESULT_CONTRACT = BAYESIAN_PACKAGE / "result_contract.py"
SAMPLER_CHILD = BAYESIAN_PACKAGE / "sampler_child.py"
FIT_EXECUTION = BAYESIAN_PACKAGE / "fit_execution.py"
P7_TESTS = Path("backend/tests/test_b24_p7_diagnostic_semantics.py")
P7_DB_TESTS = Path("backend/tests/test_b24_p7_postgres_runtime.py")
P7_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606041200_b24_p7_diagnostic_semantics.py"
)
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
ENFORCER_REGISTRY = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_MATRIX = Path("docs/ci/gate_subsumption_matrix.yaml")
TOPOLOGY_MAP = Path("docs/ci/ci_topology_map.md")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)

REQUIRED_FILES = {
    DIAGNOSTICS,
    INTERVALS,
    RESULT_CONTRACT,
    SAMPLER_CHILD,
    FIT_EXECUTION,
    P7_TESTS,
    P7_DB_TESTS,
    P7_MIGRATION,
    WORKFLOW,
    MAKEFILE,
    ENFORCER_REGISTRY,
    SUBSUMPTION_MATRIX,
    TOPOLOGY_MAP,
    REQUIRED_STATUS_CONTRACT,
}


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    full = ROOT / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def validate_policy_authority(diagnostics_text: str | None = None) -> None:
    diagnostics = diagnostics_text if diagnostics_text is not None else _read(DIAGNOSTICS)
    for token in (
        "B24_P7_DIAGNOSTIC_POLICY_VERSION",
        "b24-p7-diagnostic-policy-v1",
        "B24_P7_DIAGNOSTIC_TARGET_FILTER_VERSION",
        "b24-p7-target-filter-v1",
        "B24_P7_INTERVAL_POLICY_VERSION",
        "b24-p7-interval-policy-v1",
        "r_hat_max_threshold: float = 1.01",
        "ess_min_threshold: float = 400.0",
        "divergence_count_threshold: int = 0",
        'diagnostic_target_var_names: tuple[str, ...] = ("mu",)',
        'interval_target_var_names: tuple[str, ...] = ("mu",)',
        'excluded_deterministic_var_names: tuple[str, ...] = ("observed_signal",)',
        "max_diagnostic_variables",
        "max_diagnostic_elements",
        "max_interval_summary_bytes",
        'finite_value_policy: str = "required"',
    ):
        _require(token in diagnostics, f"P7 diagnostic policy missing: {token}")


def validate_child_arviz_boundary(
    diagnostics_text: str | None = None,
    child_text: str | None = None,
    fit_execution_text: str | None = None,
) -> None:
    diagnostics = diagnostics_text if diagnostics_text is not None else _read(DIAGNOSTICS)
    child = child_text if child_text is not None else _read(SAMPLER_CHILD)
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    for path, text in (
        (INTERVALS, _read(INTERVALS)),
        (RESULT_CONTRACT, _read(RESULT_CONTRACT)),
        (FIT_EXECUTION, fit_execution),
    ):
        tree = ast.parse(text, filename=path.as_posix())
        imports = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        from_imports = {
            node.module
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module is not None
        }
        forbidden = {"arviz", "pymc", "pytensor"}
        _require(not (forbidden & imports), f"parent imports native stack: {path}")
        _require(not (forbidden & from_imports), f"parent imports native stack: {path}")
    _require("import arviz as az" in diagnostics, "child diagnostic reducer lacks ArviZ import")
    _require("compute_arviz_diagnostic_summary(" in child, "sampler child does not compute P7 diagnostics")
    _require("return_inferencedata=True" in child, "sampler child does not keep in-child InferenceData")
    _require("validate_result_summary(result)" in child, "child summary is not validated before write")
    _require('"diagnostics_started"' in child, "diagnostic stage marker missing")
    _require('"result_summary_written"' in child, "result summary stage marker missing")
    _require('"execution_success": True' in child, "child summary missing execution_success")


def validate_governed_arviz_calls(diagnostics_text: str | None = None) -> None:
    diagnostics = diagnostics_text if diagnostics_text is not None else _read(DIAGNOSTICS)
    _require("az.summary(" not in diagnostics, "unbounded az.summary call is forbidden")
    for call in ("az.rhat(", "az.ess(", "az.hdi("):
        _require(call in diagnostics, f"missing governed diagnostic call: {call}")
    for token in (
        "_select_coords(idata, policy.diagnostic_target_coords)",
        "_select_coords(idata, policy.interval_target_coords)",
        "var_names=list(policy.diagnostic_target_var_names)",
        "var_names=list(policy.interval_target_var_names)",
    ):
        _require(token in diagnostics, f"ArviZ call lacks governed scope: {token}")


def validate_interval_conditionality(intervals_text: str | None = None) -> None:
    intervals = intervals_text if intervals_text is not None else _read(INTERVALS)
    for token in (
        "rhat > thresholds.r_hat_max_threshold",
        "ess < thresholds.ess_min_threshold",
        "divergences > thresholds.divergence_count_threshold",
        'reason="bad_rhat"',
        'reason="low_ess"',
        'reason="divergence"',
        'reason="nonfinite_diagnostic"',
        'reason="interval_payload_too_large"',
        'credible_interval_status="available"',
        "hdi_lower=None",
        "hdi_upper=None",
    ):
        _require(token in intervals, f"P7 interval conditionality missing: {token}")


def validate_result_contract(result_contract_text: str | None = None) -> None:
    result_contract = (
        result_contract_text if result_contract_text is not None else _read(RESULT_CONTRACT)
    )
    for token in (
        "MAX_RESULT_SUMMARY_BYTES",
        "allow_nan=False",
        "posterior_samples",
        "posterior_array",
        "posterior_draws",
        "inference_data",
        "inference_data_blob",
        "hdi_values",
        "netcdf",
        "zarr",
        "non-finite number",
    ):
        _require(token in result_contract, f"P7 bounded result contract missing: {token}")


def validate_no_trace_artifacts() -> None:
    combined = "\n".join(
        _read(path)
        for path in (
            DIAGNOSTICS,
            INTERVALS,
            RESULT_CONTRACT,
            SAMPLER_CHILD,
            FIT_EXECUTION,
        )
    )
    for token in (
        ".to_netcdf(",
        ".to_zarr(",
        "az.to_netcdf",
        "InferenceData.to_netcdf",
        "posterior_array",
        "posterior_draws",
    ):
        if token in {"posterior_array", "posterior_draws"}:
            _require(token in _read(RESULT_CONTRACT), f"result contract must reject {token}")
        else:
            _require(token not in combined, f"P7 path writes ungoverned trace artifact: {token}")


def validate_persistence_migration(migration_text: str | None = None) -> None:
    migration = migration_text if migration_text is not None else _read(P7_MIGRATION)
    for token in (
        "diagnostic_status",
        "diagnostic_failure_reason",
        "diagnostic_policy_version",
        "diagnostic_target_filter_version",
        "interval_policy_version",
        "diagnostics_computed_at",
        "hdi_lower",
        "hdi_upper",
        "interval_shape jsonb",
        "interval_element_count",
        "interval_summary_bytes",
        "credible_interval_status <> 'available'",
        "diagnostic_status = 'passed'",
        "fallback_applied = false",
        "r_hat_max <= 1.01",
        "ess_min >= 400",
        "divergence_count = 0",
    ):
        _require(token in migration, f"P7 migration missing: {token}")


def validate_ci_and_governance(
    workflow_text: str | None = None,
    required_status_text: str | None = None,
) -> None:
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    required_status = (
        required_status_text
        if required_status_text is not None
        else _read(REQUIRED_STATUS_CONTRACT)
    )
    makefile = _read(MAKEFILE)
    registry = _read(ENFORCER_REGISTRY)
    subsumption = _read(SUBSUMPTION_MATRIX)
    topology = _read(TOPOLOGY_MAP)
    for token in (
        "validate-b24-p7-diagnostics",
        "B2.4-P7 Diagnostic Semantics Proof",
        "test_b24_p7_diagnostic_semantics.py",
        "test_b24_p7_postgres_runtime.py",
        "requirements-bayesian.txt",
        "SKELDIR_B24_P7_REQUIRE_DB_PROOFS",
        "scripts/ci/validate_b24_p7_diagnostics.py --negative-control",
    ):
        _require(token in workflow, f"P7 workflow wiring missing: {token}")
    _require("validate-b24-p7-diagnostics" in makefile, "Makefile missing P7 validator target")
    for text, name in (
        (registry, "enforcer registry"),
        (subsumption, "gate subsumption matrix"),
        (topology, "CI topology map"),
    ):
        _require("validate-b24-p7-diagnostics" in text, f"{name} missing P7 gate")
        _require("B2.4-P7 Diagnostic Semantics Proof" in text, f"{name} missing P7 job")
    _require(
        '"B2.4-P7 Diagnostic Semantics Proof"' in required_status,
        "required-status contract missing P7 proof context",
    )


def validate_tests(tests_text: str | None = None) -> None:
    tests = tests_text if tests_text is not None else _read(P7_TESTS)
    db_tests = _read(P7_DB_TESTS)
    for token in (
        "test_b24_p7_bad_rhat_blocks_interval",
        "test_b24_p7_low_ess_blocks_interval",
        "test_b24_p7_divergence_blocks_interval",
        "test_b24_p7_positive_interval_requires_all_governed_conditions",
        "test_b24_p7_nonfinite_governed_diagnostics_cannot_pass",
        "test_b24_p7_interval_payload_bounds_are_enforced",
        "test_b24_p7_sampled_unvalidated_alone_is_not_interval_valid",
        "test_b24_p7_diagnostic_stage_timeout_is_classified",
        "test_b24_p7_oversized_scope_fails_before_arviz_diagnostic_calls",
        "test_b24_p7_non_target_deterministic_nan_does_not_poison_governed_target",
        "test_b24_p7_arviz_calls_are_child_scoped_and_governed",
        "test_b24_p7_migration_contains_interval_conditionality_constraints",
    ):
        _require(token in tests, f"P7 proof test missing: {token}")
    for token in (
        "test_b24_p7_db_rejects_available_interval_without_passed_diagnostics",
        "test_b24_p7_db_accepts_available_interval_only_with_passed_diagnostics",
        "test_b24_p7_db_persists_representative_failure_states_unavailable",
        "SKELDIR_B24_P7_REQUIRE_DB_PROOFS",
        "credible_interval_status=\"available\"",
        "diagnostic_status=\"passed\"",
    ):
        _require(token in db_tests, f"P7 DB proof test missing: {token}")


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_policy_authority()
    validate_child_arviz_boundary()
    validate_governed_arviz_calls()
    validate_interval_conditionality()
    validate_result_contract()
    validate_no_trace_artifacts()
    validate_persistence_migration()
    validate_ci_and_governance()
    validate_tests()


def run_negative_controls() -> None:
    controls = (
        (
            "missing_rhat_threshold",
            lambda: validate_policy_authority(
                diagnostics_text=_read(DIAGNOSTICS).replace(
                    "r_hat_max_threshold: float = 1.01",
                    "r_hat_max_threshold: float = 1.2",
                )
            ),
            "r_hat",
        ),
        (
            "parent_imports_arviz",
            lambda: validate_child_arviz_boundary(
                fit_execution_text="import arviz\n" + _read(FIT_EXECUTION)
            ),
            "parent imports",
        ),
        (
            "unscoped_arviz",
            lambda: validate_governed_arviz_calls(
                diagnostics_text=_read(DIAGNOSTICS).replace(
                    "var_names=list(policy.diagnostic_target_var_names)",
                    "var_names=None",
                )
            ),
            "governed scope",
        ),
        (
            "bad_rhat_not_blocked",
            lambda: validate_interval_conditionality(
                intervals_text=_read(INTERVALS).replace(
                    "rhat > thresholds.r_hat_max_threshold",
                    "False",
                )
            ),
            "rhat",
        ),
        (
            "missing_db_condition",
            lambda: validate_persistence_migration(
                migration_text=_read(P7_MIGRATION).replace(
                    "credible_interval_status <> 'available'",
                    "credible_interval_status = 'available'",
                )
            ),
            "migration",
        ),
        (
            "missing_required_status",
            lambda: validate_ci_and_governance(
                required_status_text=_read(REQUIRED_STATUS_CONTRACT).replace(
                    '"B2.4-P7 Diagnostic Semantics Proof"',
                    '"B2.4-P7 Missing Proof"',
                )
            ),
            "required-status",
        ),
        (
            "missing_db_test",
            lambda: validate_tests(
                tests_text=_read(P7_TESTS).replace(
                    "test_b24_p7_non_target_deterministic_nan_does_not_poison_governed_target",
                    "missing_non_target_nan_test",
                )
            ),
            "proof test",
        ),
    )
    for name, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{name} failed for wrong reason: {exc}",
            )
        else:
            raise ValidationError(f"negative control did not fail: {name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P7_DIAGNOSTIC_SEMANTICS_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P7_DIAGNOSTIC_SEMANTICS_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
