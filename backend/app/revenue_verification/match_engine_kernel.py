"""B2.3-P2 deterministic match-engine kernel."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Mapping
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .extraction_registry import (
    B23ProviderKey,
    PersistedIngressExtractionInput,
    RevenueExtractionInput,
    extract_revenue_from_typed_input,
)
from .failure_boundary import B23FailureBoundaryClass, classify_b23_failure_boundary
from .semantic_authority import (
    B23DiscrepancyClass,
    CanonicalizationStatus,
    resolve_canonical_match_key,
)
from .timing_constants import PROVISIONAL_MATCH_WINDOW, WEBHOOK_ARRIVAL_WINDOW


B23_POST_CAPTURE_EVENT_TYPE = Literal[
    "payment_capture",
    "partial_refund",
    "full_refund",
    "chargeback_opened",
    "chargeback_won",
    "chargeback_lost",
    "reversal",
]

_B23_PERCENT_DENOMINATOR = Decimal("100")
_B23_HIGH_RATIO_MAX = Decimal("0.02")
_B23_MEDIUM_RATIO_MAX = Decimal("0.10")

B23_POST_CAPTURE_HANDLER_REGISTRY: Mapping[
    B23ProviderKey, tuple[B23_POST_CAPTURE_EVENT_TYPE, ...]
] = {
    "stripe": (
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
        "reversal",
    ),
    "paypal": (
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
        "reversal",
    ),
    "shopify": (
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
        "reversal",
    ),
    "woocommerce": (
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
        "reversal",
    ),
}


class B23CaptureMatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    provider: B23ProviderKey
    provider_native_event_reference: str = Field(min_length=1)
    provider_native_commerce_reference: str = Field(min_length=1)
    normalized_commerce_reference: str | None = None
    strict_order_id: str | None = None
    attribution_event_id: UUID | None = None
    webhook_ingress_identity_id: UUID | None = None
    attributed_amount_minor: int = Field(ge=0)
    attributed_currency_code: str = Field(min_length=3, max_length=3)
    verified_revenue_input: RevenueExtractionInput
    event_occurred_at: datetime
    conversion_occurred_at: datetime


class B23PostCaptureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    provider: B23ProviderKey
    event_type: B23_POST_CAPTURE_EVENT_TYPE
    provider_native_event_reference: str = Field(min_length=1)
    provider_native_commerce_reference: str = Field(min_length=1)
    currency_code: str = Field(min_length=3, max_length=3)
    amount_minor: int = Field(ge=0)
    event_occurred_at: datetime
    match_verdict_id: UUID | None = None
    canonical_commerce_reference: str | None = None
    failure_reason: str | None = None
    is_gross_capture_correction: bool = False


@dataclass(frozen=True)
class B23MatchKernelOutcome:
    match_verdict_id: UUID
    revenue_event_written: bool
    discrepancy_amount_minor: int
    discrepancy_ratio: Decimal
    discrepancy_class: B23DiscrepancyClass
    match_quality: Literal["high", "medium", "low"]


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _canonical_discrepancy_ratio(
    *,
    attributed_amount_minor: int,
    verified_amount_minor: int,
) -> Decimal:
    delta = abs(verified_amount_minor - attributed_amount_minor)
    baseline = max(verified_amount_minor, attributed_amount_minor, 1)
    return (Decimal(delta) / Decimal(baseline)).quantize(Decimal("0.0001"))


def _canonical_discrepancy_ratio_bps(
    *,
    canonical_expected_gross_amount_minor: int,
    discrepancy_amount_minor: int,
) -> int:
    if canonical_expected_gross_amount_minor == 0:
        return 0
    ratio_bps = (
        Decimal(discrepancy_amount_minor)
        * Decimal("10000")
        / Decimal(canonical_expected_gross_amount_minor)
    )
    return int(ratio_bps)


def _discrepancy_band_from_bps(discrepancy_ratio_bps: int) -> B23DiscrepancyClass:
    absolute_bps = abs(int(discrepancy_ratio_bps))
    if absolute_bps == 0:
        return B23DiscrepancyClass.EXACT
    if absolute_bps <= 200:
        return B23DiscrepancyClass.WITHIN_TOLERANCE
    if absolute_bps <= 1000:
        return B23DiscrepancyClass.OVER_TOLERANCE
    return B23DiscrepancyClass.SEVERE_GAP


def _post_capture_revenue_operands(
    *,
    event_type: B23_POST_CAPTURE_EVENT_TYPE,
    amount_minor: int,
) -> tuple[int | None, int | None, int | None, int | None, int]:
    if event_type == "payment_capture":
        return amount_minor, None, None, None, 1
    if event_type in {"partial_refund", "full_refund"}:
        return None, amount_minor, None, None, -1
    if event_type == "chargeback_opened":
        return None, None, amount_minor, None, 0
    if event_type == "chargeback_lost":
        return None, None, amount_minor, None, -1
    if event_type == "chargeback_won":
        return None, None, amount_minor, None, 1
    if event_type == "reversal":
        return None, None, None, amount_minor, 1
    raise ValueError("unsupported_post_capture_event_type")


def classify_b23_discrepancy(
    *,
    attributed_amount_minor: int,
    verified_amount_minor: int,
) -> tuple[int, Decimal, B23DiscrepancyClass]:
    delta = abs(verified_amount_minor - attributed_amount_minor)
    ratio = _canonical_discrepancy_ratio(
        attributed_amount_minor=attributed_amount_minor,
        verified_amount_minor=verified_amount_minor,
    )
    if delta == 0:
        return delta, ratio, B23DiscrepancyClass.EXACT
    if ratio <= _B23_HIGH_RATIO_MAX:
        return delta, ratio, B23DiscrepancyClass.WITHIN_TOLERANCE
    if ratio <= _B23_MEDIUM_RATIO_MAX:
        return delta, ratio, B23DiscrepancyClass.OVER_TOLERANCE
    return delta, ratio, B23DiscrepancyClass.SEVERE_GAP


def classify_b23_match_quality(
    *,
    precedence_source_field: str | None,
    discrepancy_ratio: Decimal,
    conversion_to_event_delta: timedelta,
) -> Literal["high", "medium", "low"]:
    if (
        precedence_source_field == "normalized_commerce_reference"
        and discrepancy_ratio <= _B23_HIGH_RATIO_MAX
        and conversion_to_event_delta <= timedelta(minutes=10)
    ):
        return "high"
    if (
        discrepancy_ratio <= _B23_MEDIUM_RATIO_MAX
        and conversion_to_event_delta <= WEBHOOK_ARRIVAL_WINDOW
    ):
        return "medium"
    return "low"


async def reconcile_b23_attribution_exception_lifecycle(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    match_verdict_id: UUID,
    provider: str,
    canonical_commerce_reference: str,
    discrepancy_band: str | B23DiscrepancyClass,
    now_utc: datetime,
) -> None:
    band_value = (
        discrepancy_band.value
        if isinstance(discrepancy_band, B23DiscrepancyClass)
        else str(discrepancy_band)
    )
    target_severity: Literal["flagged", "alert"] | None
    if band_value == B23DiscrepancyClass.OVER_TOLERANCE.value:
        target_severity = "flagged"
    elif band_value == B23DiscrepancyClass.SEVERE_GAP.value:
        target_severity = "alert"
    else:
        target_severity = None

    timestamp = _normalize_utc(now_utc)
    existing_result = await session.execute(
        text(
            """
            SELECT id
            FROM b23_exception_records
            WHERE tenant_id = :tenant_id
              AND match_verdict_id = :match_verdict_id
              AND status IN ('open', 'acknowledged')
            ORDER BY raised_at DESC, id DESC
            FOR UPDATE
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "match_verdict_id": str(match_verdict_id),
        },
    )
    existing_ids = [UUID(str(row[0])) for row in existing_result.fetchall()]

    if target_severity is None:
        if existing_ids:
            await session.execute(
                text(
                    """
                    UPDATE b23_exception_records
                    SET
                        status = 'resolved',
                        resolution_code = 'system_gross_discrepancy_clean',
                        resolution_notes = 'Gross expected and gross captured discrepancy returned to clean band.',
                        resolved_at = :resolved_at,
                        updated_at = :updated_at
                    WHERE tenant_id = :tenant_id
                      AND match_verdict_id = :match_verdict_id
                      AND status IN ('open', 'acknowledged')
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "match_verdict_id": str(match_verdict_id),
                    "resolved_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        return

    if existing_ids:
        primary_id = existing_ids[0]
        await session.execute(
            text(
                """
                UPDATE b23_exception_records
                SET
                    status = 'open',
                    severity = :severity,
                    resolution_code = NULL,
                    resolution_notes = :resolution_notes,
                    resolved_at = NULL,
                    dismissed_at = NULL,
                    updated_at = :updated_at
                WHERE tenant_id = :tenant_id AND id = :exception_id
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "exception_id": str(primary_id),
                "severity": target_severity,
                "resolution_notes": f"gross_discrepancy_band:{band_value}",
                "updated_at": timestamp,
            },
        )
        if len(existing_ids) > 1:
            await session.execute(
                text(
                    """
                    UPDATE b23_exception_records
                    SET
                        status = 'resolved',
                        resolution_code = 'system_duplicate_exception_closed',
                        resolution_notes = 'Duplicate open exception closed by deterministic lifecycle reconciliation.',
                        resolved_at = :resolved_at,
                        updated_at = :updated_at
                    WHERE tenant_id = :tenant_id
                      AND match_verdict_id = :match_verdict_id
                      AND id <> :primary_id
                      AND status IN ('open', 'acknowledged')
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "match_verdict_id": str(match_verdict_id),
                    "primary_id": str(primary_id),
                    "resolved_at": timestamp,
                    "updated_at": timestamp,
                },
            )
        return

    await session.execute(
        text(
            """
            INSERT INTO b23_exception_records (
                tenant_id,
                match_verdict_id,
                provider,
                canonical_commerce_reference,
                status,
                severity,
                resolution_code,
                resolution_notes,
                raised_at,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :match_verdict_id,
                :provider,
                :canonical_commerce_reference,
                'open',
                :severity,
                NULL,
                :resolution_notes,
                :raised_at,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "match_verdict_id": str(match_verdict_id),
            "provider": provider,
            "canonical_commerce_reference": canonical_commerce_reference,
            "severity": target_severity,
            "resolution_notes": f"gross_discrepancy_band:{band_value}",
            "raised_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )


async def _acquire_match_lock(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider: str,
    provider_native_event_reference: str,
) -> None:
    lock_key = f"{tenant_id}:{provider}:{provider_native_event_reference}"
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
        {"lock_key": lock_key},
    )


async def process_b23_capture_match(
    session: AsyncSession,
    match_input: B23CaptureMatchInput,
) -> B23MatchKernelOutcome:
    await _acquire_match_lock(
        session,
        tenant_id=match_input.tenant_id,
        provider=match_input.provider,
        provider_native_event_reference=match_input.provider_native_event_reference,
    )
    extracted = extract_revenue_from_typed_input(match_input.verified_revenue_input)
    attributed_currency = match_input.attributed_currency_code.strip().upper()
    verified_currency = extracted.currency_code.strip().upper()
    if attributed_currency != verified_currency:
        raise ValueError("cross_currency_matching_is_unsupported")

    precedence = resolve_canonical_match_key(
        provider=match_input.provider,
        normalized_commerce_reference=match_input.normalized_commerce_reference,
        provider_native_commerce_reference=match_input.provider_native_commerce_reference,
        strict_order_id=match_input.strict_order_id,
    )
    if (
        precedence.status is CanonicalizationStatus.CANONICALIZATION_FAILED
        or precedence.canonical_reference is None
    ):
        raise ValueError("canonicalization_failed_explicit")

    event_occurred_at = _normalize_utc(match_input.event_occurred_at)
    conversion_occurred_at = _normalize_utc(match_input.conversion_occurred_at)
    delta, ratio, discrepancy_class = classify_b23_discrepancy(
        attributed_amount_minor=match_input.attributed_amount_minor,
        verified_amount_minor=extracted.amount_minor,
    )
    match_quality = classify_b23_match_quality(
        precedence_source_field=precedence.source_field,
        discrepancy_ratio=ratio,
        conversion_to_event_delta=(event_occurred_at - conversion_occurred_at),
    )
    canonical_expected_gross_amount_minor = match_input.attributed_amount_minor
    canonical_captured_gross_amount_minor = extracted.amount_minor
    canonical_net_verified_amount_minor = extracted.amount_minor
    discrepancy_amount_minor = abs(
        canonical_expected_gross_amount_minor - canonical_captured_gross_amount_minor
    )
    discrepancy_ratio_bps = _canonical_discrepancy_ratio_bps(
        canonical_expected_gross_amount_minor=canonical_expected_gross_amount_minor,
        discrepancy_amount_minor=discrepancy_amount_minor,
    )

    verdict_result = await session.execute(
        text(
            """
            INSERT INTO b23_match_verdicts (
                tenant_id,
                attribution_event_id,
                webhook_ingress_identity_id,
                provider,
                canonical_commerce_reference,
                provider_native_event_reference,
                provider_native_commerce_reference,
                status,
                match_quality,
                attributed_amount_minor,
                verified_amount_minor,
                currency_code,
                pending_since,
                provisional_expires_at,
                last_transition_at,
                created_at,
                updated_at,
                canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor,
                discrepancy_amount_minor,
                discrepancy_ratio_bps,
                discrepancy_band
            )
            VALUES (
                :tenant_id,
                :attribution_event_id,
                :webhook_ingress_identity_id,
                :provider,
                :canonical_commerce_reference,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                'matched_provisional',
                :match_quality,
                :attributed_amount_minor,
                :verified_amount_minor,
                :currency_code,
                :pending_since,
                :provisional_expires_at,
                :last_transition_at,
                :created_at,
                :updated_at,
                :canonical_expected_gross_amount_minor,
                :canonical_captured_gross_amount_minor,
                :canonical_net_verified_amount_minor,
                :discrepancy_amount_minor,
                :discrepancy_ratio_bps,
                :discrepancy_band
            )
            ON CONFLICT (tenant_id, provider, provider_native_event_reference)
            DO UPDATE SET
                canonical_commerce_reference = EXCLUDED.canonical_commerce_reference,
                provider_native_commerce_reference = EXCLUDED.provider_native_commerce_reference,
                match_quality = EXCLUDED.match_quality,
                attributed_amount_minor = EXCLUDED.attributed_amount_minor,
                verified_amount_minor = EXCLUDED.verified_amount_minor,
                currency_code = EXCLUDED.currency_code,
                provisional_expires_at = EXCLUDED.provisional_expires_at,
                canonical_expected_gross_amount_minor = EXCLUDED.canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor = EXCLUDED.canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor = EXCLUDED.canonical_net_verified_amount_minor,
                discrepancy_amount_minor = EXCLUDED.discrepancy_amount_minor,
                discrepancy_ratio_bps = EXCLUDED.discrepancy_ratio_bps,
                discrepancy_band = EXCLUDED.discrepancy_band,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """
        ),
        {
            "tenant_id": str(match_input.tenant_id),
            "attribution_event_id": (
                str(match_input.attribution_event_id)
                if match_input.attribution_event_id
                else None
            ),
            "webhook_ingress_identity_id": (
                str(match_input.webhook_ingress_identity_id)
                if match_input.webhook_ingress_identity_id
                else None
            ),
            "provider": match_input.provider,
            "canonical_commerce_reference": precedence.canonical_reference,
            "provider_native_event_reference": match_input.provider_native_event_reference,
            "provider_native_commerce_reference": match_input.provider_native_commerce_reference,
            "match_quality": match_quality,
            "attributed_amount_minor": match_input.attributed_amount_minor,
            "verified_amount_minor": extracted.amount_minor,
            "currency_code": verified_currency,
            "pending_since": conversion_occurred_at,
            "provisional_expires_at": event_occurred_at + PROVISIONAL_MATCH_WINDOW,
            "last_transition_at": event_occurred_at,
            "created_at": event_occurred_at,
            "updated_at": event_occurred_at,
            "canonical_expected_gross_amount_minor": canonical_expected_gross_amount_minor,
            "canonical_captured_gross_amount_minor": canonical_captured_gross_amount_minor,
            "canonical_net_verified_amount_minor": canonical_net_verified_amount_minor,
            "discrepancy_amount_minor": discrepancy_amount_minor,
            "discrepancy_ratio_bps": discrepancy_ratio_bps,
            "discrepancy_band": discrepancy_class.value,
        },
    )
    verdict_id = UUID(str(verdict_result.scalar_one()))

    await reconcile_b23_attribution_exception_lifecycle(
        session,
        tenant_id=match_input.tenant_id,
        match_verdict_id=verdict_id,
        provider=match_input.provider,
        canonical_commerce_reference=precedence.canonical_reference,
        discrepancy_band=discrepancy_class,
        now_utc=event_occurred_at,
    )

    revenue_event_result = await session.execute(
        text(
            """
            INSERT INTO b23_revenue_events (
                tenant_id,
                match_verdict_id,
                webhook_ingress_identity_id,
                provider,
                provider_native_event_reference,
                provider_native_commerce_reference,
                canonical_commerce_reference,
                event_type,
                captured_amount_minor,
                currency_code,
                event_occurred_at,
                recorded_at,
                created_at,
                updated_at,
                net_effect_sign
            )
            VALUES (
                :tenant_id,
                :match_verdict_id,
                :webhook_ingress_identity_id,
                :provider,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                :canonical_commerce_reference,
                'payment_capture',
                :captured_amount_minor,
                :currency_code,
                :event_occurred_at,
                :recorded_at,
                :created_at,
                :updated_at,
                1
            )
            ON CONFLICT (tenant_id, provider, provider_native_event_reference)
            DO NOTHING
            RETURNING id
            """
        ),
        {
            "tenant_id": str(match_input.tenant_id),
            "match_verdict_id": str(verdict_id),
            "webhook_ingress_identity_id": (
                str(match_input.webhook_ingress_identity_id)
                if match_input.webhook_ingress_identity_id
                else None
            ),
            "provider": match_input.provider,
            "provider_native_event_reference": match_input.provider_native_event_reference,
            "provider_native_commerce_reference": match_input.provider_native_commerce_reference,
            "canonical_commerce_reference": precedence.canonical_reference,
            "captured_amount_minor": extracted.amount_minor,
            "currency_code": verified_currency,
            "event_occurred_at": event_occurred_at,
            "recorded_at": event_occurred_at,
            "created_at": event_occurred_at,
            "updated_at": event_occurred_at,
        },
    )
    revenue_event_written = revenue_event_result.scalar_one_or_none() is not None

    return B23MatchKernelOutcome(
        match_verdict_id=verdict_id,
        revenue_event_written=revenue_event_written,
        discrepancy_amount_minor=delta,
        discrepancy_ratio=ratio,
        discrepancy_class=discrepancy_class,
        match_quality=match_quality,
    )


async def _insert_unresolved_post_capture_failure(
    session: AsyncSession,
    post_capture_input: B23PostCaptureInput,
) -> UUID:
    boundary = classify_b23_failure_boundary(
        B23FailureBoundaryClass.VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY
    )
    timestamp = _normalize_utc(post_capture_input.event_occurred_at)
    canonical_reference = (
        post_capture_input.canonical_commerce_reference
        or post_capture_input.provider_native_commerce_reference
        or f"unresolved-{post_capture_input.provider_native_event_reference}"
    )
    verdict_result = await session.execute(
        text(
            """
            INSERT INTO b23_match_verdicts (
                tenant_id,
                provider,
                canonical_commerce_reference,
                provider_native_event_reference,
                provider_native_commerce_reference,
                status,
                match_quality,
                attributed_amount_minor,
                verified_amount_minor,
                currency_code,
                pending_since,
                last_transition_at,
                created_at,
                updated_at,
                canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor,
                discrepancy_amount_minor,
                discrepancy_ratio_bps,
                discrepancy_band
            )
            VALUES (
                :tenant_id,
                :provider,
                :canonical_commerce_reference,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                'pending',
                'low',
                0,
                0,
                :currency_code,
                :pending_since,
                :last_transition_at,
                :created_at,
                :updated_at,
                0,
                0,
                0,
                0,
                0,
                'exact'
            )
            ON CONFLICT (tenant_id, provider, provider_native_event_reference)
            DO UPDATE SET updated_at = EXCLUDED.updated_at
            RETURNING id
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "provider": post_capture_input.provider,
            "canonical_commerce_reference": canonical_reference,
            "provider_native_event_reference": post_capture_input.provider_native_event_reference,
            "provider_native_commerce_reference": post_capture_input.provider_native_commerce_reference,
            "currency_code": post_capture_input.currency_code.strip().upper(),
            "pending_since": timestamp,
            "last_transition_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    verdict_id = UUID(str(verdict_result.scalar_one()))

    await session.execute(
        text(
            """
            INSERT INTO b23_exception_records (
                tenant_id,
                match_verdict_id,
                provider,
                canonical_commerce_reference,
                status,
                severity,
                resolution_code,
                resolution_notes,
                raised_at,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :match_verdict_id,
                :provider,
                :canonical_commerce_reference,
                'open',
                'alert',
                NULL,
                :resolution_notes,
                :raised_at,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "match_verdict_id": str(verdict_id),
            "provider": post_capture_input.provider,
            "canonical_commerce_reference": canonical_reference,
            "resolution_notes": post_capture_input.failure_reason
            or boundary.boundary_class.value,
            "raised_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            INSERT INTO b23_webhook_ingestion_logs (
                tenant_id,
                provider,
                provider_native_event_reference,
                ingestion_status,
                failure_reason,
                received_at,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :provider,
                :provider_native_event_reference,
                'failed',
                :failure_reason,
                :received_at,
                :created_at,
                :updated_at
            )
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "provider": post_capture_input.provider,
            "provider_native_event_reference": post_capture_input.provider_native_event_reference,
            "failure_reason": post_capture_input.failure_reason
            or boundary.boundary_class.value,
            "received_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return verdict_id


async def _insert_unsupported_post_capture_failure(
    session: AsyncSession,
    post_capture_input: B23PostCaptureInput,
) -> None:
    boundary = classify_b23_failure_boundary(
        B23FailureBoundaryClass.UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE
    )
    timestamp = _normalize_utc(post_capture_input.event_occurred_at)
    await session.execute(
        text(
            """
            INSERT INTO b23_webhook_ingestion_logs (
                tenant_id,
                provider,
                provider_native_event_reference,
                ingestion_status,
                failure_reason,
                received_at,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :provider,
                :provider_native_event_reference,
                'failed',
                :failure_reason,
                :received_at,
                :created_at,
                :updated_at
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "provider": post_capture_input.provider,
            "provider_native_event_reference": post_capture_input.provider_native_event_reference,
            "failure_reason": (
                f"{boundary.boundary_class.value}:{post_capture_input.event_type}"
            ),
            "received_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )


async def _recompute_b23_net_verified_amount(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    match_verdict_id: UUID,
) -> int:
    result = await session.execute(
        text(
            """
            SELECT
                v.canonical_captured_gross_amount_minor
                + COALESCE(
                    SUM(
                        CASE
                            WHEN e.is_gross_capture_correction THEN 0
                            WHEN e.event_type IN ('partial_refund', 'full_refund')
                                THEN -COALESCE(e.refund_amount_minor, 0)
                            WHEN e.event_type = 'chargeback_lost'
                                THEN -COALESCE(e.chargeback_amount_minor, 0)
                            WHEN e.event_type = 'chargeback_won'
                                THEN COALESCE(e.chargeback_amount_minor, 0)
                            WHEN e.event_type = 'reversal'
                                THEN COALESCE(e.reversal_amount_minor, 0)
                            ELSE 0
                        END
                    ),
                    0
                ) AS net_verified_amount_minor
            FROM b23_match_verdicts v
            LEFT JOIN b23_revenue_events e
                ON e.tenant_id = v.tenant_id
               AND e.match_verdict_id = v.id
            WHERE v.tenant_id = :tenant_id
              AND v.id = :match_verdict_id
            GROUP BY v.id, v.canonical_captured_gross_amount_minor
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "match_verdict_id": str(match_verdict_id),
        },
    )
    return max(0, int(result.scalar_one()))


async def _apply_gross_capture_correction(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    match_verdict_id: UUID,
    corrected_captured_gross_amount_minor: int,
    timestamp: datetime,
) -> tuple[str, int]:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    provider,
                    canonical_commerce_reference,
                    canonical_expected_gross_amount_minor
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id AND id = :match_verdict_id
                FOR UPDATE
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "match_verdict_id": str(match_verdict_id),
            },
        )
    ).mappings().one()
    expected_gross = int(row["canonical_expected_gross_amount_minor"])
    discrepancy_amount_minor = abs(
        expected_gross - corrected_captured_gross_amount_minor
    )
    discrepancy_ratio_bps = _canonical_discrepancy_ratio_bps(
        canonical_expected_gross_amount_minor=expected_gross,
        discrepancy_amount_minor=discrepancy_amount_minor,
    )
    discrepancy_band = _discrepancy_band_from_bps(discrepancy_ratio_bps)

    await session.execute(
        text(
            """
            UPDATE b23_match_verdicts
            SET
                canonical_captured_gross_amount_minor = :captured_gross,
                verified_amount_minor = :captured_gross,
                discrepancy_amount_minor = :discrepancy_amount_minor,
                discrepancy_ratio_bps = :discrepancy_ratio_bps,
                discrepancy_band = :discrepancy_band,
                last_transition_at = :last_transition_at,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id
              AND id = :match_verdict_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "match_verdict_id": str(match_verdict_id),
            "captured_gross": corrected_captured_gross_amount_minor,
            "discrepancy_amount_minor": discrepancy_amount_minor,
            "discrepancy_ratio_bps": discrepancy_ratio_bps,
            "discrepancy_band": discrepancy_band.value,
            "last_transition_at": timestamp,
            "updated_at": timestamp,
        },
    )
    net_verified_amount = await _recompute_b23_net_verified_amount(
        session,
        tenant_id=tenant_id,
        match_verdict_id=match_verdict_id,
    )
    await session.execute(
        text(
            """
            UPDATE b23_match_verdicts
            SET
                canonical_net_verified_amount_minor = :net_verified_amount,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id
              AND id = :match_verdict_id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "match_verdict_id": str(match_verdict_id),
            "net_verified_amount": net_verified_amount,
            "updated_at": timestamp,
        },
    )
    await reconcile_b23_attribution_exception_lifecycle(
        session,
        tenant_id=tenant_id,
        match_verdict_id=match_verdict_id,
        provider=str(row["provider"]),
        canonical_commerce_reference=str(row["canonical_commerce_reference"]),
        discrepancy_band=discrepancy_band,
        now_utc=timestamp,
    )
    return discrepancy_band.value, net_verified_amount


async def register_b23_post_capture_event(
    session: AsyncSession,
    post_capture_input: B23PostCaptureInput,
) -> bool:
    await _acquire_match_lock(
        session,
        tenant_id=post_capture_input.tenant_id,
        provider=post_capture_input.provider,
        provider_native_event_reference=post_capture_input.provider_native_event_reference,
    )
    if (
        post_capture_input.event_type
        not in B23_POST_CAPTURE_HANDLER_REGISTRY[post_capture_input.provider]
    ):
        await _insert_unsupported_post_capture_failure(session, post_capture_input)
        raise ValueError("post_capture_event_type_not_registered")
    if (
        post_capture_input.is_gross_capture_correction
        and post_capture_input.event_type != "payment_capture"
    ):
        raise ValueError("gross_capture_correction_requires_payment_capture_event")
    if (
        not post_capture_input.is_gross_capture_correction
        and post_capture_input.event_type == "payment_capture"
    ):
        raise ValueError("payment_capture_post_capture_event_requires_gross_correction")
    timestamp = _normalize_utc(post_capture_input.event_occurred_at)
    if post_capture_input.match_verdict_id is None:
        await _insert_unresolved_post_capture_failure(session, post_capture_input)
        return False

    canonical_reference_result = await session.execute(
        text(
            """
            SELECT canonical_commerce_reference
            FROM b23_match_verdicts
            WHERE tenant_id = :tenant_id AND id = :match_verdict_id
            FOR UPDATE
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "match_verdict_id": str(post_capture_input.match_verdict_id),
        },
    )
    canonical_reference = canonical_reference_result.scalar_one_or_none()
    if canonical_reference is None:
        await _insert_unresolved_post_capture_failure(session, post_capture_input)
        return False

    (
        captured_amount_minor,
        refund_amount_minor,
        chargeback_amount_minor,
        reversal_amount_minor,
        net_effect_sign,
    ) = _post_capture_revenue_operands(
        event_type=post_capture_input.event_type,
        amount_minor=post_capture_input.amount_minor,
    )

    await session.execute(
        text(
            """
            INSERT INTO b23_revenue_events (
                tenant_id,
                match_verdict_id,
                provider,
                provider_native_event_reference,
                provider_native_commerce_reference,
                canonical_commerce_reference,
                event_type,
                captured_amount_minor,
                refund_amount_minor,
                chargeback_amount_minor,
                reversal_amount_minor,
                net_effect_sign,
                currency_code,
                event_occurred_at,
                recorded_at,
                created_at,
                updated_at,
                is_gross_capture_correction
            )
            VALUES (
                :tenant_id,
                :match_verdict_id,
                :provider,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                :canonical_commerce_reference,
                :event_type,
                :captured_amount_minor,
                :refund_amount_minor,
                :chargeback_amount_minor,
                :reversal_amount_minor,
                :net_effect_sign,
                :currency_code,
                :event_occurred_at,
                :recorded_at,
                :created_at,
                :updated_at,
                :is_gross_capture_correction
            )
            ON CONFLICT (tenant_id, provider, provider_native_event_reference)
            DO NOTHING
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "match_verdict_id": str(post_capture_input.match_verdict_id),
            "provider": post_capture_input.provider,
            "provider_native_event_reference": post_capture_input.provider_native_event_reference,
            "provider_native_commerce_reference": post_capture_input.provider_native_commerce_reference,
            "canonical_commerce_reference": str(canonical_reference),
            "event_type": post_capture_input.event_type,
            "captured_amount_minor": captured_amount_minor,
            "refund_amount_minor": refund_amount_minor,
            "chargeback_amount_minor": chargeback_amount_minor,
            "reversal_amount_minor": reversal_amount_minor,
            "net_effect_sign": net_effect_sign,
            "currency_code": post_capture_input.currency_code.strip().upper(),
            "event_occurred_at": timestamp,
            "recorded_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
            "is_gross_capture_correction": bool(
                post_capture_input.is_gross_capture_correction
            ),
        },
    )
    if post_capture_input.is_gross_capture_correction:
        await _apply_gross_capture_correction(
            session,
            tenant_id=post_capture_input.tenant_id,
            match_verdict_id=post_capture_input.match_verdict_id,
            corrected_captured_gross_amount_minor=post_capture_input.amount_minor,
            timestamp=timestamp,
        )
        return True

    net_verified_amount = await _recompute_b23_net_verified_amount(
        session,
        tenant_id=post_capture_input.tenant_id,
        match_verdict_id=post_capture_input.match_verdict_id,
    )
    await session.execute(
        text(
            """
            UPDATE b23_match_verdicts
            SET
                status = 'adjusted',
                canonical_net_verified_amount_minor = :net_verified_amount,
                adjusted_at = :adjusted_at,
                last_transition_at = :last_transition_at,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id AND id = :match_verdict_id
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "match_verdict_id": str(post_capture_input.match_verdict_id),
            "net_verified_amount": net_verified_amount,
            "adjusted_at": timestamp,
            "last_transition_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return True


async def seed_pending_match_verdict(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    provider: B23ProviderKey,
    provider_native_event_reference: str,
    provider_native_commerce_reference: str,
    canonical_commerce_reference: str,
    pending_since: datetime,
    currency_code: str = "USD",
) -> UUID:
    event_time = _normalize_utc(pending_since)
    result = await session.execute(
        text(
            """
            INSERT INTO b23_match_verdicts (
                tenant_id,
                provider,
                canonical_commerce_reference,
                provider_native_event_reference,
                provider_native_commerce_reference,
                status,
                match_quality,
                attributed_amount_minor,
                verified_amount_minor,
                currency_code,
                pending_since,
                last_transition_at,
                created_at,
                updated_at,
                canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor,
                discrepancy_amount_minor,
                discrepancy_ratio_bps,
                discrepancy_band
            )
            VALUES (
                :tenant_id,
                :provider,
                :canonical_commerce_reference,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                'pending',
                'low',
                0,
                0,
                :currency_code,
                :pending_since,
                :last_transition_at,
                :created_at,
                :updated_at,
                0,
                0,
                0,
                0,
                0,
                'exact'
            )
            ON CONFLICT (tenant_id, provider, provider_native_event_reference)
            DO UPDATE SET
                pending_since = EXCLUDED.pending_since,
                updated_at = EXCLUDED.updated_at
            RETURNING id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "provider": provider,
            "canonical_commerce_reference": canonical_commerce_reference,
            "provider_native_event_reference": provider_native_event_reference,
            "provider_native_commerce_reference": provider_native_commerce_reference,
            "currency_code": currency_code.strip().upper(),
            "pending_since": event_time,
            "last_transition_at": event_time,
            "created_at": event_time,
            "updated_at": event_time,
        },
    )
    return UUID(str(result.scalar_one()))


async def classify_stale_pending_as_unmatched(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    now_utc: datetime,
) -> int:
    normalized_now = _normalize_utc(now_utc)
    stale_before = normalized_now - WEBHOOK_ARRIVAL_WINDOW
    result = await session.execute(
        text(
            """
            UPDATE b23_match_verdicts
            SET
                status = 'unmatched',
                unmatched_marked_at = :marked_at,
                last_transition_at = :transitioned_at,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id
              AND status = 'pending'
              AND pending_since <= :stale_before
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "marked_at": normalized_now,
            "transitioned_at": normalized_now,
            "updated_at": normalized_now,
            "stale_before": stale_before,
        },
    )
    return int(result.rowcount or 0)


def build_persisted_ingress_revenue_input(
    *,
    provider: B23ProviderKey,
    verified_amount_minor: int,
    verified_amount_currency: str,
) -> PersistedIngressExtractionInput:
    return PersistedIngressExtractionInput(
        provider=provider,
        verified_amount_minor=verified_amount_minor,
        verified_amount_currency=verified_amount_currency,
    )


def discrepancy_ratio_percent(discrepancy_ratio: Decimal) -> Decimal:
    return (discrepancy_ratio * _B23_PERCENT_DENOMINATOR).quantize(Decimal("0.01"))
