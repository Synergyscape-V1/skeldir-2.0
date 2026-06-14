"""B2.4-P3 transactional dispatch outbox."""

from __future__ import annotations

from dataclasses import dataclass
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
    claim_capability: str
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
            "claim_capability": self.claim_capability,
        }


def publish_capability_bound_dispatch(row: DispatchOutboxRow) -> str:
    """Publish a broker wake-up whose execution authority is DB-bound."""

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


async def lease_due_dispatch_rows(
    session: AsyncSession,
    *,
    batch_size: int = DEFAULT_DISPATCH_BATCH_SIZE,
) -> list[DispatchOutboxRow]:
    result = await session.execute(
        text(
            """
            WITH due AS (
                SELECT tenant_id, id
                FROM public.b24_fit_dispatch_outbox
                WHERE status IN ('pending', 'failed_retryable', 'stale_recovered')
                  AND next_attempt_at <= now()
                ORDER BY next_attempt_at ASC, id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
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
                claim_capability = COALESCE(claim_capability, encode(gen_random_bytes(32), 'hex')),
                claim_capability_digest = COALESCE(
                    claim_capability_digest,
                    public.b24_sha256_text(claim_capability)
                ),
                claim_capability_expires_at = COALESCE(
                    claim_capability_expires_at,
                    now() + interval '24 hours'
                ),
                updated_at = now()
            FROM due
            WHERE outbox.tenant_id = due.tenant_id
              AND outbox.id = due.id
            RETURNING
                outbox.id,
                outbox.tenant_id,
                outbox.fit_id,
                outbox.task_name,
                outbox.attempt_id,
                outbox.payload_hash,
                outbox.claim_capability,
                outbox.attempt_count,
                outbox.max_attempts
            """
        ),
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
            claim_capability=str(row["claim_capability"]),
            attempt_count=int(row["attempt_count"]),
            max_attempts=int(row["max_attempts"]),
        )
        for row in result.mappings()
    ]


async def mark_dispatched(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    outbox_id: UUID,
) -> None:
    await session.execute(
        text(
            """
            UPDATE public.b24_fit_dispatch_outbox
            SET status = 'dispatched',
                dispatched_at = now(),
                last_error = NULL,
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND id = :outbox_id
            """
        ),
        {"tenant_id": str(tenant_id), "outbox_id": str(outbox_id)},
    )


async def mark_dispatch_failed(
    session: AsyncSession,
    *,
    row: DispatchOutboxRow,
    error: str,
    retry_delay_seconds: int = 60,
) -> None:
    dead_letter = row.attempt_count >= row.max_attempts
    await session.execute(
        text(
            """
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
        ),
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
