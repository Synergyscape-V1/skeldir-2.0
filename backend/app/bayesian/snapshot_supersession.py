"""Snapshot dominance checks for frozen B2.4-P4 authority retries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


SNAPSHOT_SUPERSESSION_POLICY_VERSION = "b24-p4-snapshot-supersession-v1"
B24_P5_OUTPUT_NON_REGRESSION_ENTRY_GATE = (
    "Before B2.4-P5 introduces artifact, TrustEnvelope, or current-output writes, "
    "those production write paths must call "
    "assert_snapshot_artifact_not_regressing_current_output."
)


@dataclass(frozen=True)
class SnapshotSupersessionResult:
    superseded: bool
    superseding_source_snapshot_hash: str | None
    supersession_reason: str | None


async def check_snapshot_supersession(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
) -> SnapshotSupersessionResult:
    """Return whether an older frozen retry lost the execution lane to a newer hash."""

    row = (
        (
            await session.execute(
                text(
                    """
                    WITH frozen_lineage AS (
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
                    active_owner AS (
                        SELECT lease.active_source_snapshot_hash AS source_snapshot_hash,
                               'newer_active_execution_owner' AS reason
                        FROM public.b24_active_execution_leases lease
                        WHERE lease.tenant_id = :tenant_id
                          AND lease.model_type = :model_type
                          AND lease.model_version = :model_version
                          AND lease.source_window_start = :source_window_start
                          AND lease.source_window_end = :source_window_end
                          AND lease.active_source_snapshot_hash IS NOT NULL
                          AND lease.active_source_snapshot_hash <> :source_snapshot_hash
                          AND lease.status IN (
                              'profiling',
                              'profile_passed',
                              'claiming',
                              'dispatch_pending',
                              'dispatched',
                              'running',
                              'succeeded'
                          )
                        LIMIT 1
                    ),
                    newer_fit AS (
                        SELECT fit.source_snapshot_hash,
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
                        ORDER BY fit.created_at DESC
                        LIMIT 1
                    ),
                    newer_dispatch AS (
                        SELECT fit.source_snapshot_hash,
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
                        ORDER BY outbox.created_at DESC
                        LIMIT 1
                    ),
                    winner AS (
                        SELECT source_snapshot_hash, reason FROM active_owner
                        UNION ALL
                        SELECT source_snapshot_hash, reason FROM newer_fit
                        UNION ALL
                        SELECT source_snapshot_hash, reason FROM newer_dispatch
                        LIMIT 1
                    )
                    SELECT source_snapshot_hash, reason
                    FROM winner
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "model_type": model_type,
                    "model_version": model_version,
                    "source_window_start": source_window_start,
                    "source_window_end": source_window_end,
                    "source_snapshot_hash": source_snapshot_hash,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return SnapshotSupersessionResult(
            superseded=False,
            superseding_source_snapshot_hash=None,
            supersession_reason=None,
        )
    return SnapshotSupersessionResult(
        superseded=True,
        superseding_source_snapshot_hash=str(row["source_snapshot_hash"]),
        supersession_reason=str(row["reason"]),
    )


async def assert_snapshot_artifact_not_regressing_current_output(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
) -> None:
    """Guard future artifact/TrustEnvelope writes from publishing older evidence."""

    # older Hash A cannot overwrite newer Hash B artifact or TrustEnvelope output.
    supersession = await check_snapshot_supersession(
        session,
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        source_snapshot_hash=source_snapshot_hash,
    )
    if supersession.superseded:
        raise RuntimeError(
            "source_snapshot_superseded: older Hash A cannot overwrite newer Hash B "
            "artifact or TrustEnvelope current output"
        )
