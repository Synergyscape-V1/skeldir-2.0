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


def _collect_call_target_name(call_node: ast.Call) -> str | None:
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _is_decimal_zero_call(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Name) or node.func.id != "Decimal":
        return False
    if not node.args:
        return False
    first = node.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value.strip() in {"0", "0.0", "0.00", "+0", "-0"}
    return False


def _is_zero_like(node: ast.AST, *, zero_names: set[str]) -> bool:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value == 0
        if isinstance(node.value, str):
            return node.value.strip() in {"0", "0.0", "0.00", "+0", "-0"}
        return False
    if isinstance(node, ast.Name):
        return node.id in zero_names
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_zero_like(node.operand, zero_names=zero_names)
    return _is_decimal_zero_call(node)


def _collect_zero_name_assignments(function_node: ast.FunctionDef) -> set[str]:
    zero_names: set[str] = set()
    for node in ast.walk(function_node):
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            if _is_zero_like(node.value, zero_names=zero_names):
                zero_names.add(node.targets[0].id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None and _is_zero_like(node.value, zero_names=zero_names):
                zero_names.add(node.target.id)
    return zero_names


def _is_zero_fallback_expression(node: ast.AST, *, zero_names: set[str]) -> bool:
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
        return any(_is_zero_like(value, zero_names=zero_names) for value in node.values)
    if isinstance(node, ast.IfExp):
        return _is_zero_like(node.orelse, zero_names=zero_names)
    return False


def _semantic_zero_fallback_violations(extraction_text: str) -> list[str]:
    tree = ast.parse(extraction_text)
    violations: list[str] = []
    for function_node in (
        node for node in tree.body if isinstance(node, ast.FunctionDef)
    ):
        zero_names = _collect_zero_name_assignments(function_node)
        for node in ast.walk(function_node):
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or):
                if any(_is_zero_like(value, zero_names=zero_names) for value in node.values):
                    violations.append(
                        f"semantic_zero_fallback_bool_or:{function_node.name}:{ast.unparse(node)}"
                    )
            elif isinstance(node, ast.IfExp):
                if _is_zero_like(node.orelse, zero_names=zero_names):
                    violations.append(
                        f"semantic_zero_fallback_ternary:{function_node.name}:{ast.unparse(node)}"
                    )
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                    if len(node.args) >= 2 and _is_zero_like(
                        node.args[1], zero_names=zero_names
                    ):
                        violations.append(
                            f"semantic_zero_fallback_dict_get_default:{function_node.name}:{ast.unparse(node)}"
                        )

                for keyword in node.keywords:
                    if keyword.arg in {"default", "fallback", "default_amount"} and _is_zero_like(
                        keyword.value, zero_names=zero_names
                    ):
                        violations.append(
                            f"semantic_zero_fallback_keyword_default:{function_node.name}:{ast.unparse(node)}"
                        )

                call_name = ast.unparse(node.func).lower()
                if "zero" in call_name and any(
                    token in call_name for token in ("coerce", "normalize", "fallback")
                ):
                    violations.append(
                        f"semantic_zero_fallback_helper:{function_node.name}:{ast.unparse(node)}"
                    )

                if isinstance(node.func, ast.Name) and node.func.id in {"int", "Decimal"}:
                    if node.args and _is_zero_fallback_expression(
                        node.args[0], zero_names=zero_names
                    ):
                        violations.append(
                            f"semantic_zero_fallback_pre_numeric_conversion:{function_node.name}:{ast.unparse(node)}"
                        )

    return sorted(set(violations))


def _function_map(module_tree: ast.Module) -> dict[str, ast.FunctionDef]:
    functions: dict[str, ast.FunctionDef] = {}
    for node in module_tree.body:
        if isinstance(node, ast.FunctionDef):
            functions[node.name] = node
    return functions


def _is_model_dump_get_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr != "get":
        return False
    owner = node.func.value
    if not isinstance(owner, ast.Call):
        return False
    if not isinstance(owner.func, ast.Attribute):
        return False
    return owner.func.attr == "model_dump"


def _is_try_handler_fail_closed(handler: ast.ExceptHandler) -> bool:
    if not handler.body:
        return False
    return all(isinstance(stmt, ast.Raise) for stmt in handler.body)


def _collect_negative_control_names(
    runtime_test_tree: ast.Module,
    explicit_names: set[str],
    prefix_allowlist: tuple[str, ...],
) -> set[str]:
    names = set(explicit_names)
    for node in runtime_test_tree.body:
        if isinstance(node, ast.FunctionDef) and any(
            node.name.startswith(prefix) for prefix in prefix_allowlist
        ):
            names.add(node.name)
    return names


def _enforce_authority_extraction_allowlist(
    *,
    extraction_tree: ast.Module,
    extraction_text: str,
    strict_cfg: dict[str, Any],
    violations: list[str],
) -> None:
    root_functions = strict_cfg.get("root_functions", [])
    if not isinstance(root_functions, list) or not all(
        isinstance(name, str) for name in root_functions
    ):
        violations.append("contract_strict_allowlist_root_functions_invalid")
        return

    allowed_node_types = strict_cfg.get("allowed_ast_node_types", [])
    if not isinstance(allowed_node_types, list) or not all(
        isinstance(name, str) for name in allowed_node_types
    ):
        violations.append("contract_strict_allowlist_allowed_ast_node_types_invalid")
        return
    allowed_node_types_set = set(allowed_node_types)

    allowed_calls = strict_cfg.get("allowed_call_names", [])
    if not isinstance(allowed_calls, list) or not all(
        isinstance(name, str) for name in allowed_calls
    ):
        violations.append("contract_strict_allowlist_allowed_call_names_invalid")
        return
    allowed_calls_set = set(allowed_calls)

    forbidden_calls = strict_cfg.get("forbidden_call_names", [])
    if not isinstance(forbidden_calls, list) or not all(
        isinstance(name, str) for name in forbidden_calls
    ):
        violations.append("contract_strict_allowlist_forbidden_call_names_invalid")
        return
    forbidden_calls_set = set(forbidden_calls)

    function_defs = _function_map(extraction_tree)
    missing_roots = [name for name in root_functions if name not in function_defs]
    for name in missing_roots:
        violations.append(f"authority_allowlist_missing_root_function:{name}")
    if missing_roots:
        return

    to_visit = list(root_functions)
    visited: set[str] = set()
    while to_visit:
        function_name = to_visit.pop()
        if function_name in visited:
            continue
        visited.add(function_name)
        function_node = function_defs[function_name]

        for node in ast.walk(function_node):
            node_type_name = type(node).__name__
            if node_type_name not in allowed_node_types_set:
                violations.append(
                    f"authority_allowlist_non_allowlisted_ast:{function_name}:{node_type_name}"
                )

            if isinstance(node, ast.Call):
                call_target = _collect_call_target_name(node)
                if call_target in forbidden_calls_set:
                    violations.append(
                        f"authority_allowlist_forbidden_call:{function_name}:{call_target}:{ast.unparse(node)}"
                    )
                if _is_model_dump_get_call(node):
                    violations.append(
                        f"authority_allowlist_forbidden_model_dump_get:{function_name}:{ast.unparse(node)}"
                    )
                if isinstance(node.func, ast.Attribute):
                    owner = node.func.value
                    if isinstance(owner, ast.Attribute) and owner.attr == "__dict__":
                        violations.append(
                            f"authority_allowlist_forbidden_dunder_dict_access:{function_name}:{ast.unparse(node)}"
                        )
                if call_target is not None and call_target in function_defs:
                    to_visit.append(call_target)
                elif call_target is not None and call_target not in allowed_calls_set:
                    violations.append(
                        f"authority_allowlist_unresolved_or_unallowlisted_call:{function_name}:{call_target}:{ast.unparse(node)}"
                    )
                elif call_target is None:
                    violations.append(
                        f"authority_allowlist_dynamic_call_target:{function_name}:{ast.unparse(node)}"
                    )

                if call_target == "getattr" and len(node.args) >= 3:
                    if _is_zero_like(node.args[2], zero_names=set()):
                        violations.append(
                            f"authority_allowlist_forbidden_getattr_zero_default:{function_name}:{ast.unparse(node)}"
                        )

            if isinstance(node, ast.Attribute) and node.attr == "__dict__":
                violations.append(
                    f"authority_allowlist_forbidden_dunder_dict_access:{function_name}:{ast.unparse(node)}"
                )

            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    if not _is_try_handler_fail_closed(handler):
                        violations.append(
                            f"authority_allowlist_exception_fallback_forbidden:{function_name}:{ast.unparse(node)}"
                        )

    # Preserve legacy semantic family checks as additional invariant protection.
    for fallback_violation in _semantic_zero_fallback_violations(extraction_text):
        violations.append(fallback_violation)


def _enforce_runtime_db_proof_anti_spoof(
    *,
    runtime_test_tree: ast.Module,
    runtime_test_text: str,
    anti_spoof_cfg: dict[str, Any],
    violations: list[str],
) -> None:
    forbidden_markers = anti_spoof_cfg.get("forbidden_tokens", [])
    if not isinstance(forbidden_markers, list) or not all(
        isinstance(token, str) for token in forbidden_markers
    ):
        violations.append("contract_runtime_db_proof_anti_spoof_forbidden_tokens_invalid")
        return
    forbidden_marker_tuple = tuple(forbidden_markers)

    allowed_negative_control_tests = anti_spoof_cfg.get("allowed_negative_control_tests", [])
    if not isinstance(allowed_negative_control_tests, list) or not all(
        isinstance(name, str) for name in allowed_negative_control_tests
    ):
        violations.append("contract_runtime_db_proof_anti_spoof_allowed_tests_invalid")
        return

    allowed_negative_control_prefixes = anti_spoof_cfg.get(
        "allowed_negative_control_test_prefixes", []
    )
    if not isinstance(allowed_negative_control_prefixes, list) or not all(
        isinstance(prefix, str) for prefix in allowed_negative_control_prefixes
    ):
        violations.append("contract_runtime_db_proof_anti_spoof_allowed_prefixes_invalid")
        return

    allowed_names = _collect_negative_control_names(
        runtime_test_tree,
        explicit_names=set(allowed_negative_control_tests),
        prefix_allowlist=tuple(allowed_negative_control_prefixes),
    )

    function_map = _function_map(runtime_test_tree)
    for function_name, function_node in function_map.items():
        function_source = ast.get_source_segment(runtime_test_text, function_node) or ""
        has_forbidden = any(marker in function_source for marker in forbidden_marker_tuple)
        if has_forbidden and function_name not in allowed_names:
            violations.append(
                f"runtime_db_proof_anti_spoof_forbidden_token_outside_negative_control:{function_name}"
            )
        if has_forbidden and function_name in allowed_names:
            # Negative controls must be fail-oriented.
            if "pytest.raises" not in function_source and "assert result.returncode != 0" not in function_source:
                violations.append(
                    f"runtime_db_proof_anti_spoof_negative_control_must_assert_failure:{function_name}"
                )


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    workflow_file: Path,
    extraction_module: Path,
    kernel_module: Path,
    failure_boundary_module: Path,
    webhook_module: Path,
    runtime_tests_module: Path,
    enforcer_tests_module: Path,
    simulate_regression: bool,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    for required in (
        contract_file,
        workflow_file,
        extraction_module,
        kernel_module,
        failure_boundary_module,
        webhook_module,
        runtime_tests_module,
        enforcer_tests_module,
    ):
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    contract = _read_json(contract_file)
    extraction_text = _read_text(extraction_module)
    kernel_text = _read_text(kernel_module)
    failure_boundary_text = _read_text(failure_boundary_module)
    webhook_text = _read_text(webhook_module)
    workflow_text = _read_text(workflow_file)
    runtime_tests_text = _read_text(runtime_tests_module)
    enforcer_tests_text = _read_text(enforcer_tests_module)
    extraction_tree = ast.parse(extraction_text)
    runtime_tests_tree = ast.parse(runtime_tests_text)

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
        "amount_minor=int(payload.gross_captured_minor)",
    )
    for token in required_extraction_tokens:
        if token not in extraction_text:
            violations.append(f"extraction_missing_token:{token}")

    if "amount_minor=int(payload.net_after_fees_minor" in extraction_text:
        violations.append("stripe_net_after_fees_used_as_canonical_amount")

    strict_cfg = contract.get("strict_authority_extraction_enforcement")
    if not isinstance(strict_cfg, dict):
        violations.append("contract_missing_strict_authority_extraction_enforcement")
    else:
        _enforce_authority_extraction_allowlist(
            extraction_tree=extraction_tree,
            extraction_text=extraction_text,
            strict_cfg=strict_cfg,
            violations=violations,
        )

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
        "classify_b23_failure_boundary",
        "VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY",
        "UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE",
    )
    for token in required_kernel_tokens:
        if token not in kernel_text:
            violations.append(f"kernel_missing_token:{token}")

    required_failure_boundary_tokens = (
        "class B23FailureBoundaryClass",
        "UNAUTHENTICATED_MALFORMED_WEBHOOK",
        "AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD",
        "VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY",
        "UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE",
        "classify_b23_failure_boundary",
    )
    for token in required_failure_boundary_tokens:
        if token not in failure_boundary_text:
            violations.append(f"failure_boundary_missing_token:{token}")

    required_webhook_boundary_tokens = (
        "B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD",
        "B23FailureBoundaryClass.UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE",
        "b23_failure_boundary",
    )
    for token in required_webhook_boundary_tokens:
        if token not in webhook_text:
            violations.append(f"webhook_boundary_missing_token:{token}")

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
    for token in contract.get("required_ci_runtime_db_proof_lock", []):
        if str(token) not in workflow_text:
            violations.append(f"ci_missing_runtime_db_proof_token:{token}")

    anti_spoof_cfg = contract.get("runtime_db_proof_anti_spoof_governance")
    if not isinstance(anti_spoof_cfg, dict):
        violations.append("contract_missing_runtime_db_proof_anti_spoof_governance")
    else:
        _enforce_runtime_db_proof_anti_spoof(
            runtime_test_tree=runtime_tests_tree,
            runtime_test_text=runtime_tests_text,
            anti_spoof_cfg=anti_spoof_cfg,
            violations=violations,
        )

    # Ensure enforcer negative controls explicitly include anti-spoof and obfuscation families.
    for required_test_token in contract.get("required_enforcer_negative_control_tokens", []):
        if str(required_test_token) not in enforcer_tests_text:
            violations.append(
                f"enforcer_negative_control_missing_token:{required_test_token}"
            )

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
    parser.add_argument("--failure-boundary-module", default="")
    parser.add_argument("--webhook-module", default="")
    parser.add_argument("--runtime-tests-module", default="")
    parser.add_argument("--enforcer-tests-module", default="")
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
    failure_boundary_module = _resolve(
        repo_root,
        args.failure_boundary_module
        or str(contract["authoritative_surfaces"]["failure_boundary_module"]),
    )
    webhook_module = _resolve(
        repo_root,
        args.webhook_module
        or str(contract["authoritative_surfaces"]["webhook_module"]),
    )
    runtime_tests_module = _resolve(
        repo_root,
        args.runtime_tests_module
        or str(contract["authoritative_surfaces"]["runtime_tests"]),
    )
    enforcer_tests_module = _resolve(
        repo_root,
        args.enforcer_tests_module
        or str(contract["authoritative_surfaces"]["enforcer_tests"]),
    )

    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=contract_file,
        workflow_file=_resolve(repo_root, args.workflow_file),
        extraction_module=extraction_module,
        kernel_module=kernel_module,
        failure_boundary_module=failure_boundary_module,
        webhook_module=webhook_module,
        runtime_tests_module=runtime_tests_module,
        enforcer_tests_module=enforcer_tests_module,
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
        "enforcement=b23_p2_typed_extraction_concurrency_unmatched_handler_boundary_and_runtime_db_lock"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
