#!/usr/bin/env python3
"""B1.4-P4 retention/deletion structural enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTEXT = "B1.4 P4 Retention + Deterministic Deletion Proofs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_enforcement(
    *,
    ci_workflow_file: Path,
    required_checks_file: Path,
    split_migration_file: Path,
    corrective_migration_file: Path,
    maintenance_file: Path,
    privacy_task_file: Path,
    event_service_file: Path,
    dlq_handler_file: Path,
    runtime_proof_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        ci_workflow_file,
        required_checks_file,
        split_migration_file,
        corrective_migration_file,
        maintenance_file,
        privacy_task_file,
        event_service_file,
        dlq_handler_file,
        runtime_proof_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    workflow_text = _read(ci_workflow_file)
    checks_contract = _load_json(required_checks_file)
    split_migration_text = _read(split_migration_file)
    corrective_migration_text = _read(corrective_migration_file)
    maintenance_text = _read(maintenance_file)
    privacy_task_text = _read(privacy_task_file)
    event_service_text = _read(event_service_file)
    dlq_handler_text = _read(dlq_handler_file)
    runtime_proof_text = _read(runtime_proof_file)

    if REQUIRED_CONTEXT not in workflow_text:
        violations.append(f"missing_required_context_in_workflow:{REQUIRED_CONTEXT}")

    contexts = checks_contract.get("required_contexts", [])
    if REQUIRED_CONTEXT not in contexts:
        violations.append(f"missing_required_context_in_contract:{REQUIRED_CONTEXT}")

    required_split_migration_tokens = (
        "CREATE TABLE public.raw_event_payloads",
        "payload_json jsonb",
        "REFERENCES public.attribution_events(id) ON DELETE CASCADE",
        "ALTER TABLE public.raw_event_payloads ENABLE ROW LEVEL SECURITY",
        "tenant_isolation_policy_raw_event_payloads",
        "INSERT INTO public.raw_event_payloads",
    )
    for token in required_split_migration_tokens:
        if token not in split_migration_text:
            violations.append(f"split_migration_missing_token:{token}")

    required_corrective_migration_tokens = (
        "CREATE TABLE public.compliance_audit_ledger",
        "fn_compliance_audit_ledger_append_only",
        "idx_raw_event_payloads_tenant_lookup_hash",
        "idx_raw_event_payloads_payload_json_gin",
        "ALTER TABLE public.dead_events",
        "ALTER TABLE public.dead_events_quarantine",
        "idx_dead_events_tenant_idempotency_key",
        "idx_dead_events_quarantine_tenant_idempotency_key",
    )
    for token in required_corrective_migration_tokens:
        if token not in corrective_migration_text:
            violations.append(f"corrective_migration_missing_token:{token}")

    required_event_service_tokens = (
        "RawEventPayload",
        "lookup_hash=",
        "payload_json=boundary.sanitized_payload",
        "session.add(raw_event_payload)",
    )
    for token in required_event_service_tokens:
        if token not in event_service_text:
            violations.append(f"event_service_missing_token:{token}")

    required_dlq_tokens = (
        "idempotency_key=",
        "INSERT INTO dead_events_quarantine",
    )
    for token in required_dlq_tokens:
        if token not in dlq_handler_text:
            violations.append(f"dlq_handler_missing_token:{token}")

    required_maintenance_tokens = (
        "gc_expired_raw_event_payloads",
        "gc_expired_raw_event_payloads_all_tenants",
        "DELETE FROM public.raw_event_payloads target",
        "created_at < :cutoff",
    )
    for token in required_maintenance_tokens:
        if token not in maintenance_text:
            violations.append(f"maintenance_missing_token:{token}")

    required_privacy_tokens = (
        "DELETE FROM raw_event_payloads rep",
        "UPDATE session_authority",
        "INSERT INTO compliance_audit_ledger",
        "privacy_audit_artifacts_inserted",
    )
    for token in required_privacy_tokens:
        if token not in privacy_task_text:
            violations.append(f"privacy_task_missing_token:{token}")
    forbidden_privacy_tokens = (
        "INSERT INTO attribution_events",
        "privacy_tombstone",
        "raw_payload->>'idempotency_key'",
        "INSERT INTO session_authority",
    )
    for token in forbidden_privacy_tokens:
        if token in privacy_task_text:
            violations.append(f"privacy_task_forbidden_token_present:{token}")

    required_runtime_tokens = (
        "test_b14_p4_runtime_schema_split_writes_raw_payloads_without_mutating_immutable_ledger",
        "test_b14_p4_runtime_90_day_gc_deletes_raw_payloads_without_touching_attribution_events",
        "test_b14_p4_runtime_deterministic_delete_wipes_payloads_and_invalidates_session_authority_and_emits_compliance_audit_artifact",
        "test_b14_p4_runtime_export_roas_survives_payload_expiry",
        "test_b14_p4_runtime_lookup_strategy_is_index_backed",
    )
    for token in required_runtime_tokens:
        if token not in runtime_proof_text:
            violations.append(f"runtime_proof_missing_token:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P4 retention/deletion enforcer")
    parser.add_argument("--workflow-file", default=".github/workflows/ci.yml")
    parser.add_argument(
        "--required-checks-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--split-migration-file",
        default=(
            "alembic/versions/007_skeldir_foundation/"
            "202603212015_b14_p4_split_substrate_raw_payloads.py"
        ),
    )
    parser.add_argument(
        "--corrective-migration-file",
        default=(
            "alembic/versions/007_skeldir_foundation/"
            "202603221130_b14_p4_corrective_audit_surface_and_lookup_hardening.py"
        ),
    )
    parser.add_argument(
        "--maintenance-file",
        default="backend/app/tasks/maintenance.py",
    )
    parser.add_argument(
        "--privacy-task-file",
        default="backend/app/tasks/privacy.py",
    )
    parser.add_argument(
        "--event-service-file",
        default="backend/app/ingestion/event_service.py",
    )
    parser.add_argument(
        "--dlq-handler-file",
        default="backend/app/ingestion/dlq_handler.py",
    )
    parser.add_argument(
        "--runtime-proof-file",
        default="backend/tests/integration/test_b14_p4_retention_deletion_runtime.py",
    )
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p4_retention_deletion_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=raw_payload_gc_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        ci_workflow_file=(REPO_ROOT / args.workflow_file).resolve(),
        required_checks_file=(REPO_ROOT / args.required_checks_file).resolve(),
        split_migration_file=(REPO_ROOT / args.split_migration_file).resolve(),
        corrective_migration_file=(REPO_ROOT / args.corrective_migration_file).resolve(),
        maintenance_file=(REPO_ROOT / args.maintenance_file).resolve(),
        privacy_task_file=(REPO_ROOT / args.privacy_task_file).resolve(),
        event_service_file=(REPO_ROOT / args.event_service_file).resolve(),
        dlq_handler_file=(REPO_ROOT / args.dlq_handler_file).resolve(),
        runtime_proof_file=(REPO_ROOT / args.runtime_proof_file).resolve(),
    )

    lines = ["b14_p4_retention_deletion_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=retention+deterministic-deletion invariants satisfied")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
