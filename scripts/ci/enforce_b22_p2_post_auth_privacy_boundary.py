#!/usr/bin/env python3
"""B2.2-P2 post-auth privacy boundary closure enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b22_p2_post_auth_privacy_boundary.main.json"
)
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
DLQ_HANDLER_FILE = "backend/app/ingestion/dlq_handler.py"
CI_WORKFLOW = ".github/workflows/ci.yml"
P2_TEST_FILE = "backend/tests/test_b22_p2_post_auth_privacy_boundary.py"
P2_ENFORCER_TEST_FILE = "backend/tests/test_b22_p2_post_auth_privacy_boundary_enforcer.py"

EXPECTED_DISALLOWED_FIELDS = {"ip_address", "user_agent", "raw_headers"}
EXPECTED_WEBHOOK_SOURCES = {"shopify", "stripe", "paypal", "woocommerce"}


def _resolve(repo_root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (repo_root / candidate).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _validate_contract(contract: dict[str, Any], violations: list[str]) -> None:
    disallowed_fields = contract.get("disallowed_durable_ingress_identifiers")
    if not isinstance(disallowed_fields, list):
        violations.append("contract_missing_disallowed_field_list")
    else:
        observed = {str(item).strip() for item in disallowed_fields}
        if observed != EXPECTED_DISALLOWED_FIELDS:
            violations.append(
                "contract_disallowed_field_set_mismatch:" + "|".join(sorted(observed))
            )

    webhook_sources = contract.get("webhook_sources")
    if not isinstance(webhook_sources, list):
        violations.append("contract_missing_webhook_sources")
    else:
        observed_sources = {str(item).strip() for item in webhook_sources}
        if observed_sources != EXPECTED_WEBHOOK_SOURCES:
            violations.append(
                "contract_webhook_sources_mismatch:" + "|".join(sorted(observed_sources))
            )

    policy = contract.get("verification_substrate_policy")
    if not isinstance(policy, dict):
        violations.append("contract_missing_verification_substrate_policy")
        return

    if policy.get("auth_precedes_durable_persistence") is not True:
        violations.append("contract_auth_sequence_policy_mismatch")
    if policy.get("raw_body_for_auth") != "required":
        violations.append("contract_raw_body_auth_policy_mismatch")
    if policy.get("signature_headers_for_auth") != "required":
        violations.append("contract_signature_header_auth_policy_mismatch")


def _validate_event_service(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "_raw_event_ingress_metadata_for_persistence(",
        "_WEBHOOK_INGRESS_SOURCES",
        "ip_address=persisted_ip_address",
        "user_agent=persisted_user_agent",
        "raw_headers=persisted_raw_headers",
        "if source.strip().lower() in _WEBHOOK_INGRESS_SOURCES:",
        "return None, None, None",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"event_service_missing_token:{token}")

    if '"ip_address=_first_header_value(' in text:
        violations.append("event_service_direct_ip_header_persistence_detected")
    if 'user_agent=_first_header_value(' in text:
        violations.append("event_service_direct_user_agent_persistence_detected")
    if "raw_headers=normalized_headers or None" in text:
        violations.append("event_service_direct_raw_headers_persistence_detected")


def _validate_webhooks(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "raw_body = await _resolve_raw_body_for_webhook_auth(request)",
        "_verified_revenue_state()",
        "not result.is_duplicate",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"webhooks_missing_token:{token}")
    forbidden_tokens = (
        "result.get(\"is_duplicate\")",
        "result[\"is_duplicate\"]",
    )
    for token in forbidden_tokens:
        if token in text:
            violations.append(f"webhooks_forbidden_token_present:{token}")


def _validate_dlq(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "_DLQ_FAILURE_SURFACE_FORBIDDEN_KEYS",
        "\"raw_headers\"",
        "drop_forbidden_keys=True",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"dlq_missing_token:{token}")

    disallowed_exclusions = (
        '"ip"',
        '"ip_address"',
    )
    for token in disallowed_exclusions:
        if token in text:
            violations.append(f"dlq_disallowed_identifier_excluded_from_sanitizer:{token}")


def _validate_ci(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "python scripts/ci/enforce_b22_p2_post_auth_privacy_boundary.py",
        "pytest backend/tests/test_b22_p2_post_auth_privacy_boundary_enforcer.py -q",
        "pytest backend/tests/test_b22_p2_post_auth_privacy_boundary.py -q",
        "SKELDIR_B22_P2_REQUIRE_DB_PROOFS: \"1\"",
        "Prepare B2.2-P2 runtime proof authority boundary",
        "Run migrations for B2.2-P2 authoritative runtime proofs",
        "--database-name \"skeldir_b22_p2_ci\"",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"ci_missing_b22_p2_token:{token}")


def _validate_test_surfaces(*, p2_test: Path, p2_enforcer_test: Path, violations: list[str]) -> None:
    p2_text = _read_text(p2_test)
    p2_required_tests = (
        "test_b22_p2_webhook_success_persists_minimized_raw_event_substrate_only",
        "test_b22_p2_webhook_malformed_dlq_path_drops_disallowed_ingress_identifiers",
        "test_b22_p2_duplicate_webhook_does_not_reenqueue_downstream_side_effects",
        "test_b22_p2_negative_control_disallowed_field_detector_is_non_vacuous",
    )
    for token in p2_required_tests:
        if token not in p2_text:
            violations.append(f"p2_test_missing_token:{token}")

    enforcer_text = _read_text(p2_enforcer_test)
    required_enforcer_tokens = (
        "test_b22_p2_post_auth_privacy_boundary_enforcer_passes_repo_state",
        "test_b22_p2_post_auth_privacy_boundary_enforcer_negative_control_forced_regression",
    )
    for token in required_enforcer_tokens:
        if token not in enforcer_text:
            violations.append(f"p2_enforcer_test_missing_token:{token}")


def run_enforcement(
    *,
    governance_contract: Path,
    event_service_file: Path,
    webhooks_file: Path,
    dlq_handler_file: Path,
    ci_workflow: Path,
    p2_test_file: Path,
    p2_enforcer_test_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        governance_contract,
        event_service_file,
        webhooks_file,
        dlq_handler_file,
        ci_workflow,
        p2_test_file,
        p2_enforcer_test_file,
    )
    for path in required_paths:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract)
    _validate_contract(contract, violations)
    _validate_event_service(event_service_file, violations)
    _validate_webhooks(webhooks_file, violations)
    _validate_dlq(dlq_handler_file, violations)
    _validate_ci(ci_workflow, violations)
    _validate_test_surfaces(
        p2_test=p2_test_file,
        p2_enforcer_test=p2_enforcer_test_file,
        violations=violations,
    )
    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P2 post-auth privacy boundary closure and merge-blocking invariants."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--dlq-handler-file", default=DLQ_HANDLER_FILE)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--p2-test-file", default=P2_TEST_FILE)
    parser.add_argument("--p2-enforcer-test-file", default=P2_ENFORCER_TEST_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p2_post_auth_privacy_boundary_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract=_resolve(repo_root, args.governance_contract),
        event_service_file=_resolve(repo_root, args.event_service_file),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        dlq_handler_file=_resolve(repo_root, args.dlq_handler_file),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        p2_test_file=_resolve(repo_root, args.p2_test_file),
        p2_enforcer_test_file=_resolve(repo_root, args.p2_enforcer_test_file),
    )

    lines = ["b22_p2_post_auth_privacy_boundary_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=post_auth_privacy_boundary_zero_disallowed_webhook_durable_ingress_identifiers"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
