"""B2.4-P2 source snapshot hashing protocol."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.eligibility import (
    EligibilityPreflightResult,
    FallbackReason,
    run_eligibility_preflight,
)
from app.bayesian.exceptions import BayesianTenantContextError
from app.bayesian.input_contract import (
    ELIGIBILITY_POLICY_VERSION,
    REQUIRED_TENANT_GUC,
    SENTINEL_PREFIX,
    SOURCE_CONTRACT_VERSION,
    STREAM_CHUNK_FORMAT_VERSION,
)


@dataclass(frozen=True)
class SourceSnapshotResult:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    preflight: EligibilityPreflightResult
    streamed_chunk_count: int
    sentinel_material: str | None = None

    @property
    def is_sentinel(self) -> bool:
        return self.sentinel_material is not None


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=timezone.utc)
    else:
        normalized = value.astimezone(timezone.utc)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def canonical_json_bytes(payload: dict[str, object]) -> bytes:
    """Serialize one canonical row/chunk without building a full manifest."""

    normalized = {key: _canonical_value(payload[key]) for key in sorted(payload)}
    return (
        json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sentinel_material_for(fallback_reason: FallbackReason | str) -> str:
    """Return stable versioned sentinel material for cold/sparse states."""

    reason = (
        fallback_reason.value
        if isinstance(fallback_reason, FallbackReason)
        else str(fallback_reason)
    )
    return (
        f"{SENTINEL_PREFIX}"
        f"|source_contract_version={SOURCE_CONTRACT_VERSION}"
        f"|eligibility_policy_version={ELIGIBILITY_POLICY_VERSION}"
        f"|fallback_reason={reason}"
    )


def sentinel_hash_for(fallback_reason: FallbackReason | str) -> str:
    """Compute the stable lowercase SHA-256 sentinel hash."""

    return hashlib.sha256(
        sentinel_material_for(fallback_reason).encode("utf-8")
    ).hexdigest()


def _hash_header(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
) -> bytes:
    return canonical_json_bytes(
        {
            "chunk_type": "header",
            "source_contract_version": SOURCE_CONTRACT_VERSION,
            "eligibility_policy_version": ELIGIBILITY_POLICY_VERSION,
            "stream_chunk_format_version": STREAM_CHUNK_FORMAT_VERSION,
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": _utc_iso(source_window_start),
            "source_window_end": _utc_iso(source_window_end),
        }
    )


_SOURCE_QUERIES = {
    "attribution_events": (
        text(
            """
            SELECT
                'attribution_events' AS source_table_discriminator,
                id::text AS id,
                tenant_id::text AS tenant_id,
                occurred_at,
                event_timestamp,
                event_type,
                channel,
                campaign_id,
                revenue_cents,
                conversion_value_cents,
                upper(coalesce(currency, 'USD')) AS currency,
                processing_status
            FROM public.attribution_events
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :window_start
              AND occurred_at < :window_end
              AND processing_status IN :processed_statuses
              AND event_type IN :conversion_event_types
            ORDER BY tenant_id ASC, occurred_at ASC NULLS LAST, id ASC
            """
        )
        .bindparams(bindparam("processed_statuses", expanding=True))
        .bindparams(bindparam("conversion_event_types", expanding=True))
    ),
    "attribution_allocations": text(
        """
        SELECT
            'attribution_allocations' AS source_table_discriminator,
            id::text AS id,
            tenant_id::text AS tenant_id,
            event_id::text AS event_id,
            created_at,
            channel_code,
            allocated_revenue_cents,
            allocation_ratio,
            model_type,
            model_version,
            verified,
            verification_source,
            verification_timestamp
        FROM public.attribution_allocations
        WHERE tenant_id = :tenant_id
          AND created_at >= :window_start
          AND created_at < :window_end
          AND verified = true
        ORDER BY tenant_id ASC, created_at ASC NULLS LAST, id ASC
        """
    ),
    "b23_match_verdicts": (
        text(
            """
            SELECT
                'b23_match_verdicts' AS source_table_discriminator,
                id::text AS id,
                tenant_id::text AS tenant_id,
                attribution_event_id::text AS attribution_event_id,
                provider,
                canonical_commerce_reference,
                status,
                match_quality,
                attributed_amount_minor,
                verified_amount_minor,
                upper(currency_code) AS currency_code,
                confirmed_at,
                adjusted_at,
                last_transition_at,
                canonical_expected_gross_amount_minor,
                canonical_captured_gross_amount_minor,
                canonical_net_verified_amount_minor,
                discrepancy_amount_minor,
                discrepancy_ratio_bps,
                discrepancy_band
            FROM public.b23_match_verdicts
            WHERE tenant_id = :tenant_id
              AND last_transition_at >= :window_start
              AND last_transition_at < :window_end
              AND status IN :match_verdict_statuses
            ORDER BY tenant_id ASC, last_transition_at ASC NULLS LAST, id ASC
            """
        ).bindparams(bindparam("match_verdict_statuses", expanding=True))
    ),
    "b23_revenue_events": (
        text(
            """
            SELECT
                'b23_revenue_events' AS source_table_discriminator,
                id::text AS id,
                tenant_id::text AS tenant_id,
                match_verdict_id::text AS match_verdict_id,
                provider,
                canonical_commerce_reference,
                event_type,
                upper(currency_code) AS currency_code,
                event_occurred_at,
                captured_amount_minor,
                refund_amount_minor,
                chargeback_amount_minor,
                reversal_amount_minor,
                net_effect_sign,
                is_gross_capture_correction
            FROM public.b23_revenue_events
            WHERE tenant_id = :tenant_id
              AND event_occurred_at >= :window_start
              AND event_occurred_at < :window_end
              AND event_type IN :revenue_event_types
            ORDER BY tenant_id ASC, event_occurred_at ASC NULLS LAST, id ASC
            """
        ).bindparams(bindparam("revenue_event_types", expanding=True))
    ),
}

_QUERY_PARAMS = {
    "processed_statuses": ("processed",),
    "conversion_event_types": ("conversion",),
    "match_verdict_statuses": ("matched_confirmed", "adjusted"),
    "revenue_event_types": (
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_lost",
        "chargeback_won",
        "reversal",
    ),
}


async def _assert_tenant_guc(session: AsyncSession, tenant_id: UUID) -> None:
    result = await session.execute(
        text("SELECT current_setting('app.current_tenant_id', true)")
    )
    current = result.scalar_one_or_none()
    if str(current or "") != str(tenant_id):
        raise BayesianTenantContextError(
            "tenant GUC must be bound before source snapshot reads"
        )


async def stream_source_chunks(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
):
    """Yield canonical row chunks from deterministic, totally ordered source streams."""

    params = {
        "tenant_id": str(tenant_id),
        "window_start": source_window_start,
        "window_end": source_window_end,
        **_QUERY_PARAMS,
    }
    for source_name, query in _SOURCE_QUERIES.items():
        yield canonical_json_bytes(
            {
                "chunk_type": "source_begin",
                "source": source_name,
                "source_contract_version": SOURCE_CONTRACT_VERSION,
            }
        )
        stream = await session.stream(query, params)
        async for row in stream.mappings():
            payload = dict(row)
            payload["chunk_type"] = "source_row"
            yield canonical_json_bytes(payload)
        yield canonical_json_bytes({"chunk_type": "source_end", "source": source_name})


async def compute_source_snapshot_hash(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
) -> SourceSnapshotResult:
    """Preflight and hash the source state under one repeatable-read transaction."""

    async with session.begin():
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        )
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
            {"guc_name": REQUIRED_TENANT_GUC, "tenant_id": str(tenant_id)},
        )
        await _assert_tenant_guc(session, tenant_id)
        preflight = await run_eligibility_preflight(
            session,
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
        )
        if not preflight.is_eligible:
            assert preflight.fallback_reason is not None
            material = sentinel_material_for(preflight.fallback_reason)
            return SourceSnapshotResult(
                tenant_id=tenant_id,
                model_type=model_type,
                model_version=model_version,
                source_window_start=source_window_start,
                source_window_end=source_window_end,
                source_snapshot_hash=hashlib.sha256(
                    material.encode("utf-8")
                ).hexdigest(),
                preflight=preflight,
                streamed_chunk_count=0,
                sentinel_material=material,
            )

        hasher = hashlib.sha256()
        hasher.update(
            _hash_header(
                tenant_id=tenant_id,
                model_type=model_type,
                model_version=model_version,
                source_window_start=source_window_start,
                source_window_end=source_window_end,
            )
        )
        chunk_count = 1
        async for canonical_chunk in stream_source_chunks(
            session,
            tenant_id=tenant_id,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
        ):
            hasher.update(canonical_chunk)
            chunk_count += 1
        return SourceSnapshotResult(
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            source_snapshot_hash=hasher.hexdigest(),
            preflight=preflight,
            streamed_chunk_count=chunk_count,
        )
