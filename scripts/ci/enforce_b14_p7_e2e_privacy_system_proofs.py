#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


REQUIRED_CONTEXT = "B1.4 P7 E2E Privacy System Proofs"
REQUIRED_TEST_NAMES = (
    "test_b14_p7_gate_passes_repo_state",
    "test_b14_p7_composed_runtime_privacy_contract_holds_end_to_end",
    "test_b14_p7_negative_controls_and_tenant_fail_closed_guards",
)
REQUIRED_RUNTIME_TEST_NAMES = (
    "test_b14_p7_composed_runtime_privacy_contract_holds_end_to_end",
    "test_b14_p7_negative_controls_and_tenant_fail_closed_guards",
)
REQUIRED_RUNTIME_ARTIFACTS = (
    "p7_composed_runtime_report.json",
    "p7_negative_controls_report.json",
    "p7_branch_protection_evidence.json",
    "p7_artifact_scan_report.json",
    "p7_legal_signoff.json",
    "p7_runtime_logs.txt",
)
FORBIDDEN_ARTIFACT_PATTERNS = (
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}\b"),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.4-P7 final E2E privacy system proof enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--branch-protection-integrity-contract",
        default="contracts-internal/governance/main_branch_protection_integrity.main.json",
    )
    parser.add_argument(
        "--p7-contract",
        default="contracts-internal/governance/b14_p7_e2e_privacy_system_proofs.main.json",
    )
    parser.add_argument(
        "--tests-file",
        default="backend/tests/integration/test_b14_p7_e2e_privacy_system_proofs.py",
    )
    parser.add_argument("--require-runtime-execution", action="store_true")
    parser.add_argument("--require-live-branch-protection", action="store_true")
    parser.add_argument("--junit-xml", default=None)
    parser.add_argument("--artifacts-dir", default="artifacts/b14_p7")
    parser.add_argument("--simulate-regression", action="store_true")
    return parser.parse_args()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_junit_cases(junit_path: Path) -> dict[str, str]:
    root = ET.fromstring(junit_path.read_text(encoding="utf-8"))
    outcomes: dict[str, str] = {}
    for case in root.iter("testcase"):
        name = case.attrib.get("name", "").strip()
        if not name:
            continue
        if case.find("failure") is not None:
            outcomes[name] = "failed"
        elif case.find("error") is not None:
            outcomes[name] = "error"
        elif case.find("skipped") is not None:
            outcomes[name] = "skipped"
        else:
            outcomes[name] = "passed"
    return outcomes


def _resolve_case_outcome(outcomes: dict[str, str], test_name: str) -> str | None:
    if test_name in outcomes:
        return outcomes[test_name]
    for name, outcome in outcomes.items():
        if name.startswith(f"{test_name}["):
            return outcome
    return None


def _check_required_context(
    *,
    workflow_text: str,
    required_checks: dict,
    branch_integrity: dict,
    p7_contract: dict,
    errors: list[str],
) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")

    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
    elif REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")

    required_checks_hardware = required_checks.get("hardware_enforcement")
    if not isinstance(required_checks_hardware, dict):
        errors.append("required checks contract missing hardware_enforcement object")
    else:
        if str(required_checks_hardware.get("status", "")).strip().lower() != "enforced":
            errors.append("required checks contract hardware_enforcement.status must be enforced")
        deferred = required_checks_hardware.get("deferred_contexts")
        if isinstance(deferred, list) and deferred:
            errors.append("required checks contract deferred_contexts must be empty in P7")

    if bool(branch_integrity.get("require_live_on_main", False)) is not True:
        errors.append("branch protection integrity contract require_live_on_main must be true in P7")
    branch_hardware = branch_integrity.get("hardware_enforcement")
    if not isinstance(branch_hardware, dict):
        errors.append("branch protection integrity contract missing hardware_enforcement object")
    elif str(branch_hardware.get("status", "")).strip().lower() != "enforced":
        errors.append("branch protection integrity hardware_enforcement.status must be enforced")

    p7_required = p7_contract.get("required_context")
    if str(p7_required).strip() != REQUIRED_CONTEXT:
        errors.append(
            f"p7 contract required_context mismatch: expected={REQUIRED_CONTEXT} observed={p7_required}"
        )


def _check_workflow_surface(workflow_text: str, errors: list[str]) -> None:
    required_fragments = (
        "name: B1.4 P7 E2E Privacy System Proofs",
        "python scripts/ci/enforce_b14_p7_e2e_privacy_system_proofs.py",
        "pytest backend/tests/integration/test_b14_p7_e2e_privacy_system_proofs.py -q -rs --junitxml=artifacts/b14_p7/junit.runtime.xml",
        "python scripts/ci/capture_b14_p7_branch_protection_evidence.py",
        "python scripts/ci/scan_b14_p7_artifacts.py --simulate-regression",
        "name: b14-p7-runtime-artifacts",
        "path: artifacts/b14_p7",
        "if-no-files-found: error",
    )
    for fragment in required_fragments:
        if fragment not in workflow_text:
            errors.append(f"workflow missing P7 closure fragment: {fragment}")


def _check_tests_surface(test_text: str, p7_contract: dict, errors: list[str]) -> None:
    for test_name in REQUIRED_TEST_NAMES:
        if test_name not in test_text:
            errors.append(f"P7 proof suite missing required test: {test_name}")

    required_fragments = (
        "_write_artifact(\"p7_composed_runtime_report.json\"",
        "_write_artifact(\"p7_negative_controls_report.json\"",
        "_write_log_artifact(",
        "authority_envelope header is required",
    )
    for fragment in required_fragments:
        if fragment not in test_text:
            errors.append(f"P7 proof suite missing closure fragment: {fragment}")

    invariants = p7_contract.get("terminal_invariants")
    if not isinstance(invariants, list) or len(invariants) != 10:
        errors.append("p7 contract terminal_invariants must enumerate 10 closure invariants")


def _check_artifact_secrecy(artifacts_dir: Path, errors: list[str]) -> None:
    for artifact in REQUIRED_RUNTIME_ARTIFACTS:
        path = artifacts_dir / artifact
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_ARTIFACT_PATTERNS:
            if pattern.search(text):
                errors.append(
                    f"P7 artifact appears to leak sensitive material ({pattern.pattern}): {path}"
                )


def _validate_composed_payload(payload: dict, errors: list[str]) -> None:
    required_true_flags = (
        "pii_stripped_before_storage",
        "session_expiry_24h_enforced",
        "cross_session_reconstruction_blocked",
        "attribution_session_scoped",
        "raw_events_older_than_90d_expired",
        "deletion_deterministic",
        "export_privacy_safe",
        "log_redaction_effective",
        "artifact_no_leak_scan_passed",
        "tenant_isolation_fail_closed",
        "prior_phase_preservation_p0_to_p6",
    )
    for flag in required_true_flags:
        if payload.get(flag) is not True:
            errors.append(f"p7 composed runtime report missing {flag}=true")


def _validate_negative_payload(payload: dict, errors: list[str]) -> None:
    required_true_flags = (
        "bad_ingress_payload_blocked",
        "cross_session_linkage_attempt_blocked",
        "stale_event_fixture_expired",
        "deletion_edge_case_handled",
        "export_leakage_attempt_blocked",
        "artifact_canary_detected_in_negative_control",
        "tenantless_worker_fail_closed",
        "cross_tenant_access_blocked",
    )
    for flag in required_true_flags:
        if payload.get(flag) is not True:
            errors.append(f"p7 negative controls report missing {flag}=true")


def _validate_legal_payload(payload: dict, errors: list[str]) -> None:
    if str(payload.get("phase", "")).strip() != "B1.4-P7":
        errors.append("p7 legal sign-off artifact missing phase=B1.4-P7")
    if str(payload.get("approval_status", "")).strip().lower() != "approved":
        errors.append("p7 legal sign-off artifact approval_status must be approved")
    approved_by = str(payload.get("approved_by", "")).strip()
    approved_at = str(payload.get("approved_at_utc", "")).strip()
    if not approved_by:
        errors.append("p7 legal sign-off artifact missing approved_by")
    if not approved_at:
        errors.append("p7 legal sign-off artifact missing approved_at_utc")


def _validate_branch_protection_payload(
    payload: dict,
    *,
    require_live: bool,
    errors: list[str],
) -> None:
    authority_mode = str(payload.get("authority_mode") or "").strip()
    if authority_mode == "live_branch_protection_api":
        if payload.get("required_context_present_in_live") is not True:
            errors.append("p7 branch-protection evidence missing required_context_present_in_live=true")
        if payload.get("required_context_present_in_contract") is not True:
            errors.append("p7 branch-protection evidence missing required_context_present_in_contract=true")
        if payload.get("required_context_present_in_workflow") is not True:
            errors.append("p7 branch-protection evidence missing required_context_present_in_workflow=true")
        if payload.get("branch_integrity_require_live_on_main") is not True:
            errors.append("p7 branch-protection evidence missing branch_integrity_require_live_on_main=true")
        if payload.get("live_strict") is not True:
            errors.append("p7 branch-protection evidence strict mode must be true")
        missing_b14 = payload.get("live_missing_b14_contexts")
        if not isinstance(missing_b14, list):
            errors.append("p7 branch-protection evidence missing live_missing_b14_contexts list")
        elif missing_b14:
            errors.append(f"p7 branch-protection evidence missing live B1.4 contexts: {missing_b14}")
    elif authority_mode == "fallback_workflow_contract_only":
        if require_live:
            errors.append("p7 branch-protection evidence used fallback mode while live mode is required")
        if payload.get("required_context_present_in_contract") is not True:
            errors.append("p7 branch-protection fallback evidence missing required context in contract")
        if payload.get("required_context_present_in_workflow") is not True:
            errors.append("p7 branch-protection fallback evidence missing required context in workflow")
    else:
        errors.append(f"p7 branch-protection evidence has unknown authority_mode: {authority_mode}")


def _validate_artifact_scan_payload(payload: dict, errors: list[str]) -> None:
    if str(payload.get("result", "")).strip().upper() != "PASS":
        errors.append("p7 artifact scan report result must be PASS")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("p7 artifact scan report findings must be a list")
    elif findings:
        errors.append("p7 artifact scan report findings must be empty")


def _check_runtime_execution(
    *,
    junit_path: Path,
    artifacts_dir: Path,
    require_live_branch_protection: bool,
    errors: list[str],
) -> None:
    if not junit_path.exists():
        errors.append(f"missing junit xml for runtime verification: {junit_path}")
        return

    try:
        outcomes = _load_junit_cases(junit_path)
    except Exception as exc:
        errors.append(f"unable to parse junit xml {junit_path}: {exc}")
        return

    for test_name in REQUIRED_RUNTIME_TEST_NAMES:
        outcome = _resolve_case_outcome(outcomes, test_name)
        if outcome is None:
            errors.append(f"runtime proof testcase missing from junit xml: {test_name}")
            continue
        if outcome != "passed":
            errors.append(f"runtime proof testcase did not pass (outcome={outcome}): {test_name}")

    if not artifacts_dir.exists():
        errors.append(f"missing runtime artifacts directory: {artifacts_dir}")
        return

    artifact_payloads: dict[str, object] = {}
    for artifact_name in REQUIRED_RUNTIME_ARTIFACTS:
        artifact_path = artifacts_dir / artifact_name
        if not artifact_path.exists():
            errors.append(f"missing runtime proof artifact: {artifact_path}")
            continue
        if artifact_name.endswith(".json"):
            try:
                artifact_payloads[artifact_name] = json.loads(artifact_path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"unable to parse runtime artifact {artifact_path}: {exc}")
        elif artifact_name.endswith(".txt"):
            text = artifact_path.read_text(encoding="utf-8", errors="replace")
            if not text.strip():
                errors.append(f"runtime log artifact is empty: {artifact_path}")

    composed_payload = artifact_payloads.get("p7_composed_runtime_report.json")
    if isinstance(composed_payload, dict):
        _validate_composed_payload(composed_payload, errors)
    elif "p7_composed_runtime_report.json" in artifact_payloads:
        errors.append("p7_composed_runtime_report.json must be a JSON object")

    negative_payload = artifact_payloads.get("p7_negative_controls_report.json")
    if isinstance(negative_payload, dict):
        _validate_negative_payload(negative_payload, errors)
    elif "p7_negative_controls_report.json" in artifact_payloads:
        errors.append("p7_negative_controls_report.json must be a JSON object")

    branch_payload = artifact_payloads.get("p7_branch_protection_evidence.json")
    if isinstance(branch_payload, dict):
        _validate_branch_protection_payload(
            branch_payload,
            require_live=require_live_branch_protection,
            errors=errors,
        )
    elif "p7_branch_protection_evidence.json" in artifact_payloads:
        errors.append("p7_branch_protection_evidence.json must be a JSON object")

    artifact_scan_payload = artifact_payloads.get("p7_artifact_scan_report.json")
    if isinstance(artifact_scan_payload, dict):
        _validate_artifact_scan_payload(artifact_scan_payload, errors)
    elif "p7_artifact_scan_report.json" in artifact_payloads:
        errors.append("p7_artifact_scan_report.json must be a JSON object")

    legal_payload = artifact_payloads.get("p7_legal_signoff.json")
    if isinstance(legal_payload, dict):
        _validate_legal_payload(legal_payload, errors)
    elif "p7_legal_signoff.json" in artifact_payloads:
        errors.append("p7_legal_signoff.json must be a JSON object")

    _check_artifact_secrecy(artifacts_dir, errors)


def main() -> int:
    args = _parse_args()
    if args.simulate_regression:
        print("B1.4-P7 final E2E gate failed:")
        print("  - synthetic regression: p7 context removed")
        return 1

    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "branch_integrity": Path(args.branch_protection_integrity_contract),
        "p7_contract": Path(args.p7_contract),
        "tests": Path(args.tests_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.4-P7 final E2E gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    branch_integrity = _load_json(paths["branch_integrity"])
    p7_contract = _load_json(paths["p7_contract"])
    tests_text = _read_text(paths["tests"])

    errors: list[str] = []
    _check_required_context(
        workflow_text=workflow_text,
        required_checks=required_checks,
        branch_integrity=branch_integrity,
        p7_contract=p7_contract,
        errors=errors,
    )
    _check_workflow_surface(workflow_text, errors)
    _check_tests_surface(tests_text, p7_contract, errors)

    if args.require_runtime_execution:
        junit_xml = Path(args.junit_xml) if args.junit_xml else None
        if junit_xml is None:
            errors.append("--require-runtime-execution requires --junit-xml")
        else:
            _check_runtime_execution(
                junit_path=junit_xml,
                artifacts_dir=Path(args.artifacts_dir),
                require_live_branch_protection=args.require_live_branch_protection,
                errors=errors,
            )

    if errors:
        print("B1.4-P7 final E2E gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.4-P7 final E2E gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print(
        "  composed_invariants=pii_strip+24h_session+no_cross_session+session_locality+90d_expiry+"
        "deletion+export_no_leak+log_no_leak+artifact_no_leak+tenant_fail_closed"
    )
    print("  negatives=bad_ingress+cross_session+stale_fixture+deletion_edge+export_leak+artifact_canary")
    print("  artifacts=composed+negatives+branch_protection+artifact_scan+legal_signoff+runtime_logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
