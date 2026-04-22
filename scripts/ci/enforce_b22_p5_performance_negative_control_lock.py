#!/usr/bin/env python3
"""B2.2-P5 performance semantics + negative-control completeness lock enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_CONTRACT = (
    "contracts-internal/governance/b22_p5_performance_negative_control_lock.main.json"
)
WEBHOOKS_FILE = "backend/app/api/webhooks.py"
BENCHMARK_FILE = "scripts/benchmarks/b22_p5_webhook_ingress_benchmark.py"
BENCHMARK_ADJUDICATOR = "scripts/ci/enforce_b22_p5_webhook_benchmark_adjudication.py"
CI_WORKFLOW = ".github/workflows/ci.yml"
P5_RUNTIME_TEST = "backend/tests/test_b22_p5_performance_negative_controls.py"
P5_ENFORCER_TEST = (
    "backend/tests/test_b22_p5_performance_negative_control_lock_enforcer.py"
)
P5_ADJUDICATOR_TEST = (
    "backend/tests/test_b22_p5_webhook_benchmark_adjudication_enforcer.py"
)

EXPECTED_ROUTES = {
    "/api/webhooks/shopify/order_create",
    "/api/webhooks/stripe/payment_intent_succeeded",
    "/api/webhooks/stripe/payment_intent/succeeded",
    "/api/webhooks/paypal/sale_completed",
    "/api/webhooks/woocommerce/order_completed",
}
EXPECTED_NEGATIVE_CONTROL_CLASSES = {
    "forged_signature",
    "missing_tenant_key",
    "wrong_tenant_key",
    "malformed_payload",
    "oversized_payload",
    "duplicate_replay",
    "unsupported_event_family",
}


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _validate_contract(payload: dict[str, Any], violations: list[str]) -> None:
    mounted_routes = payload.get("mounted_routes")
    if not isinstance(mounted_routes, list):
        violations.append("contract_mounted_routes_invalid")
    else:
        observed_routes = {str(item).strip() for item in mounted_routes}
        if observed_routes != EXPECTED_ROUTES:
            violations.append(
                "contract_mounted_routes_mismatch:" + "|".join(sorted(observed_routes))
            )

    latency = payload.get("latency_adjudication")
    if not isinstance(latency, dict):
        violations.append("contract_latency_adjudication_invalid")
    else:
        if (
            latency.get("benchmark_schema_version")
            != "b22_p5_webhook_ingress_benchmark.v1"
        ):
            violations.append("contract_benchmark_schema_version_mismatch")
        if latency.get("timing_boundary") != "mounted_http_request_to_ack_response":
            violations.append("contract_timing_boundary_mismatch")
        if float(latency.get("hard_p95_ms_threshold", 0)) != 500.0:
            violations.append("contract_hard_p95_threshold_mismatch")

    anti_cheat = payload.get("anti_cheat")
    if not isinstance(anti_cheat, dict):
        violations.append("contract_anti_cheat_invalid")
    else:
        forbidden_tokens = anti_cheat.get("forbidden_harness_tokens")
        if not isinstance(forbidden_tokens, list) or not forbidden_tokens:
            violations.append("contract_forbidden_harness_tokens_missing")

    matrix = payload.get("negative_control_matrix")
    if not isinstance(matrix, dict):
        violations.append("contract_negative_control_matrix_invalid")
    else:
        required_classes = matrix.get("required_classes")
        if not isinstance(required_classes, list):
            violations.append("contract_negative_control_required_classes_missing")
        else:
            observed_classes = {str(item).strip() for item in required_classes}
            if observed_classes != EXPECTED_NEGATIVE_CONTROL_CLASSES:
                violations.append(
                    "contract_negative_control_required_classes_mismatch:"
                    + "|".join(sorted(observed_classes))
                )
        unsupported_contract = matrix.get("unsupported_event_family_contract")
        if not isinstance(unsupported_contract, dict):
            violations.append("contract_unsupported_event_family_contract_missing")
        else:
            if (
                unsupported_contract.get("response_status")
                != "unsupported_event_family_ignored"
            ):
                violations.append("contract_unsupported_event_family_status_mismatch")
            if unsupported_contract.get("http_status") != 200:
                violations.append(
                    "contract_unsupported_event_family_http_status_mismatch"
                )
            if unsupported_contract.get("route_owned") is not True:
                violations.append(
                    "contract_unsupported_event_family_route_owned_mismatch"
                )
            if unsupported_contract.get("provider_retry_safe") is not True:
                violations.append(
                    "contract_unsupported_event_family_retry_safe_mismatch"
                )


def _validate_webhooks(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        'WEBHOOK_UNSUPPORTED_EVENT_FAMILY_STATUS = "unsupported_event_family_ignored"',
        "def _unsupported_event_family_reason(",
        "def _route_unsupported_event_family(",
        'error": "unsupported_event_family"',
        'provider="stripe"',
        'provider="shopify"',
        'provider="paypal"',
        'provider="woocommerce"',
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"webhooks_missing_token:{token}")


def _validate_benchmark(
    *,
    benchmark_file: Path,
    governance_contract: dict[str, Any],
    violations: list[str],
) -> None:
    text = _read_text(benchmark_file)
    required_tokens = (
        'BENCHMARK_SCHEMA_VERSION = "b22_p5_webhook_ingress_benchmark.v1"',
        'BENCHMARK_TIMING_BOUNDARY = "mounted_http_request_to_ack_response"',
        "_runtime_component_integrity(",
        "_run_integrity_probes(",
        "_run_measurement(",
        '"unsupported_event_family_ignored"',
        '"task_always_eager"',
        '--mode", choices=("integrity", "measure")',
        "/api/webhooks/paypal/sale_completed",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"benchmark_missing_token:{token}")

    forbidden_tokens = governance_contract.get("anti_cheat", {}).get(
        "forbidden_harness_tokens", []
    )
    if isinstance(forbidden_tokens, list):
        for token in forbidden_tokens:
            stripped = str(token).strip()
            if not stripped:
                continue
            if stripped in text:
                violations.append(f"benchmark_forbidden_token_present:{stripped}")


def _validate_benchmark_adjudicator(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        'SCHEMA_VERSION = "b22_p5_webhook_ingress_benchmark.v1"',
        "p95_threshold_exceeded",
        "component_integrity_failed",
        "task_always_eager_enabled",
        "stripe_alias_canonical_p95_delta_exceeded",
        "integrity_probe_unsupported_status_invalid",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"benchmark_adjudicator_missing_token:{token}")


def _validate_ci(path: Path, violations: list[str]) -> None:
    text = _read_text(path)
    required_tokens = (
        "b22-p5-webhook-latency-adjudication",
        "name: B2.2-P5 Webhook Latency Adjudication",
        "needs: [checkout, validate-contracts, b21-p2-strategy-kernel-session-boundary, b21-p4-queue-isolation-performance-lock, b22-p5-webhook-latency-adjudication]",
        "Enforce B2.2-P5 performance semantics + negative-control lock",
        "Run B2.2-P5 structural negative controls",
        "Run B2.2-P5 runtime negative-control + parity proofs",
        "Run B2.2-P5 benchmark adjudication negative controls",
        "python scripts/ci/enforce_b22_p5_performance_negative_control_lock.py",
        "pytest backend/tests/test_b22_p5_performance_negative_control_lock_enforcer.py -q",
        "pytest backend/tests/test_b22_p5_performance_negative_controls.py -q",
        "pytest backend/tests/test_b22_p5_webhook_benchmark_adjudication_enforcer.py -q",
        "python scripts/benchmarks/b22_p5_webhook_ingress_benchmark.py \\",
        "--mode integrity \\",
        "--mode measure \\",
        "python scripts/ci/enforce_b22_p5_webhook_benchmark_adjudication.py",
    )
    for token in required_tokens:
        if token not in text:
            violations.append(f"ci_missing_b22_p5_token:{token}")


def _validate_test_surfaces(
    *,
    runtime_test: Path,
    enforcer_test: Path,
    adjudicator_test: Path,
    violations: list[str],
) -> None:
    runtime_text = _read_text(runtime_test)
    runtime_required_tokens = (
        "test_b22_p5_negative_control_matrix_includes_route_owned_provider_safe_unsupported_family_semantics",
        "test_b22_p5_stripe_alias_and_canonical_routes_have_equivalent_success_failure_and_unsupported_family_semantics",
        "unsupported_event_family_ignored",
        "PAYMENT.CAPTURE.COMPLETED",
        "charge.succeeded",
    )
    for token in runtime_required_tokens:
        if token not in runtime_text:
            violations.append(f"runtime_test_missing_token:{token}")

    enforcer_text = _read_text(enforcer_test)
    for token in (
        "test_b22_p5_performance_negative_control_lock_enforcer_passes_repo_state",
        "test_b22_p5_performance_negative_control_lock_enforcer_negative_control_forced_regression",
    ):
        if token not in enforcer_text:
            violations.append(f"enforcer_test_missing_token:{token}")

    adjudicator_text = _read_text(adjudicator_test)
    for token in (
        "test_b22_p5_webhook_benchmark_adjudication_passes_with_valid_payload",
        "test_b22_p5_webhook_benchmark_adjudication_fails_when_p95_regresses",
    ):
        if token not in adjudicator_text:
            violations.append(f"adjudicator_test_missing_token:{token}")


def run_enforcement(
    *,
    governance_contract: Path,
    webhooks_file: Path,
    benchmark_file: Path,
    benchmark_adjudicator: Path,
    ci_workflow: Path,
    runtime_test: Path,
    enforcer_test: Path,
    adjudicator_test: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        governance_contract,
        webhooks_file,
        benchmark_file,
        benchmark_adjudicator,
        ci_workflow,
        runtime_test,
        enforcer_test,
        adjudicator_test,
    )
    for path in required_paths:
        if not path.exists():
            violations.append(f"missing_required_file:{path}")
    if violations:
        return 1, violations

    contract_payload = _read_json(governance_contract)
    _validate_contract(contract_payload, violations)
    _validate_webhooks(webhooks_file, violations)
    _validate_benchmark(
        benchmark_file=benchmark_file,
        governance_contract=contract_payload,
        violations=violations,
    )
    _validate_benchmark_adjudicator(benchmark_adjudicator, violations)
    _validate_ci(ci_workflow, violations)
    _validate_test_surfaces(
        runtime_test=runtime_test,
        enforcer_test=enforcer_test,
        adjudicator_test=adjudicator_test,
        violations=violations,
    )
    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.2-P5 performance semantics lock + negative-control completeness."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--governance-contract", default=GOVERNANCE_CONTRACT)
    parser.add_argument("--webhooks-file", default=WEBHOOKS_FILE)
    parser.add_argument("--benchmark-file", default=BENCHMARK_FILE)
    parser.add_argument("--benchmark-adjudicator", default=BENCHMARK_ADJUDICATOR)
    parser.add_argument("--ci-workflow", default=CI_WORKFLOW)
    parser.add_argument("--runtime-test", default=P5_RUNTIME_TEST)
    parser.add_argument("--enforcer-test", default=P5_ENFORCER_TEST)
    parser.add_argument("--adjudicator-test", default=P5_ADJUDICATOR_TEST)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b22_p5_performance_negative_control_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        governance_contract=_resolve(repo_root, args.governance_contract),
        webhooks_file=_resolve(repo_root, args.webhooks_file),
        benchmark_file=_resolve(repo_root, args.benchmark_file),
        benchmark_adjudicator=_resolve(repo_root, args.benchmark_adjudicator),
        ci_workflow=_resolve(repo_root, args.ci_workflow),
        runtime_test=_resolve(repo_root, args.runtime_test),
        enforcer_test=_resolve(repo_root, args.enforcer_test),
        adjudicator_test=_resolve(repo_root, args.adjudicator_test),
    )

    lines = ["b22_p5_performance_negative_control_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append(
            "enforcement=mounted_webhook_latency_anti_cheat_negative_controls_closed"
        )
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
