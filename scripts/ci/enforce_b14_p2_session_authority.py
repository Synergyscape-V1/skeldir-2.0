#!/usr/bin/env python3
"""B1.4-P2 session authority structural enforcement."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_CONTEXT = "B1.4 P2 Session Authority Proofs"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_enforcement(
    *,
    ci_workflow_file: Path,
    required_checks_file: Path,
    canonical_schema_file: Path,
    migration_file: Path,
    event_service_file: Path,
    privacy_boundary_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    required_files = (
        ci_workflow_file,
        required_checks_file,
        canonical_schema_file,
        migration_file,
        event_service_file,
        privacy_boundary_file,
    )
    for required in required_files:
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    workflow_text = _read(ci_workflow_file)
    checks_contract = _load_json(required_checks_file)
    canonical_text = _read(canonical_schema_file)
    migration_text = _read(migration_file)
    event_service_text = _read(event_service_file)
    privacy_boundary_text = _read(privacy_boundary_file)

    if REQUIRED_CONTEXT not in workflow_text:
        violations.append(f"missing_required_context_in_workflow:{REQUIRED_CONTEXT}")

    contexts = checks_contract.get("required_contexts", [])
    if REQUIRED_CONTEXT not in contexts:
        violations.append(f"missing_required_context_in_contract:{REQUIRED_CONTEXT}")

    required_schema_tokens = (
        "CREATE TABLE public.session_authority",
        "uq_session_authority_tenant_session_id",
        "ck_session_authority_max_24h",
        "fk_attribution_events_session_authority",
        "trg_bind_session_authority_from_event",
    )
    for token in required_schema_tokens:
        if token not in canonical_text:
            violations.append(f"canonical_missing_token:{token}")

    required_migration_tokens = (
        "CREATE TABLE public.session_authority",
        "fn_bind_session_authority_from_event",
        "fk_attribution_events_session_authority",
        "ALTER TABLE public.session_authority ENABLE ROW LEVEL SECURITY",
    )
    for token in required_migration_tokens:
        if token not in migration_text:
            violations.append(f"migration_missing_token:{token}")

    if "resolve_session_authority(" not in event_service_text:
        violations.append("event_service_missing_session_authority_resolution")
    if "candidate_session_id" not in event_service_text:
        violations.append("event_service_missing_candidate_session_id_path")

    if "session_id = derive_transient_session_id(" in privacy_boundary_text:
        violations.append("privacy_boundary_still_derives_session_id_deterministically")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="B1.4-P2 session authority enforcer")
    parser.add_argument(
        "--workflow-file",
        default=".github/workflows/ci.yml",
    )
    parser.add_argument(
        "--required-checks-file",
        default="contracts-internal/governance/b03_phase2_required_status_checks.main.json",
    )
    parser.add_argument(
        "--canonical-schema-file",
        default="db/schema/canonical_schema.sql",
    )
    parser.add_argument(
        "--migration-file",
        default="alembic/versions/007_skeldir_foundation/202603191730_b14_p2_session_authority_substrate.py",
    )
    parser.add_argument(
        "--event-service-file",
        default="backend/app/ingestion/event_service.py",
    )
    parser.add_argument(
        "--privacy-boundary-file",
        default="backend/app/ingestion/privacy_boundary.py",
    )
    parser.add_argument(
        "--simulate-regression",
        action="store_true",
    )
    args = parser.parse_args(argv)

    if args.simulate_regression:
        sys.stdout.write(
            "b14_p2_session_authority_enforcer\n"
            "result=FAIL\n"
            "synthetic_regression=session_authority_context_removed\n"
        )
        return 1

    status, violations = run_enforcement(
        ci_workflow_file=(REPO_ROOT / args.workflow_file).resolve(),
        required_checks_file=(REPO_ROOT / args.required_checks_file).resolve(),
        canonical_schema_file=(REPO_ROOT / args.canonical_schema_file).resolve(),
        migration_file=(REPO_ROOT / args.migration_file).resolve(),
        event_service_file=(REPO_ROOT / args.event_service_file).resolve(),
        privacy_boundary_file=(REPO_ROOT / args.privacy_boundary_file).resolve(),
    )

    lines = ["b14_p2_session_authority_enforcer"]
    if status != 0:
        lines.append("result=FAIL")
        lines.extend(violations)
    else:
        lines.append("result=PASS")
        lines.append("enforcement=session authority substrate invariants satisfied")

    sys.stdout.write("\n".join(lines) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

