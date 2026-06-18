#!/usr/bin/env python3
"""B2.3-P1 schema authority lock follow-up enforcer."""

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


_ALLOWED_P2_CLASSIFICATIONS = {
    "persisted_canonical_column",
    "materialized_indexed_telemetry",
    "derived_deterministic_value_not_stored",
    "intentionally_deferred_to_p3_read_surface",
    "not_part_of_p2_output",
}


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


def _extract_constraint_window(
    text: str, constraint_name: str, size: int = 1800
) -> str:
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


def _has_exact_named_token(text: str, token: str) -> bool:
    return re.search(rf"\b{re.escape(token)}\b(?!_)", text) is not None


def _slice_between(text: str, start_token: str, end_token: str) -> str:
    start = text.find(start_token)
    if start < 0:
        return ""
    end = text.find(end_token, start + len(start_token))
    if end < 0:
        return text[start:]
    return text[start:end]


def _extract_table_definition_window(text: str, table_name: str) -> str:
    return _slice_between(
        text,
        f"CREATE TABLE public.{table_name} (",
        "ALTER TABLE ONLY public.",
    )


def _has_table_column_definition(table_definition: str, column_name: str) -> bool:
    return (
        re.search(
            rf"(?m)^\s*{re.escape(column_name)}\s+(?:integer|character varying)\b",
            table_definition,
        )
        is not None
    )


def _has_create_index_statement(text: str, index_name: str) -> bool:
    return (
        re.search(
            rf"(?m)^CREATE\s+(?:UNIQUE\s+)?INDEX\s+{re.escape(index_name)}\s+ON\s+",
            text,
        )
        is not None
    )


def _has_create_policy_statement(text: str, policy_name: str) -> bool:
    return (
        re.search(
            rf"(?m)^CREATE\s+POLICY\s+{re.escape(policy_name)}\s+ON\s+",
            text,
        )
        is not None
    )


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


def _validate_required_contract_sections(
    contract: dict[str, Any], violations: list[str]
) -> None:
    required = (
        "lifecycle_requirements",
        "financial_operand_requirements",
        "match_verdict_operand_requirements",
        "revenue_event_operand_requirements",
        "discrepancy_persistence_requirements",
        "p2_write_surface_requirements",
        "deterministic_db_object_name_requirements",
    )
    for section in required:
        if not isinstance(contract.get(section), dict):
            violations.append(f"contract_missing_or_invalid_section:{section}")


def _validate_lifecycle_contract_and_migration(
    *,
    contract: dict[str, Any],
    followup_migration_text: str,
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    lifecycle = contract.get("lifecycle_requirements", {})
    if not isinstance(lifecycle, dict):
        return

    if lifecycle.get("mechanism") != "database_native_pg_cron_function":
        violations.append("lifecycle_mechanism_mismatch")

    function_name = str(lifecycle.get("function_name") or "").strip()
    schedule = str(lifecycle.get("schedule") or "").strip()
    job_name = str(lifecycle.get("job_name") or "").strip()
    if not function_name:
        violations.append("lifecycle_function_name_missing")
    if not schedule:
        violations.append("lifecycle_schedule_missing")
    if not job_name:
        violations.append("lifecycle_job_name_missing")

    required_tokens = (
        "CREATE OR REPLACE FUNCTION public.{_LIFECYCLE_FUNCTION}",
        "CREATE EXTENSION IF NOT EXISTS pg_cron",
        "current_setting('skeldir.require_pg_cron', true)",
        "missing_extension:pg_cron",
        "cron.schedule(",
        "cron.unschedule(existing_job_id)",
        schedule,
        job_name,
    )
    for token in required_tokens:
        if token and token not in followup_migration_text:
            violations.append(f"lifecycle_migration_missing_token:{token}")

    table_specs = lifecycle.get("tables", {})
    if not isinstance(table_specs, dict):
        violations.append("lifecycle_tables_invalid")
        return

    for table_name in (
        "b23_match_verdicts",
        "b23_exception_records",
        "b23_revenue_events",
        "b23_webhook_ingestion_logs",
    ):
        spec = table_specs.get(table_name)
        if not isinstance(spec, dict):
            violations.append(f"lifecycle_table_spec_missing:{table_name}")
            continue

        required_keys = (
            "lifecycle_class",
            "retention_days",
            "prune_timestamp_column",
            "retention_rationale",
        )
        for key in required_keys:
            value = spec.get(key)
            if value in (None, "", []):
                violations.append(
                    f"lifecycle_table_spec_missing_field:{table_name}:{key}"
                )

        retention_days = spec.get("retention_days")
        if not isinstance(retention_days, int) or retention_days <= 0:
            violations.append(f"lifecycle_retention_days_invalid:{table_name}")
            continue
        timestamp_column = str(spec.get("prune_timestamp_column") or "")
        interval_token = (
            f"{timestamp_column} < (now() - interval '{retention_days} days')"
        )
        if interval_token not in followup_migration_text:
            violations.append(
                f"lifecycle_interval_missing:{table_name}:{interval_token}"
            )

        if table_name not in canonical_schema_text:
            violations.append(f"canonical_missing_lifecycle_table:{table_name}")

    forbidden = lifecycle.get("forbidden_primary_mechanisms", [])
    if not isinstance(forbidden, list):
        violations.append("lifecycle_forbidden_primary_mechanisms_invalid")
    else:
        for entry in forbidden:
            if entry == lifecycle.get("mechanism"):
                violations.append("lifecycle_forbidden_mechanism_selected")


def _validate_financial_operands(
    *,
    contract: dict[str, Any],
    followup_migration_text: str,
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    financial = contract.get("financial_operand_requirements", {})
    if not isinstance(financial, dict):
        return

    revenue_window = _extract_table_definition_window(
        canonical_schema_text, "b23_revenue_events"
    )
    match_window = _extract_table_definition_window(
        canonical_schema_text, "b23_match_verdicts"
    )

    if "currency_code character(3) NOT NULL" not in revenue_window:
        violations.append("revenue_event_currency_binding_missing")
    if "currency_code character(3) NOT NULL" not in match_window:
        violations.append("match_verdict_currency_binding_missing")

    forbidden_generic = financial.get("forbidden_unresolved_generic_money_columns", [])
    if isinstance(forbidden_generic, list):
        for column in forbidden_generic:
            generic_pattern = rf"(?m)^\s*{re.escape(column)}\s+integer\b"
            if re.search(generic_pattern, revenue_window) is not None:
                violations.append(
                    f"revenue_event_forbidden_generic_money_column_present:{column}"
                )
            drop_token = f"DROP COLUMN IF EXISTS {column}"
            if drop_token not in followup_migration_text:
                violations.append(
                    f"migration_missing_generic_money_column_drop:{column}"
                )

    required_event_columns = (
        "captured_amount_minor integer",
        "refund_amount_minor integer",
        "chargeback_amount_minor integer",
        "reversal_amount_minor integer",
        "net_effect_sign smallint NOT NULL",
    )
    for token in required_event_columns:
        if token not in revenue_window:
            violations.append(f"revenue_event_operand_column_missing:{token}")

    required_event_constraints = (
        "ck_b23_revenue_events_operand_columns_by_event_type",
        "ck_b23_revenue_events_split_operand_exactly_one_non_null",
        "ck_b23_revenue_events_net_effect_sign",
        "ck_b23_revenue_events_net_effect_sign_by_event_type",
    )
    for token in required_event_constraints:
        if not _has_exact_named_token(canonical_schema_text, token):
            violations.append(f"revenue_event_operand_constraint_missing:{token}")


def _validate_match_verdict_operands(
    *,
    contract: dict[str, Any],
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    requirements = contract.get("match_verdict_operand_requirements", {})
    if not isinstance(requirements, dict):
        return

    window = _extract_table_definition_window(
        canonical_schema_text, "b23_match_verdicts"
    )
    required_columns = (
        requirements.get("expected_gross_column"),
        requirements.get("captured_gross_column"),
        requirements.get("net_verified_column"),
        requirements.get("discrepancy_amount_column"),
        requirements.get("discrepancy_ratio_column"),
        requirements.get("discrepancy_band_column"),
    )
    for column in required_columns:
        if not isinstance(column, str) or not column:
            violations.append("match_verdict_operand_column_name_missing")
            continue
        if not _has_table_column_definition(window, column):
            violations.append(f"match_verdict_operand_column_missing:{column}")

    band_values = requirements.get("discrepancy_band_values", [])
    band_constraint = _extract_constraint_window(
        canonical_schema_text,
        "ck_b23_match_verdicts_discrepancy_band",
    )
    if not band_constraint:
        violations.append("match_verdict_discrepancy_band_constraint_missing")
    elif isinstance(band_values, list):
        _validate_exact_tokens(
            observed=_extract_quoted_values(band_constraint),
            expected=band_values,
            violation_prefix="discrepancy_band_constraint",
            violations=violations,
        )

    required_constraints = (
        "ck_b23_match_verdicts_discrepancy_amount_consistency",
        "ck_b23_match_verdicts_discrepancy_ratio_consistency",
        "ck_b23_match_verdicts_discrepancy_ratio_range",
    )
    for token in required_constraints:
        if not _has_exact_named_token(canonical_schema_text, token):
            violations.append(f"match_verdict_discrepancy_constraint_missing:{token}")


def _validate_discrepancy_persistence(
    *,
    contract: dict[str, Any],
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    requirements = contract.get("discrepancy_persistence_requirements", {})
    if not isinstance(requirements, dict):
        return

    window = _extract_table_definition_window(
        canonical_schema_text, "b23_match_verdicts"
    )
    for column in requirements.get("required_columns", []):
        if not _has_table_column_definition(window, str(column)):
            violations.append(f"discrepancy_column_missing:{column}")

    for index_name in requirements.get("required_indexes", []):
        if not _has_create_index_statement(canonical_schema_text, str(index_name)):
            violations.append(f"discrepancy_index_missing:{index_name}")


def _validate_p2_write_surface(
    *,
    contract: dict[str, Any],
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    requirements = contract.get("p2_write_surface_requirements", {})
    if not isinstance(requirements, dict) or not requirements:
        violations.append("p2_write_surface_requirements_missing")
        return

    for name, spec in requirements.items():
        if not isinstance(spec, dict):
            violations.append(f"p2_write_surface_spec_invalid:{name}")
            continue
        classification = spec.get("classification")
        destination = spec.get("destination")
        if classification not in _ALLOWED_P2_CLASSIFICATIONS:
            violations.append(
                f"p2_write_surface_classification_invalid:{name}:{classification}"
            )
        if not isinstance(destination, str) or "." not in destination:
            violations.append(f"p2_write_surface_destination_invalid:{name}")
            continue

        # Verify primary table token appears and at least one destination column token is present.
        table_token = destination.split(".", 1)[0].strip()
        if f"CREATE TABLE public.{table_token} (" not in canonical_schema_text:
            violations.append(
                f"p2_write_surface_destination_table_missing:{name}:{table_token}"
            )

        column_candidates = re.findall(r"[a-z_]+", destination.split(".", 1)[1])
        if not any(
            f"{candidate} " in canonical_schema_text for candidate in column_candidates
        ):
            violations.append(f"p2_write_surface_destination_column_missing:{name}")


def _validate_deterministic_naming(
    *,
    contract: dict[str, Any],
    followup_migration_text: str,
    canonical_schema_text: str,
    violations: list[str],
) -> None:
    naming = contract.get("deterministic_db_object_name_requirements", {})
    if not isinstance(naming, dict):
        return

    if bool(naming.get("require_explicit_deterministic_names")) is not True:
        violations.append("deterministic_name_requirement_disabled")

    for constraint in naming.get("required_named_constraints", []):
        if not _has_exact_named_token(canonical_schema_text, constraint):
            violations.append(f"named_constraint_missing:{constraint}")

    for index_name in naming.get("required_named_indexes", []):
        if not _has_create_index_statement(canonical_schema_text, str(index_name)):
            violations.append(f"named_index_missing:{index_name}")

    for policy_name in naming.get("required_named_policies", []):
        if not _has_create_policy_statement(canonical_schema_text, str(policy_name)):
            violations.append(f"named_policy_missing:{policy_name}")

    for function_name in naming.get("required_named_functions", []):
        if (
            f"FUNCTION public.{function_name}(" not in followup_migration_text
            and "FUNCTION public.{_LIFECYCLE_FUNCTION}(" not in followup_migration_text
        ):
            violations.append(f"named_function_missing:{function_name}")

    for job_name in naming.get("required_named_jobs", []):
        if not _has_exact_named_token(followup_migration_text, job_name):
            violations.append(f"named_job_missing:{job_name}")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    ci_workflow_file: Path,
    base_migration_file: Path,
    corrective_migration_file: Path,
    canonical_schema_file: Path,
    timing_constants_module: Path,
    reversibility_script_file: Path,
) -> tuple[int, list[str]]:
    violations: list[str] = []
    required_paths = (
        contract_file,
        ci_workflow_file,
        base_migration_file,
        corrective_migration_file,
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

    _validate_required_contract_sections(contract, violations)

    base_migration_text = _read_text(base_migration_file)
    followup_migration_text = _read_text(corrective_migration_file)
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
        if token not in base_migration_text:
            violations.append(f"base_migration_missing_table_token:{token}")
        if token not in canonical_schema_text:
            violations.append(f"canonical_schema_missing_table_token:{token}")

    status_window = _extract_constraint_window(
        base_migration_text, "ck_b23_match_verdicts_status"
    )
    if not status_window:
        violations.append("base_migration_missing_match_status_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(status_window),
            expected=contract["match_verdict"]["statuses"],
            violation_prefix="match_status_constraint",
            violations=violations,
        )

    quality_window = _extract_constraint_window(
        base_migration_text, "ck_b23_match_verdicts_match_quality"
    )
    if not quality_window:
        violations.append("base_migration_missing_match_quality_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(quality_window),
            expected=contract["match_verdict"]["match_qualities"],
            violation_prefix="match_quality_constraint",
            violations=violations,
        )

    event_window = _extract_constraint_window(
        base_migration_text, "ck_b23_revenue_events_event_type"
    )
    if not event_window:
        violations.append("base_migration_missing_revenue_event_type_constraint")
    else:
        _validate_exact_tokens(
            observed=_extract_quoted_values(event_window),
            expected=contract["revenue_events"]["event_taxonomy"],
            violation_prefix="revenue_event_type_constraint",
            violations=violations,
        )

    unique_token = "uq_b23_revenue_events_tenant_provider_event_ref"
    if unique_token not in base_migration_text:
        violations.append("base_migration_missing_revenue_event_idempotency_constraint")
    if unique_token not in canonical_schema_text:
        violations.append(
            "canonical_schema_missing_revenue_event_idempotency_constraint"
        )

    resolution_constraint_token = "ck_b23_exception_records_resolution_code_required"
    if resolution_constraint_token not in base_migration_text:
        violations.append("base_migration_missing_exception_resolution_constraint")
    if resolution_constraint_token not in canonical_schema_text:
        violations.append("canonical_schema_missing_exception_resolution_constraint")

    webhook_required_columns = contract["webhook_ingestion_log"]["required_columns"]
    webhook_window = _slice_between(
        base_migration_text,
        "CREATE TABLE public.b23_webhook_ingestion_logs (",
        "COMMENT ON TABLE public.b23_webhook_ingestion_logs",
    )
    for column in webhook_required_columns:
        if (
            re.search(rf"(?m)^\s*{re.escape(column)}\s+[a-zA-Z]", webhook_window)
            is None
        ):
            violations.append(f"base_migration_missing_webhook_log_column:{column}")

    forbidden_payload_tokens = contract.get(
        "forbidden_authority_payload_column_tokens", []
    )
    if isinstance(forbidden_payload_tokens, list):
        for token in forbidden_payload_tokens:
            if token in webhook_window:
                violations.append(
                    f"webhook_log_contains_forbidden_payload_token:{token}"
                )

    rls_policy_tokens = (
        "tenant_isolation_policy_b23_match_verdicts",
        "tenant_isolation_policy_b23_exception_records",
        "tenant_isolation_policy_b23_revenue_events",
        "tenant_isolation_policy_b23_webhook_ingestion_logs",
    )
    for token in rls_policy_tokens:
        if token not in base_migration_text:
            violations.append(f"base_migration_missing_rls_policy:{token}")
        if token not in canonical_schema_text:
            violations.append(f"canonical_schema_missing_rls_policy:{token}")

    for table_name in (
        "b23_match_verdicts",
        "b23_exception_records",
        "b23_revenue_events",
        "b23_webhook_ingestion_logs",
    ):
        if f'"{table_name}"' not in base_migration_text:
            violations.append(f"base_migration_missing_rls_loop_table:{table_name}")
        if "FORCE ROW LEVEL SECURITY" not in base_migration_text:
            violations.append(f"base_migration_missing_force_rls:{table_name}")
            break
        force_token = f"ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY"
        if force_token not in canonical_schema_text:
            violations.append(f"canonical_schema_missing_force_rls:{table_name}")

    _validate_lifecycle_contract_and_migration(
        contract=contract,
        followup_migration_text=followup_migration_text,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )
    _validate_financial_operands(
        contract=contract,
        followup_migration_text=followup_migration_text,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )
    _validate_match_verdict_operands(
        contract=contract,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )
    _validate_discrepancy_persistence(
        contract=contract,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )
    _validate_p2_write_surface(
        contract=contract,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )
    _validate_deterministic_naming(
        contract=contract,
        followup_migration_text=followup_migration_text,
        canonical_schema_text=canonical_schema_text,
        violations=violations,
    )

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
            violations.append(
                f"timing_constant_value_mismatch:{name}:{value}:{expected}"
            )

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
        "constraints",
        "functions",
        "force_rls",
    )
    for token in reversibility_required_tokens:
        if token not in reversibility_text:
            violations.append(f"reversibility_script_missing_token:{token}")

    followup_hooks = (
        "def upgrade() -> None:",
        "def downgrade() -> None:",
        'revision: str = "202604301030"',
        'down_revision: Union[str, None] = "202604291200"',
        "DROP FUNCTION IF EXISTS public.{_LIFECYCLE_FUNCTION}(integer)",
    )
    for token in followup_hooks:
        if token not in followup_migration_text:
            violations.append(f"corrective_migration_missing_hook:{token}")

    return (1 if violations else 0), violations


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Enforce B2.3-P1 schema authority lock"
    )
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--ci-workflow-file", default=CI_WORKFLOW_FILE)
    parser.add_argument("--base-migration-file", default="")
    parser.add_argument("--corrective-migration-file", default="")
    parser.add_argument("--canonical-schema-file", default="")
    parser.add_argument("--timing-constants-module", default="")
    parser.add_argument(
        "--reversibility-script-file", default=REVERSIBILITY_SCRIPT_FILE
    )
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

    base_migration_file = _resolve(
        repo_root,
        args.base_migration_file
        or str(schema_surfaces.get("base_migration_file") or ""),
    )
    corrective_migration_file = _resolve(
        repo_root,
        args.corrective_migration_file
        or str(schema_surfaces.get("corrective_migration_file") or ""),
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
    reversibility_script_file = _resolve(
        repo_root,
        args.reversibility_script_file
        or str(schema_surfaces.get("reversibility_script_file") or ""),
    )

    status, violations = run_enforcement(
        repo_root=repo_root,
        contract_file=contract_file,
        ci_workflow_file=_resolve(repo_root, args.ci_workflow_file),
        base_migration_file=base_migration_file,
        corrective_migration_file=corrective_migration_file,
        canonical_schema_file=canonical_schema_file,
        timing_constants_module=timing_constants_module,
        reversibility_script_file=reversibility_script_file,
    )
    print("b23_p1_schema_authority_lock_enforcer")
    if status != 0:
        print("result=FAIL")
        for violation in violations:
            print(violation)
        return status
    print("result=PASS")
    print("enforcement=b23_p1_followup_schema_authority_non_vacuous")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
