#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


REQUIRED_CONTEXT = "B1.3 P11 E2E System Proofs"
REQUIRED_TEST_NAMES = (
    "test_b13_p11_gate_passes_repo_state",
    "test_b13_p11_composed_lifecycle_lock_with_six_provider_topology",
    "test_b13_p11_multi_tenant_safety_lock_and_tenantless_worker_fail_closed",
)
REQUIRED_RUNTIME_TEST_NAMES = (
    "test_b13_p11_composed_lifecycle_lock_with_six_provider_topology",
    "test_b13_p11_multi_tenant_safety_lock_and_tenantless_worker_fail_closed",
)
REQUIRED_RUNTIME_ARTIFACTS = (
    "p11_composed_runtime_report.json",
    "p11_negative_controls_report.json",
    "p11_db_runtime_evidence.json",
    "p11_runtime_logs.txt",
    "p11_branch_protection_evidence.json",
)
FORBIDDEN_ARTIFACT_PATTERNS = (
    re.compile(r"gho_[A-Za-z0-9_]+"),
    re.compile(r"(?:dummy|stripe|google_ads|meta_ads|paypal|shopify|woocommerce)-(?:access|refresh)-[a-z0-9]{8,}"),
    re.compile(r"(?:dummy|stripe|google_ads|meta_ads|paypal|shopify|woocommerce)-code-[a-f0-9]{8,}"),
    re.compile(r"invalid_client-terminal"),
    re.compile(r"client_secret", re.IGNORECASE),
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B1.3-P11 final E2E system proof enforcement")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-contract",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--p10-tranche-contract",
        default="contracts-internal/governance/b13_p10_provider_rollout_tranches.main.json",
    )
    parser.add_argument("--tests-file", default="backend/tests/integration/test_b13_p11_e2e_system_proofs.py")
    parser.add_argument("--require-runtime-execution", action="store_true")
    parser.add_argument("--require-live-branch-protection", action="store_true")
    parser.add_argument("--junit-xml", default=None)
    parser.add_argument("--artifacts-dir", default="artifacts/b13_p11")
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


def _check_required_context(workflow_text: str, required_checks: dict, errors: list[str]) -> None:
    if REQUIRED_CONTEXT not in workflow_text:
        errors.append(f"workflow missing required context name: {REQUIRED_CONTEXT}")
    contexts = required_checks.get("required_contexts")
    if not isinstance(contexts, list):
        errors.append("required checks contract missing required_contexts list")
        return
    if REQUIRED_CONTEXT not in contexts:
        errors.append(f"required checks contract missing context: {REQUIRED_CONTEXT}")


def _check_workflow_surface(workflow_text: str, errors: list[str]) -> None:
    required_fragments = (
        "name: B1.3 P11 E2E System Proofs",
        "python scripts/ci/enforce_b13_p11_e2e_system_proofs.py",
        "pytest backend/tests/integration/test_b13_p11_e2e_system_proofs.py -q -rs --junitxml=artifacts/b13_p11/junit.xml",
        "python scripts/ci/capture_b13_p11_branch_protection_evidence.py",
        "name: b13-p11-runtime-artifacts",
        "path: artifacts/b13_p11",
        "if-no-files-found: error",
    )
    for fragment in required_fragments:
        if fragment not in workflow_text:
            errors.append(f"workflow missing P11 closure fragment: {fragment}")


def _check_tranche_contract(contract: dict, errors: list[str]) -> set[str]:
    providers = contract.get("target_runtime_backed_provider_set")
    if not isinstance(providers, list):
        errors.append("p10 tranche contract missing target_runtime_backed_provider_set list")
        return set()
    provider_set = {str(item).strip() for item in providers if str(item).strip()}
    if len(provider_set) != 6:
        errors.append(
            "p11 expects six-provider breadth from p10 target_runtime_backed_provider_set; "
            f"got {sorted(provider_set)}"
        )
    return provider_set


def _check_tests_surface(test_text: str, target_set: set[str], errors: list[str]) -> None:
    for test_name in REQUIRED_TEST_NAMES:
        if test_name not in test_text:
            errors.append(f"P11 proof suite missing required test: {test_name}")

    required_fragments = (
        "_target_runtime_providers(",
        "ProviderValidTokenResolver",
        "refresh_provider_oauth_credential.apply(",
        "authority_envelope header is required",
        "_write_artifact(\"p11_composed_runtime_report.json\"",
        "_write_artifact(\"p11_negative_controls_report.json\"",
        "_write_artifact(\"p11_db_runtime_evidence.json\"",
        "_write_log_artifact(",
    )
    for fragment in required_fragments:
        if fragment not in test_text:
            errors.append(f"P11 proof suite missing closure fragment: {fragment}")

    for provider in sorted(target_set):
        if provider not in test_text:
            errors.append(f"P11 proof suite does not reference target runtime provider: {provider}")


def _check_artifact_secrecy(artifacts_dir: Path, errors: list[str]) -> None:
    for artifact in REQUIRED_RUNTIME_ARTIFACTS:
        path = artifacts_dir / artifact
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in FORBIDDEN_ARTIFACT_PATTERNS:
            if pattern.search(text):
                errors.append(f"P11 artifact appears to leak sensitive material ({pattern.pattern}): {path}")


def _validate_composed_payload(payload: dict, target_set: set[str], errors: list[str]) -> None:
    providers = payload.get("providers")
    target_runtime = payload.get("target_runtime_backed_provider_set")
    if not isinstance(target_runtime, list):
        errors.append("p11_composed_runtime_report.json missing target_runtime_backed_provider_set list")
    else:
        target_runtime_set = {str(item).strip() for item in target_runtime if str(item).strip()}
        if target_runtime_set != target_set:
            errors.append(
                "p11 composed report target_runtime_backed_provider_set mismatch p10 target set: "
                f"runtime={sorted(target_runtime_set)} target={sorted(target_set)}"
            )
    if not isinstance(providers, dict):
        errors.append("p11_composed_runtime_report.json missing providers object")
        return

    provider_keys = {str(key).strip() for key in providers}
    if provider_keys != target_set:
        errors.append(
            "p11 composed report providers mismatch p10 target set: "
            f"runtime={sorted(provider_keys)} target={sorted(target_set)}"
        )

    for provider, entry in providers.items():
        if not isinstance(entry, dict):
            errors.append(f"p11 composed report provider entry must be object: {provider}")
            continue
        if entry.get("authorize_state") != "authorization_pending":
            errors.append(f"provider {provider} missing authorize_state=authorization_pending proof")
        if entry.get("callback_state") != "connected":
            errors.append(f"provider {provider} missing callback_state=connected proof")
        if entry.get("refresh_status") != "refreshed":
            errors.append(f"provider {provider} missing refresh_status=refreshed proof")
        if entry.get("downstream_use_after_refresh") is not True:
            errors.append(f"provider {provider} missing downstream_use_after_refresh proof")
        if entry.get("revoked_state") != "revoked":
            errors.append(f"provider {provider} missing revoked_state=revoked proof")
        if entry.get("graceful_degraded_code") != "provider_revoked":
            errors.append(f"provider {provider} missing graceful degraded provider_revoked proof")
        if entry.get("encrypted_store_verified") is not True:
            errors.append(f"provider {provider} missing encrypted_store_verified proof")
        if entry.get("expiry_tracked") is not True:
            errors.append(f"provider {provider} missing expiry_tracked proof")

    invalid_path = payload.get("invalid_credential_path")
    if not isinstance(invalid_path, dict):
        errors.append("p11_composed_runtime_report.json missing invalid_credential_path object")
        return
    if invalid_path.get("terminal_status") != "revoked_terminal":
        errors.append("invalid_credential_path missing terminal_status=revoked_terminal")
    if invalid_path.get("terminal_failure_class") != "provider_invalid_client":
        errors.append("invalid_credential_path missing terminal_failure_class=provider_invalid_client")
    if invalid_path.get("graceful_degraded_code") != "provider_revoked":
        errors.append("invalid_credential_path missing graceful_degraded_code=provider_revoked")
    if invalid_path.get("non_leaky") is not True:
        errors.append("invalid_credential_path missing non_leaky proof")


def _validate_negative_payload(payload: dict, errors: list[str]) -> None:
    if payload.get("cross_tenant_status_code") != 404:
        errors.append("p11 negative controls missing cross_tenant_status_code=404")
    if payload.get("cross_tenant_disconnect_code") != 404:
        errors.append("p11 negative controls missing cross_tenant_disconnect_code=404")
    if payload.get("tenantless_worker_error") != "authority_envelope header is required":
        errors.append("p11 negative controls missing tenantless worker fail-closed error proof")
    if payload.get("tenantless_side_effects_blocked") is not True:
        errors.append("p11 negative controls missing tenantless_side_effects_blocked proof")
    if payload.get("worker_positive_status") != "refreshed":
        errors.append("p11 negative controls missing worker_positive_status=refreshed proof")


def _validate_db_payload(payload: dict, target_set: set[str], errors: list[str]) -> None:
    if payload.get("encrypted_credentials_verified") is not True:
        errors.append("p11 db/runtime evidence missing encrypted_credentials_verified proof")
    if payload.get("plaintext_leak_detected") is not False:
        errors.append("p11 db/runtime evidence indicates plaintext leak")
    count = payload.get("provider_row_count")
    if not isinstance(count, int) or count < len(target_set):
        errors.append(
            "p11 db/runtime evidence provider_row_count must be >= six-provider target set size"
        )


def _validate_branch_protection_payload(payload: dict, require_live: bool, errors: list[str]) -> None:
    authority_mode = str(payload.get("authority_mode") or "").strip()
    if authority_mode == "live_branch_protection_api":
        live = payload.get("live_required_status_checks")
        if not isinstance(live, dict):
            errors.append("branch-protection evidence missing live_required_status_checks payload")
            return
        contexts = live.get("contexts")
        if not isinstance(contexts, list):
            errors.append("branch-protection evidence live payload missing contexts list")
            return
        if REQUIRED_CONTEXT not in contexts:
            errors.append("branch-protection evidence live payload missing required P11 context")
        if bool(live.get("strict")) is not True:
            errors.append("branch-protection evidence live payload has strict=false")
    elif authority_mode == "fallback_workflow_contract_only":
        if require_live:
            errors.append("branch-protection evidence used fallback mode while live mode is required")
        if payload.get("required_context_present_in_contract") is not True:
            errors.append("branch-protection fallback evidence missing required context in contract")
        if payload.get("required_context_present_in_workflow") is not True:
            errors.append("branch-protection fallback evidence missing required context in workflow")
    else:
        errors.append(f"branch-protection evidence has unknown authority_mode: {authority_mode}")


def _check_runtime_execution(
    *,
    junit_path: Path,
    artifacts_dir: Path,
    target_set: set[str],
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

    composed_payload = artifact_payloads.get("p11_composed_runtime_report.json")
    if isinstance(composed_payload, dict):
        _validate_composed_payload(composed_payload, target_set, errors)
    elif "p11_composed_runtime_report.json" in artifact_payloads:
        errors.append("p11_composed_runtime_report.json must be a JSON object")

    negative_payload = artifact_payloads.get("p11_negative_controls_report.json")
    if isinstance(negative_payload, dict):
        _validate_negative_payload(negative_payload, errors)
    elif "p11_negative_controls_report.json" in artifact_payloads:
        errors.append("p11_negative_controls_report.json must be a JSON object")

    db_payload = artifact_payloads.get("p11_db_runtime_evidence.json")
    if isinstance(db_payload, dict):
        _validate_db_payload(db_payload, target_set, errors)
    elif "p11_db_runtime_evidence.json" in artifact_payloads:
        errors.append("p11_db_runtime_evidence.json must be a JSON object")

    branch_payload = artifact_payloads.get("p11_branch_protection_evidence.json")
    if isinstance(branch_payload, dict):
        _validate_branch_protection_payload(branch_payload, require_live_branch_protection, errors)
    elif "p11_branch_protection_evidence.json" in artifact_payloads:
        errors.append("p11_branch_protection_evidence.json must be a JSON object")

    _check_artifact_secrecy(artifacts_dir, errors)


def main() -> int:
    args = _parse_args()
    paths = {
        "workflow": Path(args.workflow_file),
        "required_checks": Path(args.required_checks_contract),
        "p10_contract": Path(args.p10_tranche_contract),
        "tests": Path(args.tests_file),
    }
    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        print("B1.3-P11 final E2E gate failed:")
        for item in missing:
            print(f"  - missing file: {item}")
        return 1

    workflow_text = _read_text(paths["workflow"])
    required_checks = _load_json(paths["required_checks"])
    p10_contract = _load_json(paths["p10_contract"])
    tests_text = _read_text(paths["tests"])

    errors: list[str] = []
    _check_required_context(workflow_text, required_checks, errors)
    _check_workflow_surface(workflow_text, errors)
    target_set = _check_tranche_contract(p10_contract, errors)
    _check_tests_surface(tests_text, target_set, errors)

    if args.require_runtime_execution:
        junit_xml = Path(args.junit_xml) if args.junit_xml else None
        if junit_xml is None:
            errors.append("--require-runtime-execution requires --junit-xml")
        else:
            _check_runtime_execution(
                junit_path=junit_xml,
                artifacts_dir=Path(args.artifacts_dir),
                target_set=target_set,
                require_live_branch_protection=args.require_live_branch_protection,
                errors=errors,
            )

    if errors:
        print("B1.3-P11 final E2E gate failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("B1.3-P11 final E2E gate passed.")
    print(f"  required_context={REQUIRED_CONTEXT}")
    print("  composed_chain=authorize->callback->encrypted_store->refresh->downstream_use->revoke/fail")
    print("  negatives=cross_tenant + tenantless_worker_fail_closed")
    print("  artifacts=runtime_logs + runtime_report + db_runtime_evidence + branch_protection_evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
