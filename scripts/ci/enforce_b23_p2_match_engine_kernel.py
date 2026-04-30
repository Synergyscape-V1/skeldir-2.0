#!/usr/bin/env python3
"""B2.3-P2 deterministic match-engine kernel enforcer."""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_p2_match_engine_kernel.main.json"
WORKFLOW_FILE = ".github/workflows/ci.yml"


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
        raise ValueError(f"contract_payload_not_object:{path}")
    return payload


def _registry_dict_from_ast(module_text: str, var_name: str) -> dict[str, set[str]]:
    tree = ast.parse(module_text)
    for node in tree.body:
        value_node: ast.AST | None = None
        target_name: str | None = None

        if isinstance(node, ast.Assign):
            if node.targets and isinstance(node.targets[0], ast.Name):
                target_name = node.targets[0].id
                value_node = node.value
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                target_name = node.target.id
                value_node = node.value

        if target_name != var_name or not isinstance(value_node, ast.Dict):
            continue

        parsed: dict[str, set[str]] = {}
        for key_node, value_node_item in zip(value_node.keys, value_node.values):
            if not isinstance(key_node, ast.Constant) or not isinstance(
                key_node.value, str
            ):
                continue
            value_tokens: set[str] = set()
            if isinstance(value_node_item, (ast.Tuple, ast.List)):
                for entry in value_node_item.elts:
                    if isinstance(entry, ast.Constant) and isinstance(entry.value, str):
                        value_tokens.add(entry.value)
            parsed[key_node.value] = value_tokens
        return parsed
    return {}


def _assert_forbidden_tokens_absent(
    *,
    text_payload: str,
    forbidden_tokens: tuple[str, ...],
    violation_prefix: str,
    violations: list[str],
) -> None:
    for token in forbidden_tokens:
        if token in text_payload:
            violations.append(f"{violation_prefix}:{token}")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    workflow_file: Path,
    extraction_module: Path,
    kernel_module: Path,
    simulate_regression: bool,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    for required in (contract_file, workflow_file, extraction_module, kernel_module):
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    contract = _read_json(contract_file)
    extraction_text = _read_text(extraction_module)
    kernel_text = _read_text(kernel_module)
    workflow_text = _read_text(workflow_file)

    if contract.get("contract_id") != "b23.p2.match_engine_kernel.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-P2":
        violations.append("contract_phase_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")

    platform_registry = contract["platform_keyed_extraction_registry"]["providers"]
    expected_providers = set(platform_registry)
    observed_extractor_map = _registry_dict_from_ast(
        extraction_text, "B23_REVENUE_EXTRACTOR_REGISTRY"
    )
    observed_extractor_providers = set(observed_extractor_map.keys())
    if observed_extractor_providers != expected_providers:
        missing = sorted(expected_providers - observed_extractor_providers)
        extras = sorted(observed_extractor_providers - expected_providers)
        if missing:
            violations.append(f"extractor_registry_missing:{','.join(missing)}")
        if extras:
            violations.append(f"extractor_registry_extra:{','.join(extras)}")

    observed_post_capture_map = _registry_dict_from_ast(
        kernel_text, "B23_POST_CAPTURE_HANDLER_REGISTRY"
    )
    observed_post_capture_providers = set(observed_post_capture_map.keys())
    if observed_post_capture_providers != expected_providers:
        missing = sorted(expected_providers - observed_post_capture_providers)
        extras = sorted(observed_post_capture_providers - expected_providers)
        if missing:
            violations.append(
                f"post_capture_registry_missing_provider:{','.join(missing)}"
            )
        if extras:
            violations.append(
                f"post_capture_registry_extra_provider:{','.join(extras)}"
            )

    required_event_types = set(
        contract["refund_chargeback_handlers"]["required_event_types"]
    )
    for provider in expected_providers:
        observed_event_types = observed_post_capture_map.get(provider, set())
        for missing_event in sorted(required_event_types - observed_event_types):
            violations.append(
                f"post_capture_handler_coverage_missing:{provider}:{missing_event}"
            )

    required_extraction_tokens = (
        "class StripeRevenueExtractionInput",
        "class DecimalMajorRevenueExtractionInput",
        "class PersistedIngressExtractionInput",
        "gross_captured_minor",
        "net_after_fees_minor",
        "extract_revenue_from_typed_input",
    )
    for token in required_extraction_tokens:
        if token not in extraction_text:
            violations.append(f"extraction_missing_token:{token}")

    if "amount_minor=int(payload.net_after_fees_minor" in extraction_text:
        violations.append("stripe_net_after_fees_used_as_canonical_amount")

    required_kernel_tokens = (
        "INSERT INTO b23_match_verdicts",
        "INSERT INTO b23_revenue_events",
        "INSERT INTO b23_exception_records",
        "INSERT INTO b23_webhook_ingestion_logs",
        "pg_advisory_xact_lock",
        "ON CONFLICT",
        "FOR UPDATE",
        "classify_stale_pending_as_unmatched",
        "WEBHOOK_ARRIVAL_WINDOW",
    )
    for token in required_kernel_tokens:
        if token not in kernel_text:
            violations.append(f"kernel_missing_token:{token}")

    _assert_forbidden_tokens_absent(
        text_payload=kernel_text,
        forbidden_tokens=(
            "revenue_ledger",
            "asyncio.Lock(",
            "redis_lock",
            "threading.Lock(",
            "APIRouter",
            "benchmark_1000_orders",
            "provisional_to_confirmed",
            "from app.models.llm",
            "import openai",
            "import anthropic",
        ),
        violation_prefix="kernel_forbidden_token_present",
        violations=violations,
    )

    _assert_forbidden_tokens_absent(
        text_payload=extraction_text,
        forbidden_tokens=(
            ".get(",
            "float(",
            "dict.get(",
            'payload["',
            "payload['",
        ),
        violation_prefix="extraction_forbidden_token_present",
        violations=violations,
    )

    if "timedelta(minutes=30)" in kernel_text:
        violations.append("kernel_hardcoded_arrival_window_literal_detected")
    if (
        "logger.error(" in kernel_text
        and "INSERT INTO b23_exception_records" not in kernel_text
    ):
        violations.append("logger_only_failure_path_detected")

    for token in contract.get("required_ci_wiring", []):
        if str(token) not in workflow_text:
            violations.append(f"ci_missing_token:{token}")

    if simulate_regression:
        violations.append("synthetic_regression=forced_failure_path")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.3-P2 deterministic match-engine kernel"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--extraction-module", default="")
    parser.add_argument("--kernel-module", default="")
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    contract_file = _resolve(repo_root, args.contract_file)
    contract = _read_json(contract_file)
    extraction_module = _resolve(
        repo_root,
        args.extraction_module
        or str(contract["authoritative_surfaces"]["extraction_module"]),
    )
    kernel_module = _resolve(
        repo_root,
        args.kernel_module or str(contract["authoritative_surfaces"]["kernel_module"]),
    )

    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=contract_file,
        workflow_file=_resolve(repo_root, args.workflow_file),
        extraction_module=extraction_module,
        kernel_module=kernel_module,
        simulate_regression=bool(args.simulate_regression),
    )
    print("b23_p2_match_engine_kernel_enforcer")
    if status != 0:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return status
    print("result=PASS")
    print(
        "enforcement=b23_p2_typed_extraction_concurrency_unmatched_handler_boundary_locked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
