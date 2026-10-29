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
# B2.6-P1 semantic contract: VERIFICATION_COVERAGE counts matched webhook
# revenue. A provisional match participates in the coverage numerator even
# though it is not confirmation: coverage asks whether webhook revenue has a
# match, not whether the match has matured. Unmatched/unresolved sources
# remain in the denominator and are the genuine coverage gap. Treating a
# provisional match as absent manufactured a 95% reading from a 100% match
# cohort; the canonical 95% witness therefore requires an unresolved leg.
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
    # XXV source-attestation qualification: authenticated-source revenue in
    # scope whose source signature is absent, invalid, root-unauthenticated
    # or contradictory. It is never numerator or denominator revenue.
    unverifiable_attestation_revenue_minor: int = 0


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
    unverifiable_attestation_revenue_minor: int = 0


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
            unverifiable_attestation_revenue_minor=int(
                aggregate.unverifiable_attestation_revenue_minor
            ),
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
    """Fetch coverage from source-attested, per-ingress verified money.

    XXV source-attestation closure: an ingress row's database state is not
    authority. Every denominator row must carry the authentication root's
    provider consequence and a signature that verifies over the exact
    tenant/ingress/amount/currency. Rows without that evidence are reported
    as ``unverifiable_attestation_revenue_minor`` and are never counted in
    the denominator or numerator. A settled verdict's numerator uses the
    source-attestation reader so capture plus every signed adjustment is
    included; an unverifiable verdict remains a coverage gap, not a verified
    match.
    """

    normalized_currency = _normalize_currency(currency_code)
    normalized_platforms = _normalize_platforms(supported_platforms)
    normalized_start, normalized_end = _validate_window(window_start, window_end)

    rows_sql = text(
        """
        SELECT wi.id::text AS ingress_id,
               wi.provider,
               upper(wi.verified_amount_currency) AS currency_code,
               wi.verified_amount_minor AS ingress_amount,
               wi.verified_amount_scale AS ingress_scale,
               wi.provider_native_event_reference AS ingress_event_reference,
               wi.provider_native_commerce_reference AS ingress_commerce_reference,
               wi.normalized_commerce_reference_kind AS ingress_normalized_kind,
               wi.normalized_commerce_reference_value AS ingress_normalized_value,
               wi.event_timestamp AS occurred_at,
               wi.b26_p2_demotion_reason AS demotion_reason,
               c.body_sha256 AS consequence_body_sha256,
               a.statement AS statement,
               a.signature AS signature,
               a.attested_amount_minor AS attested_amount,
               a.attested_amount_currency AS attested_currency,
               COALESCE(c.recorded_by = 'app_ingress', false)
                   AS root_authenticated,
               v.id::text AS verdict_id,
               v.status::text AS verdict_status,
               v.b26_p2_source_authority_state::text
                   AS verdict_authority_state,
               upper(v.currency_code) AS verdict_currency
          FROM public.webhook_ingress_identities AS wi
          LEFT JOIN public.b26_p2_source_money_attestation AS a
                 ON a.webhook_ingress_identity_id = wi.id
                AND a.tenant_id = wi.tenant_id
          LEFT JOIN public.b26_p2_provider_auth_consequence AS c
                 ON c.webhook_ingress_identity_id = wi.id
                AND c.tenant_id = wi.tenant_id
          LEFT JOIN LATERAL (
              SELECT mv.id, mv.status, mv.currency_code,
                     mv.b26_p2_source_authority_state
                FROM public.b23_match_verdicts AS mv
               WHERE mv.tenant_id = wi.tenant_id
                 AND mv.webhook_ingress_identity_id = wi.id
               ORDER BY mv.last_transition_at DESC, mv.id DESC
               LIMIT 1
          ) AS v ON true
         WHERE wi.tenant_id = :tenant_id
           AND wi.verified_commerce_ingress_state = 'authenticity_verified'
           AND wi.event_timestamp >= :window_start
           AND wi.event_timestamp < :window_end
           AND wi.provider IN :supported_platforms
           AND upper(wi.verified_amount_currency) = :currency_code
         ORDER BY wi.id
        """
    ).bindparams(
        bindparam("supported_platforms", expanding=True),
    )
    rows = (
        (
            await session.execute(
                rows_sql,
                {
                    "tenant_id": str(tenant_id),
                    "window_start": normalized_start,
                    "window_end": normalized_end,
                    "supported_platforms": normalized_platforms,
                    "currency_code": normalized_currency,
                },
            )
        )
        .mappings()
        .all()
    )

    from app.core.config import settings  # noqa: PLC0415
    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        SourceAttestationError,
        read_verdict_source_attestation_status,
        verify_signature,
    )

    current_universe = (
        await session.execute(
            text("SELECT public.b26_p2_authority_universe()::text")
        )
    ).scalar_one_or_none()
    denominator = 0
    numerator = 0
    historical = 0
    unattested = 0
    for row in rows:
        amount = int(row["ingress_amount"] or 0)
        if row["demotion_reason"] is not None:
            historical += amount
            continue
        statement = row["statement"]
        if statement is None or not row["root_authenticated"]:
            unattested += amount
            continue
        if isinstance(statement, str):
            import json  # noqa: PLC0415

            try:
                statement = json.loads(statement)
            except Exception:  # noqa: BLE001
                unattested += amount
                continue
        try:
            if settings.B26_P2_SOURCE_ATTESTATION_REQUIRED:
                verify_signature(
                    statement,
                    str(row["signature"] or ""),
                    public_key_path=(
                        settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH
                    ),
                )
        except (SourceAttestationError, OSError, ValueError):
            unattested += amount
            continue
        try:
            statement_instant = datetime.fromisoformat(
                str(statement.get("event_timestamp", "")).replace("Z", "+00:00")
            )
            if statement_instant.tzinfo is None:
                statement_instant = statement_instant.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            unattested += amount
            continue
        if (
            str(statement.get("tenant_id")) != str(tenant_id)
            or str(statement.get("webhook_ingress_identity_id"))
            != str(row["ingress_id"])
            or str(statement.get("provider") or "").lower()
            != str(row["provider"] or "").lower()
            or str(statement.get("provider_native_event_reference") or "")
            != str(row["ingress_event_reference"] or "")
            or str(statement.get("provider_native_commerce_reference") or "")
            != str(row["ingress_commerce_reference"] or "")
            or statement.get("normalized_commerce_reference_kind")
            != row["ingress_normalized_kind"]
            or statement.get("normalized_commerce_reference_value")
            != row["ingress_normalized_value"]
            or statement_instant.astimezone(timezone.utc)
            != row["occurred_at"].astimezone(timezone.utc)
            or int(statement.get("verified_amount_minor", -1)) != amount
            or int(statement.get("verified_amount_scale", -1))
            != int(row["ingress_scale"])
            or int(row["attested_amount"] if row["attested_amount"] is not None else -1)
            != amount
            or str(statement.get("verified_amount_currency", "")).upper()
            != normalized_currency
            or str(row["attested_currency"] or "").upper()
            != normalized_currency
            or str(statement.get("body_sha256") or "").lower()
            != str(row["consequence_body_sha256"] or "").lower()
            or current_universe is None
            or str(statement.get("authority_universe") or "")
            != str(current_universe)
        ):
            unattested += amount
            continue
        denominator += amount
        verdict_id = row["verdict_id"]
        if (
            verdict_id
            and row["verdict_status"] in _MATCHED_VERDICT_STATUSES
            and row["verdict_authority_state"] == "current"
            and row["currency_code"] == normalized_currency
            and row["verdict_currency"] == normalized_currency
        ):
            status = await read_verdict_source_attestation_status(
                session,
                tenant_id=tenant_id,
                verdict_id=verdict_id,
            )
            if status.attested and status.attested_amount_minor is not None:
                numerator += int(status.attested_amount_minor)

    return VerificationCoverageAggregate(
        tenant_id=tenant_id,
        currency_code=normalized_currency,
        window_start=normalized_start,
        window_end=normalized_end,
        matched_webhook_revenue_minor=numerator,
        connected_platform_revenue_minor=denominator,
        unverifiable_historical_revenue_minor=historical,
        unverifiable_attestation_revenue_minor=unattested,
    )


def compute_verification_coverage(
    aggregate: VerificationCoverageAggregate,
) -> VerificationCoverageResult:
    return VERIFICATION_COVERAGE.compute(aggregate)
