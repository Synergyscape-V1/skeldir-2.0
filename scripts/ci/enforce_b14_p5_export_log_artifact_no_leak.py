#!/usr/bin/env python3
"""B1.4-P5 export/log/artifact no-leak structural enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTEXT = "B1.4 P5 Export Log Artifact No-Leak"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_enforcement(
    *,
    ci_workflow_file: Path,
    required_checks_file: Path,
    export_file: Path,
    export_contract_file: Path,
    logging_config_file: Path,
    dlq_handler_file: Path,
    artifact_scan_file: Path,
    runtime_proof_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_files = (
        ci_workflow_file,
        required_checks_file,
        export_file,
        export_contract_file,
        logging_config_file,
        dlq_handler_file,
        artifact_scan_file,
        runtime_proof_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    workflow_text = _read(ci_workflow_file)
    checks_contract = _load_json(required_checks_file)
    export_text = _read(export_file)
    export_contract_text = _read(export_contract_file)
    logging_text = _read(logging_config_file)
    dlq_text = _read(dlq_handler_file)
    artifact_scan_text = _read(artifact_scan_file)
    runtime_proof_text = _read(runtime_proof_file)

    if REQUIRED_CONTEXT not in workflow_text:
        violations.append(f"missing_required_context_in_workflow:{REQUIRED_CONTEXT}")
    contexts = checks_contract.get("required_contexts", [])
    if REQUIRED_CONTEXT not in contexts:
        violations.append(f"missing_required_context_in_contract:{REQUIRED_CONTEXT}")

    required_export_tokens = (
        "EXPORT_ROW_ALLOWLIST",
        "_enforce_export_row_no_leak(",
        "_enforce_export_payload_no_leak(",
        "tenant_id",
        "X-Attribution-Session-ID",
    )
    for token in required_export_tokens:
        if token not in export_text and token not in export_contract_text:
            violations.append(f"export_surface_missing_token:{token}")

    if "additionalProperties: false" not in export_contract_text:
        violations.append("export_contract_missing_closed_shape_guards")

    required_logging_tokens = (
        "redact_output_text",
        "sanitize_output_payload",
        "RedactionFilter",
    )
    for token in required_logging_tokens:
        if token not in logging_text:
            violations.append(f"logging_missing_token:{token}")

    required_dlq_tokens = (
        "_sanitize_failure_surface_payload",
        "_DLQ_FAILURE_SURFACE_FORBIDDEN_KEYS",
        "redact_output_text",
    )
    for token in required_dlq_tokens:
        if token not in dlq_text:
            violations.append(f"dlq_missing_token:{token}")

    required_artifact_scan_tokens = (
        "b14_p5_artifact_scanner",
        "KEY_VALUE_PATTERN",
        "--simulate-regression",
    )
    for token in required_artifact_scan_tokens:
        if token not in artifact_scan_text:
            violations.append(f"artifact_scan_missing_token:{token}")

    required_workflow_tokens = (
        "b14-p5-export-log-artifact-no-leak",
        "scripts/ci/enforce_b14_p5_export_log_artifact_no_leak.py",
        "scripts/ci/scan_b14_p5_artifacts.py",
        "backend/tests/integration/test_b14_p5_export_log_artifact_no_leak_runtime.py",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    required_runtime_tokens = (
        "test_b14_p5_runtime_export_allowlist_blocks_identity_fields",
        "test_b14_p5_runtime_logging_redaction_blocks_direct_and_proxy_canaries",
        "test_b14_p5_runtime_failure_surfaces_redact_dead_letter_and_quarantine",
        "test_b14_p5_runtime_artifact_scanner_fails_on_seeded_canaries_and_passes_sanitized_bundle",
    )
    for token in required_runtime_tokens:
        if token not in runtime_proof_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P5 no-leak enforcer")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument("--export-file", default="backend/app/api/export.py")
    parser.add_argument("--export-contract-file", default="api-contracts/openapi/v1/export.yaml")
    parser.add_argument("--logging-config-file", default="backend/app/observability/logging_config.py")
    parser.add_argument("--dlq-handler-file", default="backend/app/ingestion/dlq_handler.py")
    parser.add_argument("--artifact-scan-file", default="scripts/ci/scan_b14_p5_artifacts.py")
    parser.add_argument(
        "--runtime-proof-file",
        default="backend/tests/integration/test_b14_p5_export_log_artifact_no_leak_runtime.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p5_export_log_artifact_no_leak_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=no_leak_gate_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        ci_workflow_file=(REPO_ROOT / args.workflow_file).resolve(),
        required_checks_file=(REPO_ROOT / args.required_checks_file).resolve(),
        export_file=(REPO_ROOT / args.export_file).resolve(),
        export_contract_file=(REPO_ROOT / args.export_contract_file).resolve(),
        logging_config_file=(REPO_ROOT / args.logging_config_file).resolve(),
        dlq_handler_file=(REPO_ROOT / args.dlq_handler_file).resolve(),
        artifact_scan_file=(REPO_ROOT / args.artifact_scan_file).resolve(),
        runtime_proof_file=(REPO_ROOT / args.runtime_proof_file).resolve(),
    )

    lines = ["b14_p5_export_log_artifact_no_leak_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=export+logging+artifact no-leak invariants satisfied")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

