#!/usr/bin/env python3
"""B2.3-P1 schema authority lock enforcer."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_p1_schema_authority_lock.main.json"
CI_WORKFLOW_FILE = ".github/workflows/ci.yml"
REVERSIBILITY_SCRIPT_FILE = "scripts/ci/verify_b23_p1_migration_reversibility.py"


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
        raise ValueError(f"contract_payload_not_object:{path}")
    return payload


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("b23_p1_timing_constants", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"module_load_failed:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _extract_constraint_window(text: str, constraint_name: str, size: int = 1400) -> str:
    match = re.search(rf"\b{re.escape(constraint_name)}\b", text)
    if match is None:
        return ""
    index = match.start()
    next_constraint_index = text.find("CONSTRAINT ", index + len(constraint_name))
    if next_constraint_index < 0:
        return text[index : index + size]
    return text[index:next_constraint_index]


def _extract_quoted_values(text: str) -> list[str]:
    return re.findall(r"'([^']+)'", text)


def _has_exact_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b", text) is not None


def _slice_between(text: str, start_token: str, end_token: str) -> str:
    start = text.find(start_token)
    if start < 0:
        return ""
    end = text.find(end_token, start + len(start_token))
    if end < 0:
        return text[start:]
    return text[start:end]


def _validate_exact_tokens(
    *,
    observed: list[str],
    expected: list[str],
    violation_prefix: str,
    violations: list[str],
) -> None:
    expected_set = set(expected)
    observed_set = set(observed)
    missing = sorted(expected_set - observed_set)
    extras = sorted(observed_set - expected_set)
    if missing:
        violations.append(f"{violation_prefix}_missing:{','.join(missing)}")
    if extras:
        violations.append(f"{violation_prefix}_extra:{','.join(extras)}")
    if len(observed) != len(observed_set):
        violations.append(f"{violation_prefix}_duplicates_present")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    ci_workflow_file: Path,
    migration_file: Path,
    canonical_schema_file: Path,
    timing_constants_module: Path,
    reversibility_script_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        contract_file,
        ci_workflow_file,
        migration_file,
        canonical_schema_file,
        timing_constants_module,
        reversibility_script_file,
    )
    missing = [path for path in required_paths if not path.exists()]
    if missing:
        return 1, [f"missing_file:{path}" for path in missing]

    contract = _read_json(contract_file)
    if contract.get("contract_id") != "b23.p1.schema_authority_lock.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-P1":
        violations.append("contract_phase_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")

    migration_text = _read_text(migration_file)
    canonical_schema_text = _read_text(canonical_schema_file)
    ci_text = _read_text(ci_workflow_file)
    reversibility_text = _read_text(reversibility_script_file)
    constants_module = _load_module(timing_constants_module)

    table_tokens = (
        "CREATE TABLE public.b23_match_verdicts (",
        "CREATE TABLE public.b23_exception_records (",
        "CREATE TABLE public.b23_revenue_events (",
        "CREATE TABLE public.b23_webhook_ingestion_logs (",
    )
    for token in table_tokens:
        if token not in migration_text:
            violations.append(f"migration_missing_table_token:{token}")
        if token not in canonical_schema_text:
            violations.append(f"canonical_schema_missing_table_token:{token}")

    status_window = _extract_constraint_window(migration_text, "ck_b23_match_verdicts_status")
    if not status_window:
        violations.append("migration_missing_match_status_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(status_window),
            expected=contract["match_verdict"]["statuses"],
            violation_prefix="match_status_constraint",
            violations=violations,
        )

    quality_window = _extract_constraint_window(migration_text, "ck_b23_match_verdicts_match_quality")
    if not quality_window:
        violations.append("migration_missing_match_quality_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(quality_window),
            expected=contract["match_verdict"]["match_qualities"],
            violation_prefix="match_quality_constraint",
            violations=violations,
        )

    event_window = _extract_constraint_window(migration_text, "ck_b23_revenue_events_event_type")
    if not event_window:
        violations.append("migration_missing_revenue_event_type_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(event_window),
            expected=contract["revenue_events"]["event_taxonomy"],
            violation_prefix="revenue_event_type_constraint",
            violations=violations,
        )

    unique_token = "uq_b23_revenue_events_tenant_provider_event_ref"
    if unique_token not in migration_text:
        violations.append("migration_missing_revenue_event_idempotency_constraint")
    if unique_token not in canonical_schema_text:
        violations.append("canonical_schema_missing_revenue_event_idempotency_constraint")

    resolution_constraint_token = "ck_b23_exception_records_resolution_code_required"
    if resolution_constraint_token not in migration_text:
        violations.append("migration_missing_exception_resolution_constraint")
    if resolution_constraint_token not in canonical_schema_text:
        violations.append("canonical_schema_missing_exception_resolution_constraint")

    webhook_required_columns = contract["webhook_ingestion_log"]["required_columns"]
    webhook_window = _slice_between(
        migration_text,
        "CREATE TABLE public.b23_webhook_ingestion_logs (",
        "COMMENT ON TABLE public.b23_webhook_ingestion_logs",
    )
    for column in webhook_required_columns:
        if re.search(rf"(?m)^\s*{re.escape(column)}\s+[a-zA-Z]", webhook_window) is None:
            violations.append(f"migration_missing_webhook_log_column:{column}")

    forbidden_payload_tokens = contract.get("forbidden_authority_payload_column_tokens", [])
    for token in forbidden_payload_tokens:
        if token in webhook_window:
            violations.append(f"webhook_log_contains_forbidden_payload_token:{token}")
        revenue_window = _extract_constraint_window(
            migration_text,
            "CREATE TABLE public.b23_revenue_events (",
            size=2000,
        )
        if token in revenue_window:
            violations.append(f"revenue_events_contains_forbidden_payload_token:{token}")
        verdict_window = _extract_constraint_window(
            migration_text,
            "CREATE TABLE public.b23_match_verdicts (",
            size=2200,
        )
        if token in verdict_window:
            violations.append(f"match_verdict_contains_forbidden_payload_token:{token}")

    rls_policy_tokens = (
        "tenant_isolation_policy_b23_match_verdicts",
        "tenant_isolation_policy_b23_exception_records",
        "tenant_isolation_policy_b23_revenue_events",
        "tenant_isolation_policy_b23_webhook_ingestion_logs",
    )
    for token in rls_policy_tokens:
        if not _has_exact_token(migration_text, token):
            violations.append(f"migration_missing_rls_policy:{token}")
        if not _has_exact_token(canonical_schema_text, token):
            violations.append(f"canonical_schema_missing_rls_policy:{token}")

    for table_name in (
        "b23_match_verdicts",
        "b23_exception_records",
        "b23_revenue_events",
        "b23_webhook_ingestion_logs",
    ):
        if f'"{table_name}"' not in migration_text:
            violations.append(f"migration_missing_rls_loop_table:{table_name}")
        force_token = f"ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY"
        if force_token not in canonical_schema_text:
            violations.append(f"canonical_schema_missing_force_rls:{table_name}")

    if "FORCE ROW LEVEL SECURITY" not in migration_text:
        for table_name in (
            "b23_match_verdicts",
            "b23_exception_records",
            "b23_revenue_events",
            "b23_webhook_ingestion_logs",
        ):
            violations.append(f"migration_missing_force_rls:{table_name}")

    expected_constants = {
        "WEBHOOK_ARRIVAL_WINDOW": timedelta(minutes=30),
        "PROVISIONAL_MATCH_WINDOW": timedelta(hours=24),
        "REFUND_REOPENING_WINDOW": timedelta(days=30),
    }
    for name, expected in expected_constants.items():
        value = getattr(constants_module, name, None)
        if value is None:
            violations.append(f"timing_constant_missing:{name}")
            continue
        if not isinstance(value, timedelta):
            violations.append(f"timing_constant_wrong_type:{name}")
            continue
        if value != expected:
            violations.append(f"timing_constant_value_mismatch:{name}:{value}:{expected}")

    required_ci_wiring = contract.get("required_ci_wiring", [])
    if not isinstance(required_ci_wiring, list) or not required_ci_wiring:
        violations.append("contract_required_ci_wiring_missing")
    else:
        for token in required_ci_wiring:
            if str(token) not in ci_text:
                violations.append(f"ci_missing_token:{token}")

    reversibility_required_tokens = (
        "downgrade",
        "upgrade",
        "-1",
        "before_signature",
        "after_signature",
    )
    for token in reversibility_required_tokens:
        if token not in reversibility_text:
            violations.append(f"reversibility_script_missing_token:{token}")

    migration_hooks = (
        "def upgrade() -> None:",
        "def downgrade() -> None:",
        "DROP TABLE IF EXISTS public.b23_webhook_ingestion_logs",
        "DROP TABLE IF EXISTS public.b23_revenue_events",
        "DROP TABLE IF EXISTS public.b23_exception_records",
        "DROP TABLE IF EXISTS public.b23_match_verdicts",
    )
    for token in migration_hooks:
        if token not in migration_text:
            violations.append(f"migration_missing_hook:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Enforce B2.3-P1 schema authority lock")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--migration-file", default="")
    parser.add_argument("--canonical-schema-file", default="")
    parser.add_argument("--timing-constants-module", default="")
    parser.add_argument("--reversibility-script-file", default=REVERSIBILITY_SCRIPT_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    args = parser.parse_args(argv[1:])

    if args.simulate_regression:
        print("b23_p1_schema_authority_lock_enforcer")
        print("result=FAIL")
        print("synthetic_regression=forced_failure_path")
        return 1

    repo_root = _resolve(REPO_ROOT, args.repo_root)
    contract_file = _resolve(repo_root, args.contract_file)
    contract = _read_json(contract_file)
    schema_surfaces = contract.get("schema_surfaces", {})
    migration_file = _resolve(
        repo_root,
        args.migration_file
        or str(schema_surfaces.get("migration_file") or ""),
    )
    canonical_schema_file = _resolve(
        repo_root,
        args.canonical_schema_file
        or str(schema_surfaces.get("canonical_schema_file") or ""),
    )
    timing_constants_module = _resolve(
        repo_root,
        args.timing_constants_module
        or str(schema_surfaces.get("timing_constants_module") or ""),
    )
    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=contract_file,
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        migration_file=migration_file,
        canonical_schema_file=canonical_schema_file,
        timing_constants_module=timing_constants_module,
        reversibility_script_file=_resolve(repo_root, args.reversibility_script_file),
    )
    print("b23_p1_schema_authority_lock_enforcer")
    if status != 0:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return status
    print("result=PASS")
    print("enforcement=b23_p1_schema_authority_non_vacuous")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
