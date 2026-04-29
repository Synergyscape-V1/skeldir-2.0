#!/usr/bin/env python3
"""Strict validator for B2.3 Pre-P1 governance contract."""

from __future__ import annotations

from typing import Any


PROVIDERS = ("stripe", "paypal", "shopify", "woocommerce")
SOURCE_AMOUNT_UNITS = {"minor_units_integer", "decimal_string_major_units"}
CANONICAL_STORAGE_UNITS = {"minor_units_integer"}
ROUNDING_MODES = {"ROUND_HALF_UP"}
TAX_SHIPPING_DISCOUNT_ENUM = {"yes", "no", "unknown"}
PROCESSOR_FEE_ENUM = {"no"}
MULTI_CURRENCY_POSTURE_ENUM = {"same_currency_only_no_cross_currency_match"}
TIMING_UNIT_ENUM = {"minutes", "hours", "days"}
B23_AUTH_AMOUNT_FIELD_ENUM = {"verified_amount_minor"}
B23_AUTH_CURRENCY_FIELD_ENUM = {"verified_currency_code"}
RETENTION_CLASS_ENUM = {
    "financial_audit_long_retention",
    "operational_short_to_medium_retention",
    "derived_summary_rebuildable",
}
LIFECYCLE_MECHANISM_ENUM = {
    "governed_archival_policy",
    "append_only_with_governed_archival",
    "database_native_retention_or_governed_archival",
    "materialized_view_refresh_and_rebuild",
}
RAW_PAYLOAD_POSTURE_ENUM = {
    "forbidden",
    "hashed_or_redacted_minimum_fields_only",
    "redacted_or_structurally_minimized",
}
MONEY_STORAGE_AMOUNT_ENUM = {"integer_minor_units"}
MONEY_STORAGE_CURRENCY_ENUM = {"iso_4217_code"}
BINARY_FLOAT_FORBIDDEN_SCOPES = {
    "provider_amount_parsing",
    "json_deserialization_normalization",
    "decimal_string_to_minor_unit_conversion",
    "currency_exponent_application",
    "canonical_financial_storage",
    "match_arithmetic",
    "discrepancy_percentage_computation",
    "refund_chargeback_adjustment_arithmetic",
    "test_fixtures_except_explicit_rejection_or_normalization_tests",
}
ADJUSTMENT_EVENTS = {
    "refund_partial",
    "refund_full",
    "chargeback_opened",
    "chargeback_won",
    "chargeback_lost",
    "reversal",
}


def _is_non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_required_keys(
    *,
    obj: dict[str, Any],
    path: str,
    required: set[str],
    errors: list[str],
    forbid_extra: bool = True,
) -> None:
    missing = sorted(required - set(obj.keys()))
    for key in missing:
        errors.append(f"{path}.missing_key:{key}")
    if forbid_extra:
        extras = sorted(set(obj.keys()) - required)
        for key in extras:
            errors.append(f"{path}.unexpected_key:{key}")


def _validate_enum_str(
    *,
    obj: dict[str, Any],
    key: str,
    allowed: set[str],
    path: str,
    errors: list[str],
) -> None:
    value = obj.get(key)
    if not _is_non_empty_str(value):
        errors.append(f"{path}.{key}.type_or_empty")
        return
    if value not in allowed:
        errors.append(f"{path}.{key}.invalid_enum:{value}")


def _validate_str(
    *,
    obj: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
) -> None:
    if not _is_non_empty_str(obj.get(key)):
        errors.append(f"{path}.{key}.type_or_empty")


def _validate_bool(
    *,
    obj: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
) -> None:
    if not _is_bool(obj.get(key)):
        errors.append(f"{path}.{key}.type_not_bool")


def _validate_str_list(
    *,
    obj: dict[str, Any],
    key: str,
    path: str,
    errors: list[str],
    min_length: int = 1,
) -> list[str]:
    value = obj.get(key)
    if not isinstance(value, list):
        errors.append(f"{path}.{key}.type_not_list")
        return []
    if len(value) < min_length:
        errors.append(f"{path}.{key}.min_length_violation")
    parsed: list[str] = []
    for idx, item in enumerate(value):
        if not _is_non_empty_str(item):
            errors.append(f"{path}.{key}[{idx}].type_or_empty")
            continue
        parsed.append(item)
    return parsed


def validate_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    top_required = {
        "contract_id",
        "contract_version",
        "repository",
        "branch",
        "phase",
        "description",
        "inherits_from",
        "p0_inherited_truth_correction",
        "revenue_extraction_standard",
        "refund_chargeback_concurrency_law",
        "table_privacy_lifecycle_pre_spec",
        "timing_constants",
        "required_ci_wiring",
    }
    _validate_required_keys(
        obj=payload,
        path="contract",
        required=top_required,
        errors=errors,
    )

    for key in (
        "contract_id",
        "contract_version",
        "repository",
        "branch",
        "phase",
        "description",
    ):
        _validate_str(obj=payload, key=key, path="contract", errors=errors)

    inherits = payload.get("inherits_from")
    if not isinstance(inherits, dict):
        errors.append("inherits_from.type_not_dict")
    else:
        _validate_required_keys(
            obj=inherits,
            path="inherits_from",
            required={"b23_p0_semantic_authority_freeze_contract", "required_invariants"},
            errors=errors,
        )
        _validate_str(
            obj=inherits,
            key="b23_p0_semantic_authority_freeze_contract",
            path="inherits_from",
            errors=errors,
        )
        _validate_str_list(
            obj=inherits,
            key="required_invariants",
            path="inherits_from",
            errors=errors,
        )

    p0_truth = payload.get("p0_inherited_truth_correction")
    if not isinstance(p0_truth, dict):
        errors.append("p0_inherited_truth_correction.type_not_dict")
    else:
        _validate_required_keys(
            obj=p0_truth,
            path="p0_inherited_truth_correction",
            required={
                "activity_independent_lifecycle_mode",
                "governed_runtime_mechanism",
                "scheduled_job_name",
                "forbid_trigger_only_authority_claim",
                "preserve_contract_version",
                "preserve_false_authority_exclusion",
                "preserve_no_llm_deterministic_authority_path",
            },
            errors=errors,
        )
        _validate_str(
            obj=p0_truth,
            key="activity_independent_lifecycle_mode",
            path="p0_inherited_truth_correction",
            errors=errors,
        )
        _validate_str(
            obj=p0_truth,
            key="governed_runtime_mechanism",
            path="p0_inherited_truth_correction",
            errors=errors,
        )
        _validate_str(
            obj=p0_truth,
            key="scheduled_job_name",
            path="p0_inherited_truth_correction",
            errors=errors,
        )
        _validate_str(
            obj=p0_truth,
            key="preserve_contract_version",
            path="p0_inherited_truth_correction",
            errors=errors,
        )
        for key in (
            "forbid_trigger_only_authority_claim",
            "preserve_false_authority_exclusion",
            "preserve_no_llm_deterministic_authority_path",
        ):
            _validate_bool(
                obj=p0_truth,
                key=key,
                path="p0_inherited_truth_correction",
                errors=errors,
            )

    revenue = payload.get("revenue_extraction_standard")
    if not isinstance(revenue, dict):
        errors.append("revenue_extraction_standard.type_not_dict")
    else:
        _validate_required_keys(
            obj=revenue,
            path="revenue_extraction_standard",
            required={
                "source_boundary",
                "raw_webhook_payload_forbidden_as_b23_authority",
                "provider_origin_fields_are_provenance_only",
                "canonical_amount_basis",
                "canonical_storage",
                "exact_decimal_parsing_policy",
                "platform_keyed_extraction_registry_requirement",
                "providers",
                "unsupported_or_ambiguous_field_policy",
                "rationale",
            },
            errors=errors,
        )
        for key in (
            "source_boundary",
            "canonical_amount_basis",
            "unsupported_or_ambiguous_field_policy",
            "rationale",
        ):
            _validate_str(
                obj=revenue,
                key=key,
                path="revenue_extraction_standard",
                errors=errors,
            )
        for key in (
            "raw_webhook_payload_forbidden_as_b23_authority",
            "provider_origin_fields_are_provenance_only",
        ):
            _validate_bool(
                obj=revenue,
                key=key,
                path="revenue_extraction_standard",
                errors=errors,
            )

        storage = revenue.get("canonical_storage")
        if not isinstance(storage, dict):
            errors.append("revenue_extraction_standard.canonical_storage.type_not_dict")
        else:
            _validate_required_keys(
                obj=storage,
                path="revenue_extraction_standard.canonical_storage",
                required={
                    "amount",
                    "currency",
                    "binary_float_forbidden",
                    "binary_float_forbidden_scopes",
                    "numeric_exception_policy",
                },
                errors=errors,
            )
            _validate_enum_str(
                obj=storage,
                key="amount",
                allowed=MONEY_STORAGE_AMOUNT_ENUM,
                path="revenue_extraction_standard.canonical_storage",
                errors=errors,
            )
            _validate_enum_str(
                obj=storage,
                key="currency",
                allowed=MONEY_STORAGE_CURRENCY_ENUM,
                path="revenue_extraction_standard.canonical_storage",
                errors=errors,
            )
            _validate_bool(
                obj=storage,
                key="binary_float_forbidden",
                path="revenue_extraction_standard.canonical_storage",
                errors=errors,
            )
            float_scopes = _validate_str_list(
                obj=storage,
                key="binary_float_forbidden_scopes",
                path="revenue_extraction_standard.canonical_storage",
                errors=errors,
                min_length=len(BINARY_FLOAT_FORBIDDEN_SCOPES),
            )
            for scope in float_scopes:
                if scope not in BINARY_FLOAT_FORBIDDEN_SCOPES:
                    errors.append(
                        "revenue_extraction_standard.canonical_storage.binary_float_forbidden_scopes.invalid_enum:"
                        f"{scope}"
                    )
            numeric = storage.get("numeric_exception_policy")
            if not isinstance(numeric, dict):
                errors.append(
                    "revenue_extraction_standard.canonical_storage.numeric_exception_policy.type_not_dict"
                )
            else:
                _validate_required_keys(
                    obj=numeric,
                    path="revenue_extraction_standard.canonical_storage.numeric_exception_policy",
                    required={
                        "postgres_numeric_allowed_only_with_declared_scale",
                        "declared_rounding_mode_required",
                        "default_rounding_mode",
                    },
                    errors=errors,
                )
                _validate_bool(
                    obj=numeric,
                    key="postgres_numeric_allowed_only_with_declared_scale",
                    path="revenue_extraction_standard.canonical_storage.numeric_exception_policy",
                    errors=errors,
                )
                _validate_bool(
                    obj=numeric,
                    key="declared_rounding_mode_required",
                    path="revenue_extraction_standard.canonical_storage.numeric_exception_policy",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=numeric,
                    key="default_rounding_mode",
                    allowed=ROUNDING_MODES,
                    path="revenue_extraction_standard.canonical_storage.numeric_exception_policy",
                    errors=errors,
                )

        exact_decimal = revenue.get("exact_decimal_parsing_policy")
        if not isinstance(exact_decimal, dict):
            errors.append("revenue_extraction_standard.exact_decimal_parsing_policy.type_not_dict")
        else:
            _validate_required_keys(
                obj=exact_decimal,
                path="revenue_extraction_standard.exact_decimal_parsing_policy",
                required={
                    "required_for_source_units",
                    "providers_requiring_exact_decimal",
                    "require_exact_decimal_arithmetic",
                    "forbidden_binary_float_conversions",
                },
                errors=errors,
            )
            _validate_bool(
                obj=exact_decimal,
                key="require_exact_decimal_arithmetic",
                path="revenue_extraction_standard.exact_decimal_parsing_policy",
                errors=errors,
            )
            source_units = _validate_str_list(
                obj=exact_decimal,
                key="required_for_source_units",
                path="revenue_extraction_standard.exact_decimal_parsing_policy",
                errors=errors,
            )
            for unit in source_units:
                if unit not in SOURCE_AMOUNT_UNITS:
                    errors.append(
                        "revenue_extraction_standard.exact_decimal_parsing_policy.required_for_source_units.invalid_enum:"
                        f"{unit}"
                    )
            providers_req = _validate_str_list(
                obj=exact_decimal,
                key="providers_requiring_exact_decimal",
                path="revenue_extraction_standard.exact_decimal_parsing_policy",
                errors=errors,
            )
            for provider in providers_req:
                if provider not in PROVIDERS:
                    errors.append(
                        "revenue_extraction_standard.exact_decimal_parsing_policy.providers_requiring_exact_decimal.invalid_enum:"
                        f"{provider}"
                    )
            _validate_str_list(
                obj=exact_decimal,
                key="forbidden_binary_float_conversions",
                path="revenue_extraction_standard.exact_decimal_parsing_policy",
                errors=errors,
            )

        registry = revenue.get("platform_keyed_extraction_registry_requirement")
        if not isinstance(registry, dict):
            errors.append(
                "revenue_extraction_standard.platform_keyed_extraction_registry_requirement.type_not_dict"
            )
        else:
            _validate_required_keys(
                obj=registry,
                path="revenue_extraction_standard.platform_keyed_extraction_registry_requirement",
                required={
                    "required",
                    "inline_provider_amount_access_in_match_kernel_forbidden",
                    "registry_key",
                    "missing_registry_entry_must_fail_tests",
                },
                errors=errors,
            )
            _validate_bool(
                obj=registry,
                key="required",
                path="revenue_extraction_standard.platform_keyed_extraction_registry_requirement",
                errors=errors,
            )
            _validate_bool(
                obj=registry,
                key="inline_provider_amount_access_in_match_kernel_forbidden",
                path="revenue_extraction_standard.platform_keyed_extraction_registry_requirement",
                errors=errors,
            )
            _validate_bool(
                obj=registry,
                key="missing_registry_entry_must_fail_tests",
                path="revenue_extraction_standard.platform_keyed_extraction_registry_requirement",
                errors=errors,
            )
            _validate_str(
                obj=registry,
                key="registry_key",
                path="revenue_extraction_standard.platform_keyed_extraction_registry_requirement",
                errors=errors,
            )

        providers = revenue.get("providers")
        if not isinstance(providers, dict):
            errors.append("revenue_extraction_standard.providers.type_not_dict")
        else:
            _validate_required_keys(
                obj=providers,
                path="revenue_extraction_standard.providers",
                required=set(PROVIDERS),
                errors=errors,
            )
            provider_required = {
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
            }
            for provider in PROVIDERS:
                entry = providers.get(provider)
                if not isinstance(entry, dict):
                    errors.append(f"revenue_extraction_standard.providers.{provider}.type_not_dict")
                    continue
                _validate_required_keys(
                    obj=entry,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    required=provider_required,
                    errors=errors,
                )
                for key in (
                    "provider_origin_revenue_field",
                    "provider_origin_currency_field",
                    "canonical_amount_basis",
                    "currency_exponent_source",
                    "refund_chargeback_adjustment_posture",
                ):
                    _validate_str(
                        obj=entry,
                        key=key,
                        path=f"revenue_extraction_standard.providers.{provider}",
                        errors=errors,
                    )
                _validate_enum_str(
                    obj=entry,
                    key="b23_authority_amount_field",
                    allowed=B23_AUTH_AMOUNT_FIELD_ENUM,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="b23_authority_currency_field",
                    allowed=B23_AUTH_CURRENCY_FIELD_ENUM,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="source_amount_unit",
                    allowed=SOURCE_AMOUNT_UNITS,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="canonical_storage_unit",
                    allowed=CANONICAL_STORAGE_UNITS,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="rounding_mode",
                    allowed=ROUNDING_MODES,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                for key in ("tax_inclusion", "shipping_inclusion", "discount_inclusion"):
                    _validate_enum_str(
                        obj=entry,
                        key=key,
                        allowed=TAX_SHIPPING_DISCOUNT_ENUM,
                        path=f"revenue_extraction_standard.providers.{provider}",
                        errors=errors,
                    )
                _validate_enum_str(
                    obj=entry,
                    key="processor_fee_inclusion",
                    allowed=PROCESSOR_FEE_ENUM,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="multi_currency_posture",
                    allowed=MULTI_CURRENCY_POSTURE_ENUM,
                    path=f"revenue_extraction_standard.providers.{provider}",
                    errors=errors,
                )

    concurrency = payload.get("refund_chargeback_concurrency_law")
    if not isinstance(concurrency, dict):
        errors.append("refund_chargeback_concurrency_law.type_not_dict")
    else:
        _validate_required_keys(
            obj=concurrency,
            path="refund_chargeback_concurrency_law",
            required={
                "model",
                "tenant_scoped_provider_idempotency_required",
                "database_duplicate_event_rejection_required",
                "forbid_unsafe_read_modify_write_net_updates",
                "net_revenue_computation",
                "required_concurrency_controls",
                "concurrent_partial_refunds_requirement",
                "distinct_adjustment_events",
            },
            errors=errors,
        )
        _validate_str(
            obj=concurrency,
            key="model",
            path="refund_chargeback_concurrency_law",
            errors=errors,
        )
        _validate_str(
            obj=concurrency,
            key="net_revenue_computation",
            path="refund_chargeback_concurrency_law",
            errors=errors,
        )
        _validate_str(
            obj=concurrency,
            key="concurrent_partial_refunds_requirement",
            path="refund_chargeback_concurrency_law",
            errors=errors,
        )
        for key in (
            "tenant_scoped_provider_idempotency_required",
            "database_duplicate_event_rejection_required",
            "forbid_unsafe_read_modify_write_net_updates",
        ):
            _validate_bool(
                obj=concurrency,
                key=key,
                path="refund_chargeback_concurrency_law",
                errors=errors,
            )
        _validate_str_list(
            obj=concurrency,
            key="required_concurrency_controls",
            path="refund_chargeback_concurrency_law",
            errors=errors,
        )
        events = _validate_str_list(
            obj=concurrency,
            key="distinct_adjustment_events",
            path="refund_chargeback_concurrency_law",
            errors=errors,
            min_length=len(ADJUSTMENT_EVENTS),
        )
        for event in events:
            if event not in ADJUSTMENT_EVENTS:
                errors.append(
                    "refund_chargeback_concurrency_law.distinct_adjustment_events.invalid_enum:"
                    f"{event}"
                )

    privacy = payload.get("table_privacy_lifecycle_pre_spec")
    if not isinstance(privacy, dict):
        errors.append("table_privacy_lifecycle_pre_spec.type_not_dict")
    else:
        _validate_required_keys(
            obj=privacy,
            path="table_privacy_lifecycle_pre_spec",
            required={"global_rules", "table_classes"},
            errors=errors,
        )
        global_rules = privacy.get("global_rules")
        if not isinstance(global_rules, dict):
            errors.append("table_privacy_lifecycle_pre_spec.global_rules.type_not_dict")
        else:
            _validate_required_keys(
                obj=global_rules,
                path="table_privacy_lifecycle_pre_spec.global_rules",
                required={
                    "tenant_isolation_required",
                    "rls_required",
                    "pii_forbidden",
                    "raw_provider_payload_must_be_minimized",
                },
                errors=errors,
            )
            for key in (
                "tenant_isolation_required",
                "rls_required",
                "pii_forbidden",
                "raw_provider_payload_must_be_minimized",
            ):
                _validate_bool(
                    obj=global_rules,
                    key=key,
                    path="table_privacy_lifecycle_pre_spec.global_rules",
                    errors=errors,
                )
        table_classes = privacy.get("table_classes")
        if not isinstance(table_classes, dict):
            errors.append("table_privacy_lifecycle_pre_spec.table_classes.type_not_dict")
        else:
            table_required = {
                "match_verdicts",
                "exception_records",
                "revenue_events",
                "webhook_ingestion_logs",
                "read_models_or_materialized_summaries",
            }
            _validate_required_keys(
                obj=table_classes,
                path="table_privacy_lifecycle_pre_spec.table_classes",
                required=table_required,
                errors=errors,
            )
            class_required_fields = {
                "data_classification",
                "allowed_identifier_classes",
                "forbidden_columns",
                "raw_provider_payload_posture",
                "tenant_isolation_requirement",
                "rls_requirement",
                "retention_or_archival_class",
                "lifecycle_mechanism",
                "retention_rationale",
            }
            for class_name in table_required:
                entry = table_classes.get(class_name)
                if not isinstance(entry, dict):
                    errors.append(
                        f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}.type_not_dict"
                    )
                    continue
                _validate_required_keys(
                    obj=entry,
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    required=class_required_fields,
                    errors=errors,
                )
                for key in (
                    "data_classification",
                    "tenant_isolation_requirement",
                    "rls_requirement",
                    "retention_rationale",
                ):
                    _validate_str(
                        obj=entry,
                        key=key,
                        path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                        errors=errors,
                    )
                _validate_str_list(
                    obj=entry,
                    key="allowed_identifier_classes",
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    errors=errors,
                )
                _validate_str_list(
                    obj=entry,
                    key="forbidden_columns",
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="raw_provider_payload_posture",
                    allowed=RAW_PAYLOAD_POSTURE_ENUM,
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="retention_or_archival_class",
                    allowed=RETENTION_CLASS_ENUM,
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    errors=errors,
                )
                _validate_enum_str(
                    obj=entry,
                    key="lifecycle_mechanism",
                    allowed=LIFECYCLE_MECHANISM_ENUM,
                    path=f"table_privacy_lifecycle_pre_spec.table_classes.{class_name}",
                    errors=errors,
                )

    timing = payload.get("timing_constants")
    if not isinstance(timing, dict):
        errors.append("timing_constants.type_not_dict")
    else:
        _validate_required_keys(
            obj=timing,
            path="timing_constants",
            required={
                "WEBHOOK_ARRIVAL_WINDOW",
                "PROVISIONAL_MATCH_WINDOW",
                "REFUND_REOPENING_WINDOW",
                "performance_scope",
            },
            errors=errors,
        )
        timing_fields = {
            "value",
            "unit",
            "rationale",
            "consuming_phases",
            "tenant_configurable_pre_launch",
            "state_transition_effect",
            "future_constants_module_name",
        }
        for name in ("WEBHOOK_ARRIVAL_WINDOW", "PROVISIONAL_MATCH_WINDOW", "REFUND_REOPENING_WINDOW"):
            entry = timing.get(name)
            if not isinstance(entry, dict):
                errors.append(f"timing_constants.{name}.type_not_dict")
                continue
            _validate_required_keys(
                obj=entry,
                path=f"timing_constants.{name}",
                required=timing_fields,
                errors=errors,
            )
            if not _is_int(entry.get("value")):
                errors.append(f"timing_constants.{name}.value.type_not_int")
            _validate_enum_str(
                obj=entry,
                key="unit",
                allowed=TIMING_UNIT_ENUM,
                path=f"timing_constants.{name}",
                errors=errors,
            )
            _validate_str(
                obj=entry,
                key="rationale",
                path=f"timing_constants.{name}",
                errors=errors,
            )
            _validate_str(
                obj=entry,
                key="state_transition_effect",
                path=f"timing_constants.{name}",
                errors=errors,
            )
            _validate_str(
                obj=entry,
                key="future_constants_module_name",
                path=f"timing_constants.{name}",
                errors=errors,
            )
            _validate_bool(
                obj=entry,
                key="tenant_configurable_pre_launch",
                path=f"timing_constants.{name}",
                errors=errors,
            )
            _validate_str_list(
                obj=entry,
                key="consuming_phases",
                path=f"timing_constants.{name}",
                errors=errors,
            )

        perf = timing.get("performance_scope")
        if not isinstance(perf, dict):
            errors.append("timing_constants.performance_scope.type_not_dict")
        else:
            _validate_required_keys(
                obj=perf,
                path="timing_constants.performance_scope",
                required={"lt_10_seconds_definition", "explicit_non_scope"},
                errors=errors,
            )
            _validate_str(
                obj=perf,
                key="lt_10_seconds_definition",
                path="timing_constants.performance_scope",
                errors=errors,
            )
            _validate_str_list(
                obj=perf,
                key="explicit_non_scope",
                path="timing_constants.performance_scope",
                errors=errors,
                min_length=1,
            )

    _validate_str_list(
        obj=payload,
        key="required_ci_wiring",
        path="contract",
        errors=errors,
    )
    return errors
