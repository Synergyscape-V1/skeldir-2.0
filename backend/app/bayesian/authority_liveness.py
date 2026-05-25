"""Transient liveness controls for B2.4-P4 feature authority readiness."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.enums import FallbackReason
from app.bayesian.source_snapshot import SourceSnapshotResult


AUTHORITY_LIVENESS_POLICY_VERSION = "b24-p4-authority-liveness-v1"
DEFAULT_AUTHORITY_RETRY_DELAY_SECONDS = 60
DEFAULT_AUTHORITY_MAX_RETRIES = 5
AUTHORITY_YIELD_REASONS = (
    "cardinality_authority_missing",
    "cardinality_authority_stale",
    "cardinality_authority_mismatch",
)


class AuthorityBuildStatus(StrEnum):
    BUILD_REQUESTED = "authority_build_requested"
    WAITING = "authority_waiting"
    RETRY_READY = "authority_retry_ready"
    COMPLETED = "authority_completed"
    TIMEOUT = "authority_timeout"
    BUILD_FAILED = "authority_build_failed"


@dataclass(frozen=True)
class AuthorityBuildRequestResult:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    status: AuthorityBuildStatus
    retry_count: int
    max_retries: int
    retry_after_at: datetime | None
    terminal_reason: FallbackReason | None


UPSERT_AUTHORITY_BUILD_REQUEST_SQL = """
INSERT INTO public.b24_feature_authority_build_requests (
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash,
    status,
    authority_reason,
    detail,
    retry_count,
    max_retries,
    retry_after_at,
    policy_version,
    requested_at,
    updated_at
)
VALUES (
    :tenant_id,
    :model_type,
    :model_version,
    :source_window_start,
    :source_window_end,
    :source_snapshot_hash,
    'authority_build_requested',
    :authority_reason,
    :detail,
    0,
    :max_retries,
    now() + (:retry_delay_seconds * interval '1 second'),
    :policy_version,
    now(),
    now()
)
ON CONFLICT (
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash
)
DO UPDATE SET
    status = CASE
        WHEN b24_feature_authority_build_requests.status IN (
            'authority_completed',
            'authority_timeout',
            'authority_build_failed'
        )
            THEN b24_feature_authority_build_requests.status
        WHEN b24_feature_authority_build_requests.retry_count + 1
             >= b24_feature_authority_build_requests.max_retries
            THEN 'authority_timeout'
        ELSE 'authority_waiting'
    END,
    retry_count = CASE
        WHEN b24_feature_authority_build_requests.status IN (
            'authority_completed',
            'authority_timeout',
            'authority_build_failed'
        )
            THEN b24_feature_authority_build_requests.retry_count
        ELSE b24_feature_authority_build_requests.retry_count + 1
    END,
    authority_reason = EXCLUDED.authority_reason,
    detail = EXCLUDED.detail,
    retry_after_at = CASE
        WHEN b24_feature_authority_build_requests.status IN (
            'authority_completed',
            'authority_timeout',
            'authority_build_failed'
        )
            THEN b24_feature_authority_build_requests.retry_after_at
        ELSE now() + (
            ((b24_feature_authority_build_requests.retry_count + 1)
             * :retry_delay_seconds) * interval '1 second'
        )
    END,
    terminal_reason = CASE
        WHEN b24_feature_authority_build_requests.status IN (
            'authority_completed',
            'authority_build_failed'
        )
            THEN b24_feature_authority_build_requests.terminal_reason
        WHEN b24_feature_authority_build_requests.status = 'authority_timeout'
            THEN 'cardinality_authority_timeout'
        WHEN b24_feature_authority_build_requests.retry_count + 1
             >= b24_feature_authority_build_requests.max_retries
            THEN 'cardinality_authority_timeout'
        ELSE NULL
    END,
    terminal_at = CASE
        WHEN b24_feature_authority_build_requests.status IN (
            'authority_completed',
            'authority_build_failed'
        )
            THEN b24_feature_authority_build_requests.terminal_at
        WHEN b24_feature_authority_build_requests.status = 'authority_timeout'
            THEN COALESCE(b24_feature_authority_build_requests.terminal_at, now())
        WHEN b24_feature_authority_build_requests.retry_count + 1
             >= b24_feature_authority_build_requests.max_retries
            THEN now()
        ELSE NULL
    END,
    updated_at = now()
RETURNING
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash,
    status,
    retry_count,
    max_retries,
    retry_after_at,
    terminal_reason
"""


REACTIVATE_PLANNER_FOR_AUTHORITY_SQL = """
WITH transitioned AS (
    UPDATE public.b24_feature_authority_build_requests
    SET status = 'authority_completed',
        completed_at = now(),
        retry_after_at = NULL,
        terminal_reason = NULL,
        terminal_at = NULL,
        updated_at = now()
    WHERE tenant_id = :tenant_id
      AND model_type = :model_type
      AND model_version = :model_version
      AND source_window_start = :source_window_start
      AND source_window_end = :source_window_end
      AND source_snapshot_hash = :source_snapshot_hash
      AND status IN (
          'authority_build_requested',
          'authority_waiting',
          'authority_retry_ready'
      )
    RETURNING
        tenant_id,
        model_type,
        model_version,
        source_window_start,
        source_window_end,
        source_snapshot_hash
),
reactivated_waiters AS (
    UPDATE public.b24_dirty_events dirty
    SET status = 'authority_retry_ready',
        authority_reactivated_at = now(),
        updated_at = now()
    FROM transitioned ready
    WHERE dirty.tenant_id = ready.tenant_id
      AND dirty.model_type = ready.model_type
      AND dirty.model_version = ready.model_version
      AND dirty.source_window_start = ready.source_window_start
      AND dirty.source_window_end = ready.source_window_end
      AND dirty.source_snapshot_hash = ready.source_snapshot_hash
      AND dirty.status = 'authority_waiting'
    RETURNING dirty.tenant_id
),
inserted_dirty AS (
    INSERT INTO public.b24_dirty_events (
        tenant_id,
        model_type,
        model_version,
        source_window_start,
        source_window_end,
        source_snapshot_hash,
        dirty_reason,
        source_family,
        source_event_id,
        status,
        observed_at,
        created_at,
        updated_at
    )
    SELECT
        tenant_id,
        model_type,
        model_version,
        source_window_start,
        source_window_end,
        source_snapshot_hash,
        'feature_authority_fresh',
        'b24_feature_authority',
        source_snapshot_hash,
        'pending',
        now(),
        now(),
        now()
    FROM transitioned
    RETURNING id
)
SELECT count(*)::int AS reactivated_count
FROM inserted_dirty
"""


SWEEP_AUTHORITY_WAITING_REQUESTS_SQL = """
WITH due AS (
    SELECT
        req.tenant_id,
        req.model_type,
        req.model_version,
        req.source_window_start,
        req.source_window_end,
        req.source_snapshot_hash,
        req.retry_count,
        req.max_retries
    FROM public.b24_feature_authority_build_requests req
    WHERE req.tenant_id = :tenant_id
      AND req.status IN ('authority_build_requested', 'authority_waiting')
      AND req.retry_after_at <= now()
    ORDER BY req.retry_after_at ASC
    LIMIT :limit
    FOR UPDATE SKIP LOCKED
),
ready AS (
    SELECT due.*
    FROM due
    JOIN public.b24_source_window_feature_authority auth
      ON auth.tenant_id = due.tenant_id
     AND auth.model_type = due.model_type
     AND auth.model_version = due.model_version
     AND auth.source_window_start = due.source_window_start
     AND auth.source_window_end = due.source_window_end
     AND auth.source_snapshot_hash = due.source_snapshot_hash
     AND auth.freshness_status = 'fresh'
),
marked_ready AS (
    UPDATE public.b24_feature_authority_build_requests req
    SET status = 'authority_retry_ready',
        retry_after_at = now(),
        updated_at = now()
    FROM ready
    WHERE req.tenant_id = ready.tenant_id
      AND req.model_type = ready.model_type
      AND req.model_version = ready.model_version
      AND req.source_window_start = ready.source_window_start
      AND req.source_window_end = ready.source_window_end
      AND req.source_snapshot_hash = ready.source_snapshot_hash
    RETURNING req.tenant_id
),
timed_out AS (
    UPDATE public.b24_feature_authority_build_requests req
    SET status = 'authority_timeout',
        terminal_reason = 'cardinality_authority_timeout',
        terminal_at = now(),
        updated_at = now()
    FROM due
    WHERE req.tenant_id = due.tenant_id
      AND req.model_type = due.model_type
      AND req.model_version = due.model_version
      AND req.source_window_start = due.source_window_start
      AND req.source_window_end = due.source_window_end
      AND req.source_snapshot_hash = due.source_snapshot_hash
      AND due.retry_count >= due.max_retries
      AND NOT EXISTS (
          SELECT 1
          FROM ready
          WHERE ready.tenant_id = due.tenant_id
            AND ready.model_type = due.model_type
            AND ready.model_version = due.model_version
            AND ready.source_window_start = due.source_window_start
            AND ready.source_window_end = due.source_window_end
            AND ready.source_snapshot_hash = due.source_snapshot_hash
      )
    RETURNING req.tenant_id
)
SELECT
    (SELECT count(*)::int FROM marked_ready) AS retry_ready_count,
    (SELECT count(*)::int FROM timed_out) AS timeout_count
"""


MARK_AUTHORITY_BUILD_FAILED_SQL = """
UPDATE public.b24_feature_authority_build_requests
SET status = 'authority_build_failed',
    terminal_reason = 'cardinality_authority_build_failed',
    terminal_at = now(),
    detail = COALESCE(:detail, detail),
    updated_at = now()
WHERE tenant_id = :tenant_id
  AND model_type = :model_type
  AND model_version = :model_version
  AND source_window_start = :source_window_start
  AND source_window_end = :source_window_end
  AND source_snapshot_hash = :source_snapshot_hash
  AND status IN (
      'authority_build_requested',
      'authority_waiting',
      'authority_retry_ready'
  )
RETURNING 1
"""


def _request_result_from_row(row: dict[str, object]) -> AuthorityBuildRequestResult:
    reason_value = row.get("terminal_reason")
    return AuthorityBuildRequestResult(
        tenant_id=row["tenant_id"],
        model_type=str(row["model_type"]),
        model_version=str(row["model_version"]),
        source_window_start=row["source_window_start"],
        source_window_end=row["source_window_end"],
        source_snapshot_hash=str(row["source_snapshot_hash"]),
        status=AuthorityBuildStatus(str(row["status"])),
        retry_count=int(row["retry_count"]),
        max_retries=int(row["max_retries"]),
        retry_after_at=row["retry_after_at"],
        terminal_reason=FallbackReason(str(reason_value)) if reason_value else None,
    )


async def request_feature_authority_build(
    session: AsyncSession,
    *,
    snapshot: SourceSnapshotResult,
    reason: FallbackReason,
    detail: str,
    retry_delay_seconds: int = DEFAULT_AUTHORITY_RETRY_DELAY_SECONDS,
    max_retries: int = DEFAULT_AUTHORITY_MAX_RETRIES,
) -> AuthorityBuildRequestResult:
    """Create or update the source-snapshot-scoped authority-build request."""

    result = await session.execute(
        text(UPSERT_AUTHORITY_BUILD_REQUEST_SQL),
        {
            "tenant_id": str(snapshot.tenant_id),
            "model_type": snapshot.model_type,
            "model_version": snapshot.model_version,
            "source_window_start": snapshot.source_window_start,
            "source_window_end": snapshot.source_window_end,
            "source_snapshot_hash": snapshot.source_snapshot_hash,
            "authority_reason": reason.value,
            "detail": detail[:512],
            "retry_delay_seconds": max(1, int(retry_delay_seconds)),
            "max_retries": max(1, int(max_retries)),
            "policy_version": AUTHORITY_LIVENESS_POLICY_VERSION,
        },
    )
    return _request_result_from_row(dict(result.mappings().one()))


async def reactivate_planner_for_feature_authority(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
) -> int:
    """Idempotently append one pending dirty event when authority becomes fresh."""

    result = await session.execute(
        text(REACTIVATE_PLANNER_FOR_AUTHORITY_SQL),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "source_snapshot_hash": source_snapshot_hash,
        },
    )
    return int(result.scalar_one() or 0)


async def sweep_authority_waiting_requests(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    limit: int = 100,
) -> tuple[int, int]:
    """Bounded sweeper hook for retry-ready and timeout authority requests."""

    result = await session.execute(
        text(SWEEP_AUTHORITY_WAITING_REQUESTS_SQL),
        {"tenant_id": str(tenant_id), "limit": max(1, int(limit))},
    )
    row = result.mappings().one()
    return int(row["retry_ready_count"]), int(row["timeout_count"])


async def mark_feature_authority_build_failed(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    detail: str | None = None,
) -> bool:
    """Terminalize a requested authority build with an explicit failure reason."""

    result = await session.execute(
        text(MARK_AUTHORITY_BUILD_FAILED_SQL),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "source_snapshot_hash": source_snapshot_hash,
            "detail": detail[:512] if detail else None,
        },
    )
    return result.scalar_one_or_none() is not None
