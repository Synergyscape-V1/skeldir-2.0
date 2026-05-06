#!/usr/bin/env python3
"""Enforce B2.3-P4 queue isolation and performance semantics lock."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_p4_queue_performance.main.json"
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


def _worker_queue_sets(procfile_text: str, compose_text: str) -> dict[str, set[str]]:
    workers: dict[str, set[str]] = {}
    for line in procfile_text.splitlines():
        if not line.strip() or line.strip().startswith("#") or ":" not in line:
            continue
        name, command = line.split(":", 1)
        match = re.search(r"--queues=([^\s]+)", command)
        if match:
            workers[name.strip()] = {part.strip() for part in match.group(1).split(",")}
    service_name: str | None = None
    for line in compose_text.splitlines():
        if re.match(r"^  [A-Za-z0-9_-]+:\s*$", line):
            service_name = line.strip()[:-1]
        match = re.search(r"--queues=([^\s]+)", line)
        if service_name and match:
            workers[f"compose:{service_name}"] = {
                part.strip() for part in match.group(1).split(",")
            }
    return workers


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

    texts = {
        name: _read_text(_resolve(repo_root, str(path)))
        for name, path in surfaces.items()
    }
    workflow_text = _read_text(workflow_file)

    if contract.get("contract_id") != "b23.p4.queue_performance.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-P4":
        violations.append("contract_phase_mismatch")

    queue_name = contract["queue_isolation"]["canonical_queue_name"]
    queue_constant = contract["queue_isolation"]["canonical_queue_constant"]
    if f'{queue_constant} = "{queue_name}"' not in texts["queue_module"]:
        violations.append("canonical_b23_queue_constant_missing")
    if f"Queue({queue_constant}," not in texts["celery_app_module"]:
        violations.append("celery_queue_declaration_missing")
    expected_route = (
        "'app.tasks.revenue_verification.*': "
        "{'queue': QUEUE_B23_MATCH_ENGINE, 'routing_key': f'{QUEUE_B23_MATCH_ENGINE}.task'}"
    )
    if expected_route not in texts["celery_app_module"]:
        violations.append("b23_task_route_not_isolated")

    for task_name in contract["queue_isolation"]["required_b23_task_names"]:
        if task_name not in texts["task_module"]:
            violations.append(f"b23_task_name_missing:{task_name}")
    if f"--queues={queue_name}" not in texts["procfile"]:
        violations.append("procfile_b23_worker_missing")
    if f"--queues={queue_name}" not in texts["e2e_compose"]:
        violations.append("compose_b23_worker_missing")
    workers = _worker_queue_sets(texts["procfile"], texts["e2e_compose"])
    forbidden_adjacent = set(contract["queue_isolation"]["forbidden_adjacent_queues"])
    b23_workers = {name: queues for name, queues in workers.items() if queue_name in queues}
    if not b23_workers:
        violations.append("no_b23_worker_topology_found")
    for worker_name, queues in b23_workers.items():
        overlap = (queues - {queue_name}) & forbidden_adjacent
        if queues != {queue_name} or overlap:
            violations.append(f"b23_worker_forbidden_queue_overlap:{worker_name}:{sorted(queues)}")

    for setting in contract["db_pool_budget"]["required_settings"]:
        if setting not in texts["config_module"]:
            violations.append(f"b23_db_pool_setting_missing:{setting}")
    for token in (
        contract["db_pool_budget"]["dedicated_engine_name"],
        contract["db_pool_budget"]["dedicated_session_name"],
        "pool_timeout=settings.B23_DATABASE_POOL_TIMEOUT_SECONDS",
        "SET LOCAL statement_timeout",
        "SET LOCAL lock_timeout",
    ):
        if token not in texts["db_session_module"]:
            violations.append(f"b23_db_pool_token_missing:{token}")
    if "b23_worker_demand > b23_pool_capacity" not in texts["config_module"]:
        violations.append("b23_pool_budget_math_missing")

    batch_text = texts["batch_engine_module"]
    micro_batch = contract["micro_batch"]
    if f"{micro_batch['chunk_size_constant']} = {micro_batch['chunk_size']}" not in batch_text:
        violations.append("batch_chunk_size_constant_mismatch")
    if f"{micro_batch['background_cardinality_constant']} = {micro_batch['background_cardinality']:_}" not in batch_text:
        violations.append("background_cardinality_constant_mismatch")
    for token in micro_batch["required_tokens"]:
        if token not in batch_text:
            violations.append(f"batch_required_token_missing:{token}")
    for token in micro_batch["forbidden_tokens"]:
        if token in batch_text:
            violations.append(f"batch_forbidden_token_present:{token}")

    schema_text = texts["canonical_schema"]
    migration_text = texts["p4_migration"]
    for index_name in contract["telemetry"]["required_indexes"]:
        if index_name not in schema_text or index_name not in migration_text:
            violations.append(f"telemetry_index_missing:{index_name}")
    for sql_surface in ("match_rate_sql", "dlq_depth_sql", "webhook_failure_sql"):
        sql_text = texts[sql_surface]
        if "SELECT" not in sql_text.upper():
            violations.append(f"telemetry_sql_not_select:{sql_surface}")
        if sql_surface != "dlq_depth_sql" and "tenant_id" not in sql_text:
            violations.append(f"telemetry_sql_missing_tenant_predicate:{sql_surface}")
    if "ingestion_status = 'failed'" not in texts["webhook_failure_sql"]:
        violations.append("webhook_failure_sql_missing_failure_predicate")
    if "status IN ('pending', 'in_progress')" not in texts["dlq_depth_sql"]:
        violations.append("dlq_depth_sql_missing_open_status_predicate")

    for token in contract["required_ci_wiring"]:
        if token not in workflow_text:
            violations.append(f"ci_missing_token:{token}")
    for forbidden in contract["phase_boundary_forbidden_tokens"]:
        for surface_name in ("batch_engine_module", "task_module", "runtime_tests"):
            if forbidden in texts[surface_name].lower():
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
    print("b23_p4_queue_performance_enforcer")
    if status != 0:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return status
    print("result=PASS")
    print("enforcement=queue_pool_microbatch_planner_telemetry_lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
