"""B2.3-P6 deterministic verification coverage primitive."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Literal
from uuid import UUID


SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS = frozenset(
    {"shopify", "stripe", "paypal", "woocommerce"}
)
SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES = frozenset({"USD"})
VERIFICATION_COVERAGE_ZERO_DENOMINATOR_PERCENT = Decimal("0.00")
_PERCENT = Decimal("100")
_PERCENT_QUANTIZER = Decimal("0.01")


@dataclass(frozen=True)
class VerificationCoverageRevenue:
    tenant_id: UUID
    platform: str
    revenue_minor: int
    currency_code: str
    occurred_at: datetime
    rail: Literal["connected_platform", "unsupported"]
    matched_webhook: bool


@dataclass(frozen=True)
class VerificationCoverageResult:
    tenant_id: UUID
    currency_code: str
    window_start: datetime
    window_end: datetime
    numerator_matched_webhook_revenue_minor: int
    denominator_connected_platform_revenue_minor: int
    coverage_percent: Decimal
    zero_denominator: bool


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_in_half_open_window(
    *, occurred_at: datetime, window_start: datetime, window_end: datetime
) -> bool:
    normalized = _normalize_utc(occurred_at)
    return _normalize_utc(window_start) <= normalized < _normalize_utc(window_end)


class VerificationCoverageMetric:
    """Governed B2.6-ready metric primitive over B2.3/B2.2 revenue surfaces."""

    name = "VERIFICATION_COVERAGE"

    def compute(
        self,
        rows: Iterable[VerificationCoverageRevenue],
        *,
        tenant_id: UUID,
        window_start: datetime,
        window_end: datetime,
        currency_code: str = "USD",
    ) -> VerificationCoverageResult:
        normalized_currency = currency_code.strip().upper()
        if normalized_currency not in SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES:
            raise ValueError("unsupported_verification_coverage_currency")
        if _normalize_utc(window_start) >= _normalize_utc(window_end):
            raise ValueError("verification_coverage_window_must_be_half_open")

        denominator = 0
        numerator = 0
        for row in rows:
            if row.tenant_id != tenant_id:
                continue
            if row.rail != "connected_platform":
                continue
            platform = row.platform.strip().lower()
            if platform not in SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS:
                continue
            if row.currency_code.strip().upper() != normalized_currency:
                continue
            if row.revenue_minor < 0:
                raise ValueError("verification_coverage_revenue_must_be_non_negative")
            if not _is_in_half_open_window(
                occurred_at=row.occurred_at,
                window_start=window_start,
                window_end=window_end,
            ):
                continue
            denominator += int(row.revenue_minor)
            if row.matched_webhook:
                numerator += int(row.revenue_minor)

        if denominator == 0:
            coverage = VERIFICATION_COVERAGE_ZERO_DENOMINATOR_PERCENT
            zero_denominator = True
        else:
            coverage = (
                (Decimal(numerator) * _PERCENT) / Decimal(denominator)
            ).quantize(_PERCENT_QUANTIZER, rounding=ROUND_HALF_UP)
            zero_denominator = False

        return VerificationCoverageResult(
            tenant_id=tenant_id,
            currency_code=normalized_currency,
            window_start=_normalize_utc(window_start),
            window_end=_normalize_utc(window_end),
            numerator_matched_webhook_revenue_minor=numerator,
            denominator_connected_platform_revenue_minor=denominator,
            coverage_percent=coverage,
            zero_denominator=zero_denominator,
        )


VERIFICATION_COVERAGE = VerificationCoverageMetric()


def compute_verification_coverage(
    rows: Iterable[VerificationCoverageRevenue],
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    currency_code: str = "USD",
) -> VerificationCoverageResult:
    return VERIFICATION_COVERAGE.compute(
        rows,
        tenant_id=tenant_id,
        window_start=window_start,
        window_end=window_end,
        currency_code=currency_code,
    )
