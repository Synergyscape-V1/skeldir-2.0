"""B1.7-P4 event-driven prewarm policy planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

B17_P4_COLD_PATH_STRATEGY = "prewarm_required_event_driven_bounded"
B17_P4_PREWARM_TRIGGER_EVENT = "deterministic_truth_change_event"
B17_P4_PREWARM_ORIGIN = "b17_p4_event_driven"

_B17_COMPANION_ENTITY_TYPES: dict[str, tuple[str, ...]] = {
    "attribution_score": ("attribution_score", "channel_performance"),
    "channel_performance": ("channel_performance", "attribution_score"),
    "reconciliation_discrepancy": ("reconciliation_discrepancy",),
}

PrewarmDecisionReason = Literal[
    "triggered",
    "prewarm_disabled",
    "entity_type_ineligible",
    "already_prewarmed_for_watermark",
    "minimum_interval_not_elapsed",
    "tenant_hourly_cap_reached",
    "no_targets_after_caps",
    "stale_replay_path_suppressed",
]


@dataclass(frozen=True)
class B17PrewarmPlan:
    eligible: bool
    should_trigger: bool
    reason: PrewarmDecisionReason
    strategy: str
    trigger_event: str
    target_entity_types: tuple[str, ...]
    target_count: int
    max_permutations_per_trigger: int
    min_trigger_interval_seconds: int
    max_calls_per_tenant_per_hour: int
    call_budget_cents: int
    trigger_identity: str
    truth_watermark: int


def _eligible_entity_types() -> set[str]:
    return {
        item.strip()
        for item in settings.LLM_B17_PREWARM_ELIGIBLE_ENTITY_TYPES.split(",")
        if item and item.strip()
    }


def _candidate_targets(entity_type: str) -> tuple[str, ...]:
    defaults = _B17_COMPANION_ENTITY_TYPES.get(entity_type, (entity_type,))
    eligible = _eligible_entity_types()
    filtered = tuple(item for item in defaults if item in eligible)
    return filtered


def _bounded_targets(entity_type: str) -> tuple[str, ...]:
    candidates = _candidate_targets(entity_type)
    max_targets = max(0, int(settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER))
    if max_targets <= 0:
        return ()
    return candidates[:max_targets]


async def plan_b17_p4_event_driven_prewarm(
    *,
    db_session: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    truth_watermark: int,
    endpoint: str,
) -> B17PrewarmPlan:
    targets = _bounded_targets(entity_type)
    target_count = len(targets)
    trigger_identity = f"{tenant_id}:{user_id}:{entity_type}:{entity_id}"
    plan_base = dict(
        strategy=B17_P4_COLD_PATH_STRATEGY,
        trigger_event=B17_P4_PREWARM_TRIGGER_EVENT,
        target_entity_types=targets,
        target_count=target_count,
        max_permutations_per_trigger=max(
            0, int(settings.LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER)
        ),
        min_trigger_interval_seconds=max(
            0, int(settings.LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS)
        ),
        max_calls_per_tenant_per_hour=max(
            0, int(settings.LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR)
        ),
        call_budget_cents=max(0, int(settings.LLM_B17_PREWARM_CALL_BUDGET_CENTS)),
        trigger_identity=trigger_identity,
        truth_watermark=int(truth_watermark),
    )

    if not settings.LLM_B17_PREWARM_ENABLED:
        return B17PrewarmPlan(
            eligible=False,
            should_trigger=False,
            reason="prewarm_disabled",
            **plan_base,
        )

    if entity_type not in _eligible_entity_types():
        return B17PrewarmPlan(
            eligible=False,
            should_trigger=False,
            reason="entity_type_ineligible",
            **plan_base,
        )

    if target_count == 0:
        return B17PrewarmPlan(
            eligible=True,
            should_trigger=False,
            reason="no_targets_after_caps",
            **plan_base,
        )

    prewarmed_for_watermark = int(
        (
            await db_session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND endpoint = :endpoint
                      AND status = 'success'
                      AND response_metadata_ref ->> 'prewarm_origin' = :prewarm_origin
                      AND response_metadata_ref ->> 'prewarm_trigger_identity' = :trigger_identity
                      AND (
                        response_metadata_ref ->> 'prewarm_truth_watermark'
                      )::bigint = :truth_watermark
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "endpoint": endpoint,
                    "prewarm_origin": B17_P4_PREWARM_ORIGIN,
                    "trigger_identity": trigger_identity,
                    "truth_watermark": int(truth_watermark),
                },
            )
        ).scalar_one()
    )
    if prewarmed_for_watermark > 0:
        return B17PrewarmPlan(
            eligible=True,
            should_trigger=False,
            reason="already_prewarmed_for_watermark",
            **plan_base,
        )

    interval_seconds = max(0, int(settings.LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS))
    if interval_seconds > 0:
        latest_trigger_age_seconds = (
            await db_session.execute(
                text(
                    """
                    SELECT EXTRACT(EPOCH FROM (now() - MAX(created_at)))
                    FROM llm_api_calls
                    WHERE tenant_id = :tenant_id
                      AND endpoint = :endpoint
                      AND status = 'success'
                      AND response_metadata_ref ->> 'prewarm_origin' = :prewarm_origin
                      AND response_metadata_ref ->> 'prewarm_trigger_identity' = :trigger_identity
                    """
                ),
                {
                    "tenant_id": str(tenant_id),
                    "endpoint": endpoint,
                    "prewarm_origin": B17_P4_PREWARM_ORIGIN,
                    "trigger_identity": trigger_identity,
                },
            )
        ).scalar_one()
        if latest_trigger_age_seconds is not None and float(latest_trigger_age_seconds) < float(
            interval_seconds
        ):
            return B17PrewarmPlan(
                eligible=True,
                should_trigger=False,
                reason="minimum_interval_not_elapsed",
                **plan_base,
            )

    hourly_cap = max(0, int(settings.LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR))
    if hourly_cap > 0:
        tenant_hourly_calls = int(
            (
                await db_session.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM llm_api_calls
                        WHERE tenant_id = :tenant_id
                          AND endpoint = :endpoint
                          AND status = 'success'
                          AND response_metadata_ref ->> 'prewarm_origin' = :prewarm_origin
                          AND created_at >= now() - interval '1 hour'
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "endpoint": endpoint,
                        "prewarm_origin": B17_P4_PREWARM_ORIGIN,
                    },
                )
            ).scalar_one()
        )
        if tenant_hourly_calls >= hourly_cap:
            return B17PrewarmPlan(
                eligible=True,
                should_trigger=False,
                reason="tenant_hourly_cap_reached",
                **plan_base,
            )

    return B17PrewarmPlan(
        eligible=True,
        should_trigger=True,
        reason="triggered",
        **plan_base,
    )
