"""B2.3-P6 Postgres-bound deterministic verification coverage primitive."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession


SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS = frozenset(
    {"shopify", "stripe", "paypal", "woocommerce"}
)
SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES = frozenset({"USD"})
VERIFICATION_COVERAGE_ZERO_DENOMINATOR_PERCENT = Decimal("0.00")
_PERCENT = Decimal("100")
_PERCENT_QUANTIZER = Decimal("0.01")
_MATCHED_VERDICT_STATUSES = ("matched_provisional", "matched_confirmed", "adjusted")


@dataclass(frozen=True)
class VerificationCoverageAggregate:
    tenant_id: UUID
    currency_code: str
    window_start: datetime
    window_end: datetime
    matched_webhook_revenue_minor: int
    connected_platform_revenue_minor: int
    # XVIII (H-XVIII-R8): explicitly non-authoritative historical money
    # in scope. Never part of the verified numerator; carried so reads
    # cannot mistake its exclusion for absence (no false confidence).
    unverifiable_historical_revenue_minor: int = 0


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


def _normalize_currency(currency_code: str) -> str:
    normalized = currency_code.strip().upper()
    if normalized not in SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES:
        raise ValueError("unsupported_verification_coverage_currency")
    return normalized


def _normalize_platforms(
    supported_platforms: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    normalized = tuple(
        sorted(
            {platform.strip().lower() for platform in supported_platforms if platform}
        )
    )
    if not normalized:
        raise ValueError("verification_coverage_supported_platforms_required")
    unsupported = set(normalized) - SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS
    if unsupported:
        raise ValueError("unsupported_verification_coverage_platform")
    return normalized


def _validate_window(
    window_start: datetime, window_end: datetime
) -> tuple[datetime, datetime]:
    start = _normalize_utc(window_start)
    end = _normalize_utc(window_end)
    if start >= end:
        raise ValueError("verification_coverage_window_must_be_half_open")
    return start, end


class VerificationCoverageMetric:
    """Governed B2.6-ready metric primitive over aggregate B2.3/B2.2 facts."""

    name = "VERIFICATION_COVERAGE"

    def compute(
        self, aggregate: VerificationCoverageAggregate
    ) -> VerificationCoverageResult:
        currency_code = _normalize_currency(aggregate.currency_code)
        window_start, window_end = _validate_window(
            aggregate.window_start, aggregate.window_end
        )
        denominator = int(aggregate.connected_platform_revenue_minor)
        numerator = int(aggregate.matched_webhook_revenue_minor)
        if denominator < 0 or numerator < 0:
            raise ValueError("verification_coverage_revenue_must_be_non_negative")
        if numerator > denominator:
            raise ValueError("verification_coverage_numerator_exceeds_denominator")

        if denominator == 0:
            coverage = VERIFICATION_COVERAGE_ZERO_DENOMINATOR_PERCENT
            zero_denominator = True
        else:
            coverage = (
                (Decimal(numerator) * _PERCENT) / Decimal(denominator)
            ).quantize(_PERCENT_QUANTIZER, rounding=ROUND_HALF_UP)
            zero_denominator = False

        return VerificationCoverageResult(
            tenant_id=aggregate.tenant_id,
            currency_code=currency_code,
            window_start=window_start,
            window_end=window_end,
            numerator_matched_webhook_revenue_minor=numerator,
            denominator_connected_platform_revenue_minor=denominator,
            coverage_percent=coverage,
            zero_denominator=zero_denominator,
        )


VERIFICATION_COVERAGE = VerificationCoverageMetric()


async def fetch_verification_coverage_aggregate(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    supported_platforms: tuple[str, ...] | list[str] = tuple(
        sorted(SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS)
    ),
    currency_code: str = "USD",
) -> VerificationCoverageAggregate:
    """Fetch bounded Postgres aggregate facts for VERIFICATION_COVERAGE."""

    normalized_currency = _normalize_currency(currency_code)
    normalized_platforms = _normalize_platforms(supported_platforms)
    normalized_start, normalized_end = _validate_window(window_start, window_end)

    aggregate_sql = text(
        """
        WITH canonical_verified_revenue AS MATERIALIZED (
            -- XVIII (H-XVIII-R8): the verified leg measures the
            -- currently governed truth state ONLY (central authority
            -- predicate). Demoted history cannot enter the numerator.
            SELECT
                wi.id,
                wi.tenant_id,
                wi.provider,
                upper(wi.verified_amount_currency) AS currency_code,
                wi.verified_amount_minor,
                wi.event_timestamp AS occurred_at
            FROM public.webhook_ingress_identities wi
            WHERE wi.tenant_id = :tenant_id
              AND wi.verified_commerce_ingress_state = 'authenticity_verified'
              AND public.b26_p2_ingress_has_current_authority(wi.id)
        ),
        unverifiable_historical_revenue AS MATERIALIZED (
            -- XVIII (H-XVIII-R8): demoted history in scope, stated
            -- explicitly as non-authoritative context. Excluded from
            -- the verified numerator by construction; represented here
            -- so its absence from verified revenue is visible, never
            -- silent, and can never read as false confidence.
            SELECT
                COALESCE(SUM(wi.verified_amount_minor), 0)::bigint
                    AS unverifiable_historical_revenue_minor
            FROM public.webhook_ingress_identities wi
            WHERE wi.tenant_id = :tenant_id
              AND wi.verified_commerce_ingress_state = 'authenticity_verified'
              AND NOT public.b26_p2_ingress_has_current_authority(wi.id)
              AND wi.event_timestamp >= :window_start
              AND wi.event_timestamp < :window_end
              AND wi.provider IN :supported_platforms
              AND upper(wi.verified_amount_currency) = :currency_code
        ),
        connected_platform AS (
            SELECT
                COALESCE(SUM(verified_amount_minor), 0)::bigint
                    AS connected_platform_revenue_minor
            FROM canonical_verified_revenue
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :window_start
              AND occurred_at < :window_end
              AND provider IN :supported_platforms
              AND currency_code = :currency_code
        ),
        matched_webhook AS (
            SELECT
                COALESCE(SUM(v.canonical_net_verified_amount_minor), 0)::bigint
                    AS matched_webhook_revenue_minor
            FROM public.b23_match_verdicts v
            JOIN canonical_verified_revenue wi
              ON wi.tenant_id = v.tenant_id
             AND wi.id = v.webhook_ingress_identity_id
            WHERE v.tenant_id = :tenant_id
              AND wi.tenant_id = :tenant_id
              AND wi.occurred_at >= :window_start
              AND wi.occurred_at < :window_end
              AND v.status IN :matched_statuses
              AND v.b26_p2_source_authority_state = 'current'
              AND v.provider IN :supported_platforms
              AND wi.provider IN :supported_platforms
              AND upper(v.currency_code) = :currency_code
              AND wi.currency_code = :currency_code
        )
        SELECT
            matched_webhook.matched_webhook_revenue_minor,
            connected_platform.connected_platform_revenue_minor,
            unverifiable_historical_revenue.unverifiable_historical_revenue_minor
        FROM matched_webhook
        CROSS JOIN connected_platform
        CROSS JOIN unverifiable_historical_revenue
        """
    ).bindparams(
        bindparam("supported_platforms", expanding=True),
        bindparam("matched_statuses", expanding=True),
    )
    row = (
        (
            await session.execute(
                aggregate_sql,
                {
                    "tenant_id": str(tenant_id),
                    "window_start": normalized_start,
                    "window_end": normalized_end,
                    "supported_platforms": normalized_platforms,
                    "currency_code": normalized_currency,
                    "matched_statuses": _MATCHED_VERDICT_STATUSES,
                },
            )
        )
        .mappings()
        .one()
    )
    return VerificationCoverageAggregate(
        tenant_id=tenant_id,
        currency_code=normalized_currency,
        window_start=normalized_start,
        window_end=normalized_end,
        matched_webhook_revenue_minor=int(row["matched_webhook_revenue_minor"]),
        connected_platform_revenue_minor=int(row["connected_platform_revenue_minor"]),
        unverifiable_historical_revenue_minor=int(
            row["unverifiable_historical_revenue_minor"]
        ),
    )


def compute_verification_coverage(
    aggregate: VerificationCoverageAggregate,
) -> VerificationCoverageResult:
    return VERIFICATION_COVERAGE.compute(aggregate)
