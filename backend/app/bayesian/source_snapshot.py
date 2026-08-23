"""B2.4-P2 source snapshot hashing protocol."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.eligibility import (
    EligibilityPreflightResult,
    FallbackReason,
    run_eligibility_preflight,
    run_eligibility_preflight_sync,
)
from app.bayesian.enums import FallbackReason as WorkerFallbackReason
from app.bayesian.exceptions import BayesianTenantContextError
from app.bayesian.input_contract import (
    ALLOWED_SOURCE_READ_MODELS,
    ELIGIBILITY_POLICY_VERSION,
    SENTINEL_PREFIX,
    SOURCE_CONTRACT_VERSION,
    SOURCE_STREAM_MAX_ROW_BUFFER,
    SOURCE_STREAM_PARTITION_SIZE,
    STREAM_CHUNK_FORMAT_VERSION,
)


P6_SOURCE_OBSERVED_SIGNAL_VERSION = "b24-p6-source-observed-v1"


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
    source_read_started_at: datetime | None = None
    source_read_completed_at: datetime | None = None
    #: Whatever ``within_snapshot`` measured, measured inside the same
    #: transaction that produced ``source_snapshot_hash``. Carrying it here
    #: rather than returning it separately keeps the measurement and the hash
    #: that authorises it inseparable at the type level.
    within_snapshot_result: object | None = None
    sentinel_material: str | None = None

    @property
    def is_sentinel(self) -> bool:
        return self.sentinel_material is not None


@dataclass(frozen=True)
class P6SourceObservedInput:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    observed_signal: list[float]
    observed_signal_version: str
    streamed_chunk_count: int
    streamed_source_row_count: int
    source_amount_minor_total: int
    deterministic_revenue_minor: int
    deterministic_revenue_row_count: int
    deterministic_match_verdict_count: int
    deterministic_currency_count: int
    resource_policy_version: str

    def metadata(self) -> dict[str, object]:
        return {
            "observed_signal_version": self.observed_signal_version,
            "streamed_chunk_count": self.streamed_chunk_count,
            "streamed_source_row_count": self.streamed_source_row_count,
            "source_amount_minor_total": self.source_amount_minor_total,
            "deterministic_revenue_minor": self.deterministic_revenue_minor,
            "deterministic_revenue_row_count": self.deterministic_revenue_row_count,
            "deterministic_match_verdict_count": self.deterministic_match_verdict_count,
            "deterministic_currency_count": self.deterministic_currency_count,
            "resource_policy_version": self.resource_policy_version,
        }


class P6SourceAuthorityError(RuntimeError):
    """P6 cannot launch the sampler because source authority failed closed."""

    def __init__(self, reason: WorkerFallbackReason, detail: str) -> None:
        super().__init__(detail)
        self.reason = reason
        self.detail = detail


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


def _contract_row_payload(
    source_name: str, row: dict[str, object]
) -> dict[str, object]:
    """Project a streamed row onto the versioned source contract allowlist."""

    allowed = set(ALLOWED_SOURCE_READ_MODELS[source_name])
    allowed.add("source_table_discriminator")
    extra_fields = set(row) - allowed
    if extra_fields:
        raise ValueError(
            f"non-contract source fields for {source_name}: {sorted(extra_fields)}"
        )
    return {field: row.get(field) for field in sorted(allowed) if field in row}


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

_STREAM_EXECUTION_OPTIONS = {
    "stream_results": True,
    "yield_per": SOURCE_STREAM_PARTITION_SIZE,
    "max_row_buffer": SOURCE_STREAM_MAX_ROW_BUFFER,
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


def _assert_tenant_guc_sync(conn, tenant_id: UUID) -> None:
    result = conn.execute(text("SELECT current_setting('app.current_tenant_id', true)"))
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
        stream = await session.stream(
            query.execution_options(**_STREAM_EXECUTION_OPTIONS),
            params,
        )
        async for partition in stream.mappings().partitions(
            SOURCE_STREAM_PARTITION_SIZE
        ):
            for row in partition:
                payload = _contract_row_payload(source_name, dict(row))
                payload["chunk_type"] = "source_row"
                yield canonical_json_bytes(payload)
        yield canonical_json_bytes({"chunk_type": "source_end", "source": source_name})


def _integer_payload_value(payload: dict[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return 0
    return int(value)


def _p6_amount_minor(payload: dict[str, object]) -> int:
    source_name = str(payload.get("source_table_discriminator", ""))
    if source_name == "attribution_events":
        return _integer_payload_value(payload, "revenue_cents")
    if source_name == "attribution_allocations":
        return _integer_payload_value(payload, "allocated_revenue_cents")
    if source_name == "b23_match_verdicts":
        return _integer_payload_value(payload, "canonical_net_verified_amount_minor")
    if source_name == "b23_revenue_events":
        return (
            _integer_payload_value(payload, "captured_amount_minor")
            + _integer_payload_value(payload, "refund_amount_minor")
            + _integer_payload_value(payload, "chargeback_amount_minor")
            + _integer_payload_value(payload, "reversal_amount_minor")
        )
    return 0


def _bounded_signal_from_source_rows(
    *, row_count: int, amount_minor: int
) -> list[float]:
    amount_signal = max(-10.0, min(10.0, amount_minor / 100_000.0))
    row_signal = max(0.0, min(10.0, row_count / 1_000.0))
    mean_signal = 0.0
    if row_count > 0:
        mean_signal = max(-10.0, min(10.0, (amount_minor / row_count) / 10_000.0))
    return [
        round(amount_signal, 6),
        round(row_signal, 6),
        round(mean_signal, 6),
    ]


def _b23_deterministic_net_minor(payload: dict[str, object]) -> int:
    """Return B2.3's sovereign signed net amount for one revenue event."""

    captured = _integer_payload_value(payload, "captured_amount_minor")
    if _integer_payload_value(payload, "net_effect_sign") >= 0:
        return captured
    adjustment = (
        payload.get("refund_amount_minor")
        or payload.get("chargeback_amount_minor")
        or payload.get("reversal_amount_minor")
        or payload.get("captured_amount_minor")
        or 0
    )
    if isinstance(adjustment, bool) or not isinstance(adjustment, (int, str)):
        return 0
    return -int(adjustment)


def load_p6_observed_input_from_source_snapshot_sync(
    conn,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    preflight_lease_id: str,
) -> P6SourceObservedInput:
    """Verify the frozen P2 source authority and derive bounded P6 input.

    This synchronous worker path intentionally replays the same source contract
    used by P2 hashing. The hash verifies identity; source rows produce the
    observed signal.
    """

    from app.bayesian.feature_authority import (
        FeatureAuthorityUnavailable,
        load_source_window_feature_authority_sync,
    )
    from app.bayesian.resource_profile import evaluate_source_snapshot_resource_bounds

    conn.execute(
        text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    _assert_tenant_guc_sync(conn, tenant_id)
    preflight = run_eligibility_preflight_sync(
        conn,
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
    )
    if not preflight.is_eligible:
        raise P6SourceAuthorityError(
            WorkerFallbackReason.SOURCE_UNAVAILABLE,
            "fit source snapshot is not eligible for P6 real-fit execution",
        )
    try:
        feature_authority = load_source_window_feature_authority_sync(
            conn,
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            source_snapshot_hash=source_snapshot_hash,
        )
    except FeatureAuthorityUnavailable as exc:
        raise P6SourceAuthorityError(exc.reason, exc.detail) from exc

    pre_materialization_snapshot = SourceSnapshotResult(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        source_snapshot_hash=source_snapshot_hash,
        preflight=preflight,
        streamed_chunk_count=0,
    )
    resource_decision = evaluate_source_snapshot_resource_bounds(
        snapshot=pre_materialization_snapshot,
        preflight_lease_id=preflight_lease_id,
        feature_authority=feature_authority,
    )
    if not resource_decision.allowed:
        assert resource_decision.failure_reason is not None
        raise P6SourceAuthorityError(
            resource_decision.failure_reason,
            "P4 resource authority rejected source snapshot before P6 materialization",
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
    source_row_count = 0
    amount_minor_total = 0
    deterministic_revenue_minor = 0
    deterministic_revenue_row_count = 0
    deterministic_match_verdict_ids: set[str] = set()
    deterministic_currencies: set[str] = set()
    params = {
        "tenant_id": str(tenant_id),
        "window_start": source_window_start,
        "window_end": source_window_end,
        **_QUERY_PARAMS,
    }
    for source_name, query in _SOURCE_QUERIES.items():
        hasher.update(
            canonical_json_bytes(
                {
                    "chunk_type": "source_begin",
                    "source": source_name,
                    "source_contract_version": SOURCE_CONTRACT_VERSION,
                }
            )
        )
        chunk_count += 1
        result = conn.execute(
            query.execution_options(**_STREAM_EXECUTION_OPTIONS), params
        )
        for partition in result.mappings().partitions(SOURCE_STREAM_PARTITION_SIZE):
            for row in partition:
                payload = _contract_row_payload(source_name, dict(row))
                payload["chunk_type"] = "source_row"
                hasher.update(canonical_json_bytes(payload))
                chunk_count += 1
                source_row_count += 1
                amount_minor_total += _p6_amount_minor(payload)
                if source_name == "b23_revenue_events":
                    deterministic_revenue_minor += _b23_deterministic_net_minor(payload)
                    deterministic_revenue_row_count += 1
                    match_verdict_id = str(payload.get("match_verdict_id") or "")
                    if match_verdict_id:
                        deterministic_match_verdict_ids.add(match_verdict_id)
                    currency = str(payload.get("currency_code") or "").strip().upper()
                    if currency:
                        deterministic_currencies.add(currency)
        hasher.update(
            canonical_json_bytes({"chunk_type": "source_end", "source": source_name})
        )
        chunk_count += 1

    verified_hash = hasher.hexdigest()
    if verified_hash != source_snapshot_hash:
        raise P6SourceAuthorityError(
            WorkerFallbackReason.SOURCE_SNAPSHOT_MISMATCH,
            "fit source_snapshot_hash does not match replayed P2 source authority",
        )
    return P6SourceObservedInput(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        source_snapshot_hash=verified_hash,
        observed_signal=_bounded_signal_from_source_rows(
            row_count=source_row_count,
            amount_minor=amount_minor_total,
        ),
        observed_signal_version=P6_SOURCE_OBSERVED_SIGNAL_VERSION,
        streamed_chunk_count=chunk_count,
        streamed_source_row_count=source_row_count,
        source_amount_minor_total=amount_minor_total,
        deterministic_revenue_minor=deterministic_revenue_minor,
        deterministic_revenue_row_count=deterministic_revenue_row_count,
        deterministic_match_verdict_count=len(deterministic_match_verdict_ids),
        deterministic_currency_count=len(deterministic_currencies),
        resource_policy_version=resource_decision.input_profile.policy_version,
    )


async def compute_source_snapshot_hash(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    within_snapshot: Callable[[AsyncSession], Awaitable[Any]] | None = None,
) -> SourceSnapshotResult:
    """Preflight and hash the source state under one repeatable-read transaction.

    ``within_snapshot`` runs any additional measurement inside that same
    transaction, and its result is carried back on
    ``SourceSnapshotResult.within_snapshot_result``.

    It exists because a caller that needs a second measurement of the same
    source state has exactly two options, and only one of them is true. It can
    open its own transaction afterwards -- in which case it measures a
    *different* MVCC snapshot than the one this function hashed, and any claim
    that the two describe the same source state is a guess about timing. Or it
    can measure here, inside the snapshot this function already holds, and the
    claim becomes a property of the database rather than of luck.

    Passing nothing leaves the behaviour of every existing caller unchanged.
    """

    async with session.begin():
        await session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        )
        source_read_started_at = (
            await session.execute(
                text(
                    """
                    SELECT
                        clock_timestamp() AS source_read_started_at,
                        set_config('app.current_tenant_id', :tenant_id, true)
                    """
                ),
                {"tenant_id": str(tenant_id)},
            )
        ).scalar_one()
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
            within_result = (
                None if within_snapshot is None else await within_snapshot(session)
            )
            source_read_completed_at = (
                await session.execute(text("SELECT clock_timestamp()"))
            ).scalar_one()
            return SourceSnapshotResult(
                within_snapshot_result=within_result,
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
                source_read_started_at=source_read_started_at,
                source_read_completed_at=source_read_completed_at,
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
        within_result = (
            None if within_snapshot is None else await within_snapshot(session)
        )
        source_read_completed_at = (
            await session.execute(text("SELECT clock_timestamp()"))
        ).scalar_one()
        return SourceSnapshotResult(
            within_snapshot_result=within_result,
            tenant_id=tenant_id,
            model_type=model_type,
            model_version=model_version,
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            source_snapshot_hash=hasher.hexdigest(),
            preflight=preflight,
            streamed_chunk_count=chunk_count,
            source_read_started_at=source_read_started_at,
            source_read_completed_at=source_read_completed_at,
        )
