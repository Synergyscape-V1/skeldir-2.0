"""B2.4-P3 transactional dispatch outbox."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Callable
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.dispatch_authority import (
    BAYESIAN_FIT_EXECUTION_TASK,
    dispatch_payload_hash,
)
from app.celery_app import celery_app
from app.core.queues import QUEUE_BAYESIAN


DEFAULT_DISPATCH_BATCH_SIZE = 25
DEFAULT_STALE_DISPATCHING_SECONDS = 300
DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS = 300


class DispatchStatus(StrEnum):
    PENDING = "pending"
    DISPATCHING = "dispatching"
    DISPATCHED = "dispatched"
    LEASED = "leased"
    RUNNING = "running"
    FAILED_RETRYABLE = "failed_retryable"
    COMPLETED = "completed"
    FAILED_TERMINAL = "failed_terminal"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    SUPERSEDED = "superseded"
    QUARANTINED = "quarantined"
    DEAD_LETTERED = "dead_lettered"
    STALE_RECOVERED = "stale_recovered"


@dataclass(frozen=True)
class DispatchOutboxRow:
    id: UUID
    tenant_id: UUID
    fit_id: UUID
    task_name: str
    attempt_id: UUID
    payload_hash: str
    recovery_generation: int
    assigned_worker_generation: str
    attempt_count: int
    max_attempts: int

    @property
    def queue_payload(self) -> dict[str, str]:
        return {
            "dispatch_id": str(self.id),
            "fit_id": str(self.fit_id),
            "task_name": self.task_name,
            "attempt_id": str(self.attempt_id),
            "payload_hash": self.payload_hash,
            "recovery_generation": str(self.recovery_generation),
        }


@dataclass(frozen=True)
class RecoveryOutboxRow:
    id: UUID
    tenant_id: UUID
    dispatch_id: UUID
    fit_id: UUID
    task_name: str
    attempt_id: UUID
    payload_hash: str
    recovery_generation: int
    publish_attempt_count: int
    published_task_id: str | None = None

    @property
    def queue_payload(self) -> dict[str, str]:
        return {
            "dispatch_id": str(self.dispatch_id),
            "fit_id": str(self.fit_id),
            "task_name": self.task_name,
            "attempt_id": str(self.attempt_id),
            "payload_hash": self.payload_hash,
            "recovery_generation": str(self.recovery_generation),
        }


def publish_secret_free_dispatch(row: DispatchOutboxRow) -> str:
    """Publish a broker wake-up whose possession cannot authorize execution."""

    result = celery_app.send_task(
        BAYESIAN_FIT_EXECUTION_TASK,
        kwargs=row.queue_payload,
        queue=QUEUE_BAYESIAN,
        routing_key=f"{QUEUE_BAYESIAN}.task",
    )
    return str(result.id)


publish_capability_bound_dispatch = publish_secret_free_dispatch


def publish_secret_free_recovery(row: RecoveryOutboxRow) -> str:
    """Republish a durable recovery wake-up without broker-carried authority."""

    result = celery_app.send_task(
        BAYESIAN_FIT_EXECUTION_TASK,
        kwargs=row.queue_payload,
        queue=QUEUE_BAYESIAN,
        routing_key=f"{QUEUE_BAYESIAN}.task",
    )
    return str(result.id)


async def recover_stale_dispatching(
    session: AsyncSession,
    *,
    stale_after_seconds: int = DEFAULT_STALE_DISPATCHING_SECONDS,
) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=max(1, stale_after_seconds))
    result = await session.execute(
        text(
            """
            UPDATE public.b24_fit_dispatch_outbox
            SET status = 'stale_recovered',
                stale_recovered_at = now(),
                next_attempt_at = now(),
                updated_at = now()
            WHERE status = 'dispatching'
              AND dispatching_started_at < :cutoff
            """
        ),
        {"cutoff": cutoff},
    )
    return int(result.rowcount or 0)


_LEASE_DUE_DISPATCH_SQL = """
            WITH due AS (
                SELECT tenant_id, id
                FROM public.b24_fit_dispatch_outbox
                WHERE status IN ('pending', 'failed_retryable', 'stale_recovered')
                  AND next_attempt_at <= now()
                ORDER BY next_attempt_at ASC, id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            ),
            live_generation AS (
                SELECT public.b24_next_active_worker_generation() AS generation_id
            )
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'dispatching',
                dispatching_started_at = now(),
                last_attempt_at = now(),
                attempt_count = attempt_count + 1,
                task_name = COALESCE(task_name, :task_name),
                attempt_id = COALESCE(attempt_id, gen_random_uuid()),
                payload_hash = COALESCE(
                    payload_hash,
                    public.b24_sha256_text(:task_name || ':' || outbox.fit_id::text)
                ),
                claim_capability = NULL,
                claim_capability_digest = NULL,
                claim_capability_expires_at = NULL,
                assigned_worker_generation = live_generation.generation_id,
                assignment_generation = assignment_generation + 1,
                assignment_expires_at = now() + interval '10 minutes',
                assignment_reason = 'initial_dispatch',
                updated_at = now()
            FROM due, live_generation
            WHERE outbox.tenant_id = due.tenant_id
              AND outbox.id = due.id
              AND live_generation.generation_id IS NOT NULL
            RETURNING
                outbox.id,
                outbox.tenant_id,
                outbox.fit_id,
                outbox.task_name,
                outbox.attempt_id,
                outbox.payload_hash,
                outbox.recovery_generation,
                outbox.assigned_worker_generation,
                outbox.attempt_count,
                outbox.max_attempts
            """


async def _bind_initial_dispatch_publisher(session: AsyncSession) -> None:
    await session.execute(
        text("SELECT set_config('app.b24_initial_dispatch_publisher', 'on', true)")
    )


def _bind_initial_dispatch_publisher_sync(conn) -> None:
    conn.execute(
        text("SELECT set_config('app.b24_initial_dispatch_publisher', 'on', true)")
    )


async def lease_due_dispatch_rows(
    session: AsyncSession,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> list[DispatchOutboxRow]:
    await _bind_initial_dispatch_publisher(session)
    result = await session.execute(
        text(_LEASE_DUE_DISPATCH_SQL),
        {
            "batch_size": max(1, int(batch_size)),
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
        },
    )
    return [
        DispatchOutboxRow(
            id=row["id"],
            tenant_id=row["tenant_id"],
            fit_id=row["fit_id"],
            task_name=str(row["task_name"] or BAYESIAN_FIT_EXECUTION_TASK),
            attempt_id=row["attempt_id"],
            payload_hash=str(
                row["payload_hash"] or dispatch_payload_hash(fit_id=row["fit_id"])
            ),
            recovery_generation=int(row["recovery_generation"] or 0),
            assigned_worker_generation=str(row["assigned_worker_generation"]),
            attempt_count=int(row["attempt_count"]),
            max_attempts=int(row["max_attempts"]),
        )
        for row in result.mappings()
    ]


_MARK_DISPATCHED_SQL = """
            UPDATE public.b24_fit_dispatch_outbox
            SET status = 'dispatched',
                dispatched_at = now(),
                last_error = NULL,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :outbox_id
            """


async def mark_dispatched(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    outbox_id: UUID,
) -> None:
    await session.execute(
        text(_MARK_DISPATCHED_SQL),
        {"tenant_id": str(tenant_id), "outbox_id": str(outbox_id)},
    )


_MARK_DISPATCH_FAILED_SQL = """
            UPDATE public.b24_fit_dispatch_outbox
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


async def mark_dispatch_failed(
    session: AsyncSession,
    *,
    row: DispatchOutboxRow,
    error: str,
    retry_delay_seconds: int = 60,
) -> None:
    dead_letter = row.attempt_count >= row.max_attempts
    await session.execute(
        text(_MARK_DISPATCH_FAILED_SQL),
        {
            "tenant_id": str(row.tenant_id),
            "outbox_id": str(row.id),
            "status": (
                DispatchStatus.DEAD_LETTERED.value
                if dead_letter
                else DispatchStatus.FAILED_RETRYABLE.value
            ),
            "dead_letter": dead_letter,
            "retry_delay_seconds": max(1, int(retry_delay_seconds)),
            "error": error[:2048],
        },
    )


async def dispatch_due_outbox_rows(
    session: AsyncSession,
    *,
    publish: Callable[[DispatchOutboxRow], str] = publish_capability_bound_dispatch,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> list[DispatchOutboxRow]:
    """Publish due rows after they have been durably leased with SKIP LOCKED."""

    rows = await lease_due_dispatch_rows(session, batch_size=batch_size)
    for row in rows:
        try:
            publish(row)
        except Exception as exc:
            await mark_dispatch_failed(session, row=row, error=str(exc))
            continue
        await mark_dispatched(session, tenant_id=row.tenant_id, outbox_id=row.id)
    return rows


# ---------------------------------------------------------------------------
# Fast-path publication, synchronous.
#
# `dispatch_due_outbox_rows` above has been present and correct for as long as
# this module has, and had no caller anywhere in the application: no Beat entry,
# no task, no production call site. A freshly claimed fit therefore had no wired
# route to a worker at all. The only publication that ever ran was the recovery
# reconciler's sweep of rows that had already gone stale -- a repair mechanism
# carrying the primary path, with the delay and attempt-count semantics of a
# repair rather than of a dispatch.
#
# These mirror the async functions above and reuse their exact SQL, because the
# Celery worker lane runs on a synchronous engine and an independently written
# publisher would be a second design free to drift from the first.
# ---------------------------------------------------------------------------


def lease_due_dispatch_rows_sync(
    conn,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> list[DispatchOutboxRow]:
    """Durably lease due dispatch rows with SKIP LOCKED, on a sync connection."""

    _bind_initial_dispatch_publisher_sync(conn)
    result = conn.execute(
        text(_LEASE_DUE_DISPATCH_SQL),
        {
            "batch_size": max(1, int(batch_size)),
            "task_name": BAYESIAN_FIT_EXECUTION_TASK,
        },
    )
    return [
        DispatchOutboxRow(
            id=row["id"],
            tenant_id=row["tenant_id"],
            fit_id=row["fit_id"],
            task_name=str(row["task_name"] or BAYESIAN_FIT_EXECUTION_TASK),
            attempt_id=row["attempt_id"],
            payload_hash=str(
                row["payload_hash"] or dispatch_payload_hash(fit_id=row["fit_id"])
            ),
            recovery_generation=int(row["recovery_generation"] or 0),
            assigned_worker_generation=str(row["assigned_worker_generation"]),
            attempt_count=int(row["attempt_count"]),
            max_attempts=int(row["max_attempts"]),
        )
        for row in result.mappings()
    ]


def mark_dispatched_sync(conn, *, tenant_id: UUID, outbox_id: UUID) -> None:
    conn.execute(
        text(_MARK_DISPATCHED_SQL),
        {"tenant_id": str(tenant_id), "outbox_id": str(outbox_id)},
    )


def mark_dispatch_failed_sync(
    conn,
    *,
    row: DispatchOutboxRow,
    error: str,
    retry_delay_seconds: int = 60,
) -> None:
    dead_letter = row.attempt_count >= row.max_attempts
    conn.execute(
        text(_MARK_DISPATCH_FAILED_SQL),
        {
            "tenant_id": str(row.tenant_id),
            "outbox_id": str(row.id),
            "status": (
                DispatchStatus.DEAD_LETTERED.value
                if dead_letter
                else DispatchStatus.FAILED_RETRYABLE.value
            ),
            "dead_letter": dead_letter,
            "retry_delay_seconds": max(1, int(retry_delay_seconds)),
            "error": error[:2048],
        },
    )


def publish_due_dispatch_rows_sync(
    conn,
    *,
    publish: Callable[[DispatchOutboxRow], str] = publish_capability_bound_dispatch,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> list[DispatchOutboxRow]:
    """Lease, then publish, the initial broker wake-up for fresh dispatches.

    Identical task name, queue, payload shape and capability semantics as the
    recovery republisher: possession of what crosses the broker still authorises
    nothing, and the worker must lease the row to execute. The only differences
    are which rows are eligible and the assignment reason recorded against them.
    """

    rows = lease_due_dispatch_rows_sync(conn, batch_size=batch_size)
    published: list[DispatchOutboxRow] = []
    for row in rows:
        try:
            publish(row)
        except Exception as exc:  # noqa: BLE001 - the failure is recorded, not raised
            mark_dispatch_failed_sync(conn, row=row, error=str(exc))
            continue
        mark_dispatched_sync(conn, tenant_id=row.tenant_id, outbox_id=row.id)
        published.append(row)
    return published


async def create_recovery_wakeups(
    session: AsyncSession,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> int:
    result = await session.execute(
        text("SELECT public.b24_create_fit_recovery_wakeups(:batch_size)"),
        {"batch_size": max(1, int(batch_size))},
    )
    return int(result.scalar_one())


async def lease_due_recovery_rows(
    session: AsyncSession,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
    stale_publishing_seconds: int = DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS,
) -> list[RecoveryOutboxRow]:
    await session.execute(
        text(
            """
            SELECT
                set_config('app.b24_recovery_reconciler', 'on', true),
                set_config('app.b24_dispatch_claim_access', 'on', true)
            """
        )
    )
    result = await session.execute(
        text(
            """
            WITH due AS (
                SELECT tenant_id, id, dispatch_id
                FROM public.b24_fit_recovery_outbox
                WHERE (
                    status IN ('pending', 'failed_retryable')
                    OR (
                        status = 'publishing'
                        AND updated_at <= now() - (:stale_publishing_seconds * interval '1 second')
                    )
                )
                ORDER BY created_at ASC, id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            ),
            assigned AS (
                UPDATE public.b24_fit_dispatch_outbox outbox
                SET status = 'dispatching',
                    assigned_worker_generation = NULL,
                    assignment_generation = assignment_generation + 1,
                    assignment_expires_at = now() + interval '10 minutes',
                    assignment_reason = 'recovery_shared_eligible',
                    dispatching_started_at = now(),
                    updated_at = now()
                FROM due
                WHERE outbox.tenant_id = due.tenant_id
                  AND outbox.id = due.dispatch_id
                RETURNING
                    outbox.tenant_id,
                    outbox.id AS dispatch_id,
                    outbox.fit_id,
                    outbox.task_name,
                    outbox.attempt_id,
                    outbox.payload_hash,
                    outbox.recovery_generation
            )
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'publishing',
                publish_attempt_count = publish_attempt_count + 1,
                updated_at = now()
            FROM due
            JOIN assigned
              ON assigned.tenant_id = due.tenant_id
             AND assigned.dispatch_id = due.dispatch_id
            WHERE recovery.tenant_id = due.tenant_id
              AND recovery.id = due.id
            RETURNING
                recovery.id,
                recovery.tenant_id,
                recovery.dispatch_id,
                assigned.fit_id,
                assigned.task_name,
                assigned.attempt_id,
                assigned.payload_hash,
                assigned.recovery_generation,
                recovery.publish_attempt_count
            """
        ),
        {
            "batch_size": max(1, int(batch_size)),
            "stale_publishing_seconds": max(1, int(stale_publishing_seconds)),
        },
    )
    return [
        RecoveryOutboxRow(
            id=row["id"],
            tenant_id=row["tenant_id"],
            dispatch_id=row["dispatch_id"],
            fit_id=row["fit_id"],
            task_name=str(row["task_name"]),
            attempt_id=row["attempt_id"],
            payload_hash=str(row["payload_hash"]),
            recovery_generation=int(row["recovery_generation"]),
            publish_attempt_count=int(row["publish_attempt_count"]),
        )
        for row in result.mappings()
    ]


async def mark_recovery_published(
    session: AsyncSession,
    *,
    row: RecoveryOutboxRow,
) -> None:
    await session.execute(
        text(
            """
            UPDATE public.b24_fit_recovery_outbox
            SET status = 'published',
                published_at = now(),
                updated_at = now(),
                last_error = NULL
            WHERE tenant_id = :tenant_id
              AND id = :id;
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "id": str(row.id),
        },
    )
    await session.execute(
        text(
            """
            UPDATE public.b24_fit_dispatch_outbox
            SET status = 'dispatched',
                dispatched_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :dispatch_id;
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "id": str(row.id),
            "dispatch_id": str(row.dispatch_id),
        },
    )


async def mark_recovery_publish_failed(
    session: AsyncSession,
    *,
    row: RecoveryOutboxRow,
    error: str,
    max_attempts: int = 5,
) -> None:
    await session.execute(
        text(
            """
            UPDATE public.b24_fit_recovery_outbox
            SET status = CASE
                    WHEN publish_attempt_count >= :max_attempts THEN 'quarantined'
                    ELSE 'failed_retryable'
                END,
                last_error = :error,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :id
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "id": str(row.id),
            "max_attempts": max(1, int(max_attempts)),
            "error": error[:2048],
        },
    )


async def publish_due_recovery_rows(
    session: AsyncSession,
    *,
    publish: Callable[[RecoveryOutboxRow], str] = publish_secret_free_recovery,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
    stale_publishing_seconds: int = DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS,
) -> list[RecoveryOutboxRow]:
    rows = await lease_due_recovery_rows(
        session,
        batch_size=batch_size,
        stale_publishing_seconds=stale_publishing_seconds,
    )
    attempted_rows: list[RecoveryOutboxRow] = []
    for row in rows:
        try:
            published_task_id = publish(row)
        except Exception as exc:
            await mark_recovery_publish_failed(session, row=row, error=str(exc))
            attempted_rows.append(row)
            continue
        await mark_recovery_published(session, row=row)
        attempted_rows.append(replace(row, published_task_id=published_task_id))
    return attempted_rows


def lease_due_recovery_rows_sync(
    conn,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
    stale_publishing_seconds: int = DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS,
) -> list[RecoveryOutboxRow]:
    conn.execute(
        text(
            """
            SELECT
                set_config('app.b24_recovery_reconciler', 'on', true),
                set_config('app.b24_dispatch_claim_access', 'on', true)
            """
        )
    )
    result = conn.execute(
        text(
            """
            WITH due AS (
                SELECT tenant_id, id, dispatch_id
                FROM public.b24_fit_recovery_outbox
                WHERE (
                    status IN ('pending', 'failed_retryable')
                    OR (
                        status = 'publishing'
                        AND updated_at <= now() - (:stale_publishing_seconds * interval '1 second')
                    )
                )
                ORDER BY created_at ASC, id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            ),
            assigned AS (
                UPDATE public.b24_fit_dispatch_outbox outbox
                SET status = 'dispatching',
                    assigned_worker_generation = NULL,
                    assignment_generation = assignment_generation + 1,
                    assignment_expires_at = now() + interval '10 minutes',
                    assignment_reason = 'recovery_shared_eligible',
                    dispatching_started_at = now(),
                    updated_at = now()
                FROM due
                WHERE outbox.tenant_id = due.tenant_id
                  AND outbox.id = due.dispatch_id
                RETURNING
                    outbox.tenant_id,
                    outbox.id AS dispatch_id,
                    outbox.fit_id,
                    outbox.task_name,
                    outbox.attempt_id,
                    outbox.payload_hash,
                    outbox.recovery_generation
            )
            UPDATE public.b24_fit_recovery_outbox recovery
            SET status = 'publishing',
                publish_attempt_count = publish_attempt_count + 1,
                updated_at = now()
            FROM due
            JOIN assigned
              ON assigned.tenant_id = due.tenant_id
             AND assigned.dispatch_id = due.dispatch_id
            WHERE recovery.tenant_id = due.tenant_id
              AND recovery.id = due.id
            RETURNING
                recovery.id,
                recovery.tenant_id,
                recovery.dispatch_id,
                assigned.fit_id,
                assigned.task_name,
                assigned.attempt_id,
                assigned.payload_hash,
                assigned.recovery_generation,
                recovery.publish_attempt_count
            """
        ),
        {
            "batch_size": max(1, int(batch_size)),
            "stale_publishing_seconds": max(1, int(stale_publishing_seconds)),
        },
    )
    return [
        RecoveryOutboxRow(
            id=row["id"],
            tenant_id=row["tenant_id"],
            dispatch_id=row["dispatch_id"],
            fit_id=row["fit_id"],
            task_name=str(row["task_name"]),
            attempt_id=row["attempt_id"],
            payload_hash=str(row["payload_hash"]),
            recovery_generation=int(row["recovery_generation"]),
            publish_attempt_count=int(row["publish_attempt_count"]),
        )
        for row in result.mappings()
    ]


def mark_recovery_published_sync(conn, *, row: RecoveryOutboxRow) -> None:
    conn.execute(
        text(
            """
            UPDATE public.b24_fit_recovery_outbox
            SET status = 'published',
                published_at = now(),
                updated_at = now(),
                last_error = NULL
            WHERE tenant_id = :tenant_id
              AND id = :id;
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "id": str(row.id),
        },
    )
    conn.execute(
        text(
            """
            UPDATE public.b24_fit_dispatch_outbox
            SET status = 'dispatched',
                dispatched_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :dispatch_id;
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "dispatch_id": str(row.dispatch_id),
        },
    )


def mark_recovery_publish_failed_sync(
    conn,
    *,
    row: RecoveryOutboxRow,
    error: str,
    max_attempts: int = 5,
) -> None:
    conn.execute(
        text(
            """
            UPDATE public.b24_fit_recovery_outbox
            SET status = CASE
                    WHEN publish_attempt_count >= :max_attempts THEN 'quarantined'
                    ELSE 'failed_retryable'
                END,
                last_error = :error,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :id
            """
        ),
        {
            "tenant_id": str(row.tenant_id),
            "id": str(row.id),
            "max_attempts": max(1, int(max_attempts)),
            "error": error[:2048],
        },
    )


def publish_due_recovery_rows_sync(
    conn,
    *,
    publish: Callable[[RecoveryOutboxRow], str] = publish_secret_free_recovery,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
    stale_publishing_seconds: int = DEFAULT_STALE_RECOVERY_PUBLISHING_SECONDS,
) -> list[RecoveryOutboxRow]:
    rows = lease_due_recovery_rows_sync(
        conn,
        batch_size=batch_size,
        stale_publishing_seconds=stale_publishing_seconds,
    )
    attempted_rows: list[RecoveryOutboxRow] = []
    for row in rows:
        try:
            published_task_id = publish(row)
        except Exception as exc:
            mark_recovery_publish_failed_sync(conn, row=row, error=str(exc))
            attempted_rows.append(row)
            continue
        mark_recovery_published_sync(conn, row=row)
        attempted_rows.append(replace(row, published_task_id=published_task_id))
    return attempted_rows
