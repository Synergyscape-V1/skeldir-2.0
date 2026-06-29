"""Pure B2.5-P4 authoritative money source adapter."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from app.trust.money_authority_registry import (
    CURRENCY_EXPONENTS,
    FORBIDDEN_DTO_SOURCE_DOMAINS,
    FORBIDDEN_MONEY_FIELD_NAMES,
    MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
    MoneyAuthorityClass,
    MoneyFieldPolicy,
    MoneySourceMapping,
    find_source_mapping,
    get_trust_money_authority,
)


MoneyAuthorityStatus = Literal[
    "accepted_authoritative_minor_units",
    "refused_money_source_not_authoritative",
    "degraded_money_source_not_authoritative",
    "invalid_currency_or_exponent",
    "invalid_numeric_format",
    "source_field_unmapped",
]

_DECIMAL_STRING_RE = re.compile(r"^[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
JSON_SAFE_INTEGER_LIMIT = 9_007_199_254_740_991


@dataclass(frozen=True)
class MoneyAuthorityDecision:
    status: MoneyAuthorityStatus
    reason_code: str | None
    source_domain: str
    source_field_path: str
    intended_trust_field: str
    currency: str | None
    amount_minor: int | None
    source_value_type: str
    authority_class: MoneyAuthorityClass
    conversion_method: str
    evidence_label: str

    def external_projection(self) -> dict[str, object]:
        """Return deterministic metadata for future builder/refusal consumers."""
        return asdict(self)


@dataclass(frozen=True)
class AuthoritativeMoneyMinor(MoneyAuthorityDecision):
    status: Literal["accepted_authoritative_minor_units"]
    reason_code: None
    currency: str
    amount_minor: int


@dataclass(frozen=True)
class MoneyAuthorityRefusal(MoneyAuthorityDecision):
    status: Literal["refused_money_source_not_authoritative", "source_field_unmapped"]
    reason_code: str
    amount_minor: None


@dataclass(frozen=True)
class MoneyAuthorityDegraded(MoneyAuthorityDecision):
    status: Literal["degraded_money_source_not_authoritative"]
    reason_code: str
    amount_minor: None


@dataclass(frozen=True)
class MoneyAuthorityInvalid(MoneyAuthorityDecision):
    status: Literal["invalid_currency_or_exponent", "invalid_numeric_format"]
    reason_code: str
    amount_minor: None


def resolve_authoritative_money(
    *,
    source_domain: str,
    source_field_path: str,
    raw_value: Any,
    currency: str | None,
    intended_trust_field: str,
) -> MoneyAuthorityDecision:
    """Resolve whether a candidate value may authoritatively populate trust money."""
    normalized_currency = _normalize_currency(currency)
    mapping = find_source_mapping(
        source_domain=source_domain,
        source_field_path=source_field_path,
        intended_trust_field=intended_trust_field,
    )
    authority = get_trust_money_authority(intended_trust_field)
    if authority is None or mapping is None:
        return _unmapped_decision(
            source_domain=source_domain,
            source_field_path=source_field_path,
            raw_value=raw_value,
            currency=normalized_currency,
            intended_trust_field=intended_trust_field,
        )

    if normalized_currency not in CURRENCY_EXPONENTS:
        return _invalid_decision(
            "invalid_currency_or_exponent",
            source_domain=source_domain,
            source_field_path=source_field_path,
            raw_value=raw_value,
            currency=normalized_currency,
            intended_trust_field=intended_trust_field,
            mapping=mapping,
        )

    if raw_value is None:
        return MoneyAuthorityDegraded(
            status="degraded_money_source_not_authoritative",
            reason_code=MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
            source_domain=source_domain,
            source_field_path=source_field_path,
            intended_trust_field=intended_trust_field,
            currency=normalized_currency,
            amount_minor=None,
            source_value_type="NoneType",
            authority_class=mapping.authority_class,
            conversion_method="missing_authoritative_value",
            evidence_label=mapping.evidence_label,
        )

    if mapping.authority_class in {
        "authoritative_minor_units",
        "authoritative_cents",
        "money_cents_type",
    }:
        if (
            mapping.authority_class in {"authoritative_cents", "money_cents_type"}
            and CURRENCY_EXPONENTS[normalized_currency] != 2
        ):
            return _invalid_decision(
                "invalid_currency_or_exponent",
                source_domain=source_domain,
                source_field_path=source_field_path,
                raw_value=raw_value,
                currency=normalized_currency,
                intended_trust_field=intended_trust_field,
                mapping=mapping,
            )
        amount_minor = _parse_integer_minor(raw_value)
        if amount_minor is None:
            return _invalid_decision(
                "invalid_numeric_format",
                source_domain=source_domain,
                source_field_path=source_field_path,
                raw_value=raw_value,
                currency=normalized_currency,
                intended_trust_field=intended_trust_field,
                mapping=mapping,
            )
    elif mapping.authority_class == "provider_decimal_string":
        parsed = _provider_decimal_string_to_minor(raw_value, normalized_currency)
        if isinstance(parsed, str):
            return _invalid_decision(
                parsed,
                source_domain=source_domain,
                source_field_path=source_field_path,
                raw_value=raw_value,
                currency=normalized_currency,
                intended_trust_field=intended_trust_field,
                mapping=mapping,
            )
        amount_minor = parsed
    else:
        return _refusal_decision(
            source_domain=source_domain,
            source_field_path=source_field_path,
            raw_value=raw_value,
            currency=normalized_currency,
            intended_trust_field=intended_trust_field,
            authority_class=mapping.authority_class,
            conversion_method="forbidden_source_class",
            evidence_label=mapping.evidence_label,
        )

    if not _passes_field_policy(amount_minor, authority.field_policy):
        return _refusal_decision(
            source_domain=source_domain,
            source_field_path=source_field_path,
            raw_value=raw_value,
            currency=normalized_currency,
            intended_trust_field=intended_trust_field,
            authority_class=mapping.authority_class,
            conversion_method="field_negative_zero_policy_refusal",
            evidence_label=mapping.evidence_label,
        )

    return AuthoritativeMoneyMinor(
        status="accepted_authoritative_minor_units",
        reason_code=None,
        source_domain=source_domain,
        source_field_path=source_field_path,
        intended_trust_field=intended_trust_field,
        currency=normalized_currency,
        amount_minor=amount_minor,
        source_value_type=type(raw_value).__name__,
        authority_class=mapping.authority_class,
        conversion_method=mapping.conversion_method,
        evidence_label=mapping.evidence_label,
    )


def _normalize_currency(currency: str | None) -> str | None:
    if currency is None:
        return None
    return currency.strip().upper()


def _source_class_for_unmapped(
    *, source_domain: str, source_field_path: str, raw_value: Any
) -> MoneyAuthorityClass:
    if source_domain in FORBIDDEN_DTO_SOURCE_DOMAINS:
        return FORBIDDEN_DTO_SOURCE_DOMAINS[source_domain]
    field_leaf = source_field_path.rsplit(".", maxsplit=1)[-1]
    if field_leaf in FORBIDDEN_MONEY_FIELD_NAMES:
        if isinstance(raw_value, str):
            return "non_authoritative_display_string"
        if isinstance(raw_value, float):
            return "non_authoritative_display_float"
        return "unknown_money_source"
    return "unknown_money_source"


def _unmapped_decision(
    *,
    source_domain: str,
    source_field_path: str,
    raw_value: Any,
    currency: str | None,
    intended_trust_field: str,
) -> MoneyAuthorityRefusal:
    authority_class = _source_class_for_unmapped(
        source_domain=source_domain,
        source_field_path=source_field_path,
        raw_value=raw_value,
    )
    status: Literal["refused_money_source_not_authoritative", "source_field_unmapped"]
    status = (
        "refused_money_source_not_authoritative"
        if authority_class != "unknown_money_source"
        else "source_field_unmapped"
    )
    return MoneyAuthorityRefusal(
        status=status,
        reason_code=MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
        source_domain=source_domain,
        source_field_path=source_field_path,
        intended_trust_field=intended_trust_field,
        currency=currency,
        amount_minor=None,
        source_value_type=type(raw_value).__name__,
        authority_class=authority_class,
        conversion_method="unmapped_source_refusal",
        evidence_label=f"{source_domain}.{source_field_path}",
    )


def _refusal_decision(
    *,
    source_domain: str,
    source_field_path: str,
    raw_value: Any,
    currency: str | None,
    intended_trust_field: str,
    authority_class: MoneyAuthorityClass,
    conversion_method: str,
    evidence_label: str,
) -> MoneyAuthorityRefusal:
    return MoneyAuthorityRefusal(
        status="refused_money_source_not_authoritative",
        reason_code=MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
        source_domain=source_domain,
        source_field_path=source_field_path,
        intended_trust_field=intended_trust_field,
        currency=currency,
        amount_minor=None,
        source_value_type=type(raw_value).__name__,
        authority_class=authority_class,
        conversion_method=conversion_method,
        evidence_label=evidence_label,
    )


def _invalid_decision(
    status: Literal["invalid_currency_or_exponent", "invalid_numeric_format"],
    *,
    source_domain: str,
    source_field_path: str,
    raw_value: Any,
    currency: str | None,
    intended_trust_field: str,
    mapping: MoneySourceMapping,
) -> MoneyAuthorityInvalid:
    return MoneyAuthorityInvalid(
        status=status,
        reason_code=MONEY_SOURCE_NOT_AUTHORITATIVE_REASON,
        source_domain=source_domain,
        source_field_path=source_field_path,
        intended_trust_field=intended_trust_field,
        currency=currency,
        amount_minor=None,
        source_value_type=type(raw_value).__name__,
        authority_class=mapping.authority_class,
        conversion_method=mapping.conversion_method,
        evidence_label=mapping.evidence_label,
    )


def _parse_integer_minor(raw_value: Any) -> int | None:
    if isinstance(raw_value, bool) or not isinstance(raw_value, int):
        return None
    amount_minor = int(raw_value)
    if abs(amount_minor) > JSON_SAFE_INTEGER_LIMIT:
        return None
    return amount_minor


def _provider_decimal_string_to_minor(
    raw_value: Any,
    currency: str | None,
) -> int | Literal["invalid_currency_or_exponent", "invalid_numeric_format"]:
    if currency not in CURRENCY_EXPONENTS:
        return "invalid_currency_or_exponent"
    if not isinstance(raw_value, str):
        return "invalid_numeric_format"
    candidate = raw_value.strip()
    if not _DECIMAL_STRING_RE.fullmatch(candidate):
        return "invalid_numeric_format"
    try:
        decimal_value = Decimal(candidate)
    except InvalidOperation:
        return "invalid_numeric_format"
    if not decimal_value.is_finite():
        return "invalid_numeric_format"

    exponent = CURRENCY_EXPONENTS[currency]
    scaled = decimal_value * (Decimal(10) ** exponent)
    if scaled != scaled.to_integral_value():
        return "invalid_currency_or_exponent"
    amount_minor = int(scaled)
    if abs(amount_minor) > JSON_SAFE_INTEGER_LIMIT:
        return "invalid_numeric_format"
    return amount_minor


def _passes_field_policy(amount_minor: int, policy: MoneyFieldPolicy) -> bool:
    if amount_minor == 0:
        return policy.zero_allowed
    if amount_minor < 0:
        return policy.negative_policy == "refund_or_adjustment_only"
    return True
