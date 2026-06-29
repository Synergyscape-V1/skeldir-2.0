"""B2.5-P4 money authority adapter tests."""

from __future__ import annotations

from decimal import Decimal

from app.trust.money_authority_registry import (
    MONEY_FIELD_REGISTRY,
    MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
    FORBIDDEN_MONEY_FIELD_NAMES,
)
from app.trust.money_source_adapter import (
    AuthoritativeMoneyMinor,
    MoneyAuthorityDecision,
    resolve_authoritative_money,
)


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


def test_registry_maps_current_trust_money_field_to_approved_sources() -> None:
    authority = MONEY_FIELD_REGISTRY["verified_revenue_minor"]
    assert authority.field_policy.zero_allowed is True
    assert authority.field_policy.negative_policy == "forbidden"
    source_paths = {
        (mapping.source_domain, mapping.source_field_path, mapping.authority_class)
        for mapping in authority.approved_sources
    }
    assert (
        "b23_match_verdicts",
        "canonical_net_verified_amount_minor",
        "authoritative_minor_units",
    ) in source_paths
    assert (
        "webhook_ingress_identities",
        "verified_amount_minor",
        "authoritative_minor_units",
    ) in source_paths
    assert ("provider_payload", "gross_major", "provider_decimal_string") in source_paths


def test_integer_minor_unit_source_is_accepted_with_typed_result() -> None:
    result = _resolve(raw_value=12345, currency="usd")
    assert isinstance(result, AuthoritativeMoneyMinor)
    assert result.status == "accepted_authoritative_minor_units"
    assert result.reason_code is None
    assert result.amount_minor == 12345
    assert result.currency == "USD"
    assert result.authority_class == "authoritative_minor_units"
    assert result.external_projection()["amount_minor"] == 12345


def test_legacy_float_only_state_refuses_without_exception_or_amount() -> None:
    result = _resolve(
        source_domain="attribution_dashboard",
        source_field_path="revenue",
        raw_value=123.45,
    )
    assert result.status == "refused_money_source_not_authoritative"
    assert result.reason_code == MONEY_SOURCE_NOT_AUTHORITATIVE_REASON
    assert result.amount_minor is None
    assert result.authority_class == "legacy_dashboard_float"


def test_forbidden_dto_float_field_names_are_not_authoritative() -> None:
    for field_name in FORBIDDEN_MONEY_FIELD_NAMES:
        result = _resolve(
            source_domain="export_row",
            source_field_path=field_name,
            raw_value=123.45,
        )
        assert result.status == "refused_money_source_not_authoritative"
        assert result.amount_minor is None


def test_raw_float_on_approved_minor_source_is_invalid_not_rounded() -> None:
    result = _resolve(raw_value=123.45)
    assert result.status == "invalid_numeric_format"
    assert result.amount_minor is None


def test_missing_authoritative_value_degrades_without_exception() -> None:
    result = _resolve(raw_value=None)
    assert result.status == "degraded_money_source_not_authoritative"
    assert result.reason_code == MONEY_SOURCE_NOT_AUTHORITATIVE_REASON
    assert result.amount_minor is None


def test_unknown_source_path_fails_closed() -> None:
    result = _resolve(
        source_domain="b23_match_verdicts",
        source_field_path="unknown_display_amount",
        raw_value=12345,
    )
    assert result.status == "source_field_unmapped"
    assert result.amount_minor is None


def test_provider_decimal_strings_convert_exactly_by_currency_exponent() -> None:
    assert _resolve(
        source_domain="provider_payload",
        source_field_path="gross_major",
        raw_value="123.45",
        currency="USD",
    ).amount_minor == 12345
    assert _resolve(
        source_domain="provider_payload",
        source_field_path="gross_major",
        raw_value="123.45",
        currency="EUR",
    ).amount_minor == 12345
    assert _resolve(
        source_domain="provider_payload",
        source_field_path="gross_major",
        raw_value="123",
        currency="JPY",
    ).amount_minor == 123
    assert _resolve(
        source_domain="provider_payload",
        source_field_path="gross_major",
        raw_value="1.234",
        currency="KWD",
    ).amount_minor == 1234


def test_provider_decimal_strings_reject_sub_minor_and_unknown_currency() -> None:
    cases = [
        ("123.45", "JPY", "invalid_currency_or_exponent"),
        ("1.2345", "KWD", "invalid_currency_or_exponent"),
        ("1.234", "USD", "invalid_currency_or_exponent"),
        ("1.00", "ZZZ", "invalid_currency_or_exponent"),
        ("1e2", "USD", "invalid_numeric_format"),
        ("$1.00", "USD", "invalid_numeric_format"),
    ]
    for raw_value, currency, status in cases:
        result = _resolve(
            source_domain="provider_payload",
            source_field_path="gross_major",
            raw_value=raw_value,
            currency=currency,
        )
        assert result.status == status
        assert result.amount_minor is None


def test_cents_labeled_sources_fail_closed_for_non_cent_currencies() -> None:
    accepted = _resolve(
        source_domain="revenue_ledger",
        source_field_path="verified_total_cents",
        raw_value=12345,
        currency="USD",
    )
    assert accepted.status == "accepted_authoritative_minor_units"
    assert accepted.amount_minor == 12345

    for currency in ("JPY", "KWD"):
        result = _resolve(
            source_domain="revenue_ledger",
            source_field_path="verified_total_cents",
            raw_value=12345,
            currency=currency,
        )
        assert result.status == "invalid_currency_or_exponent"
        assert result.amount_minor is None


def test_decimal_objects_and_decimal_from_float_are_not_provider_string_authority() -> None:
    for raw_value in (Decimal("123.45"), Decimal(1.23)):
        result = _resolve(
            source_domain="provider_payload",
            source_field_path="gross_major",
            raw_value=raw_value,
            currency="USD",
        )
        assert result.status == "invalid_numeric_format"
        assert result.amount_minor is None


def test_zero_and_negative_policy_is_field_specific() -> None:
    zero = _resolve(raw_value=0)
    assert zero.status == "accepted_authoritative_minor_units"
    assert zero.amount_minor == 0

    negative = _resolve(raw_value=-1)
    assert negative.status == "refused_money_source_not_authoritative"
    assert negative.reason_code == MONEY_SOURCE_NOT_AUTHORITATIVE_REASON
    assert negative.amount_minor is None


def test_result_shape_is_not_bool_or_ambiguous_none() -> None:
    accepted = _resolve()
    refused = _resolve(source_domain="budget_dto", source_field_path="total_budget", raw_value=1000.0)
    for result in (accepted, refused):
        assert not isinstance(result, bool)
        projection = result.external_projection()
        assert projection["status"]
        assert projection["source_domain"]
        assert projection["source_field_path"]
        assert projection["intended_trust_field"]
        assert "amount_minor" in projection
        if result.status != "accepted_authoritative_minor_units":
            assert projection["reason_code"] == MONEY_SOURCE_NOT_AUTHORITATIVE_REASON
