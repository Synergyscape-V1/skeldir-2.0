"""B2.4-P3 atomic fit claim authority."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.source_snapshot import SourceSnapshotResult


ACTIVE_EXECUTION_STATUSES = frozenset(
    {"claiming", "dispatch_pending", "dispatched", "running", "cancel_requested"}
)
TERMINAL_EXECUTION_STATUSES = frozenset(
    {"succeeded", "failed", "fallback_only", "cancelled", "stale_recovered"}
)
DEFAULT_ACTIVE_LEASE_SECONDS = 3600


class FitClaimOutcome(StrEnum):
    CLAIMED = "claimed"
    REUSED = "reused"
    SUPPRESSED_ACTIVE = "suppressed_active"


@dataclass(frozen=True)
class FitClaimResult:
    outcome: FitClaimOutcome
    tenant_id: UUID
    fit_id: UUID | None
    dispatch_outbox_id: UUID | None
    active_execution_status: str
    needs_refit_after_current: bool
    active_source_snapshot_hash: str | None
    latest_desired_source_snapshot_hash: str | None

    @property
    def claimed_for_dispatch(self) -> bool:
        return self.outcome in {FitClaimOutcome.CLAIMED, FitClaimOutcome.REUSED}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _dispatch_key(*, tenant_id: UUID, fit_id: UUID) -> str:
    return f"b24-fit:{tenant_id}:{fit_id}"


async def claim_fit_for_snapshot(
    session: AsyncSession,
    *,
    snapshot: SourceSnapshotResult,
    claim_owner: str,
    lease_seconds: int = DEFAULT_ACTIVE_LEASE_SECONDS,
) -> FitClaimResult:
    """Claim one active execution and one outbox row in the same transaction.

    Historical fit identity includes ``source_snapshot_hash``. The active
    execution lease key intentionally excludes it, so a newer hash cannot create
    concurrent expensive work for the same tenant/model/window.
    """

    now = datetime.now(timezone.utc)
    leased_until = now + timedelta(seconds=max(1, int(lease_seconds)))
    params = {
        "tenant_id": str(snapshot.tenant_id),
        "model_type": snapshot.model_type,
        "model_version": snapshot.model_version,
        "source_window_start": _utc(snapshot.source_window_start),
        "source_window_end": _utc(snapshot.source_window_end),
        "source_snapshot_hash": snapshot.source_snapshot_hash,
        "claim_owner": claim_owner,
        "leased_until": leased_until,
    }

    inserted = (
        (
            await session.execute(
                text(
                    """
                    INSERT INTO public.b24_active_execution_leases (
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        active_source_snapshot_hash,
                        latest_desired_source_snapshot_hash,
                        status,
                        needs_refit_after_current,
                        lease_owner,
                        leased_until,
                        heartbeat_at,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :tenant_id,
                        :model_type,
                        :model_version,
                        :source_window_start,
                        :source_window_end,
                        :source_snapshot_hash,
                        :source_snapshot_hash,
                        'claiming',
                        false,
                        :claim_owner,
                        :leased_until,
                        now(),
                        now(),
                        now()
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING tenant_id
                    """
                ),
                params,
            )
        )
        .mappings()
        .one_or_none()
    )

    if inserted is None:
        existing = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            fit_id,
                            status,
                            active_source_snapshot_hash,
                            latest_desired_source_snapshot_hash,
                            needs_refit_after_current,
                            leased_until
                        FROM public.b24_active_execution_leases
                        WHERE tenant_id = :tenant_id
                          AND model_type = :model_type
                          AND model_version = :model_version
                          AND source_window_start = :source_window_start
                          AND source_window_end = :source_window_end
                        FOR UPDATE
                        """
                    ),
                    params,
                )
            )
            .mappings()
            .one()
        )
        status = str(existing["status"])
        stale = existing["leased_until"] is not None and existing["leased_until"] < now
        if status in ACTIVE_EXECUTION_STATUSES and not stale:
            await session.execute(
                text(
                    """
                    UPDATE public.b24_active_execution_leases
                    SET latest_desired_source_snapshot_hash = :source_snapshot_hash,
                        needs_refit_after_current =
                            needs_refit_after_current
                            OR active_source_snapshot_hash IS DISTINCT FROM :source_snapshot_hash,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND model_type = :model_type
                      AND model_version = :model_version
                      AND source_window_start = :source_window_start
                      AND source_window_end = :source_window_end
                    """
                ),
                params,
            )
            return FitClaimResult(
                outcome=FitClaimOutcome.SUPPRESSED_ACTIVE,
                tenant_id=snapshot.tenant_id,
                fit_id=existing["fit_id"],
                dispatch_outbox_id=None,
                active_execution_status=status,
                needs_refit_after_current=True,
                active_source_snapshot_hash=existing["active_source_snapshot_hash"],
                latest_desired_source_snapshot_hash=snapshot.source_snapshot_hash,
            )

        await session.execute(
            text(
                """
                UPDATE public.b24_active_execution_leases
                SET fit_id = NULL,
                    active_source_snapshot_hash = :source_snapshot_hash,
                    latest_desired_source_snapshot_hash = :source_snapshot_hash,
                    status = 'claiming',
                    needs_refit_after_current = false,
                    lease_owner = :claim_owner,
                    lease_acquired_at = now(),
                    leased_until = :leased_until,
                    heartbeat_at = now(),
                    stale_recovered_at = CASE
                        WHEN :was_stale THEN now()
                        ELSE stale_recovered_at
                    END,
                    terminal_at = NULL,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND model_type = :model_type
                  AND model_version = :model_version
                  AND source_window_start = :source_window_start
                  AND source_window_end = :source_window_end
                """
            ),
            {**params, "was_stale": bool(stale)},
        )

    fit_id = (
        await session.execute(
            text(
                """
                INSERT INTO public.bayesian_model_fits (
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash,
                    status,
                    eligibility_status,
                    data_completeness_status,
                    fallback_applied,
                    fallback_reason,
                    last_eligibility_check_at,
                    max_runtime_seconds,
                    max_samples,
                    max_cores
                )
                VALUES (
                    :tenant_id,
                    :model_type,
                    :model_version,
                    :source_window_start,
                    :source_window_end,
                    :source_snapshot_hash,
                    'queued',
                    'eligible',
                    'complete',
                    false,
                    NULL,
                    now(),
                    60,
                    0,
                    1
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
                        WHEN bayesian_model_fits.status IN ('succeeded', 'failed', 'cancelled')
                            THEN bayesian_model_fits.status
                        ELSE 'queued'
                    END,
                    eligibility_status = 'eligible',
                    data_completeness_status = 'complete',
                    fallback_applied = false,
                    fallback_reason = NULL,
                    last_eligibility_check_at = now(),
                    updated_at = now()
                RETURNING id
                """
            ),
            params,
        )
    ).scalar_one()

    dispatch_key = _dispatch_key(tenant_id=snapshot.tenant_id, fit_id=fit_id)
    outbox_id = (
        await session.execute(
            text(
                """
                INSERT INTO public.b24_fit_dispatch_outbox (
                    tenant_id,
                    fit_id,
                    dispatch_key,
                    status,
                    attempt_count,
                    next_attempt_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :tenant_id,
                    :fit_id,
                    :dispatch_key,
                    'pending',
                    0,
                    now(),
                    now(),
                    now()
                )
                ON CONFLICT (tenant_id, fit_id)
                DO UPDATE SET
                    status = CASE
                        WHEN b24_fit_dispatch_outbox.status = 'dispatched'
                            THEN 'dispatched'
                        ELSE 'pending'
                    END,
                    next_attempt_at = CASE
                        WHEN b24_fit_dispatch_outbox.status = 'dispatched'
                            THEN b24_fit_dispatch_outbox.next_attempt_at
                        ELSE now()
                    END,
                    updated_at = now()
                RETURNING id
                """
            ),
            {
                **params,
                "fit_id": str(fit_id),
                "dispatch_key": dispatch_key,
            },
        )
    ).scalar_one()

    await session.execute(
        text(
            """
            UPDATE public.b24_active_execution_leases
            SET fit_id = :fit_id,
                status = 'dispatch_pending',
                lease_owner = :claim_owner,
                leased_until = :leased_until,
                heartbeat_at = now(),
                updated_at = now()
            WHERE tenant_id = :tenant_id
              AND model_type = :model_type
              AND model_version = :model_version
              AND source_window_start = :source_window_start
              AND source_window_end = :source_window_end
            """
        ),
        {**params, "fit_id": str(fit_id)},
    )

    return FitClaimResult(
        outcome=FitClaimOutcome.CLAIMED,
        tenant_id=snapshot.tenant_id,
        fit_id=fit_id,
        dispatch_outbox_id=outbox_id,
        active_execution_status="dispatch_pending",
        needs_refit_after_current=False,
        active_source_snapshot_hash=snapshot.source_snapshot_hash,
        latest_desired_source_snapshot_hash=snapshot.source_snapshot_hash,
    )
