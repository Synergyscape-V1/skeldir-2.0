#!/usr/bin/env python3
"""Validate B2.5-P4 authoritative money source adapter."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping

import yaml


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.trust.money_authority_registry import (  # noqa: E402
    CURRENCY_EXPONENTS,
    FORBIDDEN_MONEY_FIELD_NAMES,
    MONEY_FIELD_REGISTRY,
    MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
    MoneySourceMapping,
    TrustMoneyFieldAuthority,
    iter_trust_money_authorities,
)
from app.trust.money_source_adapter import (  # noqa: E402
    AuthoritativeMoneyMinor,
    MoneyAuthorityDecision,
    resolve_authoritative_money,
)


class B25P4ValidationError(RuntimeError):
    """Raised when B2.5-P4 validation fails."""


TRUST_SCHEMA_PATH = ROOT / "contracts/trust-api/trust-envelope.v1.yaml"
TRUST_DIR = ROOT / "backend/app/trust"
TRUST_MONEY_FILES = (
    TRUST_DIR / "money_authority_registry.py",
    TRUST_DIR / "money_source_adapter.py",
)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise B25P4ValidationError(f"{path} did not parse as a mapping")
    return data


def _is_integer_schema(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    if node.get("type") == "integer":
        return True
    if "$ref" in node and str(node["$ref"]).endswith("Integer"):
        return True
    return any(
        _is_integer_schema(child)
        for key in ("anyOf", "oneOf", "allOf")
        for child in node.get(key, [])
        if isinstance(node.get(key), list)
    )


def discover_authoritative_money_fields() -> set[str]:
    schema = _read_yaml(TRUST_SCHEMA_PATH)
    props = schema.get("properties")
    if not isinstance(props, dict):
        raise B25P4ValidationError("TrustEnvelope schema properties missing")
    fields: set[str] = set()
    for field_name, node in props.items():
        if not isinstance(field_name, str):
            continue
        money_name = (
            field_name == "amount_minor"
            or field_name.endswith("_minor")
            and any(
                field_name.startswith(prefix)
                for prefix in ("verified_", "revenue_", "spend_", "budget_", "allocation_")
            )
        )
        if money_name and _is_integer_schema(node):
            fields.add(field_name)
    return fields


def validate_registry_totality(
    *,
    registry: Mapping[str, TrustMoneyFieldAuthority] = MONEY_FIELD_REGISTRY,
) -> int:
    fields = discover_authoritative_money_fields()
    missing = fields - set(registry)
    extra = set(registry) - fields
    if missing or extra:
        raise B25P4ValidationError(
            f"money registry mismatch missing={sorted(missing)} extra={sorted(extra)}"
        )
    checked = 0
    for field_name in sorted(fields):
        authority = registry[field_name]
        if not authority.approved_sources:
            raise B25P4ValidationError(f"{field_name} has no approved/refusal source policy")
        if authority.field_policy.trust_field != field_name:
            raise B25P4ValidationError(f"{field_name} field policy is not field-bound")
        for mapping in authority.approved_sources:
            if mapping.authority_class not in {
                "authoritative_minor_units",
                "authoritative_cents",
                "money_cents_type",
                "provider_decimal_string",
            }:
                raise B25P4ValidationError(f"{field_name} maps forbidden source class")
            checked += 1
    return checked


def _resolve(
    *,
    source_domain: str = "b23_match_verdicts",
    source_field_path: str = "canonical_net_verified_amount_minor",
    raw_value: object = 12345,
    currency: str | None = "USD",
    intended_trust_field: str = "verified_revenue_minor",
) -> MoneyAuthorityDecision:
    return resolve_authoritative_money(
        source_domain=source_domain,
        source_field_path=source_field_path,
        raw_value=raw_value,
        currency=currency,
        intended_trust_field=intended_trust_field,
    )


def _require_accepted(result: MoneyAuthorityDecision, expected_minor: int) -> None:
    if not isinstance(result, AuthoritativeMoneyMinor):
        raise B25P4ValidationError(f"expected accepted result, got {result}")
    if result.amount_minor != expected_minor:
        raise B25P4ValidationError(f"amount mismatch: {result.amount_minor}")
    if not isinstance(result.amount_minor, int) or isinstance(result.amount_minor, bool):
        raise B25P4ValidationError("accepted amount_minor is not an int")
    if result.reason_code is not None:
        raise B25P4ValidationError("accepted money carried refusal reason")


def _require_refused(result: MoneyAuthorityDecision, status_prefix: str | None = None) -> None:
    if result.status == "accepted_authoritative_minor_units":
        raise B25P4ValidationError(f"unexpected accepted result: {result}")
    if status_prefix and not result.status.startswith(status_prefix):
        raise B25P4ValidationError(f"unexpected status {result.status}")
    if result.reason_code != MONEY_SOURCE_NOT_AUTHORITATIVE_REASON:
        raise B25P4ValidationError(f"missing reason code: {result}")
    if result.amount_minor is not None:
        raise B25P4ValidationError(f"refusal carried amount_minor: {result}")


def validate_positive_integer_sources() -> int:
    count = 0
    for authority in iter_trust_money_authorities():
        for mapping in authority.approved_sources:
            if mapping.authority_class == "provider_decimal_string":
                continue
            _require_accepted(
                _resolve(
                    source_domain=mapping.source_domain,
                    source_field_path=mapping.source_field_path,
                    raw_value=12345,
                    currency="USD",
                    intended_trust_field=authority.trust_field,
                ),
                12345,
            )
            count += 1
    return count


def validate_dto_float_rejection() -> int:
    count = 0
    domains = ("attribution_dashboard", "export_row", "budget_dto")
    for domain in domains:
        for field_name in FORBIDDEN_MONEY_FIELD_NAMES:
            _require_refused(
                _resolve(
                    source_domain=domain,
                    source_field_path=field_name,
                    raw_value=123.45,
                ),
                "refused",
            )
            count += 1
    return count


def validate_legacy_float_refusal() -> int:
    _require_refused(
        _resolve(
            source_domain="attribution_dashboard",
            source_field_path="revenue",
            raw_value=123.45,
        ),
        "refused",
    )
    _require_refused(_resolve(raw_value=123.45), "invalid")
    return 2


def validate_decimal_conversion() -> int:
    cases = (
        ("USD", "123.45", 12345),
        ("EUR", "123.45", 12345),
        ("JPY", "123", 123),
        ("KWD", "1.234", 1234),
    )
    for currency, raw, expected in cases:
        _require_accepted(
            _resolve(
                source_domain="provider_payload",
                source_field_path="gross_major",
                raw_value=raw,
                currency=currency,
            ),
            expected,
        )
    return len(cases)


def validate_currency_exponents() -> int:
    required = {"USD": 2, "EUR": 2, "JPY": 0, "KWD": 3}
    for currency, exponent in required.items():
        if CURRENCY_EXPONENTS.get(currency) != exponent:
            raise B25P4ValidationError(f"currency exponent mismatch: {currency}")
    for currency in ("JPY", "KWD"):
        result = _resolve(
            source_domain="revenue_ledger",
            source_field_path="verified_total_cents",
            raw_value=12345,
            currency=currency,
        )
        if result.status != "invalid_currency_or_exponent":
            raise B25P4ValidationError(f"cents source accepted for {currency}")
    return len(required) + 2


def validate_rejections() -> tuple[int, int]:
    sub_minor_cases = (("JPY", "123.45"), ("KWD", "1.2345"), ("USD", "1.234"))
    for currency, raw in sub_minor_cases:
        result = _resolve(
            source_domain="provider_payload",
            source_field_path="gross_major",
            raw_value=raw,
            currency=currency,
        )
        if result.status != "invalid_currency_or_exponent":
            raise B25P4ValidationError(f"sub-minor accepted: {currency} {raw}")
    unknown = _resolve(
        source_domain="provider_payload",
        source_field_path="gross_major",
        raw_value="1.00",
        currency="ZZZ",
    )
    if unknown.status != "invalid_currency_or_exponent":
        raise B25P4ValidationError("unknown currency was accepted")
    return len(sub_minor_cases), 1


def validate_negative_zero_policy() -> int:
    _require_accepted(_resolve(raw_value=0), 0)
    _require_refused(_resolve(raw_value=-1), "refused")
    for authority in iter_trust_money_authorities():
        policy = authority.field_policy
        if not isinstance(policy.zero_allowed, bool):
            raise B25P4ValidationError(f"{authority.trust_field} zero policy missing")
        if policy.negative_policy not in {"forbidden", "refund_or_adjustment_only"}:
            raise B25P4ValidationError(f"{authority.trust_field} negative policy missing")
    return len(MONEY_FIELD_REGISTRY) + 2


def validate_typed_result_shape() -> int:
    results = (
        _resolve(),
        _resolve(source_domain="export_row", source_field_path="revenue", raw_value=123.45),
        _resolve(raw_value=None),
        _resolve(raw_value=123.45),
        _resolve(source_field_path="unknown_amount", raw_value=123),
    )
    for result in results:
        if isinstance(result, bool):
            raise B25P4ValidationError("bare bool result detected")
        projection = result.external_projection()
        for key in (
            "status",
            "source_domain",
            "source_field_path",
            "intended_trust_field",
            "source_value_type",
            "authority_class",
            "conversion_method",
            "evidence_label",
        ):
            if key not in projection:
                raise B25P4ValidationError(f"typed result missing {key}")
        if result.status == "accepted_authoritative_minor_units":
            if result.reason_code is not None or result.amount_minor is None:
                raise B25P4ValidationError("accepted result is ambiguous")
        else:
            _require_refused(result)
    return len(results)


def validate_static_import_isolation() -> int:
    forbidden_modules = (
        "app.api.attribution",
        "backend.app.api.attribution",
        "app.schemas.attribution",
        "backend.app.schemas.attribution",
        "app.api.export",
        "backend.app.api.export",
        "app.api.budget",
        "backend.app.api.budget",
        "sqlalchemy",
        "psycopg",
        "asyncpg",
        "celery",
        "requests",
        "httpx",
        "urllib",
        "openai",
        "anthropic",
    )
    checked = 0
    for path in TRUST_MONEY_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name
                    if module in forbidden_modules or any(
                        module.startswith(prefix + ".") for prefix in forbidden_modules
                    ):
                        raise B25P4ValidationError(f"forbidden import {module} in {path}")
                    checked += 1
                continue
            if module:
                if module in forbidden_modules or any(
                    module.startswith(prefix + ".") for prefix in forbidden_modules
                ):
                    raise B25P4ValidationError(f"forbidden import {module} in {path}")
                checked += 1
    return checked


def validate_numeric_preservation() -> int:
    for raw_value in (1.25, float("nan"), float("inf"), float("-inf")):
        _require_refused(_resolve(raw_value=raw_value))
    accepted = _resolve(raw_value=12345).external_projection()
    if not isinstance(accepted["amount_minor"], int):
        raise B25P4ValidationError("accepted result did not emit integer amount_minor")
    return 5


def validate_scope_overreach() -> int:
    disallowed_tokens = (
        "TrustEnvelopeBuilder",
        "APIRouter",
        "/trust/v1",
        "sign_trust_envelope",
        "verify_trust_envelope",
        "jwks",
        "machine_caller",
        "trust_access",
        "mcp",
    )
    checked = 0
    for path in TRUST_MONEY_FILES:
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in disallowed_tokens:
            if token in text:
                raise B25P4ValidationError(f"P4 scope overreach token {token} in {path}")
            checked += 1
    return checked


def _run_validator(command: list[str], marker: str) -> None:
    proc = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        raise B25P4ValidationError(
            f"{command} failed stdout={proc.stdout[-1000:]} stderr={proc.stderr[-1000:]}"
        )
    if marker not in proc.stdout:
        raise B25P4ValidationError(f"{marker} missing from {command}")


def validate_prior_phase_regressions() -> tuple[int, int, int]:
    _run_validator(
        [sys.executable, "scripts/ci/validate_b25_p1_contracts.py", "--negative-control"],
        "B25_P1_CONTRACT_VALIDATION_PASS",
    )
    _run_validator(
        [sys.executable, "scripts/ci/validate_b25_p1_trust_drift.py", "--negative-control"],
        "B25_P1_TRUST_DRIFT_VALIDATION_PASS",
    )
    _run_validator(
        [sys.executable, "scripts/ci/validate_b25_p2_canonicalization.py", "--negative-control"],
        "B25_P2_CANONICALIZATION_VALIDATION_PASS",
    )
    _run_validator(
        [sys.executable, "scripts/ci/validate_b25_p3_text_disposition.py", "--negative-control"],
        "B25_P3_TEXT_DISPOSITION_VALIDATION_PASS",
    )
    return 2, 1, 1


def validate_meta_negative_controls() -> int:
    controls = 0
    try:
        validate_registry_totality(registry={})
    except B25P4ValidationError:
        controls += 1
    else:
        raise B25P4ValidationError("missing mapping mutation was accepted")

    authority = MONEY_FIELD_REGISTRY["verified_revenue_minor"]
    bad_source = MoneySourceMapping(
        source_domain="attribution_dashboard",
        source_field_path="revenue",
        authority_class="legacy_dashboard_float",
        evidence_label="attribution_dashboard.revenue",
        conversion_method="float_direct",
    )
    mutated = {
        "verified_revenue_minor": replace(
            authority,
            approved_sources=authority.approved_sources + (bad_source,),
        )
    }
    try:
        validate_registry_totality(registry=mutated)
    except B25P4ValidationError:
        controls += 1
    else:
        raise B25P4ValidationError("float authority mutation was accepted")

    for kwargs in (
        {"raw_value": 123.45},
        {
            "source_domain": "provider_payload",
            "source_field_path": "gross_major",
            "raw_value": 1.23,
            "currency": "USD",
        },
        {
            "source_domain": "provider_payload",
            "source_field_path": "gross_major",
            "raw_value": "1.234",
            "currency": "USD",
        },
        {
            "source_domain": "provider_payload",
            "source_field_path": "gross_major",
            "raw_value": "1.00",
            "currency": "ZZZ",
        },
    ):
        result = _resolve(**kwargs)
        if result.status == "accepted_authoritative_minor_units":
            raise B25P4ValidationError(f"negative control accepted: {kwargs}")
        controls += 1

    refused = _resolve(source_domain="budget_dto", source_field_path="total_budget", raw_value=1000.0)
    if refused.reason_code != MONEY_SOURCE_NOT_AUTHORITATIVE_REASON:
        raise B25P4ValidationError("typed refusal reason mutation control failed")
    controls += 1
    return controls


def validate_all() -> None:
    source_mappings = validate_registry_totality()
    positive = validate_positive_integer_sources()
    dto_float = validate_dto_float_rejection()
    legacy_float = validate_legacy_float_refusal()
    decimal_controls = validate_decimal_conversion()
    exponent_controls = validate_currency_exponents()
    sub_minor, unknown_currency = validate_rejections()
    negative_zero = validate_negative_zero_policy()
    typed_shape = validate_typed_result_shape()
    static_isolation = validate_static_import_isolation()
    numeric_preservation = validate_numeric_preservation()
    p1_controls, p2_controls, p3_controls = validate_prior_phase_regressions()
    scope_controls = validate_scope_overreach()
    meta_negative = validate_meta_negative_controls()

    print("B25_P4_MONEY_AUTHORITY_VALIDATION_PASS")
    print(f"money_authority_fields_checked={len(discover_authoritative_money_fields())}")
    print(f"minor_unit_source_mappings_checked={source_mappings}")
    print(f"approved_integer_source_controls_passed={positive}")
    print(f"dto_float_rejection_controls_passed={dto_float}")
    print(f"legacy_float_refusal_controls_passed={legacy_float}")
    print(f"decimal_string_conversion_controls_passed={decimal_controls}")
    print(f"currency_exponent_controls_passed={exponent_controls}")
    print(f"sub_minor_rejection_controls_passed={sub_minor}")
    print(f"unknown_currency_rejection_controls_passed={unknown_currency}")
    print(f"negative_zero_policy_controls_passed={negative_zero}")
    print(f"typed_result_shape_controls_passed={typed_shape}")
    print(f"static_dto_import_isolation_controls_passed={static_isolation}")
    print(f"raw_float_hash_or_canonicalization_controls_passed={numeric_preservation}")
    print(f"p1_regression_controls_passed={p1_controls}")
    print(f"p2_regression_controls_passed={p2_controls}")
    print(f"p3_regression_controls_passed={p3_controls}")
    print(f"scope_overreach_controls_passed={scope_controls}")
    print(f"meta_negative_controls_passed={meta_negative}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    parser.parse_args()
    try:
        validate_all()
    except Exception as exc:
        print(f"B25_P4_MONEY_AUTHORITY_VALIDATION_FAIL: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
