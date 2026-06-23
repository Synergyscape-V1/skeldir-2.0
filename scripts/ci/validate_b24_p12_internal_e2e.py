#!/usr/bin/env python3
"""Validate B2.4-P12 internal E2E proof harness wiring and boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend/tests/test_b24_p12_internal_e2e.py"
HARNESS = ROOT / "backend/app/bayesian/e2e_harness.py"
CONFIDENCE_METADATA = ROOT / "backend/app/bayesian/confidence_metadata.py"
WORKFLOW = ROOT / ".github/workflows/b2_4-gate-dry-run.yml"
MAKEFILE = ROOT / "Makefile"
REGISTRY = ROOT / "docs/ci/enforcer_registry.yaml"
SUBSUMPTION = ROOT / "docs/ci/gate_subsumption_matrix.yaml"
MANIFEST = ROOT / "docs/ci/b24_p11_execution_manifest.yaml"
REQUIRED_STATUS = ROOT / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
EVIDENCE_PACK = ROOT / "docs/forensics/B2.4-P12 Remediation Evidence Pack .md"

P12_CONTEXT = "B2.4-P12 Internal E2E Proof Harness"
P12_MAKE_TARGET = "validate-b24-p12-internal-e2e"
P12_VALIDATOR_COMMAND = "python scripts/ci/validate_b24_p12_internal_e2e.py --negative-control"
P12_NON_OVERCLAIM = (
    "P12 proves internal/local/CI topology substrate composition and does not "
    "claim production-topology trust closure."
)
REQUIRED_TEST_CASES = (
    "test_b24_p12_committed_visibility_and_uncommitted_negative_control",
    "test_b24_p12_terminal_waiter_is_state_driven_and_diagnostic",
    "test_b24_p12_async_coordination_uses_no_arbitrary_sleep",
    "test_b24_p12_positive_projection_payload_is_backend_owned_and_sealed",
    "test_b24_p12_cold_start_projection_is_reason_coded_without_sampling",
    "test_b24_p12_diagnostic_failures_block_intervals",
    "test_b24_p12_resource_and_duplicate_burst_controls_are_pre_worker",
    "test_b24_p12_artifact_hash_corruption_and_pruning_degrade_auditably",
    "test_b24_p12_projection_read_only_and_missing_fit_safe",
    "test_b24_p12_source_snapshot_drift_blocks_current_confidence",
    "test_b24_p12_sequential_tenant_artifact_and_projection_isolation",
    "test_b24_p12_boundary_scans_no_public_route_llm_action_or_overclaim",
    "test_b24_p12_validator_negative_controls",
)


class ValidationError(RuntimeError):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise ValidationError(f"missing required file: {path.relative_to(ROOT).as_posix()}")
    return path.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(_read(path))
    except yaml.YAMLError as exc:
        raise ValidationError(f"invalid YAML: {path.relative_to(ROOT).as_posix()}: {exc}") from exc


def validate_harness(tests_text: str | None = None, harness_text: str | None = None) -> None:
    tests = tests_text if tests_text is not None else _read(TESTS)
    harness = harness_text if harness_text is not None else _read(HARNESS)
    for case in REQUIRED_TEST_CASES:
        _require(case in tests, f"P12 test case missing: {case}")
    for token in (
        "wait_for_fit_terminal_state_sync",
        "P12_TERMINAL_FIT_STATUSES",
        "time.monotonic()",
        "last_observed",
        "canonical_projection_json",
        "sort_keys=True",
        "allow_nan=False",
    ):
        _require(token in harness, f"P12 harness missing token: {token}")
    _require("time.sleep(" not in tests, "P12 tests use arbitrary sleep")
    _require("time.sleep(" not in harness, "P12 harness uses arbitrary sleep")
    _require("Event().wait(" in harness, "P12 waiter lacks bounded wait primitive")
    _require("source_snapshot_mismatch=True" in tests, "P12 drift fixture missing")
    _require("<|system|>" in tests, "P12 prompt-control negative fixture missing")


def validate_projection_schema(metadata_text: str | None = None) -> None:
    metadata = metadata_text if metadata_text is not None else _read(CONFIDENCE_METADATA)
    for token in (
        "_PROMPT_CONTROL_TOKENS",
        "_validate_safe_code",
        "_validate_safe_mapping",
        "field_validator",
        "contains prompt-control syntax",
        "bounded code value",
    ):
        _require(token in metadata, f"P12 sealed payload schema missing: {token}")


def validate_ci_wiring(
    workflow_text: str | None = None,
    makefile_text: str | None = None,
    registry_text: str | None = None,
    required_status_text: str | None = None,
    evidence_text: str | None = None,
) -> None:
    workflow = workflow_text if workflow_text is not None else _read(WORKFLOW)
    makefile = makefile_text if makefile_text is not None else _read(MAKEFILE)
    registry = registry_text if registry_text is not None else _read(REGISTRY)
    required_status = required_status_text if required_status_text is not None else _read(REQUIRED_STATUS)
    evidence = evidence_text if evidence_text is not None else _read(EVIDENCE_PACK)

    for token in (
        P12_CONTEXT,
        "SKELDIR_B24_P12_REQUIRE_DB_PROOFS: \"1\"",
        "pytest backend/tests/test_b24_p12_internal_e2e.py",
        "--junitxml=artifacts/junit/b24_p12_internal_e2e.xml",
        "validate_b24_p12_internal_e2e.py --negative-control",
        "b24-p11-junit-p12-internal-e2e",
    ):
        _require(token in workflow, f"P12 workflow wiring missing: {token}")
    _require(
        "b2-4-p12-internal-e2e-proof" in workflow
        and "b2-4-p12-internal-e2e-proof" in workflow.split("b2-4-p11-ci-gates-and-negative-control-harness", 1)[1],
        "P11 job must need P12 before artifact adjudication",
    )
    _require(P12_MAKE_TARGET in makefile, "P12 Makefile target missing")
    _require(P12_VALIDATOR_COMMAND in makefile, "P12 Makefile validator command missing")
    _require("id: validate-b24-p12-internal-e2e" in registry, "P12 registry entry missing")
    _require(P12_VALIDATOR_COMMAND in registry, "P12 registry command missing")
    _require(P12_CONTEXT in required_status, "P12 required status missing")
    _require(P12_NON_OVERCLAIM in evidence, "P12 evidence pack missing non-overclaim boundary")
    for token in (
        "transaction visibility proof",
        "uncommitted visibility negative control",
        "worker/subprocess boundary proof",
        "sealed payload result",
        "P1-P11 non-regression proof",
        "exit-gate matrix",
    ):
        _require(token in evidence, f"P12 evidence pack missing section token: {token}")


def validate_manifest(manifest_text: str | None = None) -> None:
    if manifest_text is None:
        rows = _load_yaml(MANIFEST)
    else:
        rows = yaml.safe_load(manifest_text)
    _require(isinstance(rows, list), "P11 execution manifest must be a list")
    p12_rows = [row for row in rows if isinstance(row, dict) and row.get("phase_id") == "B2.4-P12"]
    _require(len(p12_rows) == 1, "P12 execution manifest row must exist exactly once")
    row = p12_rows[0]
    _require(row.get("workflow_job") == P12_CONTEXT, "P12 manifest workflow job mismatch")
    _require(row.get("required_status") == P12_CONTEXT, "P12 manifest required status mismatch")
    _require(row.get("execution_required") is True, "P12 manifest must require execution")
    _require(not row.get("allowed_skips"), "P12 manifest cannot allow skips")
    _require(not row.get("allowed_xfails"), "P12 manifest cannot allow xfails")
    expected = "\n".join(str(item) for item in row.get("expected_test_cases", []))
    for case in REQUIRED_TEST_CASES:
        _require(case in expected, f"P12 manifest missing case: {case}")
    fragments = "\n".join(str(item) for item in row.get("required_command_fragments", []))
    _require("pytest backend/tests/test_b24_p12_internal_e2e.py" in fragments, "P12 manifest missing pytest command")
    _require("validate_b24_p12_internal_e2e.py --negative-control" in fragments, "P12 manifest missing validator command")


def validate_subsumption(subsumption_text: str | None = None) -> None:
    text = subsumption_text if subsumption_text is not None else _read(SUBSUMPTION)
    for token in (
        "gate_id: validate-b24-p12-internal-e2e",
        "owning_phase: B2.4-P12",
        "local_reproduction_command: make validate-b24-p12-internal-e2e",
    ):
        _require(token in text, f"P12 subsumption matrix missing: {token}")


def validate_all() -> None:
    validate_harness()
    validate_projection_schema()
    validate_ci_wiring()
    validate_manifest()
    validate_subsumption()


def _expect_failure(name: str, runner: Any, expected: str) -> None:
    try:
        runner()
    except ValidationError as exc:
        _require(expected.lower() in str(exc).lower(), f"{name} failed for wrong reason: {exc}")
    else:
        raise ValidationError(f"negative control did not fail: {name}")


def run_negative_controls() -> None:
    tests = _read(TESTS)
    harness = _read(HARNESS)
    metadata = _read(CONFIDENCE_METADATA)
    workflow = _read(WORKFLOW)
    makefile = _read(MAKEFILE)
    registry = _read(REGISTRY)
    required_status = _read(REQUIRED_STATUS)
    evidence = _read(EVIDENCE_PACK)
    manifest = _read(MANIFEST)
    subsumption = _read(SUBSUMPTION)

    _expect_failure(
        "committed_visibility_case_removed",
        lambda: validate_harness(tests_text=tests.replace("test_b24_p12_committed_visibility_and_uncommitted_negative_control", "removed")),
        "test case",
    )
    _expect_failure(
        "sleep_added",
        lambda: validate_harness(tests_text=tests + "\ntime.sleep(1)\n"),
        "sleep",
    )
    _expect_failure(
        "monotonic_removed",
        lambda: validate_harness(harness_text=harness.replace("time.monotonic()", "time.time()")),
        "monotonic",
    )
    _expect_failure(
        "prompt_control_validator_removed",
        lambda: validate_projection_schema(metadata_text=metadata.replace("_PROMPT_CONTROL_TOKENS", "PROMPT_CONTROL_REMOVED")),
        "prompt",
    )
    _expect_failure(
        "workflow_job_removed",
        lambda: validate_ci_wiring(workflow_text=workflow.replace(P12_CONTEXT, "B2.4-P12 Missing")),
        "workflow",
    )
    _expect_failure(
        "make_target_removed",
        lambda: validate_ci_wiring(makefile_text=makefile.replace(P12_MAKE_TARGET, "validate-b24-p12-removed")),
        "Makefile",
    )
    _expect_failure(
        "registry_removed",
        lambda: validate_ci_wiring(registry_text=registry.replace("id: validate-b24-p12-internal-e2e", "id: validate-b24-p12-removed")),
        "registry",
    )
    _expect_failure(
        "required_status_removed",
        lambda: validate_ci_wiring(required_status_text=required_status.replace(P12_CONTEXT, "B2.4-P12 Missing")),
        "required status",
    )
    _expect_failure(
        "evidence_overclaim",
        lambda: validate_ci_wiring(evidence_text=evidence.replace(P12_NON_OVERCLAIM, "P12 proves production topology trust closure.")),
        "non-overclaim",
    )
    _expect_failure(
        "manifest_case_removed",
        lambda: validate_manifest(manifest_text=manifest.replace("test_b24_p12_source_snapshot_drift_blocks_current_confidence", "test_removed")),
        "manifest missing case",
    )
    _expect_failure(
        "subsumption_removed",
        lambda: validate_subsumption(subsumption_text=subsumption.replace("gate_id: validate-b24-p12-internal-e2e", "gate_id: removed")),
        "subsumption",
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
        print(f"B24_P12_INTERNAL_E2E_VALIDATION_FAIL: {exc}")
        return 1
    print("B24_P12_INTERNAL_E2E_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
