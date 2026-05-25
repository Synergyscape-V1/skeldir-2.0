"""B2.4-P3 debounced fit planning orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import text

from app.bayesian.authority_liveness import (
    AuthorityBuildRequestResult,
    AuthorityBuildStatus,
    request_feature_authority_build,
)
from app.bayesian.enums import FallbackReason
from app.bayesian.feature_authority import (
    FeatureAuthorityUnavailable,
    load_source_window_feature_authority,
)
from app.bayesian.fit_claim import FitClaimResult, claim_fit_for_snapshot
from app.bayesian.preflight_lease import (
    PreflightLeaseResult,
    acquire_preflight_lease,
    terminalize_preflight_lease,
)
from app.bayesian.repository import BayesianFitRepository
from app.bayesian.resource_profile import (
    B24ResourceDecision,
    evaluate_source_snapshot_resource_bounds,
)
from app.bayesian.source_snapshot import SourceSnapshotResult
from app.db.session import AsyncSessionLocal, get_session


DEBOUNCE_POLICY_VERSION = "b24-p3-debounce-v1"
QUIET_PERIOD_SECONDS = 120
MAX_WAIT_SECONDS = 900
PLANNER_CANDIDATE_LIMIT = 100
DIRTY_EVENT_LEASE_SECONDS = 300


@dataclass(frozen=True)
class DirtyPlanningCandidate:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    dirty_event_count: int
    first_observed_at: datetime
    last_observed_at: datetime


@dataclass(frozen=True)
class PlannedFitIntent:
    candidate: DirtyPlanningCandidate
    snapshot: SourceSnapshotResult | None
    preflight_lease: PreflightLeaseResult | None
    resource_decision: B24ResourceDecision | None
    claim: FitClaimResult | None
    fallback_only: bool
    authority_yield: AuthorityBuildRequestResult | None = None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def lease_debounced_dirty_candidates(
    *,
    tenant_id: UUID,
    planner_owner: str,
    quiet_period_seconds: int = QUIET_PERIOD_SECONDS,
    max_wait_seconds: int = MAX_WAIT_SECONDS,
    limit: int = PLANNER_CANDIDATE_LIMIT,
) -> list[DirtyPlanningCandidate]:
    """Lease debounced dirty rows using FOR UPDATE SKIP LOCKED."""

    quiet_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=max(1, quiet_period_seconds)
    )
    stale_cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=max(quiet_period_seconds, max_wait_seconds)
    )
    lease_expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=DIRTY_EVENT_LEASE_SECONDS
    )
    async with get_session(tenant_id) as session:
        result = await session.execute(
            text(
                """
                WITH candidate_keys AS (
                    SELECT
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end,
                        count(*)::int AS dirty_event_count,
                        min(observed_at) AS first_observed_at,
                        max(observed_at) AS last_observed_at
                    FROM public.b24_dirty_events
                    WHERE tenant_id = :tenant_id
                      AND status IN ('pending', 'authority_retry_ready')
                    GROUP BY
                        tenant_id,
                        model_type,
                        model_version,
                        source_window_start,
                        source_window_end
                    HAVING
                        max(observed_at) <= :quiet_cutoff
                        OR min(observed_at) <= :stale_cutoff
                    ORDER BY min(observed_at) ASC
                    LIMIT :limit
                ),
                leased_rows AS (
                    SELECT dirty.tenant_id, dirty.id
                    FROM public.b24_dirty_events dirty
                    JOIN candidate_keys keys
                      ON keys.tenant_id = dirty.tenant_id
                     AND keys.model_type = dirty.model_type
                     AND keys.model_version = dirty.model_version
                     AND keys.source_window_start = dirty.source_window_start
                     AND keys.source_window_end = dirty.source_window_end
                    WHERE dirty.status IN ('pending', 'authority_retry_ready')
                    ORDER BY dirty.observed_at ASC, dirty.id ASC
                    FOR UPDATE OF dirty SKIP LOCKED
                ),
                updated AS (
                    UPDATE public.b24_dirty_events dirty
                    SET status = 'leased',
                        planner_owner = :planner_owner,
                        leased_at = now(),
                        lease_expires_at = :lease_expires_at,
                        updated_at = now()
                    FROM leased_rows
                    WHERE dirty.tenant_id = leased_rows.tenant_id
                      AND dirty.id = leased_rows.id
                    RETURNING
                        dirty.tenant_id,
                        dirty.model_type,
                        dirty.model_version,
                        dirty.source_window_start,
                        dirty.source_window_end,
                        dirty.observed_at
                )
                SELECT
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    count(*)::int AS dirty_event_count,
                    min(observed_at) AS first_observed_at,
                    max(observed_at) AS last_observed_at
                FROM updated
                GROUP BY
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end
                ORDER BY min(observed_at) ASC
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "planner_owner": planner_owner,
                "lease_expires_at": lease_expires_at,
                "quiet_cutoff": quiet_cutoff,
                "stale_cutoff": stale_cutoff,
                "limit": max(1, int(limit)),
            },
        )
        return [
            DirtyPlanningCandidate(
                tenant_id=row["tenant_id"],
                model_type=row["model_type"],
                model_version=row["model_version"],
                source_window_start=_utc(row["source_window_start"]),
                source_window_end=_utc(row["source_window_end"]),
                dirty_event_count=int(row["dirty_event_count"]),
                first_observed_at=_utc(row["first_observed_at"]),
                last_observed_at=_utc(row["last_observed_at"]),
            )
            for row in result.mappings()
        ]


async def mark_dirty_events_for_candidate(
    *,
    tenant_id: UUID,
    candidate: DirtyPlanningCandidate,
    status: str,
) -> int:
    timestamp_column = {
        "coalesced": "coalesced_at",
        "claimed": "claimed_at",
        "fallback_only": "fallback_at",
        "superseded": "superseded_at",
        "dispatched": "dispatched_at",
        "suppressed": "suppressed_at",
        "authority_timeout": "authority_terminal_at",
        "authority_build_failed": "authority_terminal_at",
        "pruned": "pruned_at",
    }.get(status)
    if timestamp_column is None:
        raise ValueError(f"unsupported dirty event terminal status: {status}")
    async with get_session(tenant_id) as session:
        result = await session.execute(
            text(
                f"""
                UPDATE public.b24_dirty_events
                SET status = :status,
                    {timestamp_column} = now(),
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND model_type = :model_type
                  AND model_version = :model_version
                  AND source_window_start = :source_window_start
                  AND source_window_end = :source_window_end
                  AND status = 'leased'
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "model_type": candidate.model_type,
                "model_version": candidate.model_version,
                "source_window_start": candidate.source_window_start,
                "source_window_end": candidate.source_window_end,
                "status": status,
            },
        )
        return int(result.rowcount or 0)


async def mark_authority_waiting_dirty_events(
    *,
    tenant_id: UUID,
    candidate: DirtyPlanningCandidate,
    snapshot: SourceSnapshotResult,
    request: AuthorityBuildRequestResult,
) -> int:
    """Park leased dirty events in a non-dispatchable authority wait state."""

    async with get_session(tenant_id) as session:
        result = await session.execute(
            text(
                """
                UPDATE public.b24_dirty_events
                SET status = 'authority_waiting',
                    source_snapshot_hash = :source_snapshot_hash,
                    authority_retry_count = :authority_retry_count,
                    authority_retry_after_at = :authority_retry_after_at,
                    authority_wait_started_at = COALESCE(authority_wait_started_at, now()),
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND model_type = :model_type
                  AND model_version = :model_version
                  AND source_window_start = :source_window_start
                  AND source_window_end = :source_window_end
                  AND status = 'leased'
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "model_type": candidate.model_type,
                "model_version": candidate.model_version,
                "source_window_start": candidate.source_window_start,
                "source_window_end": candidate.source_window_end,
                "source_snapshot_hash": snapshot.source_snapshot_hash,
                "authority_retry_count": request.retry_count,
                "authority_retry_after_at": request.retry_after_at,
            },
        )
        return int(result.rowcount or 0)


async def plan_candidate(
    *,
    candidate: DirtyPlanningCandidate,
    planner_owner: str,
) -> PlannedFitIntent:
    """Acquire P4 preflight, compute P2/P4, then persist claim/outbox intent."""

    from app.bayesian.source_snapshot import compute_source_snapshot_hash

    async with get_session(candidate.tenant_id) as lease_session:
        preflight_lease = await acquire_preflight_lease(
            lease_session,
            tenant_id=candidate.tenant_id,
            model_type=candidate.model_type,
            model_version=candidate.model_version,
            source_window_start=candidate.source_window_start,
            source_window_end=candidate.source_window_end,
            lease_owner=planner_owner,
        )

    if not preflight_lease.acquired:
        await mark_dirty_events_for_candidate(
            tenant_id=candidate.tenant_id,
            candidate=candidate,
            status="suppressed",
        )
        return PlannedFitIntent(
            candidate=candidate,
            snapshot=None,
            preflight_lease=preflight_lease,
            resource_decision=None,
            claim=None,
            fallback_only=True,
            authority_yield=None,
        )

    async with AsyncSessionLocal() as snapshot_session:
        snapshot = await compute_source_snapshot_hash(
            snapshot_session,
            tenant_id=candidate.tenant_id,
            model_type=candidate.model_type,
            model_version=candidate.model_version,
            source_window_start=candidate.source_window_start,
            source_window_end=candidate.source_window_end,
        )

    if not snapshot.preflight.is_eligible:
        async with get_session(candidate.tenant_id) as session:
            repo = BayesianFitRepository(session)
            fit_id = await repo.upsert_fallback_from_snapshot(snapshot=snapshot)
            await terminalize_preflight_lease(
                session,
                tenant_id=candidate.tenant_id,
                model_type=candidate.model_type,
                model_version=candidate.model_version,
                source_window_start=candidate.source_window_start,
                source_window_end=candidate.source_window_end,
                fit_id=fit_id,
                terminal_status="fallback_only",
            )
        await mark_dirty_events_for_candidate(
            tenant_id=candidate.tenant_id,
            candidate=candidate,
            status="fallback_only",
        )
        return PlannedFitIntent(
            candidate=candidate,
            snapshot=snapshot,
            preflight_lease=preflight_lease,
            resource_decision=None,
            claim=None,
            fallback_only=True,
            authority_yield=None,
        )

    authority_yield: AuthorityBuildRequestResult | None = None
    authority_terminal_reason: FallbackReason | None = None
    feature_authority = None
    async with get_session(candidate.tenant_id) as session:
        try:
            feature_authority = await load_source_window_feature_authority(
                session,
                tenant_id=candidate.tenant_id,
                model_type=candidate.model_type,
                model_version=candidate.model_version,
                source_window_start=candidate.source_window_start,
                source_window_end=candidate.source_window_end,
                source_snapshot_hash=snapshot.source_snapshot_hash,
            )
        except FeatureAuthorityUnavailable as exc:
            authority_yield = await request_feature_authority_build(
                session,
                snapshot=snapshot,
                reason=exc.reason,
                detail=exc.detail,
            )
            authority_terminal_reason = authority_yield.terminal_reason
            fit_id = None
            if authority_yield.status in {
                AuthorityBuildStatus.TIMEOUT,
                AuthorityBuildStatus.BUILD_FAILED,
            }:
                repo = BayesianFitRepository(session)
                fit_id = await repo.upsert_feature_authority_fallback_from_snapshot(
                    snapshot=snapshot,
                    fallback_reason=authority_terminal_reason
                    or FallbackReason.CARDINALITY_AUTHORITY_TIMEOUT,
                    detail=exc.detail,
                )
            await terminalize_preflight_lease(
                session,
                tenant_id=candidate.tenant_id,
                model_type=candidate.model_type,
                model_version=candidate.model_version,
                source_window_start=candidate.source_window_start,
                source_window_end=candidate.source_window_end,
                fit_id=fit_id,
                terminal_status=(
                    "fallback_only"
                    if fit_id is not None
                    else AuthorityBuildStatus.WAITING.value
                ),
            )

    if authority_yield is not None:
        if authority_yield.status in {
            AuthorityBuildStatus.TIMEOUT,
            AuthorityBuildStatus.BUILD_FAILED,
        }:
            await mark_dirty_events_for_candidate(
                tenant_id=candidate.tenant_id,
                candidate=candidate,
                status=authority_yield.status.value,
            )
            return PlannedFitIntent(
                candidate=candidate,
                snapshot=snapshot,
                preflight_lease=preflight_lease,
                resource_decision=None,
                claim=None,
                fallback_only=True,
                authority_yield=authority_yield,
            )
        await mark_authority_waiting_dirty_events(
            tenant_id=candidate.tenant_id,
            candidate=candidate,
            snapshot=snapshot,
            request=authority_yield,
        )
        return PlannedFitIntent(
            candidate=candidate,
            snapshot=snapshot,
            preflight_lease=preflight_lease,
            resource_decision=None,
            claim=None,
            fallback_only=False,
            authority_yield=authority_yield,
        )

    assert feature_authority is not None
    resource_decision = evaluate_source_snapshot_resource_bounds(
        snapshot=snapshot,
        preflight_lease_id=preflight_lease.preflight_lease_id,
        feature_authority=feature_authority,
    )
    if not resource_decision.allowed:
        async with get_session(candidate.tenant_id) as session:
            repo = BayesianFitRepository(session)
            fit_id = await repo.upsert_resource_fallback_from_snapshot(
                snapshot=snapshot,
                resource_decision=resource_decision,
            )
            await terminalize_preflight_lease(
                session,
                tenant_id=candidate.tenant_id,
                model_type=candidate.model_type,
                model_version=candidate.model_version,
                source_window_start=candidate.source_window_start,
                source_window_end=candidate.source_window_end,
                fit_id=fit_id,
                terminal_status="fallback_only",
            )
        await mark_dirty_events_for_candidate(
            tenant_id=candidate.tenant_id,
            candidate=candidate,
            status="fallback_only",
        )
        return PlannedFitIntent(
            candidate=candidate,
            snapshot=snapshot,
            preflight_lease=preflight_lease,
            resource_decision=resource_decision,
            claim=None,
            fallback_only=True,
            authority_yield=None,
        )

    async with get_session(candidate.tenant_id) as session:
        claim = await claim_fit_for_snapshot(
            session,
            snapshot=snapshot,
            claim_owner=planner_owner,
        )

    if claim.claimed_for_dispatch:
        status = "claimed"
    else:
        status = "superseded"
    await mark_dirty_events_for_candidate(
        tenant_id=candidate.tenant_id,
        candidate=candidate,
        status=status,
    )
    return PlannedFitIntent(
        candidate=candidate,
        snapshot=snapshot,
        preflight_lease=preflight_lease,
        resource_decision=resource_decision,
        claim=claim,
        fallback_only=False,
        authority_yield=None,
    )


async def plan_due_dirty_events(
    *,
    tenant_id: UUID,
    planner_owner: str,
    quiet_period_seconds: int = QUIET_PERIOD_SECONDS,
    max_wait_seconds: int = MAX_WAIT_SECONDS,
    limit: int = PLANNER_CANDIDATE_LIMIT,
) -> list[PlannedFitIntent]:
    candidates = await lease_debounced_dirty_candidates(
        tenant_id=tenant_id,
        planner_owner=planner_owner,
        quiet_period_seconds=quiet_period_seconds,
        max_wait_seconds=max_wait_seconds,
        limit=limit,
    )
    return [
        await plan_candidate(candidate=candidate, planner_owner=planner_owner)
        for candidate in candidates
    ]
