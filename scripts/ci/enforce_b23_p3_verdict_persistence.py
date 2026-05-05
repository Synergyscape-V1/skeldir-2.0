#!/usr/bin/env python3
"""Enforce B2.3-P3 verdict persistence and strict read contract parity."""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_p3_verdict_persistence.main.json"
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


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"yaml_payload_not_object:{path}")
    return payload


def _schema_ref_name(schema: dict[str, Any]) -> str | None:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return None
    return ref.rsplit("/", 1)[-1]


def _resolve_ref(schema: dict[str, Any], *, root: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not isinstance(ref, str):
        return schema
    name = ref.rsplit("/", 1)[-1]
    if ref.startswith("#/components/schemas/"):
        return root["components"]["schemas"][name]
    if ref.startswith("#/$defs/"):
        return root["$defs"][name]
    raise ValueError(f"unsupported_ref:{ref}")


def _nullable_type(schema: dict[str, Any]) -> tuple[str | None, bool]:
    raw_type = schema.get("type")
    if isinstance(raw_type, list):
        non_null = [value for value in raw_type if value != "null"]
        return (str(non_null[0]) if non_null else None, "null" in raw_type)
    if isinstance(raw_type, str):
        return raw_type, False
    any_of = schema.get("anyOf")
    if isinstance(any_of, list):
        nullable = any(item.get("type") == "null" for item in any_of if isinstance(item, dict))
        non_null = [
            item
            for item in any_of
            if isinstance(item, dict) and item.get("type") != "null"
        ]
        if len(non_null) == 1:
            resolved = non_null[0]
            if "$ref" in resolved:
                return "ref", nullable
            return str(resolved.get("type")) if resolved.get("type") else None, nullable
    if "$ref" in schema:
        return "ref", False
    return None, False


def _enum_values(schema: dict[str, Any], *, root: dict[str, Any]) -> set[str] | None:
    resolved = _resolve_ref(schema, root=root) if "$ref" in schema else schema
    enum_values = resolved.get("enum")
    if isinstance(enum_values, list):
        return {str(value) for value in enum_values}
    if "const" in resolved:
        return {str(resolved["const"])}
    return None


def _compare_schema(
    *,
    openapi_schema: dict[str, Any],
    pydantic_schema: dict[str, Any],
    openapi_root: dict[str, Any],
    pydantic_root: dict[str, Any],
    path: str,
    violations: list[str],
) -> None:
    openapi_schema = _resolve_ref(openapi_schema, root=openapi_root)
    pydantic_schema = _resolve_ref(pydantic_schema, root=pydantic_root)

    openapi_enum = _enum_values(openapi_schema, root=openapi_root)
    pydantic_enum = _enum_values(pydantic_schema, root=pydantic_root)
    if openapi_enum is not None or pydantic_enum is not None:
        if openapi_enum != pydantic_enum:
            violations.append(f"schema_enum_mismatch:{path}:{openapi_enum}!={pydantic_enum}")
        return

    openapi_type, openapi_nullable = _nullable_type(openapi_schema)
    pydantic_type, pydantic_nullable = _nullable_type(pydantic_schema)
    if openapi_type == "integer" and pydantic_type == "number":
        violations.append(f"schema_money_integer_drift:{path}")
    if openapi_type != pydantic_type:
        # UUID/date-time strings and refs still normalize to string/ref.
        violations.append(f"schema_type_mismatch:{path}:{openapi_type}!={pydantic_type}")
    if openapi_nullable != pydantic_nullable:
        violations.append(f"schema_nullable_mismatch:{path}")

    if openapi_type == "object":
        if openapi_schema.get("additionalProperties") is not False:
            violations.append(f"openapi_additional_properties_not_false:{path}")
        if pydantic_schema.get("additionalProperties") is not False:
            violations.append(f"pydantic_additional_properties_not_false:{path}")
        openapi_required = set(openapi_schema.get("required") or [])
        pydantic_required = set(pydantic_schema.get("required") or [])
        if openapi_required != pydantic_required:
            required_delta = (
                f"{sorted(openapi_required)}!={sorted(pydantic_required)}"
            )
            violations.append(
                f"schema_required_mismatch:{path}:{required_delta}"
            )
        openapi_props = openapi_schema.get("properties") or {}
        pydantic_props = pydantic_schema.get("properties") or {}
        if set(openapi_props) != set(pydantic_props):
            props_delta = f"{sorted(openapi_props)}!={sorted(pydantic_props)}"
            violations.append(
                f"schema_properties_mismatch:{path}:{props_delta}"
            )
            return
        for prop_name in sorted(openapi_props):
            _compare_schema(
                openapi_schema=openapi_props[prop_name],
                pydantic_schema=pydantic_props[prop_name],
                openapi_root=openapi_root,
                pydantic_root=pydantic_root,
                path=f"{path}.{prop_name}",
                violations=violations,
            )
    elif openapi_type == "array":
        openapi_items = openapi_schema.get("items")
        pydantic_items = pydantic_schema.get("items")
        if not isinstance(openapi_items, dict) or not isinstance(pydantic_items, dict):
            violations.append(f"schema_array_items_missing:{path}")
            return
        _compare_schema(
            openapi_schema=openapi_items,
            pydantic_schema=pydantic_items,
            openapi_root=openapi_root,
            pydantic_root=pydantic_root,
            path=f"{path}[]",
            violations=violations,
        )


def _pydantic_model_schema(model_name: str) -> dict[str, Any]:
    module = importlib.import_module("app.schemas.revenue_verification")
    model = getattr(module, model_name)
    schema = model.model_json_schema(ref_template="#/$defs/{model}")
    if not isinstance(schema, dict):
        raise ValueError(f"pydantic_schema_not_object:{model_name}")
    return schema


def _validate_read_surface(
    *,
    contract: dict[str, Any],
    openapi: dict[str, Any],
    api_text: str,
    schema_text: str,
    frontend_text: str,
    violations: list[str],
) -> None:
    paths = openapi.get("paths") or {}
    for route_path, operation_id in contract["read_surface"]["required_paths"].items():
        route = paths.get(route_path)
        if not isinstance(route, dict) or "get" not in route:
            violations.append(f"openapi_path_missing:{route_path}")
            continue
        observed_operation_id = route["get"].get("operationId")
        if observed_operation_id != operation_id:
            operation_delta = f"{observed_operation_id}!={operation_id}"
            violations.append(
                f"openapi_operation_id_mismatch:{route_path}:{operation_delta}"
            )
        if operation_id not in api_text:
            violations.append(f"api_operation_id_missing:{operation_id}")
        if operation_id not in frontend_text:
            violations.append(f"frontend_operation_id_missing:{operation_id}")

    for model_name in contract["read_surface"]["required_response_models"]:
        if f"class {model_name}" not in schema_text:
            violations.append(f"response_model_missing:{model_name}")
        if f"response_model={model_name}" not in api_text:
            violations.append(f"api_response_model_missing:{model_name}")

    for enum_value in contract["read_surface"]["required_status_enum_values"]:
        if enum_value not in schema_text:
            violations.append(f"backend_status_enum_missing:{enum_value}")
        if enum_value not in frontend_text:
            violations.append(f"frontend_status_enum_missing:{enum_value}")

    for field_name in (
        contract["read_surface"]["required_match_fields"]
        + contract["read_surface"]["required_exception_fields"]
    ):
        if field_name not in schema_text:
            violations.append(f"backend_field_missing:{field_name}")
        if field_name not in frontend_text:
            violations.append(f"frontend_field_missing:{field_name}")

    forbidden_type_tokens = (
        ": dict",
        "dict[",
        "Any",
        "extra=\"ignore\"",
        "extra='ignore'",
        "extra=\"allow\"",
        "extra='allow'",
    )
    for token in forbidden_type_tokens:
        if token in schema_text:
            violations.append(f"strict_response_model_forbidden_token:{token}")
    if schema_text.count('ConfigDict(extra="forbid")') < 4:
        violations.append("strict_response_model_missing_extra_forbid")

    operation_to_schema = {
        "getB23MatchVerdict": "B23MatchVerdictDetailResponse",
        "listB23ExceptionRecords": "B23ExceptionListResponse",
        "getB23ExceptionRecord": "B23ExceptionRecordResponse",
    }
    for route_path, operation_id in contract["read_surface"]["required_paths"].items():
        response_schema = (
            paths[route_path]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        )
        model_name = operation_to_schema[operation_id]
        pydantic_schema = _pydantic_model_schema(model_name)
        _compare_schema(
            openapi_schema=response_schema,
            pydantic_schema=pydantic_schema,
            openapi_root=openapi,
            pydantic_root=pydantic_schema,
            path=model_name,
            violations=violations,
        )


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    workflow_file: Path,
    simulate_regression: bool,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    contract = _read_json(contract_file)
    surfaces = contract.get("authoritative_surfaces", {})
    required_files = [contract_file, workflow_file]
    required_files.extend(_resolve(repo_root, str(path)) for path in surfaces.values())
    for path in required_files:
        if not path.exists():
            violations.append(f"missing_file:{path}")
    if violations:
        return 1, violations

    if str(repo_root / "backend") not in sys.path:
        sys.path.insert(0, str(repo_root / "backend"))

    migration_text = _read_text(_resolve(repo_root, surfaces["phase_exception_migration"]))
    canonical_schema_text = _read_text(_resolve(repo_root, surfaces["canonical_schema"]))
    kernel_text = _read_text(_resolve(repo_root, surfaces["kernel_module"]))
    transition_text = _read_text(_resolve(repo_root, surfaces["state_transition_module"]))
    task_text = _read_text(_resolve(repo_root, surfaces["task_module"]))
    beat_text = _read_text(_resolve(repo_root, surfaces["beat_schedule_module"]))
    celery_text = _read_text(_resolve(repo_root, surfaces["celery_app_module"]))
    api_text = _read_text(_resolve(repo_root, surfaces["api_module"]))
    schema_text = _read_text(_resolve(repo_root, surfaces["schema_module"]))
    frontend_text = _read_text(_resolve(repo_root, surfaces["frontend_generated_types"]))
    workflow_text = _read_text(workflow_file)
    runtime_tests_text = _read_text(_resolve(repo_root, surfaces["runtime_tests"]))

    if contract.get("contract_id") != "b23.p3.verdict_persistence.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-P3":
        violations.append("contract_phase_mismatch")

    for task_name in contract["state_transition_registration"]["required_task_names"]:
        if task_name not in task_text and task_name not in celery_text:
            violations.append(f"transition_task_missing:{task_name}")
    for schedule_key in contract["state_transition_registration"]["required_beat_schedule_keys"]:
        if schedule_key not in beat_text:
            violations.append(f"beat_schedule_key_missing:{schedule_key}")
    required_transition_functions = contract["state_transition_registration"][
        "required_transition_functions"
    ]
    for function_name in required_transition_functions:
        if f"def {function_name}" not in transition_text:
            violations.append(f"transition_function_missing:{function_name}")
    for constant in contract["state_transition_registration"]["required_timing_constants"]:
        if constant not in transition_text and constant not in task_text:
            violations.append(f"transition_timing_constant_missing:{constant}")
    for token in contract["state_transition_registration"]["required_postgres_concurrency_tokens"]:
        if token not in transition_text:
            violations.append(f"transition_postgres_concurrency_token_missing:{token}")
    if "timedelta(minutes=30)" in transition_text or "timedelta(hours=24)" in transition_text:
        violations.append("transition_hardcoded_timing_literal_detected")

    gross_expression = contract["basis_separation"]["discrepancy_amount_constraint_expression"]
    if gross_expression not in migration_text.replace("\n", " "):
        violations.append("migration_gross_discrepancy_constraint_expression_missing")
    constraint_window_match = re.search(
        r"ck_b23_match_verdicts_discrepancy_amount_consistency.*?CHECK\s*\((.*?)\)",
        canonical_schema_text,
        flags=re.DOTALL,
    )
    if not constraint_window_match:
        violations.append("canonical_discrepancy_constraint_missing")
    else:
        constraint_window = constraint_window_match.group(0)
        forbidden_operand = contract["basis_separation"][
            "forbidden_discrepancy_constraint_operand"
        ]
        if forbidden_operand in constraint_window:
            violations.append("canonical_discrepancy_constraint_uses_net_verified")
        if "canonical_captured_gross_amount_minor" not in constraint_window:
            violations.append("canonical_discrepancy_constraint_missing_captured_gross")
    correction_column = contract["basis_separation"]["gross_capture_correction_column"]
    if correction_column not in canonical_schema_text:
        violations.append("gross_capture_correction_column_missing_canonical_schema")
    for token in contract["basis_separation"]["required_kernel_tokens"]:
        if token not in kernel_text:
            violations.append(f"kernel_basis_token_missing:{token}")
    net_discrepancy_operand = (
        "canonical_expected_gross_amount_minor - canonical_net_verified_amount_minor"
    )
    if net_discrepancy_operand in kernel_text:
        violations.append("kernel_discrepancy_uses_net_verified")

    exception_contract = contract["exception_persistence"]
    for token_name in (
        "base_table",
        "one_open_exception_index",
        "duplicate_resolution_code",
        "required_resolution_constraint",
    ):
        token = exception_contract[token_name]
        if token not in migration_text and token not in canonical_schema_text:
            violations.append(f"exception_persistence_token_missing:{token}")

    openapi = _read_yaml(_resolve(repo_root, surfaces["openapi_contract"]))
    _validate_read_surface(
        contract=contract,
        openapi=openapi,
        api_text=api_text,
        schema_text=schema_text,
        frontend_text=frontend_text,
        violations=violations,
    )

    for token in contract["required_ci_wiring"]:
        if token not in workflow_text:
            violations.append(f"ci_missing_token:{token}")
    for forbidden in contract["phase_boundary_forbidden_tokens"]:
        for surface_name, text_payload in {
            "api": api_text,
            "kernel": kernel_text,
            "transition": transition_text,
            "runtime_tests": runtime_tests_text,
        }.items():
            if forbidden in text_payload:
                violations.append(f"phase_boundary_forbidden_token:{surface_name}:{forbidden}")

    if simulate_regression:
        violations.append("synthetic_regression=forced_failure_path")
    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=_resolve(repo_root, args.contract_file),
        workflow_file=_resolve(repo_root, args.workflow_file),
        simulate_regression=bool(args.simulate_regression),
    )
    print("b23_p3_verdict_persistence_enforcer")
    if status != 0:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return status
    print("result=PASS")
    print("enforcement=b23_p3_verdict_persistence_transition_read_contract_parity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
