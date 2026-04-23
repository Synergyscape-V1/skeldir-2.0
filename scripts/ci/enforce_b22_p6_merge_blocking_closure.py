#!/usr/bin/env python3
"""B2.2-P6 merge-blocking closure + downstream-readiness enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b22_p6_merge_blocking_closure.main.json"
)
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"
P6_TRUTH_INGRESS_TEST_FILE = (
    "backend/tests/integration/test_b22_p6_end_to_end_truth_ingress.py"
)
P6_B23_COMPAT_TEST_FILE = (
    "backend/tests/integration/test_b22_p6_b23_downstream_readiness.py"
)
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
EVENT_SERVICE_FILE = "backend/app/ingestion/event_service.py"
P6_ENFORCER_TEST_FILE = "backend/tests/test_b22_p6_merge_blocking_closure_enforcer.py"


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


def _validate_required_contexts(
    *,
    contract: dict[str, Any],
    required_checks: dict[str, Any],
    violations: list[str],
) -> None:
    expected_contexts = contract.get("required_check_contexts", [])
    if not isinstance(expected_contexts, list) or not expected_contexts:
        violations.append("contract_required_check_contexts_invalid")
        return

    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
        required_contexts = []

    for context in expected_contexts:
        context_name = str(context).strip()
        if not context_name:
            continue
        if context_name not in required_contexts:
            violations.append(f"required_checks_missing_context:{context_name}")

    future_contexts = required_checks.get("future_required_context_declarations", [])
    if isinstance(future_contexts, list):
        future_names = {
            item.get("name")
            for item in future_contexts
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for context in expected_contexts:
            context_name = str(context).strip()
            if context_name in future_names:
                violations.append(
                    f"required_checks_context_must_not_be_future_declared:{context_name}"
                )


def _validate_ci_workflow(
    *,
    workflow_text: str,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    required_tokens = (
        "name: B2.2-P6 Merge-Blocking Closure + Downstream Readiness",
        "needs: [checkout, validate-contracts, contract-semantic-drift-gate, b22-p5-webhook-latency-adjudication]",
        "python scripts/ci/enforce_b22_p6_merge_blocking_closure.py",
        "pytest backend/tests/test_b22_p6_merge_blocking_closure_enforcer.py -q",
        "pytest backend/tests/integration/test_b22_p6_end_to_end_truth_ingress.py -q",
        "pytest backend/tests/integration/test_b22_p6_b23_downstream_readiness.py -q",
        "SKELDIR_B22_P6_REQUIRE_DB_PROOFS: \"1\"",
    )
    for token in required_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    required_enforcer_tokens = contract.get("required_b22_phase_enforcers", [])
    if not isinstance(required_enforcer_tokens, list):
        violations.append("contract_required_b22_phase_enforcers_invalid")
    else:
        for token in required_enforcer_tokens:
            normalized = str(token).strip()
            if normalized and normalized not in workflow_text:
                violations.append(f"workflow_missing_b22_phase_enforcer_token:{normalized}")

    required_runtime_tokens = contract.get("required_b22_phase_runtime_proofs", [])
    if not isinstance(required_runtime_tokens, list):
        violations.append("contract_required_b22_phase_runtime_proofs_invalid")
    else:
        for token in required_runtime_tokens:
            normalized = str(token).strip()
            if normalized and normalized not in workflow_text:
                violations.append(
                    f"workflow_missing_b22_phase_runtime_proof_token:{normalized}"
                )


def _validate_truth_ingress_suite(
    *,
    suite_text: str,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    suite_spec = contract.get("required_provider_truth_ingress_suite", {})
    if not isinstance(suite_spec, dict):
        violations.append("contract_required_provider_truth_ingress_suite_invalid")
        return

    required_tests = suite_spec.get("required_tests", [])
    if not isinstance(required_tests, list) or not required_tests:
        violations.append("contract_required_provider_truth_ingress_tests_invalid")
    else:
        for test_name in required_tests:
            normalized = str(test_name).strip()
            if normalized and normalized not in suite_text:
                violations.append(f"truth_ingress_suite_missing_test:{normalized}")

    required_providers = suite_spec.get("required_providers", [])
    if not isinstance(required_providers, list):
        violations.append("contract_required_provider_truth_ingress_providers_invalid")
    else:
        provider_tokens = {
            "shopify": "/api/webhooks/shopify/order_create",
            "woocommerce": "/api/webhooks/woocommerce/order_completed",
            "stripe": "/api/webhooks/stripe/payment_intent/succeeded",
            "paypal": "/api/webhooks/paypal/sale_completed",
        }
        for provider in required_providers:
            normalized = str(provider).strip().lower()
            route_token = provider_tokens.get(normalized)
            if route_token is None:
                violations.append(f"truth_ingress_suite_unknown_provider:{normalized}")
                continue
            if route_token not in suite_text:
                violations.append(
                    f"truth_ingress_suite_missing_provider_route_token:{normalized}"
                )

    required_truth_tokens = (
        "WebhookIngressIdentity",
        "AttributionEvent",
        "RawEventPayload",
        "assert len(observed_calls) == 4",
        "verified_commerce_ingress_state == \"authenticity_verified\"",
    )
    for token in required_truth_tokens:
        if token not in suite_text:
            violations.append(f"truth_ingress_suite_missing_token:{token}")


def _validate_b23_compat_suite(
    *,
    suite_text: str,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    suite_spec = contract.get("required_b23_downstream_readiness_suite", {})
    if not isinstance(suite_spec, dict):
        violations.append("contract_required_b23_downstream_readiness_suite_invalid")
        return

    required_tests = suite_spec.get("required_tests", [])
    if not isinstance(required_tests, list) or not required_tests:
        violations.append("contract_required_b23_readiness_tests_invalid")
    else:
        for test_name in required_tests:
            normalized = str(test_name).strip()
            if normalized and normalized not in suite_text:
                violations.append(f"b23_readiness_suite_missing_test:{normalized}")

    required_fields = suite_spec.get("required_ingress_fields", [])
    if not isinstance(required_fields, list):
        violations.append("contract_required_b23_readiness_fields_invalid")
    else:
        for field_name in required_fields:
            normalized = str(field_name).strip()
            if normalized and normalized not in suite_text:
                violations.append(f"b23_readiness_suite_missing_ingress_field:{normalized}")

    required_tokens = (
        "RevenueReconciliationService",
        "reconcile_order",
        "get_reconciliation_by_order",
        "monkeypatch.setattr(",
        "reconciliation_invocations[\"count\"] == 0",
    )
    for token in required_tokens:
        if token not in suite_text:
            violations.append(f"b23_readiness_suite_missing_token:{token}")


def _validate_ingress_forbidden_tokens(
    *,
    webhooks_text: str,
    event_service_text: str,
    contract: dict[str, Any],
    violations: list[str],
) -> None:
    forbidden_tokens = contract.get("forbidden_reconciliation_tokens_in_ingress", [])
    if not isinstance(forbidden_tokens, list):
        violations.append("contract_forbidden_reconciliation_tokens_in_ingress_invalid")
        return

    combined_text = f"{webhooks_text}\n{event_service_text}"
    for token in forbidden_tokens:
        normalized = str(token).strip()
        if normalized and normalized in combined_text:
            violations.append(f"ingress_forbidden_reconciliation_token_present:{normalized}")


def run_enforcement(
    *,
    governance_contract_file: Path,
    required_checks_file: Path,
    ci_workflow_file: Path,
    p6_truth_ingress_test_file: Path,
    p6_b23_compat_test_file: Path,
    webhooks_file: Path,
    event_service_file: Path,
    p6_enforcer_test_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        governance_contract_file,
        required_checks_file,
        ci_workflow_file,
        p6_truth_ingress_test_file,
        p6_b23_compat_test_file,
        webhooks_file,
        event_service_file,
        p6_enforcer_test_file,
    )
    for path in required_files:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract = _read_json(governance_contract_file)
    required_checks = _read_json(required_checks_file)
    ci_text = _read_text(ci_workflow_file)
    truth_ingress_text = _read_text(p6_truth_ingress_test_file)
    b23_compat_text = _read_text(p6_b23_compat_test_file)
    webhooks_text = _read_text(webhooks_file)
    event_service_text = _read_text(event_service_file)
    enforcer_test_text = _read_text(p6_enforcer_test_file)

    _validate_required_contexts(
        contract=contract,
        required_checks=required_checks,
        violations=violations,
    )
    _validate_ci_workflow(
        workflow_text=ci_text,
        contract=contract,
        violations=violations,
    )
    _validate_truth_ingress_suite(
        suite_text=truth_ingress_text,
        contract=contract,
        violations=violations,
    )
    _validate_b23_compat_suite(
        suite_text=b23_compat_text,
        contract=contract,
        violations=violations,
    )
    _validate_ingress_forbidden_tokens(
        webhooks_text=webhooks_text,
        event_service_text=event_service_text,
        contract=contract,
        violations=violations,
    )

    enforcer_test_tokens = (
        "test_b22_p6_merge_blocking_closure_enforcer_passes_repo_state",
        "test_b22_p6_merge_blocking_closure_enforcer_negative_control_forced_regression",
    )
    for token in enforcer_test_tokens:
        if token not in enforcer_test_text:
            violations.append(f"p6_enforcer_test_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce B2.2-P6 merge-blocking closure and downstream-readiness contract "
            "binding across required checks, CI wiring, and runtime proof suites."
        )
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract-file", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument(
        "--p6-truth-ingress-test-file", default=P6_TRUTH_INGRESS_TEST_FILE
    )
    parser.add_argument("--p6-b23-compat-test-file", default=P6_B23_COMPAT_TEST_FILE)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--event-service-file", default=EVENT_SERVICE_FILE)
    parser.add_argument("--p6-enforcer-test-file", default=P6_ENFORCER_TEST_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p6_merge_blocking_closure_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract_file=_resolve(repo_root, args.governance_contract_file),
        required_checks_file=_resolve(repo_root, args.required_checks_file),
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        p6_truth_ingress_test_file=_resolve(repo_root, args.p6_truth_ingress_test_file),
        p6_b23_compat_test_file=_resolve(repo_root, args.p6_b23_compat_test_file),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        event_service_file=_resolve(repo_root, args.event_service_file),
        p6_enforcer_test_file=_resolve(repo_root, args.p6_enforcer_test_file),
    )

    lines = ["b22_p6_merge_blocking_closure_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=required_checks_plus_ci_plus_truth_ingress_plus_b23_readiness_no_reconciliation_closure"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
