#!/usr/bin/env python3
"""B2.2-P4 idempotent ACK semantics + orchestration side-effect isolation enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b22_p4_idempotent_ack_orchestration.main.json"
)
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
CI_WORKFLOW = ".github/workflows/ci.yml"
P4_TEST_FILE = "backend/tests/test_b22_p4_idempotent_ack_orchestration.py"
P4_ENFORCER_TEST_FILE = "backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py"

EXPECTED_PROVIDERS = {"shopify", "woocommerce", "stripe", "paypal"}
EXPECTED_OUTCOMES = {
    "success",
    "duplicate",
    "forged_signature",
    "malformed_authenticated_payload",
    "oversized_payload",
    "missing_tenant_key",
    "wrong_tenant_key",
    "unsupported_event_family",
}


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
    providers = {str(item).strip() for item in contract.get("supported_providers", [])}
    if providers != EXPECTED_PROVIDERS:
        violations.append("contract_provider_set_mismatch:" + "|".join(sorted(providers)))

    duplicate_contract = contract.get("duplicate_signal_contract")
    if not isinstance(duplicate_contract, dict):
        violations.append("contract_missing_duplicate_signal_contract")
    else:
        if duplicate_contract.get("ingestion_decision_type") != "IngestionDecision":
            violations.append("contract_duplicate_signal_type_mismatch")
        states = {str(item).strip() for item in duplicate_contract.get("state_enum", [])}
        if states != {"inserted", "duplicate"}:
            violations.append("contract_duplicate_state_enum_mismatch")
        if duplicate_contract.get("webhook_orchestration_gate_field") != "is_duplicate":
            violations.append("contract_duplicate_gate_field_mismatch")
        if duplicate_contract.get("forbid_private_orm_duplicate_marker") is not True:
            violations.append("contract_private_marker_policy_mismatch")

    ack_matrix = contract.get("ack_matrix_contract")
    if not isinstance(ack_matrix, dict):
        violations.append("contract_missing_ack_matrix")
        return
    outcomes = {str(key).strip() for key in ack_matrix.keys()}
    if outcomes != EXPECTED_OUTCOMES:
        violations.append("contract_ack_outcome_set_mismatch:" + "|".join(sorted(outcomes)))


def _validate_event_service(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "class IngestionResultState(str, Enum):",
        "class IngestionDecision:",
        "async def ingest_event_with_decision(",
        "\"ingestion_state\": decision.state.value",
        "IngestionResultState.DUPLICATE",
        "IngestionResultState.INSERTED",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"event_service_missing_token:{token}")
    forbidden_tokens = (
        "_ingestion_duplicate",
        "getattr(event, \"_ingestion_duplicate\"",
    )
    for token in forbidden_tokens:
        if token in text:
            violations.append(f"event_service_forbidden_token_present:{token}")


def _validate_webhooks(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "not bool(result.get(\"is_duplicate\"))",
        "\"status\": \"dlq_routed\"",
        "status.HTTP_413_REQUEST_ENTITY_TOO_LARGE",
        "/webhooks/stripe/payment_intent_succeeded",
        "/webhooks/stripe/payment_intent/succeeded",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"webhooks_missing_token:{token}")


def _validate_ci(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "SKELDIR_B22_P4_REQUIRE_DB_PROOFS: \"1\"",
        "python scripts/ci/enforce_b22_p4_idempotent_ack_orchestration.py",
        "pytest backend/tests/test_b22_p4_idempotent_ack_orchestration_enforcer.py -q",
        "pytest backend/tests/test_b22_p4_idempotent_ack_orchestration.py -q",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"ci_missing_b22_p4_token:{token}")


def _validate_test_surfaces(*, p4_test: Path, p4_enforcer_test: Path, violations: list[str]) -> None:
    p4_text = _read_text(p4_test)
    p4_required_tests = (
        "test_b22_p4_duplicate_replay_suppresses_downstream_tasks_for_all_supported_providers",
        "test_b22_p4_duplicate_replay_preserves_single_durable_event_row",
        "test_b22_p4_ack_matrix_is_stable_for_success_duplicate_forged_malformed_oversized_tenant_and_unsupported_outcomes",
        "test_b22_p4_stripe_alias_and_canonical_routes_share_ack_semantics",
    )
    for token in p4_required_tests:
        if token not in p4_text:
            violations.append(f"p4_test_missing_token:{token}")

    enforcer_text = _read_text(p4_enforcer_test)
    enforcer_required_tests = (
        "test_b22_p4_idempotent_ack_orchestration_enforcer_passes_repo_state",
        "test_b22_p4_idempotent_ack_orchestration_enforcer_negative_control_forced_regression",
    )
    for token in enforcer_required_tests:
        if token not in enforcer_text:
            violations.append(f"p4_enforcer_test_missing_token:{token}")


def run_enforcement(
    *,
    governance_contract: Path,
    event_service_file: Path,
    webhooks_file: Path,
    ci_workflow: Path,
    p4_test_file: Path,
    p4_enforcer_test_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        governance_contract,
        event_service_file,
        webhooks_file,
        ci_workflow,
        p4_test_file,
        p4_enforcer_test_file,
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
    _validate_ci(ci_workflow, violations)
    _validate_test_surfaces(
        p4_test=p4_test_file,
        p4_enforcer_test=p4_enforcer_test_file,
        violations=violations,
    )
    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P4 idempotent ACK semantics and webhook side-effect isolation."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--p4-test-file", default=P4_TEST_FILE)
    parser.add_argument("--p4-enforcer-test-file", default=P4_ENFORCER_TEST_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p4_idempotent_ack_orchestration_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract=_resolve(repo_root, args.governance_contract),
        event_service_file=_resolve(repo_root, args.event_service_file),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        p4_test_file=_resolve(repo_root, args.p4_test_file),
        p4_enforcer_test_file=_resolve(repo_root, args.p4_enforcer_test_file),
    )

    lines = ["b22_p4_idempotent_ack_orchestration_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=explicit_duplicate_signal_and_ack_matrix_side_effect_isolation")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
