"""B2.5-P4 registry for TrustEnvelope authoritative money sources."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping


MoneyAuthorityClass = Literal[
    "authoritative_minor_units",
    "authoritative_cents",
    "money_cents_type",
    "provider_decimal_string",
    "non_authoritative_display_float",
    "non_authoritative_display_string",
    "legacy_dashboard_float",
    "legacy_export_float",
    "legacy_budget_float",
    "unknown_money_source",
]

NegativeMoneyPolicy = Literal["forbidden", "refund_or_adjustment_only"]

MONEY_SOURCE_NOT_AUTHORITATIVE_REASON = "money_source_not_authoritative"


@dataclass(frozen=True)
class MoneyFieldPolicy:
    """Field-specific zero and negative-value authority policy."""

    trust_field: str
    zero_allowed: bool
    negative_policy: NegativeMoneyPolicy


@dataclass(frozen=True)
class MoneySourceMapping:
    """Approved source path for one TrustEnvelope money field."""

    source_domain: str
    source_field_path: str
    authority_class: MoneyAuthorityClass
    evidence_label: str
    conversion_method: str


@dataclass(frozen=True)
class TrustMoneyFieldAuthority:
    """Complete authority policy for one TrustEnvelope money field."""

    trust_field: str
    field_policy: MoneyFieldPolicy
    approved_sources: tuple[MoneySourceMapping, ...]


AUTHORIZED_TRUST_MONEY_FIELD_PATTERNS: tuple[str, ...] = (
    "verified_*_minor",
    "revenue_*_minor",
    "spend_*_minor",
    "budget_*_minor",
    "allocation_*_minor",
    "amount_minor",
)

CURRENCY_EXPONENTS: Mapping[str, int] = MappingProxyType(
    {
        "USD": 2,
        "EUR": 2,
        "GBP": 2,
        "CAD": 2,
        "AUD": 2,
        "JPY": 0,
        "KWD": 3,
    }
)

FORBIDDEN_MONEY_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "total_revenue",
        "revenue",
        "revenue_total",
        "total_budget",
        "min_budget",
        "max_budget",
        "display_amount",
        "formatted_amount",
        "amount_display",
    }
)

FORBIDDEN_DTO_SOURCE_DOMAINS: Mapping[str, MoneyAuthorityClass] = MappingProxyType(
    {
        "attribution_dashboard": "legacy_dashboard_float",
        "backend.app.schemas.attribution": "legacy_dashboard_float",
        "export_row": "legacy_export_float",
        "backend.app.api.export": "legacy_export_float",
        "budget_dto": "legacy_budget_float",
        "backend.app.api.budget": "legacy_budget_float",
    }
)

VERIFIED_REVENUE_MINOR_AUTHORITY = TrustMoneyFieldAuthority(
    trust_field="verified_revenue_minor",
    field_policy=MoneyFieldPolicy(
        trust_field="verified_revenue_minor",
        zero_allowed=True,
        negative_policy="forbidden",
    ),
    approved_sources=(
        MoneySourceMapping(
            source_domain="b23_match_verdicts",
            source_field_path="canonical_net_verified_amount_minor",
            authority_class="authoritative_minor_units",
            evidence_label="b23_match_verdicts.canonical_net_verified_amount_minor",
            conversion_method="integer_minor_units_direct",
        ),
        MoneySourceMapping(
            source_domain="b23_match_verdicts",
            source_field_path="canonical_gross_captured_amount_minor",
            authority_class="authoritative_minor_units",
            evidence_label="b23_match_verdicts.canonical_gross_captured_amount_minor",
            conversion_method="integer_minor_units_direct",
        ),
        MoneySourceMapping(
            source_domain="webhook_ingress_identities",
            source_field_path="verified_amount_minor",
            authority_class="authoritative_minor_units",
            evidence_label="webhook_ingress_identities.verified_amount_minor",
            conversion_method="integer_minor_units_direct",
        ),
        MoneySourceMapping(
            source_domain="revenue_ledger",
            source_field_path="verified_total_cents",
            authority_class="authoritative_cents",
            evidence_label="revenue_ledger.verified_total_cents",
            conversion_method="integer_cents_direct",
        ),
        MoneySourceMapping(
            source_domain="provider_payload",
            source_field_path="gross_major",
            authority_class="provider_decimal_string",
            evidence_label="provider_payload.gross_major",
            conversion_method="decimal_string_currency_exponent",
        ),
    ),
)

MONEY_FIELD_REGISTRY: Mapping[str, TrustMoneyFieldAuthority] = MappingProxyType(
    {
        VERIFIED_REVENUE_MINOR_AUTHORITY.trust_field: VERIFIED_REVENUE_MINOR_AUTHORITY,
    }
)


def get_trust_money_authority(
    intended_trust_field: str,
) -> TrustMoneyFieldAuthority | None:
    """Return the registered authority policy for a TrustEnvelope money field."""
    return MONEY_FIELD_REGISTRY.get(intended_trust_field)


def iter_trust_money_authorities() -> tuple[TrustMoneyFieldAuthority, ...]:
    """Return registry entries in deterministic field-name order."""
    return tuple(MONEY_FIELD_REGISTRY[key] for key in sorted(MONEY_FIELD_REGISTRY))


def find_source_mapping(
    *,
    source_domain: str,
    source_field_path: str,
    intended_trust_field: str,
) -> MoneySourceMapping | None:
    """Return the approved mapping for a source path and TrustEnvelope field."""
    authority = get_trust_money_authority(intended_trust_field)
    if authority is None:
        return None
    for mapping in authority.approved_sources:
        if (
            mapping.source_domain == source_domain
            and mapping.source_field_path == source_field_path
        ):
            return mapping
    return None

