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
from .semantic_authority import (
    B23DiscrepancyClass,
    CanonicalizationStatus,
    resolve_canonical_match_key,
)
from .timing_constants import WEBHOOK_ARRIVAL_WINDOW


B23_POST_CAPTURE_EVENT_TYPE = Literal[
    "partial_refund",
    "full_refund",
    "chargeback_opened",
    "chargeback_won",
    "chargeback_lost",
]

_B23_PERCENT_DENOMINATOR = Decimal("100")
_B23_HIGH_RATIO_MAX = Decimal("0.02")
_B23_MEDIUM_RATIO_MAX = Decimal("0.10")

B23_POST_CAPTURE_HANDLER_REGISTRY: Mapping[
    B23ProviderKey, tuple[B23_POST_CAPTURE_EVENT_TYPE, ...]
] = {
    "stripe": (
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
    ),
    "paypal": (
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
    ),
    "shopify": (
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
    ),
    "woocommerce": (
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
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
    discrepancy_amount_minor = (
        canonical_expected_gross_amount_minor - canonical_net_verified_amount_minor
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
            "provisional_expires_at": conversion_occurred_at + WEBHOOK_ARRIVAL_WINDOW,
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
                amount_minor,
                currency_code,
                event_occurred_at,
                recorded_at,
                created_at,
                updated_at
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
                :amount_minor,
                :currency_code,
                :event_occurred_at,
                :recorded_at,
                :created_at,
                :updated_at
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
            "amount_minor": extracted.amount_minor,
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
            or "unresolved_post_capture_event",
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
            or "unresolved_post_capture_event",
            "received_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    return verdict_id


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
        raise ValueError("post_capture_event_type_not_registered")
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
                amount_minor,
                currency_code,
                event_occurred_at,
                recorded_at,
                created_at,
                updated_at
            )
            VALUES (
                :tenant_id,
                :match_verdict_id,
                :provider,
                :provider_native_event_reference,
                :provider_native_commerce_reference,
                :canonical_commerce_reference,
                :event_type,
                :amount_minor,
                :currency_code,
                :event_occurred_at,
                :recorded_at,
                :created_at,
                :updated_at
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
            "amount_minor": post_capture_input.amount_minor,
            "currency_code": post_capture_input.currency_code.strip().upper(),
            "event_occurred_at": timestamp,
            "recorded_at": timestamp,
            "created_at": timestamp,
            "updated_at": timestamp,
        },
    )
    await session.execute(
        text(
            """
            UPDATE b23_match_verdicts
            SET
                status = 'adjusted',
                adjusted_at = :adjusted_at,
                last_transition_at = :last_transition_at,
                updated_at = :updated_at
            WHERE tenant_id = :tenant_id AND id = :match_verdict_id
            """
        ),
        {
            "tenant_id": str(post_capture_input.tenant_id),
            "match_verdict_id": str(post_capture_input.match_verdict_id),
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
