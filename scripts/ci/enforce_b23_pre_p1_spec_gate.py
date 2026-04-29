#!/usr/bin/env python3
"""B2.3 Pre-P1 specification closure enforcer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_b23_pre_p1_spec_contract import (
    ADJUSTMENT_EVENTS,
    BINARY_FLOAT_FORBIDDEN_SCOPES,
    PROVIDERS,
    validate_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_pre_p1_spec_gate.main.json"
SPEC_FILE = "docs/forensics/B2.3-Pre-P1 Specification Gates A-B.md"
CI_FILE = ".github/workflows/ci.yml"

_REQUIRED_PROVIDER_FIELDS = (
    "provider_origin_revenue_field",
    "provider_origin_currency_field",
    "source_amount_unit",
    "canonical_amount_basis",
    "b23_authority_amount_field",
    "b23_authority_currency_field",
    "canonical_storage_unit",
    "currency_exponent_source",
    "rounding_mode",
    "tax_inclusion",
    "shipping_inclusion",
    "discount_inclusion",
    "processor_fee_inclusion",
    "refund_chargeback_adjustment_posture",
    "multi_currency_posture",
)
_REQUIRED_TABLE_CLASSES = (
    "match_verdicts",
    "exception_records",
    "revenue_events",
    "webhook_ingestion_logs",
    "read_models_or_materialized_summaries",
)
_REQUIRED_TABLE_CLASS_FIELDS = (
    "data_classification",
    "allowed_identifier_classes",
    "forbidden_columns",
    "raw_provider_payload_posture",
    "tenant_isolation_requirement",
    "rls_requirement",
    "retention_or_archival_class",
    "lifecycle_mechanism",
    "retention_rationale",
)
_REQUIRED_TIMING_CONSTANTS = (
    "WEBHOOK_ARRIVAL_WINDOW",
    "PROVISIONAL_MATCH_WINDOW",
    "REFUND_REOPENING_WINDOW",
)
_REQUIRED_TIMING_FIELDS = (
    "value",
    "unit",
    "rationale",
    "consuming_phases",
    "tenant_configurable_pre_launch",
    "state_transition_effect",
    "future_constants_module_name",
)
_REQUIRED_DECIMAL_CONVERSION_GUARDS = (
    "python_float",
    "javascript_number",
    "javascript_parseFloat",
    "double",
)


def _resolve(repo_root: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (repo_root / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"json_object_required:{path}")
    return payload


def _is_non_empty(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None


def _require_fields(
    obj: dict[str, Any],
    fields: tuple[str, ...],
    prefix: str,
    violations: list[str],
) -> None:
    for field in fields:
        if not _is_non_empty(obj.get(field)):
            violations.append(f"{prefix}_missing_field:{field}")


def run_enforcement(
    *,
    repo_root: Path,
    contract_file: Path,
    spec_file: Path,
    ci_file: Path,
    simulate_regression: bool,
) -> tuple[int, list[str]]:
    violations: list[str] = []

    for required in (contract_file, spec_file, ci_file):
        if not required.exists():
            violations.append(f"missing_file:{required}")
    if violations:
        return 1, violations

    contract = _read_json(contract_file)
    spec_text = spec_file.read_text(encoding="utf-8")
    ci_text = ci_file.read_text(encoding="utf-8")

    schema_errors = validate_contract(contract)
    for schema_error in schema_errors:
        violations.append(f"schema:{schema_error}")

    if contract.get("contract_id") != "b23.pre_p1.spec_gate.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-Pre-P1":
        violations.append("contract_phase_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")

    p0_truth = contract.get("p0_inherited_truth_correction")
    if isinstance(p0_truth, dict):
        if p0_truth.get("activity_independent_lifecycle_mode") != "database_scheduled_pruning":
            violations.append("p0_truth_lifecycle_mode_mismatch")
        if p0_truth.get("governed_runtime_mechanism") != "governed_neon_pg_cron":
            violations.append("p0_truth_runtime_mechanism_mismatch")
        if p0_truth.get("forbid_trigger_only_authority_claim") is not True:
            violations.append("p0_truth_trigger_only_forbid_missing")
        if p0_truth.get("preserve_false_authority_exclusion") is not True:
            violations.append("p0_truth_false_authority_preservation_missing")
        if p0_truth.get("preserve_no_llm_deterministic_authority_path") is not True:
            violations.append("p0_truth_no_llm_preservation_missing")

    revenue = contract.get("revenue_extraction_standard")
    if isinstance(revenue, dict):
        if revenue.get("source_boundary") != "verified_b22_b23_ingress_envelope":
            violations.append("revenue_source_boundary_mismatch")
        if revenue.get("raw_webhook_payload_forbidden_as_b23_authority") is not True:
            violations.append("revenue_raw_payload_forbid_missing")
        if revenue.get("provider_origin_fields_are_provenance_only") is not True:
            violations.append("revenue_provider_origin_provenance_only_missing")
        if not _is_non_empty(revenue.get("canonical_amount_basis")):
            violations.append("revenue_missing_canonical_amount_basis")

        storage = revenue.get("canonical_storage")
        if isinstance(storage, dict):
            scopes = storage.get("binary_float_forbidden_scopes", [])
            if isinstance(scopes, list):
                for scope in sorted(BINARY_FLOAT_FORBIDDEN_SCOPES):
                    if scope not in scopes:
                        violations.append(f"revenue_binary_float_scope_missing:{scope}")
            else:
                violations.append("revenue_binary_float_scopes_invalid")

        exact_decimal = revenue.get("exact_decimal_parsing_policy")
        if isinstance(exact_decimal, dict):
            if exact_decimal.get("require_exact_decimal_arithmetic") is not True:
                violations.append("revenue_exact_decimal_required_missing")
            required_units = exact_decimal.get("required_for_source_units", [])
            if "decimal_string_major_units" not in required_units:
                violations.append("revenue_exact_decimal_source_unit_missing")
            required_providers = set(exact_decimal.get("providers_requiring_exact_decimal", []))
            for provider in ("paypal", "shopify", "woocommerce"):
                if provider not in required_providers:
                    violations.append(f"revenue_exact_decimal_provider_missing:{provider}")
            forbidden_conversions = set(exact_decimal.get("forbidden_binary_float_conversions", []))
            for conversion in _REQUIRED_DECIMAL_CONVERSION_GUARDS:
                if conversion not in forbidden_conversions:
                    violations.append(f"revenue_exact_decimal_conversion_guard_missing:{conversion}")

        providers = revenue.get("providers")
        if isinstance(providers, dict):
            for provider in PROVIDERS:
                provider_payload = providers.get(provider)
                if not isinstance(provider_payload, dict):
                    violations.append(f"revenue_provider_missing:{provider}")
                    continue
                _require_fields(
                    provider_payload,
                    _REQUIRED_PROVIDER_FIELDS,
                    f"revenue_provider_{provider}",
                    violations,
                )
                if (
                    provider_payload.get("provider_origin_revenue_field")
                    == provider_payload.get("b23_authority_amount_field")
                ):
                    violations.append(f"revenue_provider_origin_runtime_boundary_broken:{provider}:amount")
                if (
                    provider_payload.get("provider_origin_currency_field")
                    == provider_payload.get("b23_authority_currency_field")
                ):
                    violations.append(f"revenue_provider_origin_runtime_boundary_broken:{provider}:currency")

    concurrency = contract.get("refund_chargeback_concurrency_law")
    if isinstance(concurrency, dict):
        events = concurrency.get("distinct_adjustment_events")
        if isinstance(events, list):
            for event in sorted(ADJUSTMENT_EVENTS):
                if event not in events:
                    violations.append(f"concurrency_adjustment_event_missing:{event}")
        else:
            violations.append("concurrency_distinct_adjustment_events_missing")

    privacy = contract.get("table_privacy_lifecycle_pre_spec")
    if isinstance(privacy, dict):
        classes = privacy.get("table_classes")
        if isinstance(classes, dict):
            for table_class in _REQUIRED_TABLE_CLASSES:
                payload = classes.get(table_class)
                if not isinstance(payload, dict):
                    violations.append(f"privacy_table_class_missing:{table_class}")
                    continue
                _require_fields(
                    payload,
                    _REQUIRED_TABLE_CLASS_FIELDS,
                    f"privacy_{table_class}",
                    violations,
                )

    timing = contract.get("timing_constants")
    if isinstance(timing, dict):
        for constant_name in _REQUIRED_TIMING_CONSTANTS:
            constant = timing.get(constant_name)
            if not isinstance(constant, dict):
                violations.append(f"timing_constant_missing:{constant_name}")
                continue
            _require_fields(constant, _REQUIRED_TIMING_FIELDS, f"timing_{constant_name}", violations)

        perf_scope = timing.get("performance_scope")
        if isinstance(perf_scope, dict):
            if perf_scope.get("lt_10_seconds_definition") != "match_engine_batch_execution_on_pre_arrived_events_only":
                violations.append("timing_lt10_scope_mismatch")
            non_scope = perf_scope.get("explicit_non_scope")
            if not isinstance(non_scope, list) or len(non_scope) < 5:
                violations.append("timing_lt10_non_scope_missing")

    required_ci_wiring = contract.get("required_ci_wiring")
    if isinstance(required_ci_wiring, list):
        for token in required_ci_wiring:
            if str(token) not in ci_text:
                violations.append(f"ci_missing_token:{token}")
    else:
        violations.append("required_ci_wiring_missing")

    spec_required_tokens = (
        "Provider-origin payload paths are **provenance metadata only**",
        "verified/canonicalized B2.2/B2.3 ingress envelope",
        "Raw unauthenticated webhook payloads are forbidden as B2.3 first-authority input",
        "provider amount parsing",
        "JSON deserialization normalization",
        "decimal-string-to-minor-unit conversion",
        "currency exponent application",
        "Decimal-string providers must use exact decimal arithmetic",
        "float()",
        "parseFloat",
        "JavaScript `Number`",
        "activity-independent database scheduled pruning via governed Neon `pg_cron`",
        "platform-keyed extraction registry",
        "The `<10 second` benchmark applies only to match-engine batch execution over pre-arrived events.",
    )
    for token in spec_required_tokens:
        if token not in spec_text:
            violations.append(f"spec_missing_token:{token}")

    if simulate_regression:
        violations.append("synthetic_regression=forced_failure_path")

    return (0 if not violations else 1), violations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enforce B2.3 Pre-P1 specification closure contract")
    parser.add_argument("--contract-file", default=CONTRACT_FILE)
    parser.add_argument("--spec-file", default=SPEC_FILE)
    parser.add_argument("--ci-file", default=CI_FILE)
    parser.add_argument("--simulate-regression", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status, violations = run_enforcement(
        repo_root=REPO_ROOT,
        contract_file=_resolve(REPO_ROOT, args.contract_file),
        spec_file=_resolve(REPO_ROOT, args.spec_file),
        ci_file=_resolve(REPO_ROOT, args.ci_file),
        simulate_regression=bool(args.simulate_regression),
    )
    if violations:
        for violation in violations:
            print(violation)
        print("result=FAIL")
    else:
        print("result=PASS")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
