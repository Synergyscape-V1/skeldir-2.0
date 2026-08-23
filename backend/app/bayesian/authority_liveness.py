"""Transient liveness controls for B2.4-P4 feature authority readiness."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Callable
from uuid import UUID

from sqlalchemy import event
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session as SyncSession

from app.celery_app import celery_app
from app.bayesian.enums import FallbackReason
from app.bayesian.source_snapshot import SourceSnapshotResult
from app.core.queues import QUEUE_BAYESIAN


logger = logging.getLogger(__name__)

AUTHORITY_LIVENESS_POLICY_VERSION = "b24-p4-authority-liveness-v1"
FEATURE_AUTHORITY_BUILD_TASK = "app.tasks.bayesian.build_feature_authority"
FEATURE_AUTHORITY_DISPATCH_TASK = "app.tasks.bayesian.dispatch_feature_authority_build"
DEFAULT_AUTHORITY_RETRY_DELAY_SECONDS = 60
DEFAULT_AUTHORITY_MAX_RETRIES = 5
DEFAULT_AUTHORITY_BUILD_DISPATCH_BATCH_SIZE = 25
NORMAL_DISPATCH_DEADLINE_MS = 5_000
RECOVERY_ORPHAN_THRESHOLD_MS = 60_000
MAX_DISPATCH_ATTEMPTS = 5
DISPATCH_RETRY_BACKOFF_MS = 30_000
POST_COMMIT_DISPATCH_SESSION_KEY = "b24_feature_authority_post_commit_dispatches"
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
    #: The request named a source snapshot that no longer exists. Distinct from
    #: BUILD_FAILED on purpose: nothing failed, and distinct from TIMEOUT on
    #: purpose: no amount of further waiting can help. Conflating "not yet" with
    #: "never again" is what made obsolete requests retry forever.
    SUPERSEDED = "authority_superseded"


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
    dispatch_key: str


@dataclass(frozen=True)
class AuthorityBuildDispatchRow:
    id: UUID
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    attempt_count: int
    max_attempts: int

    @property
    def queue_payload(self) -> dict[str, str]:
        return {
            "tenant_id": str(self.tenant_id),
            "model_type": self.model_type,
            "model_version": self.model_version,
            "source_window_start": self.source_window_start.isoformat(),
            "source_window_end": self.source_window_end.isoformat(),
            "source_snapshot_hash": self.source_snapshot_hash,
        }


UPSERT_AUTHORITY_BUILD_REQUEST_SQL = """
WITH upserted_request AS (
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
),
queued_dispatch AS (
    INSERT INTO public.b24_feature_authority_build_outbox (
        tenant_id,
        model_type,
        model_version,
        source_window_start,
        source_window_end,
        source_snapshot_hash,
        dispatch_key,
        status,
        attempt_count,
        max_attempts,
        next_attempt_at,
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
        'b24-feature-authority-build:' || tenant_id::text || ':' || source_snapshot_hash,
        'pending',
        0,
        5,
        now(),
        now(),
        now()
    FROM upserted_request
    WHERE status IN ('authority_build_requested', 'authority_waiting')
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
            WHEN b24_feature_authority_build_outbox.status IN (
                'dispatched',
                'dead_lettered'
            )
                THEN b24_feature_authority_build_outbox.status
            ELSE 'pending'
        END,
        next_attempt_at = CASE
            WHEN b24_feature_authority_build_outbox.status IN (
                'dispatched',
                'dead_lettered'
            )
                THEN b24_feature_authority_build_outbox.next_attempt_at
            ELSE now()
        END,
        updated_at = now()
    RETURNING id
)
SELECT
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
    terminal_reason,
    'b24-feature-authority-build:' || tenant_id::text || ':' || source_snapshot_hash AS dispatch_key
FROM upserted_request
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


LEASE_AUTHORITY_BUILD_OUTBOX_SQL = """
WITH due AS (
    SELECT tenant_id, id
    FROM public.b24_feature_authority_build_outbox
    WHERE status IN ('pending', 'failed_retryable', 'stale_recovered')
      AND next_attempt_at <= now()
      AND (
          status IN ('failed_retryable', 'stale_recovered')
          OR created_at <= now() - (:recovery_orphan_threshold_ms * interval '1 millisecond')
      )
    ORDER BY next_attempt_at ASC, id ASC
    LIMIT :batch_size
    FOR UPDATE SKIP LOCKED
)
UPDATE public.b24_feature_authority_build_outbox outbox
SET status = 'dispatching',
    dispatching_started_at = now(),
    last_attempt_at = now(),
    attempt_count = attempt_count + 1,
    updated_at = now()
FROM due
WHERE outbox.tenant_id = due.tenant_id
  AND outbox.id = due.id
RETURNING
    outbox.id,
    outbox.tenant_id,
    outbox.model_type,
    outbox.model_version,
    outbox.source_window_start,
    outbox.source_window_end,
    outbox.source_snapshot_hash,
    outbox.attempt_count,
    outbox.max_attempts
"""


LEASE_AUTHORITY_BUILD_OUTBOX_BY_DISPATCH_KEY_SQL = """
WITH due AS (
    SELECT tenant_id, id
    FROM public.b24_feature_authority_build_outbox
    WHERE tenant_id = :tenant_id
      AND dispatch_key = :dispatch_key
      AND status IN ('pending', 'failed_retryable', 'stale_recovered')
      AND next_attempt_at <= now()
    ORDER BY next_attempt_at ASC, id ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
)
UPDATE public.b24_feature_authority_build_outbox outbox
SET status = 'dispatching',
    dispatching_started_at = now(),
    last_attempt_at = now(),
    attempt_count = attempt_count + 1,
    updated_at = now()
FROM due
WHERE outbox.tenant_id = due.tenant_id
  AND outbox.id = due.id
RETURNING
    outbox.id,
    outbox.tenant_id,
    outbox.model_type,
    outbox.model_version,
    outbox.source_window_start,
    outbox.source_window_end,
    outbox.source_snapshot_hash,
    outbox.attempt_count,
    outbox.max_attempts
"""


MARK_AUTHORITY_BUILD_DISPATCHED_SQL = """
UPDATE public.b24_feature_authority_build_outbox
SET status = 'dispatched',
    dispatched_at = now(),
    last_error = NULL,
    updated_at = now()
WHERE tenant_id = :tenant_id
  AND id = :outbox_id
"""


MARK_AUTHORITY_BUILD_DISPATCH_FAILED_SQL = """
UPDATE public.b24_feature_authority_build_outbox
SET status = :status,
    next_attempt_at = CASE
        WHEN :dead_letter THEN next_attempt_at
        ELSE now() + (:retry_delay_seconds * interval '1 second')
    END,
    dead_lettered_at = CASE
        WHEN :dead_letter THEN now()
        ELSE dead_lettered_at
    END,
    last_error = :error,
    updated_at = now()
WHERE tenant_id = :tenant_id
  AND id = :outbox_id
"""


def _request_result_from_row(row: dict[str, object]) -> AuthorityBuildRequestResult:
    reason_value = row.get("terminal_reason")
    dispatch_key = row.get("dispatch_key") or (
        f"b24-feature-authority-build:{row['tenant_id']}:{row['source_snapshot_hash']}"
    )
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
        dispatch_key=str(dispatch_key),
    )


def _dispatch_row_from_mapping(row: dict[str, object]) -> AuthorityBuildDispatchRow:
    return AuthorityBuildDispatchRow(
        id=row["id"],
        tenant_id=row["tenant_id"],
        model_type=str(row["model_type"]),
        model_version=str(row["model_version"]),
        source_window_start=row["source_window_start"],
        source_window_end=row["source_window_end"],
        source_snapshot_hash=str(row["source_snapshot_hash"]),
        attempt_count=int(row["attempt_count"]),
        max_attempts=int(row["max_attempts"]),
    )


def publish_feature_authority_build(row: AuthorityBuildDispatchRow) -> str:
    """Publish the source-snapshot-scoped feature-authority build request."""

    result = celery_app.send_task(
        FEATURE_AUTHORITY_BUILD_TASK,
        kwargs=row.queue_payload,
        queue=QUEUE_BAYESIAN,
        routing_key=f"{QUEUE_BAYESIAN}.task",
    )
    return str(result.id)


def publish_feature_authority_dispatch(
    *, tenant_id: UUID, dispatch_key: str
) -> str:
    """Causally wake the active dispatcher for one committed authority-build row."""

    result = celery_app.send_task(
        FEATURE_AUTHORITY_DISPATCH_TASK,
        kwargs={"tenant_id": str(tenant_id), "dispatch_key": dispatch_key},
        queue=QUEUE_BAYESIAN,
        routing_key=f"{QUEUE_BAYESIAN}.task",
    )
    return str(result.id)


def _register_post_commit_authority_dispatch(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    dispatch_key: str,
) -> None:
    sync_session = getattr(session, "sync_session", None)
    if sync_session is None:
        return
    pending = sync_session.info.setdefault(
        POST_COMMIT_DISPATCH_SESSION_KEY, []
    )
    payload = (str(tenant_id), dispatch_key)
    if payload not in pending:
        pending.append(payload)


@event.listens_for(AsyncSession.sync_session_class, "after_commit")
def _publish_authority_dispatch_after_commit(session: SyncSession) -> None:
    pending = session.info.pop(POST_COMMIT_DISPATCH_SESSION_KEY, [])
    for tenant_id, dispatch_key in pending:
        try:
            publish_feature_authority_dispatch(
                tenant_id=UUID(str(tenant_id)),
                dispatch_key=str(dispatch_key),
            )
        except Exception:
            logger.exception(
                "b24_feature_authority_post_commit_dispatch_enqueue_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "dispatch_key": str(dispatch_key),
                },
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
    request = _request_result_from_row(dict(result.mappings().one()))
    if request.status in {
        AuthorityBuildStatus.BUILD_REQUESTED,
        AuthorityBuildStatus.WAITING,
    }:
        _register_post_commit_authority_dispatch(
            session, tenant_id=request.tenant_id, dispatch_key=request.dispatch_key
        )
    return request


async def request_feature_authority_build_for_hash(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    reason: FallbackReason,
    detail: str,
    retry_delay_seconds: int = DEFAULT_AUTHORITY_RETRY_DELAY_SECONDS,
    max_retries: int = DEFAULT_AUTHORITY_MAX_RETRIES,
) -> AuthorityBuildRequestResult:
    """Create build intent when frozen Hash A is known before latest P2 recompute."""

    result = await session.execute(
        text(UPSERT_AUTHORITY_BUILD_REQUEST_SQL),
        {
            "tenant_id": str(tenant_id),
            "model_type": model_type,
            "model_version": model_version,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "source_snapshot_hash": source_snapshot_hash,
            "authority_reason": reason.value,
            "detail": detail[:512],
            "retry_delay_seconds": max(1, int(retry_delay_seconds)),
            "max_retries": max(1, int(max_retries)),
            "policy_version": AUTHORITY_LIVENESS_POLICY_VERSION,
        },
    )
    request = _request_result_from_row(dict(result.mappings().one()))
    if request.status in {
        AuthorityBuildStatus.BUILD_REQUESTED,
        AuthorityBuildStatus.WAITING,
    }:
        _register_post_commit_authority_dispatch(
            session, tenant_id=request.tenant_id, dispatch_key=request.dispatch_key
        )
    return request


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


async def lease_due_feature_authority_build_dispatches(
    session: AsyncSession,
    *,
    batch_size: int = DEFAULT_AUTHORITY_BUILD_DISPATCH_BATCH_SIZE,
) -> list[AuthorityBuildDispatchRow]:
    """Lease bounded due build-dispatch rows with SKIP LOCKED."""

    result = await session.execute(
        text(LEASE_AUTHORITY_BUILD_OUTBOX_SQL),
        {
            "batch_size": max(1, int(batch_size)),
            "recovery_orphan_threshold_ms": RECOVERY_ORPHAN_THRESHOLD_MS,
        },
    )
    return [_dispatch_row_from_mapping(dict(row)) for row in result.mappings()]


async def lease_feature_authority_build_dispatch_by_key(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    dispatch_key: str,
) -> AuthorityBuildDispatchRow | None:
    """Lease one causally triggered outbox row without waiting for sweeper age."""

    result = await session.execute(
        text(LEASE_AUTHORITY_BUILD_OUTBOX_BY_DISPATCH_KEY_SQL),
        {"tenant_id": str(tenant_id), "dispatch_key": dispatch_key},
    )
    row = result.mappings().one_or_none()
    return _dispatch_row_from_mapping(dict(row)) if row is not None else None


async def mark_feature_authority_build_dispatched(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    outbox_id: UUID,
) -> None:
    await session.execute(
        text(MARK_AUTHORITY_BUILD_DISPATCHED_SQL),
        {"tenant_id": str(tenant_id), "outbox_id": str(outbox_id)},
    )


async def mark_feature_authority_build_dispatch_failed(
    session: AsyncSession,
    *,
    row: AuthorityBuildDispatchRow,
    error: str,
    retry_delay_seconds: int = DEFAULT_AUTHORITY_RETRY_DELAY_SECONDS,
) -> None:
    dead_letter = row.attempt_count >= row.max_attempts
    await session.execute(
        text(MARK_AUTHORITY_BUILD_DISPATCH_FAILED_SQL),
        {
            "tenant_id": str(row.tenant_id),
            "outbox_id": str(row.id),
            "status": "dead_lettered" if dead_letter else "failed_retryable",
            "dead_letter": dead_letter,
            "retry_delay_seconds": max(1, int(retry_delay_seconds)),
            "error": error[:2048],
        },
    )


async def dispatch_due_feature_authority_builds(
    session: AsyncSession,
    *,
    publish: Callable[
        [AuthorityBuildDispatchRow], str
    ] = publish_feature_authority_build,
    batch_size: int = DEFAULT_AUTHORITY_BUILD_DISPATCH_BATCH_SIZE,
) -> list[AuthorityBuildDispatchRow]:
    """Recovery-only sweeper for orphaned or retry-due authority-build dispatches."""

    rows = await lease_due_feature_authority_build_dispatches(
        session, batch_size=batch_size
    )
    for row in rows:
        try:
            publish(row)
        except Exception as exc:
            await mark_feature_authority_build_dispatch_failed(
                session, row=row, error=str(exc)
            )
            continue
        await mark_feature_authority_build_dispatched(
            session, tenant_id=row.tenant_id, outbox_id=row.id
        )
    return rows


async def dispatch_feature_authority_build_by_key(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    dispatch_key: str,
    publish: Callable[
        [AuthorityBuildDispatchRow], str
    ] = publish_feature_authority_build,
) -> AuthorityBuildDispatchRow | None:
    """Publish one post-commit-triggered authority-build row by dispatch key."""

    row = await lease_feature_authority_build_dispatch_by_key(
        session, tenant_id=tenant_id, dispatch_key=dispatch_key
    )
    if row is None:
        return None
    try:
        publish(row)
    except Exception as exc:
        await mark_feature_authority_build_dispatch_failed(
            session, row=row, error=str(exc)
        )
        return row
    await mark_feature_authority_build_dispatched(
        session, tenant_id=row.tenant_id, outbox_id=row.id
    )
    return row
