#!/usr/bin/env python3
"""B2.1-P3 persisted projection read-surface lock enforcement."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
TASK_FILE = "backend/app/tasks/attribution.py"
API_FILE = "backend/app/api/attribution.py"
SCHEMA_FILE = "backend/app/schemas/attribution.py"
CONTRACT_FILE = "api-contracts/openapi/v1/attribution.yaml"
RUNTIME_PROOF_FILE = "backend/tests/integration/test_b21_p3_persistence_read_surface_runtime.py"
WORKFLOW_FILE = ".github/workflows/ci.yml"
REQUIRED_CHECKS_FILE = "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
REQUIRED_CONTEXT = "B2.1-P3 Persistence Authority + Minimal Read Surface"


def _resolve(repo_root: Path, raw: str) -> Path:
    value = Path(raw)
    if value.is_absolute():
        return value
    return (repo_root / value).resolve()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON payload must be an object: {path}")
    return payload


def _load_openapi(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(_read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"OpenAPI payload must be an object: {path}")
    return payload


def run_enforcement(
    *,
    repo_root: Path,
    task_file: Path,
    api_file: Path,
    schema_file: Path,
    contract_file: Path,
    runtime_proof_file: Path,
    workflow_file: Path,
    required_checks_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        task_file,
        api_file,
        schema_file,
        contract_file,
        runtime_proof_file,
        workflow_file,
        required_checks_file,
    )
    for file_path in required_files:
        if not file_path.exists():
            violations.append(f"missing_required_file:{file_path}")
    if violations:
        return 1, violations

    task_text = _read_text(task_file)
    api_text = _read_text(api_file)
    schema_text = _read_text(schema_file)
    contract_text = _read_text(contract_file)
    contract_doc = _load_openapi(contract_file)
    runtime_text = _read_text(runtime_proof_file)
    workflow_text = _read_text(workflow_file)
    required_checks = _read_json(required_checks_file)

    required_task_tokens = (
        "recompute_job_id: UUID",
        "CAST(:recompute_job_ids AS uuid[])",
        "recompute_job_id = EXCLUDED.recompute_job_id",
        '"recompute_job_ids": []',
    )
    for token in required_task_tokens:
        if token not in task_text:
            violations.append(f"task_missing_token:{token}")

    required_api_tokens = (
        "required_query_parameters\": [\"model_type\", \"recompute_job_id\"]",
        "projection_row = (",
        "FROM attribution_recompute_jobs",
        "aa.recompute_job_id = :recompute_job_id",
        "aa.model_type = :model_type",
        "_CHANNEL_MAX_WINDOW_DAYS = 31",
        "allocation_ratio=ratio_str",
        "attribution_weight=ratio_str",
        "confidence_score=confidence_str",
        "ATTRIBUTION_WINDOW_OUT_OF_RANGE",
    )
    for token in required_api_tokens:
        if token not in api_text:
            violations.append(f"api_missing_token:{token}")

    forbidden_api_tokens = (
        "_resolve_channels_date_range(",
        "start_date: Annotated[date",
        "end_date: Annotated[date",
        "AND e.occurred_at >= :window_start\n              AND e.occurred_at < :window_end\n            GROUP BY aa.channel_code\n            ORDER BY revenue_cents DESC, aa.channel_code ASC\n            \"\"\"\n        ),\n        {\n            \"tenant_id\": str(tenant_id),\n            \"window_start\": window_start,\n            \"window_end\": window_end,",
    )
    for token in forbidden_api_tokens:
        if token in api_text:
            violations.append(f"api_forbidden_token_present:{token}")

    required_schema_tokens = (
        "class ChannelProjectionIdentity(BaseModel):",
        "allocation_ratio: Annotated[str",
        "attribution_weight: Annotated[str",
        "confidence_score: Annotated[str",
        "total_revenue_cents: Annotated[int",
    )
    for token in required_schema_tokens:
        if token not in schema_text:
            violations.append(f"schema_missing_token:{token}")

    required_contract_tokens = (
        "ChannelProjectionIdentity:",
        "allocation_ratio:",
        "attribution_weight:",
        "pattern: '^(0|1)\\.\\d{5}$'",
        "pattern: '^(0|1)\\.\\d{3}$'",
    )
    for token in required_contract_tokens:
        if token not in contract_text:
            violations.append(f"contract_missing_token:{token}")

    if not re.search(r"(?m)^\s*-\s+name:\s+model_type\s*$", contract_text):
        violations.append("contract_missing_token:- name: model_type")
    if not re.search(r"(?m)^\s*-\s+name:\s+recompute_job_id\s*$", contract_text):
        violations.append("contract_missing_token:- name: recompute_job_id")

    channels_get = (
        contract_doc.get("paths", {})
        .get("/api/attribution/channels", {})
        .get("get", {})
    )
    if not isinstance(channels_get, dict):
        violations.append("contract_missing_channels_get_operation")
        channels_get = {}

    parameters = channels_get.get("parameters", [])
    if not isinstance(parameters, list):
        violations.append("contract_channels_parameters_invalid")
        parameters = []

    query_params: dict[str, dict[str, Any]] = {}
    for item in parameters:
        if not isinstance(item, dict):
            continue
        if item.get("in") != "query":
            continue
        name = item.get("name")
        if isinstance(name, str):
            query_params[name] = item

    for required_query_param in ("model_type", "recompute_job_id"):
        param = query_params.get(required_query_param)
        if not isinstance(param, dict):
            violations.append(f"contract_missing_required_query_param:{required_query_param}")
            continue
        if param.get("required") is not True:
            violations.append(f"contract_query_param_not_required:{required_query_param}")

    for forbidden_query_param in ("start_date", "end_date"):
        if forbidden_query_param in query_params:
            violations.append(f"contract_forbidden_query_param_present:{forbidden_query_param}")

    required_runtime_tokens = (
        "test_b21_p3_channels_endpoint_reads_projection_without_recompute_and_preserves_decimal_strings",
        "test_b21_p3_cross_tenant_projection_identity_is_fail_closed",
        "test_b21_p3_projection_window_bound_exceeds_limit_fails_closed",
        "missing_shape.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY",
        "after_run_count == before_run_count",
    )
    for token in required_runtime_tokens:
        if token not in runtime_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    required_workflow_tokens = (
        "Enforce B2.1-P3 persistence read-surface lock",
        "Run B2.1-P3 persistence read-surface negative controls",
        "name: B2.1-P3 Persistence Authority + Minimal Read Surface",
        "Run B2.1-P3 persisted projection runtime proofs",
        "pytest backend/tests/integration/test_b21_p3_persistence_read_surface_runtime.py -q",
    )
    for token in required_workflow_tokens:
        if token not in workflow_text:
            violations.append(f"workflow_missing_token:{token}")

    required_contexts = required_checks.get("required_contexts", [])
    if not isinstance(required_contexts, list):
        violations.append("required_checks_required_contexts_invalid")
    elif REQUIRED_CONTEXT not in required_contexts:
        violations.append("required_checks_missing_b21_p3_context")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.1-P3 persisted projection authority and minimal read-surface lock."
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--task-file", default=TASK_FILE)
    parser.add_argument("--api-file", default=API_FILE)
    parser.add_argument("--schema-file", default=SCHEMA_FILE)
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--runtime-proof-file", default=RUNTIME_PROOF_FILE)
    parser.add_argument("--workflow-file", default=WORKFLOW_FILE)
    parser.add_argument("--required-checks-file", default=REQUIRED_CHECKS_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        sys.stdout.write(
            "b21_p3_persistence_read_surface_lock_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=forced_failure_path\n"
        )
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    status, violations = run_enforcement(
        repo_root=repo_root,
        task_file=_resolve(repo_root, args.task_file),
        api_file=_resolve(repo_root, args.api_file),
        schema_file=_resolve(repo_root, args.schema_file),
        contract_file=_resolve(repo_root, args.contract_file),
        runtime_proof_file=_resolve(repo_root, args.runtime_proof_file),
        workflow_file=_resolve(repo_root, args.workflow_file),
        required_checks_file=_resolve(repo_root, args.required_checks_file),
    )
    lines = ["b21_p3_persistence_read_surface_lock_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=projection_identity_bounded_read_and_decimal_transport_locked")
    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
