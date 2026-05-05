"""B2.3-P3 Postgres-native verdict state transitions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .timing_constants import PROVISIONAL_MATCH_WINDOW, WEBHOOK_ARRIVAL_WINDOW


B23_P3_TRANSITION_SWEEP_CADENCE: timedelta = timedelta(minutes=5)
B23_P3_TRANSITION_BATCH_SIZE = 500


@dataclass(frozen=True)
class B23TransitionResult:
    transitioned_count: int
    transition_name: str
    cadence_seconds: int


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def transition_stale_pending_to_unmatched(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    now_utc: datetime,
    batch_size: int = B23_P3_TRANSITION_BATCH_SIZE,
) -> B23TransitionResult:
    normalized_now = _normalize_utc(now_utc)
    stale_before = normalized_now - WEBHOOK_ARRIVAL_WINDOW
    result = await session.execute(
        text(
            """
            WITH claimed AS (
                SELECT id
                FROM b23_match_verdicts
                WHERE tenant_id = :tenant_id
                  AND status = 'pending'
                  AND pending_since <= :stale_before
                ORDER BY pending_since ASC, id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            UPDATE b23_match_verdicts target
            SET
                status = 'unmatched',
                unmatched_marked_at = :transitioned_at,
                last_transition_at = :transitioned_at,
                updated_at = :transitioned_at
            FROM claimed
            WHERE target.id = claimed.id
              AND target.tenant_id = :tenant_id
              AND target.status = 'pending'
            RETURNING target.id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "stale_before": stale_before,
            "transitioned_at": normalized_now,
            "batch_size": int(batch_size),
        },
    )
    transitioned_rows = result.fetchall()
    return B23TransitionResult(
        transitioned_count=len(transitioned_rows),
        transition_name="pending_to_unmatched",
        cadence_seconds=int(B23_P3_TRANSITION_SWEEP_CADENCE.total_seconds()),
    )


async def transition_stale_provisional_to_confirmed(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    now_utc: datetime,
    batch_size: int = B23_P3_TRANSITION_BATCH_SIZE,
) -> B23TransitionResult:
    normalized_now = _normalize_utc(now_utc)
    fallback_transition_before = normalized_now - PROVISIONAL_MATCH_WINDOW
    result = await session.execute(
        text(
            """
            WITH claimed AS (
                SELECT v.id
                FROM b23_match_verdicts v
                WHERE v.tenant_id = :tenant_id
                  AND v.status = 'matched_provisional'
                  AND (
                      v.provisional_expires_at <= :now_utc
                      OR (
                          v.provisional_expires_at IS NULL
                          AND v.last_transition_at <= :fallback_transition_before
                      )
                  )
                  AND NOT EXISTS (
                      SELECT 1
                      FROM b23_revenue_events e
                      WHERE e.tenant_id = v.tenant_id
                        AND e.match_verdict_id = v.id
                        AND (
                            e.event_type IN (
                                'partial_refund',
                                'full_refund',
                                'chargeback_opened',
                                'chargeback_won',
                                'chargeback_lost',
                                'reversal'
                            )
                            OR e.is_gross_capture_correction = true
                        )
                  )
                ORDER BY COALESCE(v.provisional_expires_at, v.last_transition_at) ASC, v.id ASC
                LIMIT :batch_size
                FOR UPDATE SKIP LOCKED
            )
            UPDATE b23_match_verdicts target
            SET
                status = 'matched_confirmed',
                confirmed_at = :transitioned_at,
                last_transition_at = :transitioned_at,
                updated_at = :transitioned_at
            FROM claimed
            WHERE target.id = claimed.id
              AND target.tenant_id = :tenant_id
              AND target.status = 'matched_provisional'
            RETURNING target.id
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "now_utc": normalized_now,
            "fallback_transition_before": fallback_transition_before,
            "transitioned_at": normalized_now,
            "batch_size": int(batch_size),
        },
    )
    transitioned_rows = result.fetchall()
    return B23TransitionResult(
        transitioned_count=len(transitioned_rows),
        transition_name="provisional_to_confirmed",
        cadence_seconds=int(B23_P3_TRANSITION_SWEEP_CADENCE.total_seconds()),
    )
