#!/usr/bin/env python3
"""B1.4-P3 attribution locality structural enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTEXT = "B1.4 P3 Attribution Locality Proofs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_enforcement(
    *,
    ci_workflow_file: Path,
    required_checks_file: Path,
    worker_file: Path,
    webhooks_file: Path,
    event_service_file: Path,
    export_file: Path,
    runtime_proof_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        ci_workflow_file,
        required_checks_file,
        worker_file,
        webhooks_file,
        event_service_file,
        export_file,
        runtime_proof_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    workflow_text = _read(ci_workflow_file)
    checks_contract = _load_json(required_checks_file)
    worker_text = _read(worker_file)
    webhooks_text = _read(webhooks_file)
    event_service_text = _read(event_service_file)
    export_text = _read(export_file)
    runtime_proof_text = _read(runtime_proof_file)

    if REQUIRED_CONTEXT not in workflow_text:
        violations.append(f"missing_required_context_in_workflow:{REQUIRED_CONTEXT}")

    contexts = checks_contract.get("required_contexts", [])
    if REQUIRED_CONTEXT not in contexts:
        violations.append(f"missing_required_context_in_contract:{REQUIRED_CONTEXT}")

    required_worker_tokens = (
        "ALLOWED_BOUNDED_TELEMETRY_KEYS",
        "_resolve_active_session_scopes(",
        "FROM session_authority sa",
        "session locality violation: requested session scope is stale or invalidated",
        "session_scope_count",
    )
    for token in required_worker_tokens:
        if token not in worker_text:
            violations.append(f"worker_missing_token:{token}")
    worker_session_predicates = (
        "AND e.session_id = :session_id",
        "(:session_id IS NULL OR e.session_id = :session_id)",
    )
    if not any(token in worker_text for token in worker_session_predicates):
        violations.append("worker_missing_session_local_predicate")

    legacy_window_only_query = (
        "FROM attribution_events\n                WHERE tenant_id = :tenant_id\n"
        "                  AND occurred_at >= :window_start\n"
        "                  AND occurred_at < :window_end"
    )
    if legacy_window_only_query in worker_text:
        violations.append("worker_contains_legacy_window_only_query")

    required_webhook_tokens = (
        '"session_id": session_id',
        'session_id = result.get("session_id")',
        "session_id=str(session_id)",
    )
    for token in required_webhook_tokens:
        if token not in webhooks_text:
            violations.append(f"webhooks_missing_token:{token}")

    if '"session_id": str(event.session_id)' not in event_service_text:
        violations.append("event_service_missing_session_id_in_success_payload")

    required_export_tokens = (
        "X-Attribution-Session-ID",
        "AND e.session_id = :session_id",
        "JOIN session_authority sa",
    )
    for token in required_export_tokens:
        if token not in export_text:
            violations.append(f"export_missing_token:{token}")

    required_runtime_tokens = (
        "test_b14_p3_runtime_query_locality_blocks_cross_session_reconstruction_attempt",
        "test_b14_p3_runtime_conversion_paths_are_session_local_without_durable_bridge_join",
        "test_b14_p3_runtime_session_local_replay_is_deterministic",
    )
    for token in required_runtime_tokens:
        if token not in runtime_proof_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P3 attribution locality enforcer")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--worker-file",
        default="backend/app/tasks/attribution.py",
    )
    parser.add_argument(
        "--webhooks-file",
        default="backend/app/api/webhooks.py",
    )
    parser.add_argument(
        "--event-service-file",
        default="backend/app/ingestion/event_service.py",
    )
    parser.add_argument(
        "--export-file",
        default="backend/app/api/export.py",
    )
    parser.add_argument(
        "--runtime-proof-file",
        default="backend/tests/integration/test_b14_p3_attribution_locality_runtime.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p3_attribution_locality_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=session_locality_query_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        ci_workflow_file=(REPO_ROOT / args.workflow_file).resolve(),
        required_checks_file=(REPO_ROOT / args.required_checks_file).resolve(),
        worker_file=(REPO_ROOT / args.worker_file).resolve(),
        webhooks_file=(REPO_ROOT / args.webhooks_file).resolve(),
        event_service_file=(REPO_ROOT / args.event_service_file).resolve(),
        export_file=(REPO_ROOT / args.export_file).resolve(),
        runtime_proof_file=(REPO_ROOT / args.runtime_proof_file).resolve(),
    )

    lines = ["b14_p3_attribution_locality_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=attribution locality invariants satisfied")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
