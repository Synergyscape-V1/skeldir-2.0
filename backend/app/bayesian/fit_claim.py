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
    {
        "profiling",
        "profile_passed",
        "claiming",
        "dispatch_pending",
        "dispatched",
        "running",
        "cancel_requested",
    }
)
TERMINAL_EXECUTION_STATUSES = frozenset(
    {
        "profile_rejected",
        "profile_superseded",
        "profile_timeout",
        "profile_failed",
        "succeeded",
        "failed",
        "fallback_only",
        "cancelled",
        "stale_recovered",
    }
)
DEFAULT_ACTIVE_LEASE_SECONDS = 3600


class FitClaimOutcome(StrEnum):
    CLAIMED = "claimed"
    REUSED = "reused"
    SUPPRESSED_ACTIVE = "suppressed_active"
    SOURCE_SNAPSHOT_SUPERSEDED = "source_snapshot_superseded"


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
    """Claim one active execution and one outbox row in one locked SQL boundary.

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
        "source_read_started_at": snapshot.source_read_started_at,
        "source_read_completed_at": snapshot.source_read_completed_at,
        "claim_owner": claim_owner,
        "leased_until": leased_until,
    }
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
            """
        ),
        params,
    )
    row = (
        (
            await session.execute(
                text(
                    """
                    WITH locked_execution_lane AS (
                        SELECT
                            fit_id,
                            status,
                            lease_owner,
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
                    ),
                    frozen_lineage AS (
                        SELECT COALESCE(
                            (
                                SELECT min(dirty.observed_at)
                                FROM public.b24_dirty_events dirty
                                WHERE dirty.tenant_id = :tenant_id
                                  AND dirty.model_type = :model_type
                                  AND dirty.model_version = :model_version
                                  AND dirty.source_window_start = :source_window_start
                                  AND dirty.source_window_end = :source_window_end
                                  AND dirty.source_snapshot_hash = :source_snapshot_hash
                            ),
                            (
                                SELECT min(req.requested_at)
                                FROM public.b24_feature_authority_build_requests req
                                WHERE req.tenant_id = :tenant_id
                                  AND req.model_type = :model_type
                                  AND req.model_version = :model_version
                                  AND req.source_window_start = :source_window_start
                                  AND req.source_window_end = :source_window_end
                                  AND req.source_snapshot_hash = :source_snapshot_hash
                            ),
                            now()
                        ) AS lineage_at
                    ),
                    newer_dominant_snapshot AS (
                        SELECT
                            lane.active_source_snapshot_hash AS source_snapshot_hash,
                            'newer_active_execution_owner' AS reason
                        FROM locked_execution_lane lane
                        WHERE lane.active_source_snapshot_hash IS NOT NULL
                          AND lane.active_source_snapshot_hash <> :source_snapshot_hash
                          AND lane.status IN (
                              'profiling',
                              'profile_passed',
                              'claiming',
                              'dispatch_pending',
                              'dispatched',
                              'running',
                              'succeeded'
                          )
                          AND lane.leased_until >= now()
                        UNION ALL
                        SELECT
                            fit.source_snapshot_hash,
                            'newer_fit_claimed_dispatched_or_completed' AS reason
                        FROM public.bayesian_model_fits fit
                        CROSS JOIN frozen_lineage frozen
                        WHERE fit.tenant_id = :tenant_id
                          AND fit.model_type = :model_type
                          AND fit.model_version = :model_version
                          AND fit.source_window_start = :source_window_start
                          AND fit.source_window_end = :source_window_end
                          AND fit.source_snapshot_hash <> :source_snapshot_hash
                          AND fit.created_at > frozen.lineage_at
                          AND fit.status IN ('queued', 'running', 'succeeded')
                        UNION ALL
                        SELECT
                            fit.source_snapshot_hash,
                            'newer_dispatch_outbox_visible' AS reason
                        FROM public.b24_fit_dispatch_outbox outbox
                        JOIN public.bayesian_model_fits fit
                          ON fit.tenant_id = outbox.tenant_id
                         AND fit.id = outbox.fit_id
                        CROSS JOIN frozen_lineage frozen
                        WHERE fit.tenant_id = :tenant_id
                          AND fit.model_type = :model_type
                          AND fit.model_version = :model_version
                          AND fit.source_window_start = :source_window_start
                          AND fit.source_window_end = :source_window_end
                          AND fit.source_snapshot_hash <> :source_snapshot_hash
                          AND outbox.created_at > frozen.lineage_at
                          AND outbox.status IN ('pending', 'dispatching', 'dispatched')
                        LIMIT 1
                    ),
                    lane_state AS (
                        SELECT
                            lane.*,
                            COALESCE(lane.leased_until < now(), true) AS lane_is_stale,
                            (
                                lane.status IN ('claiming', 'profiling', 'profile_passed')
                                AND lane.fit_id IS NULL
                                AND lane.lease_owner = :claim_owner
                            ) AS owned_planner_lane
                        FROM locked_execution_lane lane
                    ),
                    suppressed_active AS (
                        UPDATE public.b24_active_execution_leases lease
                        SET latest_desired_source_snapshot_hash = :source_snapshot_hash,
                            needs_refit_after_current =
                                lease.needs_refit_after_current
                                OR lease.active_source_snapshot_hash IS DISTINCT FROM :source_snapshot_hash,
                            updated_at = now()
                        FROM lane_state lane
                        WHERE lease.tenant_id = :tenant_id
                          AND lease.model_type = :model_type
                          AND lease.model_version = :model_version
                          AND lease.source_window_start = :source_window_start
                          AND lease.source_window_end = :source_window_end
                          AND NOT EXISTS (SELECT 1 FROM newer_dominant_snapshot)
                          AND lane.status IN (
                              'profiling',
                              'profile_passed',
                              'claiming',
                              'dispatch_pending',
                              'dispatched',
                              'running',
                              'cancel_requested'
                          )
                          AND NOT lane.lane_is_stale
                          AND NOT lane.owned_planner_lane
                        RETURNING
                            lease.fit_id,
                            lease.status,
                            lease.active_source_snapshot_hash,
                            lease.latest_desired_source_snapshot_hash,
                            lease.needs_refit_after_current
                    ),
                    claimable_execution_lane AS (
                        SELECT 1
                        FROM lane_state lane
                        WHERE NOT EXISTS (SELECT 1 FROM newer_dominant_snapshot)
                          AND NOT EXISTS (SELECT 1 FROM suppressed_active)
                          AND (
                              lane.owned_planner_lane
                              OR lane.lane_is_stale
                              OR lane.status IN (
                                  'profile_rejected',
                                  'profile_passed',
                                  'profile_superseded',
                                  'profile_timeout',
                                  'profile_failed',
                                  'fallback_only',
                                  'failed',
                                  'cancelled',
                                  'stale_recovered'
                              )
                          )
                    ),
                    claimed_fit AS (
                        INSERT INTO public.bayesian_model_fits (
                            tenant_id,
                            model_type,
                            model_version,
                            source_window_start,
                            source_window_end,
                            source_snapshot_hash,
                            source_read_started_at,
                            source_read_completed_at,
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
                        SELECT
                            :tenant_id,
                            :model_type,
                            :model_version,
                            :source_window_start,
                            :source_window_end,
                            :source_snapshot_hash,
                            :source_read_started_at,
                            :source_read_completed_at,
                            'queued',
                            'eligible',
                            'complete',
                            false,
                            NULL,
                            now(),
                            60,
                            0,
                            1
                        WHERE EXISTS (SELECT 1 FROM claimable_execution_lane)
                          AND NOT EXISTS (SELECT 1 FROM newer_dominant_snapshot)
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
                            source_read_started_at = EXCLUDED.source_read_started_at,
                            source_read_completed_at = EXCLUDED.source_read_completed_at,
                            last_eligibility_check_at = now(),
                            updated_at = now()
                        RETURNING id
                    ),
                    dispatchable_outbox AS (
                        INSERT INTO public.b24_fit_dispatch_outbox (
                            tenant_id,
                            fit_id,
                            dispatch_key,
                            task_name,
                            attempt_id,
                            payload_hash,
                            status,
                            attempt_count,
                            next_attempt_at,
                            created_at,
                            updated_at
                        )
                        SELECT
                            :tenant_id,
                            id,
                            'b24-fit:' || :tenant_id || ':' || id::text,
                            'app.tasks.bayesian.execute_fit_intent',
                            gen_random_uuid(),
                            public.b24_sha256_text('app.tasks.bayesian.execute_fit_intent:' || id::text),
                            'pending',
                            0,
                            now(),
                            now(),
                            now()
                        FROM claimed_fit
                        WHERE NOT EXISTS (SELECT 1 FROM newer_dominant_snapshot)
                        ON CONFLICT (tenant_id, fit_id)
                        DO UPDATE SET
                            status = CASE
                                WHEN b24_fit_dispatch_outbox.status IN (
                                    'dispatched',
                                    'leased',
                                    'running',
                                    'completed',
                                    'failed_terminal',
                                    'cancelled',
                                    'expired',
                                    'superseded',
                                    'quarantined'
                                )
                                    THEN b24_fit_dispatch_outbox.status
                                ELSE 'pending'
                            END,
                            next_attempt_at = CASE
                                WHEN b24_fit_dispatch_outbox.status IN (
                                    'dispatched',
                                    'leased',
                                    'running',
                                    'completed',
                                    'failed_terminal',
                                    'cancelled',
                                    'expired',
                                    'superseded',
                                    'quarantined'
                                )
                                    THEN b24_fit_dispatch_outbox.next_attempt_at
                                ELSE now()
                            END,
                            attempt_id = CASE
                                WHEN b24_fit_dispatch_outbox.status IN (
                                    'dispatched',
                                    'leased',
                                    'running',
                                    'completed',
                                    'failed_terminal',
                                    'cancelled',
                                    'expired',
                                    'superseded',
                                    'quarantined'
                                )
                                    THEN b24_fit_dispatch_outbox.attempt_id
                                ELSE gen_random_uuid()
                            END,
                            payload_hash = public.b24_sha256_text(
                                'app.tasks.bayesian.execute_fit_intent:' || EXCLUDED.fit_id::text
                            ),
                            claim_capability = NULL,
                            claim_capability_digest = NULL,
                            claim_capability_expires_at = NULL,
                            updated_at = now()
                        RETURNING id, fit_id
                    ),
                    activated_execution_lane AS (
                        UPDATE public.b24_active_execution_leases lease
                        SET fit_id = outbox.fit_id,
                            status = 'dispatch_pending',
                            active_source_snapshot_hash = :source_snapshot_hash,
                            latest_desired_source_snapshot_hash = :source_snapshot_hash,
                            needs_refit_after_current = false,
                            lease_owner = :claim_owner,
                            lease_acquired_at = now(),
                            leased_until = :leased_until,
                            heartbeat_at = now(),
                            terminal_at = NULL,
                            updated_at = now()
                        FROM dispatchable_outbox outbox
                        WHERE lease.tenant_id = :tenant_id
                          AND lease.model_type = :model_type
                          AND lease.model_version = :model_version
                          AND lease.source_window_start = :source_window_start
                          AND lease.source_window_end = :source_window_end
                        RETURNING
                            lease.fit_id,
                            lease.status,
                            lease.active_source_snapshot_hash,
                            lease.latest_desired_source_snapshot_hash,
                            lease.needs_refit_after_current
                    )
                    SELECT
                        'source_snapshot_superseded' AS outcome,
                        NULL::uuid AS fit_id,
                        NULL::uuid AS dispatch_outbox_id,
                        'profile_superseded' AS active_execution_status,
                        false AS needs_refit_after_current,
                        (SELECT source_snapshot_hash FROM newer_dominant_snapshot LIMIT 1)
                            AS active_source_snapshot_hash,
                        :source_snapshot_hash AS latest_desired_source_snapshot_hash
                    WHERE EXISTS (SELECT 1 FROM newer_dominant_snapshot)
                    UNION ALL
                    SELECT
                        'suppressed_active' AS outcome,
                        fit_id,
                        NULL::uuid AS dispatch_outbox_id,
                        status AS active_execution_status,
                        true AS needs_refit_after_current,
                        active_source_snapshot_hash,
                        :source_snapshot_hash AS latest_desired_source_snapshot_hash
                    FROM suppressed_active
                    UNION ALL
                    SELECT
                        'claimed' AS outcome,
                        lane.fit_id,
                        outbox.id AS dispatch_outbox_id,
                        lane.status AS active_execution_status,
                        lane.needs_refit_after_current,
                        lane.active_source_snapshot_hash,
                        lane.latest_desired_source_snapshot_hash
                    FROM activated_execution_lane lane
                    JOIN dispatchable_outbox outbox
                      ON outbox.fit_id = lane.fit_id
                    LIMIT 1
                    """
                ),
                params,
            )
        )
        .mappings()
        .one()
    )

    outcome = FitClaimOutcome(str(row["outcome"]))
    return FitClaimResult(
        outcome=outcome,
        tenant_id=snapshot.tenant_id,
        fit_id=row["fit_id"],
        dispatch_outbox_id=row["dispatch_outbox_id"],
        active_execution_status=str(row["active_execution_status"]),
        needs_refit_after_current=bool(row["needs_refit_after_current"]),
        active_source_snapshot_hash=(
            str(row["active_source_snapshot_hash"])
            if row["active_source_snapshot_hash"]
            else None
        ),
        latest_desired_source_snapshot_hash=(
            str(row["latest_desired_source_snapshot_hash"])
            if row["latest_desired_source_snapshot_hash"]
            else None
        ),
    )
