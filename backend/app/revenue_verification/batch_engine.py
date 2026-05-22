"""B2.3-P4 set-based micro-batch match execution."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import text

from app.bayesian.dirty_marker import append_dirty_event
from app.db.session import get_b23_session
from app.revenue_verification.timing_constants import PROVISIONAL_MATCH_WINDOW


B23_BATCH_MATCH_CHUNK_SIZE = 500
B23_BATCH_MATCH_QUERY_COUNT_PER_CHUNK_CEILING = 6
B23_BATCH_MATCH_PERFORMANCE_THRESHOLD_SECONDS = 10.0
B23_BATCH_MATCH_BACKGROUND_CARDINALITY = 10_000
B23_HIGH_QUALITY_MATCH_WINDOW_SECONDS = 600


@dataclass(frozen=True)
class B23BatchMatchResult:
    processed_count: int
    chunk_count: int
    chunk_size: int
    query_count_ceiling: int
    duration_seconds: float


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _execute_b23_batch_chunk(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    chunk_size: int,
) -> int:
    async with get_b23_session(tenant_id) as session:
        result = await session.execute(
            text(
                """
                WITH claimed_webhooks AS MATERIALIZED (
                    SELECT
                        wi.id AS webhook_ingress_identity_id,
                        wi.tenant_id,
                        wi.provider,
                        wi.provider_native_event_reference,
                        wi.provider_native_commerce_reference,
                        wi.normalized_commerce_reference_value AS canonical_commerce_reference,
                        wi.verified_amount_minor,
                        wi.verified_amount_currency,
                        wi.event_timestamp
                    FROM public.webhook_ingress_identities wi
                    WHERE wi.tenant_id = :tenant_id
                      AND wi.verified_commerce_ingress_state = 'authenticity_verified'
                      AND wi.event_timestamp >= :window_start
                      AND wi.event_timestamp < :window_end
                      AND NOT EXISTS (
                          SELECT 1
                          FROM public.b23_match_verdicts existing
                          WHERE existing.tenant_id = wi.tenant_id
                            AND existing.webhook_ingress_identity_id = wi.id
                      )
                      AND NOT EXISTS (
                          SELECT 1
                          FROM public.b23_match_verdicts existing
                          WHERE existing.tenant_id = wi.tenant_id
                            AND existing.provider = wi.provider
                            AND existing.provider_native_event_reference = wi.provider_native_event_reference
                      )
                    ORDER BY wi.event_timestamp ASC, wi.id ASC
                    LIMIT :chunk_size
                    FOR UPDATE OF wi SKIP LOCKED
                ),
                claimed AS (
                    SELECT
                        wi.webhook_ingress_identity_id,
                        wi.tenant_id,
                        wi.provider,
                        wi.provider_native_event_reference,
                        wi.provider_native_commerce_reference,
                        wi.canonical_commerce_reference,
                        wi.verified_amount_minor,
                        wi.verified_amount_currency,
                        wi.event_timestamp,
                        ae.id AS attribution_event_id,
                        COALESCE(ae.conversion_value_cents, ae.revenue_cents, 0) AS attributed_amount_minor,
                        COALESCE(ae.currency, wi.verified_amount_currency) AS attributed_currency_code,
                        ae.occurred_at AS conversion_occurred_at
                    FROM claimed_webhooks wi
                    JOIN LATERAL (
                        SELECT
                            aci.tenant_id,
                            aci.attribution_event_id
                        FROM public.attribution_commerce_identities aci
                        WHERE aci.tenant_id = wi.tenant_id
                          AND aci.provider = wi.provider
                          AND aci.canonical_commerce_reference = wi.canonical_commerce_reference
                        LIMIT 1
                    ) aci ON true
                    JOIN public.attribution_events ae
                      ON ae.tenant_id = aci.tenant_id
                     AND ae.id = aci.attribution_event_id
                    WHERE COALESCE(ae.currency, wi.verified_amount_currency) = wi.verified_amount_currency
                ),
                prepared AS (
                    SELECT
                        *,
                        abs(attributed_amount_minor - verified_amount_minor) AS discrepancy_amount_minor,
                        CASE
                            WHEN attributed_amount_minor = 0 THEN 0
                            ELSE (abs(attributed_amount_minor - verified_amount_minor) * 10000 / attributed_amount_minor)
                        END AS discrepancy_ratio_bps
                    FROM claimed
                ),
                upserted AS (
                    INSERT INTO public.b23_match_verdicts (
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
                    SELECT
                        tenant_id,
                        attribution_event_id,
                        webhook_ingress_identity_id,
                        provider,
                        canonical_commerce_reference,
                        provider_native_event_reference,
                        provider_native_commerce_reference,
                        'matched_provisional',
                        CASE
                            WHEN discrepancy_ratio_bps <= 200
                             AND event_timestamp - conversion_occurred_at <= (:high_quality_window_seconds * interval '1 second')
                                THEN 'high'
                            WHEN discrepancy_ratio_bps <= 1000
                                THEN 'medium'
                            ELSE 'low'
                        END,
                        attributed_amount_minor,
                        verified_amount_minor,
                        upper(verified_amount_currency),
                        conversion_occurred_at,
                        event_timestamp + (:provisional_window_seconds * interval '1 second'),
                        event_timestamp,
                        event_timestamp,
                        event_timestamp,
                        attributed_amount_minor,
                        verified_amount_minor,
                        verified_amount_minor,
                        discrepancy_amount_minor,
                        discrepancy_ratio_bps,
                        CASE
                            WHEN discrepancy_ratio_bps = 0 THEN 'exact'
                            WHEN discrepancy_ratio_bps <= 200 THEN 'within_tolerance'
                            WHEN discrepancy_ratio_bps <= 1000 THEN 'over_tolerance'
                            ELSE 'severe_gap'
                        END
                    FROM prepared
                    ON CONFLICT (tenant_id, provider, provider_native_event_reference)
                    DO UPDATE SET
                        attribution_event_id = EXCLUDED.attribution_event_id,
                        webhook_ingress_identity_id = EXCLUDED.webhook_ingress_identity_id,
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
                    RETURNING
                        id,
                        tenant_id,
                        provider,
                        canonical_commerce_reference,
                        discrepancy_band
                ),
                exception_insert AS (
                    INSERT INTO public.b23_exception_records (
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
                    SELECT
                        tenant_id,
                        id,
                        provider,
                        canonical_commerce_reference,
                        'open',
                        CASE
                            WHEN discrepancy_band = 'over_tolerance' THEN 'flagged'
                            ELSE 'alert'
                        END,
                        NULL,
                        'batch_match_discrepancy_band:' || discrepancy_band,
                        now(),
                        now(),
                        now()
                    FROM upserted
                    WHERE discrepancy_band IN ('over_tolerance', 'severe_gap')
                      AND NOT EXISTS (
                          SELECT 1
                          FROM public.b23_exception_records existing
                          WHERE existing.tenant_id = upserted.tenant_id
                            AND existing.match_verdict_id = upserted.id
                            AND existing.status IN ('open', 'acknowledged')
                      )
                    RETURNING id
                )
                SELECT count(*) AS processed_count
                FROM upserted
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "window_start": _normalize_utc(window_start),
                "window_end": _normalize_utc(window_end),
                "chunk_size": int(chunk_size),
                "high_quality_window_seconds": B23_HIGH_QUALITY_MATCH_WINDOW_SECONDS,
                "provisional_window_seconds": int(PROVISIONAL_MATCH_WINDOW.total_seconds()),
            },
        )
        processed_count = int(result.scalar_one() or 0)
        if processed_count > 0:
            await append_dirty_event(
                session,
                tenant_id=tenant_id,
                source_window_start=window_start,
                source_window_end=window_end,
                dirty_reason="b23_match_verdicts_changed",
                source_family="b23_match_verdicts",
                source_event_id=f"{window_start.isoformat()}:{window_end.isoformat()}",
                observed_at=datetime.now(timezone.utc),
            )
        return processed_count


async def execute_b23_batch_match_engine(
    *,
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    chunk_size: int = B23_BATCH_MATCH_CHUNK_SIZE,
    max_records: int | None = None,
) -> B23BatchMatchResult:
    """Process eligible pre-arrived B2.3 records in short set-based chunks."""
    if chunk_size < 1 or chunk_size > B23_BATCH_MATCH_CHUNK_SIZE:
        raise ValueError("chunk_size_must_be_between_1_and_B23_BATCH_MATCH_CHUNK_SIZE")
    started = time.perf_counter()
    processed_count = 0
    chunk_count = 0
    while True:
        remaining = None if max_records is None else max_records - processed_count
        if remaining is not None and remaining <= 0:
            break
        effective_chunk_size = min(chunk_size, remaining) if remaining is not None else chunk_size
        chunk_processed = await _execute_b23_batch_chunk(
            tenant_id=tenant_id,
            window_start=window_start,
            window_end=window_end,
            chunk_size=effective_chunk_size,
        )
        if chunk_processed == 0:
            break
        processed_count += chunk_processed
        chunk_count += 1
    duration_seconds = time.perf_counter() - started
    return B23BatchMatchResult(
        processed_count=processed_count,
        chunk_count=chunk_count,
        chunk_size=chunk_size,
        query_count_ceiling=max(1, chunk_count) * B23_BATCH_MATCH_QUERY_COUNT_PER_CHUNK_CEILING,
        duration_seconds=duration_seconds,
    )
