#!/usr/bin/env python3
"""Validate B2.4-P6 source-authorized real-fit worker wiring."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
FIT_EXECUTION = BAYESIAN_PACKAGE / "fit_execution.py"
SOURCE_SNAPSHOT = BAYESIAN_PACKAGE / "source_snapshot.py"
SAMPLER_CHILD = BAYESIAN_PACKAGE / "sampler_child.py"
SAMPLER_SUPERVISOR = BAYESIAN_PACKAGE / "sampler_supervisor.py"
P6_TESTS = Path("backend/tests/test_b24_p6_real_fit_worker.py")
P5_TESTS = Path("backend/tests/test_b24_p5_runtime_harness.py")
P6_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202606031200_b24_p6_fit_id_resolution_policy.py"
)
BAYESIAN_REQUIREMENTS = Path("backend/requirements-bayesian.txt")
WORKFLOW = Path(".github/workflows/b2_4-gate-dry-run.yml")
MAKEFILE = Path("Makefile")
ENFORCER_REGISTRY = Path("docs/ci/enforcer_registry.yaml")
SUBSUMPTION_MATRIX = Path("docs/ci/gate_subsumption_matrix.yaml")
TOPOLOGY_MAP = Path("docs/ci/ci_topology_map.md")
REQUIRED_STATUS_CONTRACT = Path(
    "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)

REQUIRED_FILES = {
    FIT_EXECUTION,
    SOURCE_SNAPSHOT,
    SAMPLER_CHILD,
    SAMPLER_SUPERVISOR,
    P6_TESTS,
    P5_TESTS,
    P6_MIGRATION,
    BAYESIAN_REQUIREMENTS,
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


def validate_parent_source_authority(
    fit_execution_text: str | None = None,
    source_snapshot_text: str | None = None,
) -> None:
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    source_snapshot = (
        source_snapshot_text
        if source_snapshot_text is not None
        else _read(SOURCE_SNAPSHOT)
    )
    for forbidden in (
        "_observed_signal_from_hash",
        "int(source_snapshot_hash[:",
        "int(source_snapshot_hash[",
        "source_snapshot_hash[:8]",
        "source_snapshot_hash[8:16]",
    ):
        _require(
            forbidden not in fit_execution,
            f"hash-derived observed input remains: {forbidden}",
        )
        _require(
            forbidden not in source_snapshot,
            f"hash-derived observed input remains: {forbidden}",
        )
    for token in (
        "load_p6_observed_input_from_source_snapshot_sync",
        "P6SourceObservedInput",
        "observed_input.observed_signal",
        "observed_signal_source",
        "source_snapshot_hash = :source_snapshot_hash",
    ):
        _require(
            token in fit_execution, f"P6 parent missing source-observed token: {token}"
        )
    for token in (
        "P6_SOURCE_OBSERVED_SIGNAL_VERSION",
        "run_eligibility_preflight_sync",
        "load_source_window_feature_authority_sync",
        "evaluate_source_snapshot_resource_bounds",
        "_SOURCE_QUERIES.items()",
        "_STREAM_EXECUTION_OPTIONS",
        "SOURCE_STREAM_PARTITION_SIZE",
        "canonical_json_bytes(payload)",
        "verified_hash != source_snapshot_hash",
        "WorkerFallbackReason.SOURCE_SNAPSHOT_MISMATCH",
        "_bounded_signal_from_source_rows",
    ):
        _require(token in source_snapshot, f"P6 source replay missing: {token}")


def validate_fit_id_resolution_policy(
    fit_execution_text: str | None = None,
    migration_text: str | None = None,
) -> None:
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    migration = migration_text if migration_text is not None else _read(P6_MIGRATION)
    _require(
        "set_config('app.b24_fit_resolution_id'" in fit_execution,
        "fit-id-only tenant resolution GUC is not set before identity lookup",
    )
    for token in (
        "ALTER POLICY tenant_isolation_policy_",
        "app.b24_fit_resolution_id",
        "tenant_id = NULLIF(current_setting('app.current_tenant_id'",
        "WITH CHECK",
        "PARTITION_COUNT = 16",
    ):
        _require(token in migration, f"P6 fit-id RLS policy migration missing: {token}")
    with_check_tail = migration.split("FIT_POLICY_WITH_CHECK", 1)[1]
    _require(
        "app.b24_fit_resolution_id" not in with_check_tail.split('"""', 2)[1],
        "fit-id resolution capability must not be a write WITH CHECK condition",
    )


def validate_pymc_child_boundary(
    fit_execution_text: str | None = None,
    sampler_child_text: str | None = None,
) -> None:
    fit_execution = (
        fit_execution_text if fit_execution_text is not None else _read(FIT_EXECUTION)
    )
    child = (
        sampler_child_text if sampler_child_text is not None else _read(SAMPLER_CHILD)
    )
    tree = ast.parse(fit_execution, filename=FIT_EXECUTION.as_posix())
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
    _require("pymc" not in imports, "P6 parent imports PyMC")
    _require("pymc" not in from_imports, "P6 parent imports PyMC")
    _require(
        "app.bayesian.sampler_child" not in from_imports,
        "P6 parent imports child module",
    )
    for token in (
        "with pm.Model() as model:",
        'pm.Normal("observed_signal"',
        "model.compile_logp()",
        "run_single_process_pymc_sample(",
        "compute_convergence_checks=False",
        'emit_stage_marker("sampling_completed"',
        "_write_json_durable(output_path, result)",
    ):
        _require(token in child, f"P6 child physical real-fit proof missing: {token}")


def validate_stream_and_stage_physics() -> None:
    supervisor = _read(SAMPLER_SUPERVISOR)
    child = _read(SAMPLER_CHILD)
    p5_tests = _read(P5_TESTS)
    for token in (
        "stdout_reader",
        "stderr_reader",
        "threading.Thread",
        "stream_capture_limit_bytes",
        "retained_bytes",
        "total_bytes",
        "synthetic_noisy_child_command",
    ):
        _require(
            token in supervisor,
            f"byte-capped concurrent stream reader missing: {token}",
        )
    for token in (
        "emit_stage_marker",
        "os.fsync(handle.fileno())",
        "_fsync_parent_dir(marker)",
        "stage-marker-kill",
    ):
        _require(token in child, f"fsynced child stage marker missing: {token}")
    for token in (
        "test_b24_p6_supervisor_drains_byte_capped_child_streams",
        "160 * 1024",
        "test_b24_p6_stage_markers_are_fsynced_before_sigkill",
    ):
        _require(token in p5_tests, f"P5/P6 physics regression test missing: {token}")


def validate_ci_and_governance() -> None:
    workflow = _read(WORKFLOW)
    makefile = _read(MAKEFILE)
    registry = _read(ENFORCER_REGISTRY)
    subsumption = _read(SUBSUMPTION_MATRIX)
    topology = _read(TOPOLOGY_MAP)
    required_status = _read(REQUIRED_STATUS_CONTRACT)
    for token in (
        "validate-b24-p6-real-fit-worker",
        "B2.4-P6 Real Fit Worker Proof",
        "SKELDIR_B24_P6_REQUIRE_REAL_FIT_PROOF",
        "requirements-bayesian.txt",
        "test_b24_p6_real_fit_worker.py",
        "scripts/ci/validate_b24_p6_real_fit_worker.py --negative-control",
    ):
        _require(token in workflow, f"P6 workflow wiring missing: {token}")
    _require(
        "validate-b24-p6-real-fit-worker" in makefile,
        "Makefile missing P6 validator target",
    )
    for text, name in (
        (registry, "enforcer registry"),
        (subsumption, "gate subsumption matrix"),
        (topology, "CI topology map"),
    ):
        _require("validate-b24-p6-real-fit-worker" in text, f"{name} missing P6 gate")
        _require(
            "B2.4-P6 Real Fit Worker Proof" in text, f"{name} missing P6 required job"
        )
    _require(
        '"B2.4-P6 Real Fit Worker Proof"' in required_status,
        "required-status contract missing P6 real-fit proof context",
    )


def validate_tests() -> None:
    tests = _read(P6_TESTS)
    for token in (
        "test_b24_p6_hash_derived_observed_signal_is_erased",
        "test_b24_p6_observed_signal_is_source_snapshot_replay_derived",
        "test_b24_p6_fit_id_only_resolution_is_explicit_rls_capability",
        "test_b24_p6_real_fit_uses_frozen_source_snapshot_authority",
        "test_b24_p6_source_snapshot_mismatch_fails_before_sampler",
        "compute_source_snapshot_hash",
        "upsert_source_window_feature_authority",
        "execute_fit_intent_sync",
        "pytest.mark.integration",
        "SKELDIR_B24_P6_REQUIRE_REAL_FIT_PROOF",
    ):
        _require(token in tests, f"P6 proof test missing: {token}")


def validate_all() -> None:
    for path in REQUIRED_FILES:
        _read(path)
    validate_parent_source_authority()
    validate_fit_id_resolution_policy()
    validate_pymc_child_boundary()
    validate_stream_and_stage_physics()
    validate_ci_and_governance()
    validate_tests()


def run_negative_controls() -> None:
    controls = (
        (
            "hash_observed_helper",
            lambda: validate_parent_source_authority(
                fit_execution_text=_read(FIT_EXECUTION)
                + "\ndef _observed_signal_from_hash(source_snapshot_hash): pass\n"
            ),
            "hash-derived",
        ),
        (
            "missing_source_loader",
            lambda: validate_parent_source_authority(
                fit_execution_text=_read(FIT_EXECUTION).replace(
                    "load_p6_observed_input_from_source_snapshot_sync",
                    "load_hash_observed_input",
                )
            ),
            "source-observed",
        ),
        (
            "missing_p4_bounds",
            lambda: validate_parent_source_authority(
                source_snapshot_text=_read(SOURCE_SNAPSHOT).replace(
                    "evaluate_source_snapshot_resource_bounds",
                    "skip_source_snapshot_resource_bounds",
                )
            ),
            "resource",
        ),
        (
            "missing_fit_resolution_guc",
            lambda: validate_fit_id_resolution_policy(
                fit_execution_text=_read(FIT_EXECUTION).replace(
                    "app.b24_fit_resolution_id",
                    "app.b24_missing_resolution",
                )
            ),
            "resolution",
        ),
        (
            "parent_imports_pymc",
            lambda: validate_pymc_child_boundary(
                fit_execution_text="import pymc\n" + _read(FIT_EXECUTION)
            ),
            "parent imports",
        ),
        (
            "missing_required_status",
            lambda: validate_ci_and_governance_text(
                required_status_text=_read(REQUIRED_STATUS_CONTRACT).replace(
                    '"B2.4-P6 Real Fit Worker Proof"', '"B2.4-P6 Missing Proof"'
                )
            ),
            "required-status",
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


def validate_ci_and_governance_text(required_status_text: str) -> None:
    _require(
        '"B2.4-P6 Real Fit Worker Proof"' in required_status_text,
        "required-status contract missing P6 real-fit proof context",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    try:
        validate_all()
        if args.negative_control:
            run_negative_controls()
    except ValidationError as exc:
        print(f"B24_P6_REAL_FIT_WORKER_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P6_REAL_FIT_WORKER_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
