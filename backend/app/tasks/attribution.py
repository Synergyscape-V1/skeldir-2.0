"""
Attribution worker stubs for B0.5.3+ foundation.

These tasks are deterministic, enforce tenant context, and record basic metadata
for attribution workflows without implementing domain logic.

B0.5.3.2: Added window-scoped idempotency enforcement via attribution_recompute_jobs
table and deterministic baseline allocation proof harness.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import BaseModel, Field
from sqlalchemy import text

from app.celery_app import celery_app
from app.core.db import engine
from app.db.session import set_tenant_guc
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.tasks.context import tenant_task, run_in_worker_loop

logger = logging.getLogger(__name__)

# B0.5.3.6: Canonical deterministic channel ordering for baseline allocations.
# NOTE: `attribution_allocations` uses `channel_code` with FK to `channel_taxonomy.code`.
BASELINE_CHANNELS = ["direct", "email", "google_search_paid"]
_ALLOCATION_ID_NAMESPACE = uuid5(NAMESPACE_URL, "skeldir:attribution_allocations:id:v1")
_R5_FAILED_ONCE_KEYS: set[str] = set()


def _run_async(coro_factory, *args, **kwargs):
    """
    Execute async coroutines on the dedicated worker event loop.

    Reusing a single loop prevents asyncpg/SQLAlchemy pools from being bound to
    multiple event loops across sequential task executions.
    """
    coro = coro_factory(*args, **kwargs)
    return run_in_worker_loop(coro)


class AttributionTaskPayload(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant context for RLS")
    correlation_id: Optional[str] = Field(None, description="Correlation for observability")
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid4()), description="Idempotency/trace id")
    window_start: Optional[str] = Field(None, description="Attribution window start timestamp")
    window_end: Optional[str] = Field(None, description="Attribution window end timestamp")


def _prepare_context(model: AttributionTaskPayload) -> str:
    correlation = model.correlation_id or str(uuid4())
    set_request_correlation_id(correlation)
    set_tenant_id(model.tenant_id)
    return correlation


def _normalize_timestamp(iso_string: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO8601 timestamp string to timezone-aware datetime.

    B0.5.3.2: Window boundaries must be normalized to UTC for deterministic
    job identity matching.

    Args:
        iso_string: ISO8601 timestamp (e.g., "2025-01-01T00:00:00Z")

    Returns:
        Timezone-aware datetime in UTC, or None if input is None

    Raises:
        ValueError: If timestamp string is invalid
    """
    if iso_string is None:
        return None

    try:
        # Parse ISO format (handles both Z suffix and +00:00 offset)
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))

        # Convert to UTC if not already
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)

        return dt
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid ISO8601 timestamp: {iso_string}") from exc


def _deterministic_allocation_id(
    *,
    tenant_id: UUID,
    event_id: UUID,
    model_version: str,
    channel_code: str,
) -> UUID:
    return uuid5(
        _ALLOCATION_ID_NAMESPACE,
        f"{tenant_id}:{event_id}:{model_version}:{channel_code}",
    )


def _split_revenue_cents_evenly(revenue_cents: int, parts: int) -> list[int]:
    if parts < 1:
        raise ValueError("parts must be >= 1")
    if revenue_cents < 0:
        raise ValueError("revenue_cents must be >= 0")
    base = revenue_cents // parts
    remainder = revenue_cents % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


async def _upsert_job_identity(
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_version: str,
    correlation_id: str,
) -> tuple[UUID, int, str]:
    """
    Upsert job identity row in attribution_recompute_jobs table.

    B0.5.3.2: This enforces window-scoped idempotency via UNIQUE constraint on
    (tenant_id, window_start, window_end, model_version). Rerunning the same
    window will update the existing row, not create a duplicate.

    Returns:
        Tuple of (job_id, run_count, previous_status)

    Raises:
        Exception: On database errors
    """
    async with engine.begin() as conn:
        # Ensure tenant-scoped RLS context for this transaction
        await set_tenant_guc(conn, tenant_id, local=True)
        # Attempt INSERT to create new job identity
        # If UNIQUE constraint violation occurs, UPDATE existing row instead
        result = await conn.execute(
            text("""
                INSERT INTO attribution_recompute_jobs (
                    id, tenant_id, window_start, window_end, model_version,
                    status, run_count, last_correlation_id, created_at, updated_at
                ) VALUES (
                    :job_id, :tenant_id, :window_start, :window_end, :model_version,
                    'running', 1, :correlation_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                ON CONFLICT (tenant_id, window_start, window_end, model_version)
                DO UPDATE SET
                    status = 'running',
                    run_count = attribution_recompute_jobs.run_count + 1,
                    last_correlation_id = EXCLUDED.last_correlation_id,
                    updated_at = CURRENT_TIMESTAMP,
                    started_at = CURRENT_TIMESTAMP
                RETURNING id, run_count, NULL as previous_status
            """),
            {
                "job_id": uuid4(),
                "tenant_id": tenant_id,
                "window_start": window_start,
                "window_end": window_end,
                "model_version": model_version,
                "correlation_id": uuid4() if correlation_id is None else UUID(correlation_id),
            }
        )
        row = result.fetchone()

        if row is None:
            raise RuntimeError("Failed to upsert job identity - no row returned")

        job_id = row[0]
        run_count = row[1]
        previous_status = row[2] if row[2] else "new"

        logger.info(
            "attribution_job_identity_upserted",
            extra={
                "job_id": str(job_id),
                "tenant_id": str(tenant_id),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "model_version": model_version,
                "run_count": run_count,
                "previous_status": previous_status,
                "correlation_id": correlation_id,
            }
        )

        return (job_id, run_count, previous_status)


async def _mark_job_status(
    job_id: UUID,
    tenant_id: UUID,
    status: str,
    error_message: Optional[str] = None,
) -> None:
    """
    Update job status in attribution_recompute_jobs table.

    B0.5.3.2: Status transitions must be deterministic for observability.

    Args:
        job_id: Job UUID
        tenant_id: Tenant UUID (for RLS enforcement)
        status: New status (succeeded|failed)
        error_message: Error message (if status=failed)
    """
    async with engine.begin() as conn:
        # Ensure tenant-scoped RLS context for this transaction
        await set_tenant_guc(conn, tenant_id, local=True)
        await conn.execute(
            text("""
                UPDATE attribution_recompute_jobs
                SET status = :status,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = :job_id
                  AND tenant_id = :tenant_id
            """),
            {
                "job_id": job_id,
                "tenant_id": tenant_id,
                "status": status,
            }
        )

    logger.info(
        "attribution_job_status_updated",
        extra={
            "job_id": str(job_id),
            "tenant_id": str(tenant_id),
            "status": status,
            "error_message": error_message,
        }
    )


async def _compute_allocations_deterministic_baseline(
    tenant_id: UUID,
    window_start: datetime,
    window_end: datetime,
    model_version: str = "1.0.0",
    *,
    inject_fail_once_key: Optional[str] = None,
    inject_fail_after_batches: int = 1,
) -> dict:
    """
    Deterministic baseline attribution allocation proof harness.

    B0.5.3.2: This is NOT the final attribution model. This is a minimal
    deterministic proof harness that:
    1. Reads events in [window_start, window_end] from attribution_events (read-only)
    2. Writes derived rows into attribution_allocations using the existing
       event-scoped overwrite strategy (upsert on unique key)

    The logic is intentionally simple and deterministic: equal allocation across
    a fixed set of channels. Rerunning the same window MUST produce identical
    allocations (same rows + same values).

    Returns:
        Dict with metadata (event_count, allocation_count)
    """
    batch_events = int(os.getenv("ATTRIBUTION_BASELINE_BATCH_EVENTS", "2000"))
    if batch_events < 1:
        raise ValueError("ATTRIBUTION_BASELINE_BATCH_EVENTS must be >= 1")

    if inject_fail_once_key is not None:
        if os.getenv("ENABLE_R5_RETRY_INJECTION", "") != "1":
            raise ValueError("Retry injection requested but ENABLE_R5_RETRY_INJECTION != '1'")
        if inject_fail_after_batches < 1:
            raise ValueError("inject_fail_after_batches must be >= 1")

    fixed_ts = window_end
    allocation_ratio = (Decimal(1) / Decimal(len(BASELINE_CHANNELS))).quantize(
        Decimal("0.00001"), rounding=ROUND_HALF_UP
    )
    confidence_score = allocation_ratio.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    model_type = "deterministic_baseline"

    async with engine.begin() as conn:
        # Set tenant context for RLS policy
        await set_tenant_guc(conn, tenant_id, local=True)

        def _event_batch_query(*, has_cursor: bool) -> str:
            cursor_clause = ""
            if has_cursor:
                cursor_clause = """
                  AND (
                        occurred_at > :last_occurred_at
                     OR (occurred_at = :last_occurred_at AND id > :last_id)
                  )
                """
            return f"""
                SELECT id, revenue_cents, occurred_at
                FROM attribution_events
                WHERE tenant_id = :tenant_id
                  AND occurred_at >= :window_start
                  AND occurred_at < :window_end
                  {cursor_clause}
                ORDER BY occurred_at ASC, id ASC
                LIMIT :limit
            """

        async def _upsert_allocations_bulk(*, rows: dict[str, list]) -> None:
            if not rows["ids"]:
                return

            await conn.execute(
                text(
                    """
                    WITH rows AS (
                        SELECT *
                        FROM unnest(
                            :ids::uuid[],
                            :tenant_ids::uuid[],
                            :event_ids::uuid[],
                            :channel_codes::text[],
                            :allocation_ratios::numeric[],
                            :model_versions::text[],
                            :model_types::text[],
                            :confidence_scores::numeric[],
                            :verifieds::bool[],
                            :allocated_revenue_cents::int[],
                            :created_ats::timestamptz[],
                            :updated_ats::timestamptz[]
                        ) AS t(
                            id,
                            tenant_id,
                            event_id,
                            channel_code,
                            allocation_ratio,
                            model_version,
                            model_type,
                            confidence_score,
                            verified,
                            allocated_revenue_cents,
                            created_at,
                            updated_at
                        )
                    )
                    INSERT INTO attribution_allocations (
                        id,
                        tenant_id,
                        event_id,
                        channel_code,
                        allocation_ratio,
                        model_version,
                        model_type,
                        confidence_score,
                        verified,
                        allocated_revenue_cents,
                        created_at,
                        updated_at
                    )
                    SELECT
                        id,
                        tenant_id,
                        event_id,
                        channel_code,
                        allocation_ratio,
                        model_version,
                        model_type,
                        confidence_score,
                        verified,
                        allocated_revenue_cents,
                        created_at,
                        updated_at
                    FROM rows
                    ON CONFLICT (id)
                    DO UPDATE SET
                        allocation_ratio = EXCLUDED.allocation_ratio,
                        model_type = EXCLUDED.model_type,
                        confidence_score = EXCLUDED.confidence_score,
                        verified = EXCLUDED.verified,
                        allocated_revenue_cents = EXCLUDED.allocated_revenue_cents,
                        updated_at = EXCLUDED.updated_at
                    WHERE
                        attribution_allocations.allocation_ratio IS DISTINCT FROM EXCLUDED.allocation_ratio
                        OR attribution_allocations.model_type IS DISTINCT FROM EXCLUDED.model_type
                        OR attribution_allocations.confidence_score IS DISTINCT FROM EXCLUDED.confidence_score
                        OR attribution_allocations.verified IS DISTINCT FROM EXCLUDED.verified
                        OR attribution_allocations.allocated_revenue_cents IS DISTINCT FROM EXCLUDED.allocated_revenue_cents;
                    """
                ),
                rows,
            )

        event_count = 0
        allocation_count = 0
        batches_written = 0
        last_occurred_at: Optional[datetime] = None
        last_id: Optional[UUID] = None

        while True:
            query = _event_batch_query(has_cursor=last_occurred_at is not None)
            params = {
                "tenant_id": tenant_id,
                "window_start": window_start,
                "window_end": window_end,
                "limit": batch_events,
            }
            if last_occurred_at is not None and last_id is not None:
                params.update({"last_occurred_at": last_occurred_at, "last_id": last_id})

            events_result = await conn.execute(text(query), params)
            events = events_result.fetchall()
            if not events:
                break

            event_count += len(events)

            batch_rows: dict[str, list] = {
                "ids": [],
                "tenant_ids": [],
                "event_ids": [],
                "channel_codes": [],
                "allocation_ratios": [],
                "model_versions": [],
                "model_types": [],
                "confidence_scores": [],
                "verifieds": [],
                "allocated_revenue_cents": [],
                "created_ats": [],
                "updated_ats": [],
            }

            for event_id, revenue_cents, _occurred_at in events:
                allocated = _split_revenue_cents_evenly(int(revenue_cents), len(BASELINE_CHANNELS))
                for channel_code, allocated_revenue_cents in zip(
                    BASELINE_CHANNELS, allocated, strict=True
                ):
                    batch_rows["ids"].append(
                        _deterministic_allocation_id(
                            tenant_id=tenant_id,
                            event_id=event_id,
                            model_version=model_version,
                            channel_code=channel_code,
                        )
                    )
                    batch_rows["tenant_ids"].append(tenant_id)
                    batch_rows["event_ids"].append(event_id)
                    batch_rows["channel_codes"].append(channel_code)
                    batch_rows["allocation_ratios"].append(str(allocation_ratio))
                    batch_rows["model_versions"].append(model_version)
                    batch_rows["model_types"].append(model_type)
                    batch_rows["confidence_scores"].append(str(confidence_score))
                    batch_rows["verifieds"].append(False)
                    batch_rows["allocated_revenue_cents"].append(int(allocated_revenue_cents))
                    batch_rows["created_ats"].append(fixed_ts)
                    batch_rows["updated_ats"].append(fixed_ts)
                    allocation_count += 1

            await _upsert_allocations_bulk(rows=batch_rows)
            batches_written += 1

            if inject_fail_once_key is not None:
                if inject_fail_once_key not in _R5_FAILED_ONCE_KEYS and batches_written >= inject_fail_after_batches:
                    _R5_FAILED_ONCE_KEYS.add(inject_fail_once_key)
                    logger.warning(
                        "attribution_baseline_r5_retry_injection_triggered",
                        extra={
                            "tenant_id": str(tenant_id),
                            "model_version": model_version,
                            "inject_fail_once_key": inject_fail_once_key,
                            "inject_fail_after_batches": inject_fail_after_batches,
                            "batches_written": batches_written,
                        },
                    )
                    raise RuntimeError("R5 retry injection: transient failure")

            last_id = events[-1][0]
            last_occurred_at = events[-1][2]

        if event_count == 0:
            logger.info(
                "attribution_baseline_no_events_in_window",
                extra={
                    "tenant_id": str(tenant_id),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "model_version": model_version,
                },
            )
            return {"event_count": 0, "allocation_count": 0}

        logger.info(
            "attribution_baseline_allocations_computed",
            extra={
                "tenant_id": str(tenant_id),
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "model_version": model_version,
                "event_count": event_count,
                "allocation_count": allocation_count,
            }
        )

        return {
            "event_count": event_count,
            "allocation_count": allocation_count,
        }


@celery_app.task(
    bind=True,
    name="app.tasks.attribution.recompute_window",
    routing_key="attribution.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def recompute_window(
    self,
    tenant_id: UUID,
    window_start: Optional[str] = None,
    window_end: Optional[str] = None,
    correlation_id: Optional[str] = None,
    model_version: str = "1.0.0",
    fail: bool = False,
):
    """
    Attribution recompute window task with window-scoped idempotency.

    B0.5.3.2: This task enforces window-scoped idempotency via the
    attribution_recompute_jobs table. Rerunning the same (tenant_id, window_start,
    window_end, model_version) will:
    1. Reuse the existing job identity row (not create a duplicate)
    2. Increment run_count for observability
    3. Produce identical allocations (deterministic baseline proof harness)

    Args:
        tenant_id: Tenant context for RLS enforcement
        window_start: Start of attribution window (ISO timestamp, inclusive)
        window_end: End of attribution window (ISO timestamp, exclusive)
        correlation_id: Request correlation for observability
        model_version: Attribution model version (default: 1.0.0)
        fail: If True, deliberately raise an error for DLQ testing

    Returns:
        Dict with status and metadata (job_id, run_count, event_count, allocation_count)

    Raises:
        ValueError: If fail=True (for DLQ testing) or invalid window bounds
    """
    import asyncio

    model = AttributionTaskPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        window_start=window_start,
        window_end=window_end,
    )
    correlation = _prepare_context(model)

    # B0.5.3.1: Deliberate failure path for DLQ testing
    if fail:
        logger.warning(
            "attribution_recompute_window_failure_requested",
            extra={
                "task_id": self.request.id,
                "tenant_id": str(model.tenant_id),
                "correlation_id": correlation,
            },
        )
        raise ValueError("attribution recompute failure requested")

    # B0.5.3.2: Validate and normalize window boundaries
    if window_start is None or window_end is None:
        raise ValueError("window_start and window_end are required for B0.5.3.2 idempotency")

    try:
        window_start_dt = _normalize_timestamp(window_start)
        window_end_dt = _normalize_timestamp(window_end)
    except ValueError as exc:
        logger.error(
            "attribution_recompute_window_invalid_timestamps",
            exc_info=exc,
            extra={
                "task_id": self.request.id,
                "tenant_id": str(model.tenant_id),
                "window_start": window_start,
                "window_end": window_end,
            },
        )
        raise

    if window_start_dt >= window_end_dt:
        raise ValueError(f"window_start ({window_start}) must be < window_end ({window_end})")

    # B0.5.3.2: Upsert job identity (idempotency gate)
    try:
        job_id, run_count, previous_status = _run_async(
            _upsert_job_identity,
            tenant_id=model.tenant_id,
            window_start=window_start_dt,
            window_end=window_end_dt,
            model_version=model_version,
            correlation_id=correlation,
        )
    except Exception as exc:
        logger.error(
            "attribution_recompute_window_job_identity_failed",
            exc_info=exc,
            extra={
                "task_id": self.request.id,
                "tenant_id": str(model.tenant_id),
                "window_start": window_start,
                "window_end": window_end,
                "model_version": model_version,
            },
        )
        raise

    logger.info(
        "attribution_recompute_window_started",
        extra={
            "task_id": self.request.id,
            "job_id": str(job_id),
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation,
            "window_start": window_start,
            "window_end": window_end,
            "model_version": model_version,
            "run_count": run_count,
            "previous_status": previous_status,
        },
    )

    # B0.5.3.2: Compute allocations (deterministic baseline proof harness)
    try:
        result = _run_async(
            _compute_allocations_deterministic_baseline,
            tenant_id=model.tenant_id,
            window_start=window_start_dt,
            window_end=window_end_dt,
            model_version=model_version,
        )

        # Mark job as succeeded
        _run_async(
            _mark_job_status,
            job_id=job_id,
            tenant_id=model.tenant_id,
            status="succeeded",
        )

        logger.info(
            "attribution_recompute_window_succeeded",
            extra={
                "task_id": self.request.id,
                "job_id": str(job_id),
                "tenant_id": str(model.tenant_id),
                "correlation_id": correlation,
                "window_start": window_start,
                "window_end": window_end,
                "model_version": model_version,
                "run_count": run_count,
                "event_count": result["event_count"],
                "allocation_count": result["allocation_count"],
            },
        )

        return {
            "status": "succeeded",
            "job_id": str(job_id),
            "run_count": run_count,
            "window_start": window_start,
            "window_end": window_end,
            "model_version": model_version,
            "event_count": result["event_count"],
            "allocation_count": result["allocation_count"],
            "request_id": model.request_id,
            "correlation_id": correlation,
        }

    except Exception as exc:
        # Mark job as failed
        _run_async(
            _mark_job_status,
            job_id=job_id,
            tenant_id=model.tenant_id,
            status="failed",
            error_message=str(exc),
        )

        logger.error(
            "attribution_recompute_window_failed",
            exc_info=exc,
            extra={
                "task_id": self.request.id,
                "job_id": str(job_id),
                "tenant_id": str(model.tenant_id),
                "correlation_id": correlation,
                "window_start": window_start,
                "window_end": window_end,
                "model_version": model_version,
            },
        )
        raise
