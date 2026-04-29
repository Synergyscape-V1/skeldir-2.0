#!/usr/bin/env python3
"""B2.3 Pre-P1 specification closure enforcer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_FILE = "contracts-internal/governance/b23_pre_p1_spec_gate.main.json"
SPEC_FILE = "docs/forensics/B2.3-Pre-P1 Specification Gates A-B.md"
CI_FILE = ".github/workflows/ci.yml"

_REQUIRED_PROVIDERS = ("stripe", "paypal", "shopify", "woocommerce")
_REQUIRED_PROVIDER_FIELDS = (
    "authoritative_revenue_field",
    "source_currency_field",
    "source_amount_unit",
    "canonical_amount_basis",
    "canonical_amount_field",
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
_REQUIRED_FLOAT_BAN_SCOPES = (
    "canonical_financial_storage",
    "match_arithmetic",
    "discrepancy_percentage_computation",
    "refund_chargeback_adjustment_arithmetic",
)
_REQUIRED_ADJUSTMENT_EVENTS = (
    "refund_partial",
    "refund_full",
    "chargeback_opened",
    "chargeback_won",
    "chargeback_lost",
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


def _require_fields(obj: dict[str, Any], fields: tuple[str, ...], prefix: str, violations: list[str]) -> None:
    for field in fields:
        value = obj.get(field)
        if not _is_non_empty(value):
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

    if contract.get("contract_id") != "b23.pre_p1.spec_gate.main":
        violations.append("contract_id_mismatch")
    if contract.get("phase") != "B2.3-Pre-P1":
        violations.append("contract_phase_mismatch")
    if contract.get("branch") != "main":
        violations.append("contract_branch_mismatch")

    p0_truth = contract.get("p0_inherited_truth_correction")
    if not isinstance(p0_truth, dict):
        violations.append("p0_inherited_truth_correction_missing")
    else:
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
    if not isinstance(revenue, dict):
        violations.append("revenue_extraction_standard_missing")
    else:
        if not _is_non_empty(revenue.get("canonical_amount_basis")):
            violations.append("revenue_missing_canonical_amount_basis")

        storage = revenue.get("canonical_storage")
        if not isinstance(storage, dict):
            violations.append("revenue_canonical_storage_missing")
        else:
            if storage.get("amount") != "integer_minor_units":
                violations.append("revenue_storage_amount_not_minor_units")
            if storage.get("currency") != "iso_4217_code":
                violations.append("revenue_storage_currency_missing_iso")
            if storage.get("binary_float_forbidden") is not True:
                violations.append("revenue_binary_float_forbidden_missing")
            scopes = storage.get("binary_float_forbidden_scopes", [])
            if not isinstance(scopes, list):
                violations.append("revenue_binary_float_scopes_invalid")
            else:
                for scope in _REQUIRED_FLOAT_BAN_SCOPES:
                    if scope not in scopes:
                        violations.append(f"revenue_binary_float_scope_missing:{scope}")
            numeric_policy = storage.get("numeric_exception_policy")
            if not isinstance(numeric_policy, dict):
                violations.append("revenue_numeric_exception_policy_missing")
            else:
                if numeric_policy.get("postgres_numeric_allowed_only_with_declared_scale") is not True:
                    violations.append("revenue_numeric_policy_scale_missing")
                if numeric_policy.get("declared_rounding_mode_required") is not True:
                    violations.append("revenue_numeric_policy_rounding_requirement_missing")

        registry = revenue.get("platform_keyed_extraction_registry_requirement")
        if not isinstance(registry, dict):
            violations.append("revenue_platform_keyed_registry_missing")
        else:
            if registry.get("required") is not True:
                violations.append("revenue_platform_keyed_registry_required_missing")
            if registry.get("inline_provider_amount_access_in_match_kernel_forbidden") is not True:
                violations.append("revenue_inline_provider_access_forbid_missing")
            if registry.get("missing_registry_entry_must_fail_tests") is not True:
                violations.append("revenue_missing_registry_entry_fail_test_missing")

        providers = revenue.get("providers")
        if not isinstance(providers, dict):
            violations.append("revenue_providers_block_missing")
        else:
            for provider in _REQUIRED_PROVIDERS:
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

        if not _is_non_empty(revenue.get("unsupported_or_ambiguous_field_policy")):
            violations.append("revenue_unsupported_field_policy_missing")
        if not _is_non_empty(revenue.get("rationale")):
            violations.append("revenue_rationale_missing")

    concurrency = contract.get("refund_chargeback_concurrency_law")
    if not isinstance(concurrency, dict):
        violations.append("refund_chargeback_concurrency_law_missing")
    else:
        if concurrency.get("model") != "append_only_immutable_revenue_events":
            violations.append("concurrency_model_mismatch")
        if concurrency.get("tenant_scoped_provider_idempotency_required") is not True:
            violations.append("concurrency_tenant_scoped_idempotency_missing")
        if concurrency.get("database_duplicate_event_rejection_required") is not True:
            violations.append("concurrency_duplicate_event_rejection_missing")
        if concurrency.get("forbid_unsafe_read_modify_write_net_updates") is not True:
            violations.append("concurrency_lost_update_forbid_missing")
        if not _is_non_empty(concurrency.get("net_revenue_computation")):
            violations.append("concurrency_net_revenue_computation_missing")
        controls = concurrency.get("required_concurrency_controls")
        if not isinstance(controls, list) or not controls:
            violations.append("concurrency_controls_missing")
        events = concurrency.get("distinct_adjustment_events")
        if not isinstance(events, list):
            violations.append("concurrency_distinct_adjustment_events_missing")
        else:
            for event in _REQUIRED_ADJUSTMENT_EVENTS:
                if event not in events:
                    violations.append(f"concurrency_adjustment_event_missing:{event}")

    privacy = contract.get("table_privacy_lifecycle_pre_spec")
    if not isinstance(privacy, dict):
        violations.append("table_privacy_lifecycle_pre_spec_missing")
    else:
        global_rules = privacy.get("global_rules")
        if not isinstance(global_rules, dict):
            violations.append("privacy_global_rules_missing")
        else:
            if global_rules.get("tenant_isolation_required") is not True:
                violations.append("privacy_tenant_isolation_requirement_missing")
            if global_rules.get("rls_required") is not True:
                violations.append("privacy_rls_requirement_missing")
            if global_rules.get("pii_forbidden") is not True:
                violations.append("privacy_pii_forbidden_missing")

        classes = privacy.get("table_classes")
        if not isinstance(classes, dict):
            violations.append("privacy_table_classes_missing")
        else:
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
    if not isinstance(timing, dict):
        violations.append("timing_constants_missing")
    else:
        for constant_name in _REQUIRED_TIMING_CONSTANTS:
            constant = timing.get(constant_name)
            if not isinstance(constant, dict):
                violations.append(f"timing_constant_missing:{constant_name}")
                continue
            _require_fields(constant, _REQUIRED_TIMING_FIELDS, f"timing_{constant_name}", violations)

        perf_scope = timing.get("performance_scope")
        if not isinstance(perf_scope, dict):
            violations.append("timing_performance_scope_missing")
        else:
            if perf_scope.get("lt_10_seconds_definition") != "match_engine_batch_execution_on_pre_arrived_events_only":
                violations.append("timing_lt10_scope_mismatch")
            non_scope = perf_scope.get("explicit_non_scope")
            if not isinstance(non_scope, list) or len(non_scope) < 5:
                violations.append("timing_lt10_non_scope_missing")

    required_ci_wiring = contract.get("required_ci_wiring")
    if not isinstance(required_ci_wiring, list) or not required_ci_wiring:
        violations.append("required_ci_wiring_missing")
    else:
        for token in required_ci_wiring:
            if str(token) not in ci_text:
                violations.append(f"ci_missing_token:{token}")

    spec_required_tokens = (
        "activity-independent database scheduled pruning via governed Neon `pg_cron`",
        "platform-keyed extraction registry",
        "Binary floating-point use is forbidden",
        "append-only immutable revenue events",
        "WEBHOOK_ARRIVAL_WINDOW = 30 minutes",
        "PROVISIONAL_MATCH_WINDOW = 24 hours",
        "REFUND_REOPENING_WINDOW = 30 days",
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
