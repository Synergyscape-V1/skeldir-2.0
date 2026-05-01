"""Typed, platform-keyed B2.3 revenue extraction registry."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Callable, Literal, Mapping, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


B23ProviderKey: TypeAlias = Literal["stripe", "paypal", "shopify", "woocommerce"]
SUPPORTED_B23_PROVIDERS: tuple[B23ProviderKey, ...] = (
    "stripe",
    "paypal",
    "shopify",
    "woocommerce",
)
_MINOR_SCALE = Decimal("0.01")


class ExtractedRevenue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_minor: int = Field(gt=0)
    currency_code: str = Field(min_length=3, max_length=3)


class PersistedIngressExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: B23ProviderKey
    verified_amount_minor: int = Field(gt=0)
    verified_amount_currency: str = Field(min_length=3, max_length=3)


class StripeRevenueExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["stripe"] = "stripe"
    gross_captured_minor: int | None = Field(default=None, gt=0)
    currency_code: str = Field(min_length=3, max_length=3)
    net_after_fees_minor: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_gross_authority(self) -> "StripeRevenueExtractionInput":
        if self.gross_captured_minor is None:
            raise ValueError("stripe_gross_captured_minor_required")
        return self


class DecimalMajorRevenueExtractionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["paypal", "shopify", "woocommerce"]
    gross_major: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)


RevenueExtractionInput: TypeAlias = (
    PersistedIngressExtractionInput
    | StripeRevenueExtractionInput
    | DecimalMajorRevenueExtractionInput
)


def _normalize_currency(currency_code: str) -> str:
    return currency_code.strip().upper()


def _major_to_minor(gross_major: str) -> int:
    try:
        major = Decimal(gross_major.strip())
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError("invalid_major_unit_amount") from exc
    quantized = major.quantize(_MINOR_SCALE, rounding=ROUND_HALF_UP)
    amount_minor = int(quantized * 100)
    if amount_minor <= 0:
        raise ValueError("non_positive_major_unit_amount")
    return amount_minor


def _extract_from_stripe(payload: StripeRevenueExtractionInput) -> ExtractedRevenue:
    return ExtractedRevenue(
        amount_minor=int(payload.gross_captured_minor),
        currency_code=_normalize_currency(payload.currency_code),
    )


def _extract_from_decimal_major(
    payload: DecimalMajorRevenueExtractionInput,
) -> ExtractedRevenue:
    return ExtractedRevenue(
        amount_minor=_major_to_minor(payload.gross_major),
        currency_code=_normalize_currency(payload.currency_code),
    )


def _extract_from_persisted_ingress(
    payload: PersistedIngressExtractionInput,
) -> ExtractedRevenue:
    return ExtractedRevenue(
        amount_minor=int(payload.verified_amount_minor),
        currency_code=_normalize_currency(payload.verified_amount_currency),
    )


ExtractorFn: TypeAlias = Callable[[RevenueExtractionInput], ExtractedRevenue]


def _stripe_dispatch(payload: RevenueExtractionInput) -> ExtractedRevenue:
    if isinstance(payload, PersistedIngressExtractionInput):
        return _extract_from_persisted_ingress(payload)
    if isinstance(payload, StripeRevenueExtractionInput):
        return _extract_from_stripe(payload)
    raise TypeError("stripe_extractor_requires_typed_stripe_or_persisted_ingress_input")


def _paypal_dispatch(payload: RevenueExtractionInput) -> ExtractedRevenue:
    if isinstance(payload, PersistedIngressExtractionInput):
        return _extract_from_persisted_ingress(payload)
    if (
        isinstance(payload, DecimalMajorRevenueExtractionInput)
        and payload.provider == "paypal"
    ):
        return _extract_from_decimal_major(payload)
    raise TypeError("paypal_extractor_requires_typed_paypal_or_persisted_ingress_input")


def _shopify_dispatch(payload: RevenueExtractionInput) -> ExtractedRevenue:
    if isinstance(payload, PersistedIngressExtractionInput):
        return _extract_from_persisted_ingress(payload)
    if (
        isinstance(payload, DecimalMajorRevenueExtractionInput)
        and payload.provider == "shopify"
    ):
        return _extract_from_decimal_major(payload)
    raise TypeError(
        "shopify_extractor_requires_typed_shopify_or_persisted_ingress_input"
    )


def _woocommerce_dispatch(payload: RevenueExtractionInput) -> ExtractedRevenue:
    if isinstance(payload, PersistedIngressExtractionInput):
        return _extract_from_persisted_ingress(payload)
    if (
        isinstance(payload, DecimalMajorRevenueExtractionInput)
        and payload.provider == "woocommerce"
    ):
        return _extract_from_decimal_major(payload)
    raise TypeError(
        "woocommerce_extractor_requires_typed_woocommerce_or_persisted_ingress_input"
    )


B23_REVENUE_EXTRACTOR_REGISTRY: Mapping[B23ProviderKey, ExtractorFn] = {
    "stripe": _stripe_dispatch,
    "paypal": _paypal_dispatch,
    "shopify": _shopify_dispatch,
    "woocommerce": _woocommerce_dispatch,
}


def extract_revenue_from_typed_input(
    payload: RevenueExtractionInput,
) -> ExtractedRevenue:
    extractor = B23_REVENUE_EXTRACTOR_REGISTRY[payload.provider]
    return extractor(payload)
