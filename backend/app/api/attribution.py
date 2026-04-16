"""
Attribution API Routes.

Implements attribution operations defined in
api-contracts/dist/openapi/v1/attribution.bundled.yaml.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
from hashlib import sha256
from typing import Annotated, Any, Literal, Mapping
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Request, Response, Security, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.attribution.strategy_kernel import (
    DETERMINISTIC_BASELINE_MODEL,
    canonical_model_type,
)
from app.core.config import settings
from app.db.deps import get_db_session
from app.db.session import get_session
from app.llm.output_validation import ATTRIBUTION_FAST_EXPLANATION_VALIDATION_SPEC
from app.llm.provider_boundary import (
    ProviderBoundaryResult,
    get_llm_provider_boundary,
)
from app.schemas.attribution import (
    AttributionExplanationResponse,
    ChannelAttribution,
    ChannelAttributionResponse,
    ChannelName,
    RealtimeRevenueResponse,
)
from app.schemas.llm_payloads import LLMTaskPayload
from app.security.auth import AuthContext, get_auth_context
from app.services.attribution_explanation_authority import (
    DETERMINISTIC_TRUTH_SOURCES,
    AttributionExplanationAuthorityNotFound,
    AttributionExplanationAuthorityRecord,
    AttributionExplanationAuthorityUnavailable,
    fetch_attribution_explanation_authority,
)
from app.services.b17_p4_prewarm_policy import (
    B17_P4_COLD_PATH_STRATEGY,
    B17_P4_PREWARM_ORIGIN,
    B17PrewarmPlan,
    plan_b17_p4_event_driven_prewarm,
)
from app.services.realtime_revenue_cache import (
    RealtimeRevenueUnavailable,
    get_realtime_revenue_snapshot,
)
from app.services.realtime_revenue_providers import build_realtime_revenue_fetcher
from app.services.realtime_revenue_response import (
    build_attribution_realtime_revenue_response,
)

router = APIRouter()
logger = logging.getLogger(__name__)

_PROVIDER_BOUNDARY = get_llm_provider_boundary()
_B17_EXPLANATION_ENDPOINT = "app.api.attribution.explanation_fastpath"
_B17_EXPLANATION_CONTRACT_VERSION = "b1.7-p4"
_CHANNEL_MAX_WINDOW_DAYS = 31
_RATIO_QUANTUM = Decimal("0.00001")
_CONFIDENCE_QUANTUM = Decimal("0.001")
_CHANNEL_CODE_TO_NAME: dict[str, ChannelName] = {
    "facebook_brand": ChannelName.Meta,
    "facebook_paid": ChannelName.Meta,
    "meta_ads": ChannelName.Meta,
    "google_search_paid": ChannelName.Google,
    "google_display_paid": ChannelName.Google,
    "google_ads": ChannelName.Google,
    "tiktok_paid": ChannelName.TikTok,
    "tiktok_ads": ChannelName.TikTok,
    "linkedin_paid": ChannelName.LinkedIn,
    "linkedin_ads": ChannelName.LinkedIn,
    "organic": ChannelName.Organic,
    "direct": ChannelName.Direct,
    "email": ChannelName.Email,
    "referral": ChannelName.Referral,
    "unknown": ChannelName.Unknown,
}


def _truth_snapshot_payload(
    authority: AttributionExplanationAuthorityRecord,
) -> dict[str, Any]:
    return {
        "version": authority.truth_snapshot_version,
        "watermark": int(authority.truth_snapshot_watermark),
        "as_of": authority.truth_snapshot_as_of.isoformat().replace("+00:00", "Z"),
        "deterministic_truth_sources": list(DETERMINISTIC_TRUTH_SOURCES),
    }


def _projection_model_type(model_version: str) -> str:
    marker = "::model_type="
    if marker not in model_version:
        return DETERMINISTIC_BASELINE_MODEL
    _, raw_model_type = model_version.rsplit(marker, 1)
    return canonical_model_type(raw_model_type)


def _format_decimal(value: Decimal, quantum: Decimal) -> str:
    return format(value.quantize(quantum, rounding=ROUND_HALF_UP), "f")


def _map_channel_code_to_name(channel_code: str) -> ChannelName:
    normalized = str(channel_code).strip().lower()
    return _CHANNEL_CODE_TO_NAME.get(normalized, ChannelName.Unknown)


def _channels_etag(payload: ChannelAttributionResponse) -> str:
    body = payload.model_dump(mode="json")
    digest = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f'W/"{digest}"'


def _authoritative_metric_payload(
    authority: AttributionExplanationAuthorityRecord,
) -> dict[str, Any]:
    return {
        "entity_type": authority.entity_type,
        "entity_id": str(authority.entity_id),
        "tenant_id": str(authority.tenant_id),
        "metric_key": authority.metric_key,
        "metric_value": authority.metric_value_usd,
        "metric_value_cents": authority.metric_value_cents,
        "currency": "USD",
        "channel_code": authority.channel_code,
        "model_type": authority.model_type,
        "model_version": authority.model_version,
        "confidence_score": authority.confidence_score,
        "verification_state": authority.verification_state,
        "last_updated": authority.last_updated,
        "data_freshness_seconds": authority.data_freshness_seconds,
        "deterministic_truth_sources": list(DETERMINISTIC_TRUTH_SOURCES),
        "truth_snapshot": _truth_snapshot_payload(authority),
        "revenue_context": {
            "cache_key": authority.revenue_cache_key,
            "total_revenue": authority.revenue_total_usd,
            "total_revenue_cents": authority.revenue_total_cents,
            "data_as_of": authority.revenue_data_as_of,
        },
    }


def _b17_explanation_prompt(
    *,
    authority: AttributionExplanationAuthorityRecord,
    entity_type: str,
    entity_id: UUID,
    user_id: UUID,
    model_tier_profile: str,
    prewarm_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    truth_snapshot = _truth_snapshot_payload(authority)
    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return one short non-authoritative explanation sentence (<=320 chars). "
                    "Include exact labels metric_value_cents and revenue_total_cents with "
                    "their deterministic values. Do not add unrelated numbers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"entity_type={entity_type}; entity_id={entity_id}; "
                    f"metric_key={authority.metric_key}; "
                    f"metric_value={authority.metric_value_usd:.2f}; "
                    f"metric_value_cents={authority.metric_value_cents}; "
                    f"revenue_total_cents={authority.revenue_total_cents}; "
                    f"model={authority.model_type}/{authority.model_version}."
                ),
            },
        ],
        "cache_enabled": True,
        "cache_watermark": int(authority.truth_snapshot_watermark),
        "cache_identity": {
            "metric_identity": {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "metric_key": authority.metric_key,
            },
            "filter_window": {
                "filter_profile": "entity_scope_default",
                "time_range": "latest_truth_snapshot",
            },
            "tenant_user_scope": {
                "tenant_id": str(authority.tenant_id),
                "user_id": str(user_id),
            },
            "explanation_contract_version": _B17_EXPLANATION_CONTRACT_VERSION,
            "model_tier_profile": model_tier_profile,
        },
        "truth_snapshot": truth_snapshot,
        "reject_provider_reentry_on_stale": True,
        # Stub-provider deterministic fallback for local/CI paths where external LLM is disabled.
        "simulated_output_text": (
            f"{authority.metric_key} shows metric_value_cents {authority.metric_value_cents} "
            f"against revenue_total_cents {authority.revenue_total_cents}; "
            f"use as non-authoritative context only."
        ),
    }
    if prewarm_context:
        payload["prewarm_context"] = dict(prewarm_context)
    return payload


def _b17_validation_context(
    *,
    authority_metric: dict[str, Any],
    correlation_id: str,
    request_id: str,
) -> dict[str, Any]:
    revenue_context = authority_metric.get("revenue_context", {})
    truth_snapshot = authority_metric.get("truth_snapshot", {})
    return {
        "contract_version": "b1.6-p3",
        "feature_surface": "attribution_explanation",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "deterministic_truth_sources": list(DETERMINISTIC_TRUTH_SOURCES),
        "deterministic_truth": {
            "metric_value_cents": authority_metric.get("metric_value_cents"),
            "revenue_total_cents": revenue_context.get("total_revenue_cents"),
            "truth_snapshot_watermark": truth_snapshot.get("watermark"),
            "truth_snapshot_version": truth_snapshot.get("version"),
        },
        "numeric_claim_bindings": [
            {
                "claim_path": "explanation.metric_value_cents",
                "truth_path": "metric_value_cents",
                "tolerance_ratio": 0.0,
            },
            {
                "claim_path": "explanation.revenue_total_cents",
                "truth_path": "revenue_total_cents",
                "tolerance_ratio": 0.0,
            },
        ],
        "numeric_tolerance_ratio": 0.0,
    }


def _b17_execution_path_state(
    *,
    cache_replay_state: str,
    synthesis_state: str,
    prewarm_assisted: bool,
) -> str:
    if (
        synthesis_state == "stale_replay_rejected"
        or cache_replay_state == "stale_replay_rejected_provider_blocked"
    ):
        return "stale_rejected_provider_blocked"
    if cache_replay_state == "cache_hit_truth_match":
        return "prewarm_assisted_cache_hit" if prewarm_assisted else "warm_cache_hit"
    return "cold_path_generated"


def _b17_prewarm_state_payload(
    *,
    plan: B17PrewarmPlan | None,
    triggered: bool,
    assisted_cache_hit: bool,
    trigger_reason_override: str | None = None,
) -> dict[str, Any]:
    if plan is None:
        return {
            "strategy": B17_P4_COLD_PATH_STRATEGY,
            "trigger_event": "deterministic_truth_change_event",
            "eligible": False,
            "triggered": False,
            "trigger_reason": "prewarm_disabled",
            "target_entity_types": [],
            "target_count": 0,
            "max_permutations_per_trigger": 0,
            "min_trigger_interval_seconds": 0,
            "max_calls_per_tenant_per_hour": 0,
            "call_budget_cents": 0,
            "assisted_cache_hit": assisted_cache_hit,
        }
    return {
        "strategy": plan.strategy,
        "trigger_event": plan.trigger_event,
        "eligible": plan.eligible,
        "triggered": triggered,
        "trigger_reason": trigger_reason_override or plan.reason,
        "target_entity_types": list(plan.target_entity_types),
        "target_count": plan.target_count,
        "max_permutations_per_trigger": plan.max_permutations_per_trigger,
        "min_trigger_interval_seconds": plan.min_trigger_interval_seconds,
        "max_calls_per_tenant_per_hour": plan.max_calls_per_tenant_per_hour,
        "call_budget_cents": plan.call_budget_cents,
        "assisted_cache_hit": assisted_cache_hit,
    }


def _b17_prewarm_prompt_context(
    *,
    plan: B17PrewarmPlan,
    target_entity_type: str,
) -> dict[str, Any]:
    return {
        "prewarm_origin": B17_P4_PREWARM_ORIGIN,
        "prewarm_strategy": plan.strategy,
        "prewarm_trigger_event": plan.trigger_event,
        "prewarm_trigger_identity": plan.trigger_identity,
        "prewarm_truth_watermark": int(plan.truth_watermark),
        "prewarm_target_entity_type": target_entity_type,
        "allow_stale_refresh": True,
    }


def _b17_prewarm_targets_for_dispatch(
    *,
    plan: B17PrewarmPlan,
    request_entity_type: str,
) -> tuple[str, ...]:
    return tuple(
        entity_type
        for entity_type in plan.target_entity_types
        if entity_type != request_entity_type
    )


async def _execute_b17_prewarm_targets(
    *,
    plan: B17PrewarmPlan,
    tenant_id: UUID,
    user_id: UUID,
    entity_id: UUID,
    correlation_id: str,
    request_entity_type: str,
) -> int:
    dispatched = 0
    targets = _b17_prewarm_targets_for_dispatch(
        plan=plan,
        request_entity_type=request_entity_type,
    )
    if not targets:
        return 0

    async with get_session(tenant_id=tenant_id, user_id=user_id) as session:
        for target_entity_type in targets:
            try:
                authority = await fetch_attribution_explanation_authority(
                    db_session=session,
                    tenant_id=tenant_id,
                    entity_type=target_entity_type,  # type: ignore[arg-type]
                    entity_id=entity_id,
                )
            except (
                AttributionExplanationAuthorityNotFound,
                AttributionExplanationAuthorityUnavailable,
            ):
                continue
            llm_payload = LLMTaskPayload(
                tenant_id=tenant_id,
                user_id=user_id,
                correlation_id=correlation_id,
                request_id=f"{uuid4()}",
                prompt=_b17_explanation_prompt(
                    authority=authority,
                    entity_type=target_entity_type,
                    entity_id=entity_id,
                    user_id=user_id,
                    model_tier_profile=settings.LLM_B17_EXPLANATION_FAST_TIER,
                    prewarm_context=_b17_prewarm_prompt_context(
                        plan=plan,
                        target_entity_type=target_entity_type,
                    ),
                ),
                max_cost_cents=max(0, int(settings.LLM_B17_PREWARM_CALL_BUDGET_CENTS)),
            )
            try:
                await _PROVIDER_BOUNDARY.complete(
                    model=llm_payload,
                    session=session,
                    endpoint=_B17_EXPLANATION_ENDPOINT,
                    validation_spec=ATTRIBUTION_FAST_EXPLANATION_VALIDATION_SPEC,
                    validation_context=_b17_validation_context(
                        authority_metric=_authoritative_metric_payload(authority),
                        correlation_id=correlation_id,
                        request_id=llm_payload.request_id or correlation_id,
                    ),
                    routing_tier_override=settings.LLM_B17_EXPLANATION_FAST_TIER,
                    timeout_ms_override=settings.LLM_B17_PREWARM_TIMEOUT_MS,
                )
                dispatched += 1
            except Exception:
                logger.exception(
                    "b17_p4_prewarm_target_failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "correlation_id": correlation_id,
                        "event_type": "attribution.explanation.prewarm_target_failed",
                        "target_entity_type": target_entity_type,
                        "target_entity_id": str(entity_id),
                    },
                )
    return dispatched


def _degraded_synthesis_state(
    result: ProviderBoundaryResult | None,
) -> tuple[str, str]:
    if result is None:
        return "provider_failed", "provider_exception"

    failure_reason = str(result.failure_reason or "")
    validation_code = str(result.validation_code or "")
    block_reason = str(result.block_reason or "")
    if (
        failure_reason == "stale_replay_rejected"
        or block_reason == "stale_replay_rejected"
    ):
        return "stale_replay_rejected", "stale_replay_rejected"
    if failure_reason == "provider_timeout":
        return "timeout", "provider_timeout"
    if result.status == "blocked":
        return "blocked", block_reason or "provider_blocked"
    if (
        failure_reason == "validation_numeric_mismatch"
        or validation_code == "numeric_mismatch"
    ):
        return "validation_rejected", "numeric_mismatch"
    if failure_reason.startswith("validation_") or validation_code in {
        "schema_failed",
        "normalization_failed",
    }:
        return "validation_rejected", failure_reason or validation_code
    return "provider_failed", failure_reason or validation_code or "provider_failed"


def _validated_explanation_payload(
    *,
    summary: str,
    generated_at: datetime,
    truth_snapshot: dict[str, Any],
    cache_replay_state: str,
    provider_reentry_blocked: bool,
    execution_path_state: str,
    prewarm_state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "explanation_class": "provider_fastpath_validated",
        "synthesis_state": "validated",
        "non_authoritative_summary": summary,
        "degraded": False,
        "degraded_reason": None,
        "generated_at": generated_at,
        "truth_snapshot": truth_snapshot,
        "cache_replay_state": cache_replay_state,
        "provider_reentry_blocked": provider_reentry_blocked,
        "execution_path_state": execution_path_state,
        "cold_path_strategy": B17_P4_COLD_PATH_STRATEGY,
        "prewarm_state": prewarm_state,
        "explanation_contract_version": _B17_EXPLANATION_CONTRACT_VERSION,
        "caveats": [
            "Explanation text is non-authoritative and cannot override deterministic metrics.",
            "Numeric authority remains deterministic and tenant-scoped.",
        ],
    }


def _degraded_explanation_payload(
    *,
    generated_at: datetime,
    synthesis_state: str,
    degraded_reason: str,
    truth_snapshot: dict[str, Any],
    cache_replay_state: str,
    provider_reentry_blocked: bool,
    execution_path_state: str,
    prewarm_state: dict[str, Any],
) -> dict[str, Any]:
    return {
        "explanation_class": "provider_fastpath_degraded",
        "synthesis_state": synthesis_state,
        "non_authoritative_summary": (
            "Explanation sidecar was suppressed; deterministic authority remains intact."
        ),
        "degraded": True,
        "degraded_reason": degraded_reason,
        "generated_at": generated_at,
        "truth_snapshot": truth_snapshot,
        "cache_replay_state": cache_replay_state,
        "provider_reentry_blocked": provider_reentry_blocked,
        "execution_path_state": execution_path_state,
        "cold_path_strategy": B17_P4_COLD_PATH_STRATEGY,
        "prewarm_state": prewarm_state,
        "explanation_contract_version": _B17_EXPLANATION_CONTRACT_VERSION,
        "caveats": [
            "Explanation text is non-authoritative and cannot override deterministic metrics.",
            "Deterministic authority remains the only source of financial truth.",
        ],
    }


@router.get(
    "/revenue/realtime",
    response_model=RealtimeRevenueResponse,
    status_code=200,
    operation_id="getRealtimeRevenue",
    summary="Get realtime revenue attribution data",
    description="Retrieve realtime revenue attribution data with verification status and data freshness",
)
async def get_realtime_revenue(
    request: Request,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
):
    tenant_id = auth_context.tenant_id
    try:
        snapshot, etag, _ = await get_realtime_revenue_snapshot(
            db_session,
            tenant_id,
            fetcher=build_realtime_revenue_fetcher(
                db_session,
                x_correlation_id,
            ),
        )
    except RealtimeRevenueUnavailable as exc:
        error_response = problem_details_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Upstream Unavailable",
            detail="Realtime revenue refresh unavailable. Retry later.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/realtime-revenue-unavailable",
        )
        error_response.headers["Retry-After"] = str(exc.retry_after_seconds)
        error_response.headers["Cache-Control"] = "no-store"
        return error_response

    response_data = build_attribution_realtime_revenue_response(
        snapshot,
        tenant_id,
    )

    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "X-Correlation-ID": str(x_correlation_id),
                "ETag": etag,
                "Cache-Control": "max-age=30",
            },
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=30"
    return response_data


@router.get(
    "/channels",
    response_model=ChannelAttributionResponse,
    status_code=200,
    responses={
        304: {
            "description": "Not Modified - ETag matches, use cached data",
            "headers": {
                "X-Correlation-ID": {
                    "schema": {"type": "string", "format": "uuid"},
                },
                "ETag": {
                    "schema": {"type": "string"},
                },
            },
        },
        404: {"description": "Projection not found for tenant"},
        409: {"description": "Projection identity mismatch or projection not succeeded"},
        422: {"description": "Projection window exceeds maximum supported range"},
    },
    operation_id="getChannelAttribution",
    summary="Get Channel Attribution Data",
    description=(
        "Returns deterministic channel attribution from persisted allocation rows "
        "for one authoritative projection identity."
    ),
    openapi_extra={
        "x-skeldir-b21-p3": {
            "implementation_status": "mounted_persisted_projection_authority_surface",
            "projection_identity": {
                "required_query_parameters": ["model_type", "recompute_job_id"],
                "cross_model_aggregation_forbidden": True,
                "tenant_only_projection_forbidden": True,
                "synchronous_recompute_on_read_forbidden": True,
            },
            "bounded_read_physics": {
                "max_window_days": _CHANNEL_MAX_WINDOW_DAYS,
                "fail_closed_on_unbounded_shape": True,
            },
            "precision_transport": {
                "allocation_ratio": "decimal_string_scale_5",
                "attribution_weight": "decimal_string_scale_5",
                "confidence_score": "decimal_string_scale_3",
            },
        }
    },
)
async def get_channel_attribution(
    request: Request,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    model_type: Annotated[
        Literal[
            "deterministic_baseline",
            "first_touch",
            "last_touch",
            "linear",
            "time_decay",
        ],
        Query(description="Deterministic model projection selector"),
    ],
    recompute_job_id: Annotated[
        UUID,
        Query(description="Deterministic recompute projection identity"),
    ],
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
):
    tenant_id = auth_context.tenant_id
    canonical_model = canonical_model_type(model_type)
    projection_row = (
        await db_session.execute(
            text(
                """
                SELECT
                    id,
                    window_start,
                    window_end,
                    model_version,
                    status,
                    COALESCE(updated_at, created_at) AS projection_last_updated
                FROM attribution_recompute_jobs
                WHERE tenant_id = :tenant_id
                  AND id = :recompute_job_id
                LIMIT 1
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "recompute_job_id": str(recompute_job_id),
            },
        )
    ).mappings().first()
    if projection_row is None:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Projection Not Found",
            detail=(
                "No deterministic recompute projection exists for the specified "
                "tenant/model identity."
            ),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-not-found",
            code="ATTRIBUTION_PROJECTION_NOT_FOUND",
        )

    projection_status = str(projection_row["status"] or "").strip().lower()
    if projection_status != "succeeded":
        return problem_details_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            title="Projection Not Succeeded",
            detail=(
                "Deterministic projection exists but is not in succeeded status; "
                "read is fail-closed."
            ),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-status-conflict",
            code="ATTRIBUTION_PROJECTION_STATUS_CONFLICT",
        )

    try:
        projection_model_type = _projection_model_type(str(projection_row["model_version"]))
    except ValueError as exc:
        return problem_details_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            title="Projection Identity Conflict",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-identity-conflict",
            code="ATTRIBUTION_PROJECTION_IDENTITY_CONFLICT",
        )
    if projection_model_type != canonical_model:
        return problem_details_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            title="Projection Identity Conflict",
            detail=(
                f"Requested model_type={canonical_model} does not match persisted "
                f"projection model_type={projection_model_type}."
            ),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-identity-conflict",
            code="ATTRIBUTION_PROJECTION_IDENTITY_CONFLICT",
        )

    window_start = projection_row["window_start"]
    window_end = projection_row["window_end"]
    if not isinstance(window_start, datetime) or not isinstance(window_end, datetime):
        return problem_details_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            title="Projection Window Invalid",
            detail="Persisted recompute projection window is invalid.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-window-invalid",
            code="ATTRIBUTION_PROJECTION_WINDOW_INVALID",
        )
    window_start = window_start.astimezone(timezone.utc)
    window_end = window_end.astimezone(timezone.utc)
    if window_end <= window_start:
        return problem_details_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            title="Projection Window Invalid",
            detail="Persisted recompute projection window bounds are invalid.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-projection-window-invalid",
            code="ATTRIBUTION_PROJECTION_WINDOW_INVALID",
        )

    if window_end - window_start > timedelta(days=_CHANNEL_MAX_WINDOW_DAYS):
        return problem_details_response(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Projection Window Too Large",
            detail=(
                f"Requested projection window exceeds {_CHANNEL_MAX_WINDOW_DAYS} days; "
                "read is fail-closed."
            ),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/attribution-window-out-of-range",
            code="ATTRIBUTION_WINDOW_OUT_OF_RANGE",
        )

    result = await db_session.execute(
        text(
            """
            SELECT
                aa.channel_code,
                COALESCE(SUM(aa.allocated_revenue_cents), 0)::bigint AS revenue_cents,
                COUNT(DISTINCT aa.event_id)::bigint AS conversion_count,
                COALESCE(AVG(aa.confidence_score), 0)::numeric AS confidence_score,
                MAX(COALESCE(aa.updated_at, aa.created_at)) AS channel_last_updated
            FROM attribution_allocations aa
            JOIN attribution_events e
              ON e.id = aa.event_id
             AND e.tenant_id = aa.tenant_id
            WHERE aa.tenant_id = :tenant_id
              AND aa.recompute_job_id = :recompute_job_id
              AND aa.model_type = :model_type
              AND e.occurred_at >= :window_start
              AND e.occurred_at < :window_end
            GROUP BY aa.channel_code
            ORDER BY revenue_cents DESC, aa.channel_code ASC
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "recompute_job_id": str(recompute_job_id),
            "model_type": canonical_model,
            "window_start": window_start,
            "window_end": window_end,
        },
    )

    channels: list[ChannelAttribution] = []
    last_updated_candidates: list[datetime] = []
    rows = result.fetchall()
    total_revenue_cents = sum(int(row.revenue_cents) for row in rows)
    for row in rows:
        revenue_cents = int(row.revenue_cents)
        confidence = Decimal(str(row.confidence_score or "0"))
        if total_revenue_cents > 0:
            ratio = Decimal(revenue_cents) / Decimal(total_revenue_cents)
        else:
            ratio = Decimal("0")
        ratio_str = _format_decimal(ratio, _RATIO_QUANTUM)
        confidence_str = _format_decimal(confidence, _CONFIDENCE_QUANTUM)
        channels.append(
            ChannelAttribution(
                channel_name=_map_channel_code_to_name(str(row.channel_code)),
                channel_code=str(row.channel_code),
                revenue=round(revenue_cents / 100.0, 2),
                revenue_cents=revenue_cents,
                conversion_count=int(row.conversion_count),
                allocation_ratio=ratio_str,
                attribution_weight=ratio_str,
                confidence_score=confidence_str,
                spend=None,
                roas=None,
            )
        )
        channel_last_updated = row.channel_last_updated
        if isinstance(channel_last_updated, datetime):
            last_updated_candidates.append(channel_last_updated.astimezone(timezone.utc))
    projection_last_updated = projection_row["projection_last_updated"]
    if isinstance(projection_last_updated, datetime):
        last_updated_candidates.append(projection_last_updated.astimezone(timezone.utc))

    now_utc = datetime.now(timezone.utc)
    last_updated = max(last_updated_candidates) if last_updated_candidates else now_utc
    total_revenue = round(total_revenue_cents / 100.0, 2)
    data_freshness_seconds = max(0, int((now_utc - last_updated).total_seconds()))

    response_payload = ChannelAttributionResponse(
        projection={
            "recompute_job_id": str(recompute_job_id),
            "model_type": canonical_model,
            "model_version": str(projection_row["model_version"]),
            "window_start": window_start,
            "window_end": window_end,
        },
        channels=channels,
        total_revenue=total_revenue,
        total_revenue_cents=total_revenue_cents,
        tenant_id=str(tenant_id),
        last_updated=last_updated,
        data_freshness_seconds=data_freshness_seconds,
    )
    etag = _channels_etag(response_payload)
    if if_none_match and if_none_match.strip() == etag:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={
                "X-Correlation-ID": str(x_correlation_id),
                "ETag": etag,
                "Cache-Control": "max-age=30",
            },
        )

    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=30"
    return response_payload


@router.get(
    "/explain/{entity_type}/{entity_id}",
    response_model=AttributionExplanationResponse,
    operation_id="explainAttributionEntity",
    summary="Get natural language explanation for attribution entities",
    description=(
        "Canonical B1.7 explanation surface with deterministic DB-backed authority "
        "read semantics and explicit authority/explanation payload separation."
    ),
    responses={
        401: {"description": "Unauthorized - invalid or missing authentication"},
        403: {"description": "Forbidden - authenticated but insufficient permissions"},
        404: {"description": "Resource not found"},
        409: {"description": "Authority contract violation"},
        500: {"description": "Internal server error"},
        503: {"description": "Deterministic authority unavailable"},
    },
    openapi_extra={
        "x-skeldir-b17-p1": {
            "implementation_status": "mounted_operational_authority_read",
            "authority_model": {
                "deterministic_truth_domain": "attribution_authority",
                "required_truth_sources": list(DETERMINISTIC_TRUTH_SOURCES),
                "required_response_separation": {
                    "authoritative_metric_payload_required": True,
                    "non_authoritative_explanation_payload_required": True,
                    "merged_payload_forbidden": True,
                },
            },
        },
        "x-skeldir-b17-p2": {
            "implementation_status": "mounted_fastpath_sidecar_validation_bound",
            "fast_tier_profile": {
                "provider_neutral": True,
                "config_key": "LLM_B17_EXPLANATION_FAST_TIER",
            },
            "fast_timeout_profile": {
                "config_key": "LLM_B17_EXPLANATION_TIMEOUT_MS",
                "fail_open_forbidden": True,
            },
            "output_envelope": {
                "schema_key": "attribution_explanation_fastpath_v1",
                "summary_max_length": 320,
            },
        },
        "x-skeldir-b17-p3": {
            "implementation_status": "deterministic_watermark_cache_identity_replay_rejection",
            "cache_replay_topology": {
                "authoritative_watermark_lookup_required_before_cache_replay": True,
                "route_entry_cache_before_authority_lookup_forbidden": True,
                "determinant_complete_identity_required": True,
                "prompt_hash_only_identity_forbidden": True,
            },
            "stale_replay_policy": {
                "stale_replay_rejection_required": True,
                "provider_reentry_on_stale_forbidden": True,
                "classification_required": True,
            },
            "citation_coherence": {
                "structured_truth_snapshot_required": True,
                "text_embedding_only_forbidden": True,
            },
        },
        "x-skeldir-b17-p4": {
            "implementation_status": "cold_path_strategy_closed_with_bounded_event_prewarm",
            "cold_path_strategy": {
                "decision": "prewarm_required",
                "selection_basis": (
                    "cold_path_provider_latency_exceeds_endpoint_target_without "
                    "bounded deterministic prewarm"
                ),
                "representative_mixed_workload_required": True,
                "warm_path_only_proof_forbidden": True,
                "ordinary_pr_ci_live_vendor_load_forbidden": True,
            },
            "execution_metadata": {
                "schema_required_fields": [
                    "execution_path_state",
                    "cold_path_strategy",
                    "prewarm_state",
                ],
                "path_classes": [
                    "warm_cache_hit",
                    "cold_path_generated",
                    "stale_rejected_provider_blocked",
                    "prewarm_assisted_cache_hit",
                ],
            },
            "prewarm_policy": {
                "trigger_mode": "deterministic_truth_change_event",
                "default_cron_forbidden": True,
                "eligibility_policy": "bounded_companion_entity_types",
                "max_permutations_per_trigger_config_key": (
                    "LLM_B17_PREWARM_MAX_PERMUTATIONS_PER_TRIGGER"
                ),
                "min_trigger_interval_seconds_config_key": (
                    "LLM_B17_PREWARM_MIN_TRIGGER_INTERVAL_SECONDS"
                ),
                "max_calls_per_tenant_per_hour_config_key": (
                    "LLM_B17_PREWARM_MAX_CALLS_PER_TENANT_PER_HOUR"
                ),
                "call_budget_cents_config_key": "LLM_B17_PREWARM_CALL_BUDGET_CENTS",
            },
        },
    },
)
async def explain_attribution_entity(
    request: Request,
    response: Response,
    entity_type: Literal[
        "attribution_score",
        "channel_performance",
        "reconciliation_discrepancy",
    ],
    entity_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
):
    tenant_id = auth_context.tenant_id
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    if not hasattr(db_session, "execute"):
        error_response = problem_details_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Deterministic Authority Unavailable",
            detail="Deterministic authority DB session is unavailable in contract-testing mode.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/deterministic-authority-unavailable",
            code="DETERMINISTIC_AUTHORITY_UNAVAILABLE",
        )
        error_response.headers["Retry-After"] = "30"
        error_response.headers["Cache-Control"] = "no-store"
        return error_response

    try:
        authority = await fetch_attribution_explanation_authority(
            db_session=db_session,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    except AttributionExplanationAuthorityNotFound:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Not Found",
            detail="Deterministic authority metric does not exist for this tenant/entity.",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/not-found",
            code="NOT_FOUND",
        )
    except AttributionExplanationAuthorityUnavailable as exc:
        error_response = problem_details_response(
            request,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            title="Deterministic Authority Unavailable",
            detail=str(exc),
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/deterministic-authority-unavailable",
            code="DETERMINISTIC_AUTHORITY_UNAVAILABLE",
        )
        error_response.headers["Retry-After"] = "30"
        error_response.headers["Cache-Control"] = "no-store"
        return error_response

    logger.info(
        "attribution_explanation_authority_read",
        extra={
            "tenant_id": str(tenant_id),
            "correlation_id": str(x_correlation_id),
            "event_type": "attribution.explanation.authority_read",
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        },
    )

    authoritative_metric = _authoritative_metric_payload(authority)
    request_id = str(x_correlation_id)
    correlation_id = str(x_correlation_id)
    llm_result: ProviderBoundaryResult | None = None
    explanation_generated_at = datetime.now(timezone.utc)
    try:
        llm_payload = LLMTaskPayload(
            tenant_id=tenant_id,
            user_id=auth_context.user_id,
            correlation_id=correlation_id,
            request_id=request_id,
            prompt=_b17_explanation_prompt(
                authority=authority,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=auth_context.user_id,
                model_tier_profile=settings.LLM_B17_EXPLANATION_FAST_TIER,
            ),
            max_cost_cents=max(0, int(settings.LLM_B17_EXPLANATION_MAX_COST_CENTS)),
        )
        llm_result = await _PROVIDER_BOUNDARY.complete(
            model=llm_payload,
            session=db_session,
            endpoint=_B17_EXPLANATION_ENDPOINT,
            validation_spec=ATTRIBUTION_FAST_EXPLANATION_VALIDATION_SPEC,
            validation_context=_b17_validation_context(
                authority_metric=authoritative_metric,
                correlation_id=correlation_id,
                request_id=request_id,
            ),
            routing_tier_override=settings.LLM_B17_EXPLANATION_FAST_TIER,
            timeout_ms_override=settings.LLM_B17_EXPLANATION_TIMEOUT_MS,
        )
    except Exception:
        logger.exception(
            "attribution_explanation_sidecar_failed",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "event_type": "attribution.explanation.sidecar_failed",
                "entity_type": entity_type,
                "entity_id": str(entity_id),
            },
        )
        llm_result = None

    result_success = (
        llm_result is not None
        and llm_result.status == "success"
        and str(llm_result.validation_code or "success") == "success"
    )

    metadata = (
        dict(llm_result.response_metadata)
        if llm_result is not None and isinstance(llm_result.response_metadata, Mapping)
        else {}
    )
    cache_replay_state = str(
        metadata.get("cache_replay_state")
        or ("cache_hit_truth_match" if result_success else "cold_miss_provider_allowed")
    )
    provider_reentry_blocked = bool(
        metadata.get(
            "provider_reentry_blocked",
            cache_replay_state == "stale_replay_rejected_provider_blocked",
        )
    )
    prewarm_assisted = bool(
        metadata.get("prewarm_assisted")
        or metadata.get("prewarm_origin") == B17_P4_PREWARM_ORIGIN
    )
    synthesis_state, degraded_reason = (
        ("validated", "")
        if result_success
        else _degraded_synthesis_state(llm_result)
    )
    execution_path_state = _b17_execution_path_state(
        cache_replay_state=cache_replay_state,
        synthesis_state=synthesis_state,
        prewarm_assisted=prewarm_assisted,
    )

    prewarm_plan = await plan_b17_p4_event_driven_prewarm(
        db_session=db_session,
        tenant_id=tenant_id,
        user_id=auth_context.user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        truth_watermark=authority.truth_snapshot_watermark,
        endpoint=_B17_EXPLANATION_ENDPOINT,
    )
    prewarm_trigger_reason_override: str | None = None
    prewarm_should_trigger = (
        prewarm_plan.should_trigger
        and execution_path_state != "stale_rejected_provider_blocked"
    )
    if prewarm_plan.should_trigger and not prewarm_should_trigger:
        prewarm_trigger_reason_override = "stale_replay_path_suppressed"
    prewarm_triggered = False
    if prewarm_should_trigger:
        if settings.LLM_B17_PREWARM_RUN_SYNC:
            prewarm_triggered = (
                await _execute_b17_prewarm_targets(
                    plan=prewarm_plan,
                    tenant_id=tenant_id,
                    user_id=auth_context.user_id,
                    entity_id=entity_id,
                    correlation_id=correlation_id,
                    request_entity_type=entity_type,
                )
                > 0
            )
        else:
            prewarm_triggered = True
            asyncio.create_task(
                _execute_b17_prewarm_targets(
                    plan=prewarm_plan,
                    tenant_id=tenant_id,
                    user_id=auth_context.user_id,
                    entity_id=entity_id,
                    correlation_id=correlation_id,
                    request_entity_type=entity_type,
                )
            )
    if prewarm_plan.eligible:
        logger.info(
            "attribution_explanation_prewarm_decision",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "event_type": "attribution.explanation.prewarm_decision",
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "prewarm_reason": prewarm_trigger_reason_override or prewarm_plan.reason,
                "prewarm_should_trigger": prewarm_should_trigger,
                "prewarm_triggered": prewarm_triggered,
                "prewarm_target_count": prewarm_plan.target_count,
                "prewarm_targets": list(prewarm_plan.target_entity_types),
                "prewarm_truth_watermark": int(prewarm_plan.truth_watermark),
            },
        )

    prewarm_state = _b17_prewarm_state_payload(
        plan=prewarm_plan,
        triggered=prewarm_triggered,
        assisted_cache_hit=prewarm_assisted,
        trigger_reason_override=prewarm_trigger_reason_override,
    )

    if result_success:
        non_authoritative_explanation = _validated_explanation_payload(
            summary=str(llm_result.output_text),
            generated_at=explanation_generated_at,
            truth_snapshot=dict(authoritative_metric.get("truth_snapshot", {})),
            cache_replay_state=cache_replay_state,
            provider_reentry_blocked=provider_reentry_blocked,
            execution_path_state=execution_path_state,
            prewarm_state=prewarm_state,
        )
    else:
        non_authoritative_explanation = _degraded_explanation_payload(
            generated_at=explanation_generated_at,
            synthesis_state=synthesis_state,
            degraded_reason=degraded_reason,
            truth_snapshot=dict(authoritative_metric.get("truth_snapshot", {})),
            cache_replay_state=cache_replay_state,
            provider_reentry_blocked=provider_reentry_blocked,
            execution_path_state=execution_path_state,
            prewarm_state=prewarm_state,
        )

    logger.info(
        "attribution_explanation_sidecar_outcome",
        extra={
            "tenant_id": str(tenant_id),
            "correlation_id": correlation_id,
            "event_type": "attribution.explanation.sidecar",
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "sidecar_status": (
                llm_result.status if llm_result is not None else "provider_exception"
            ),
            "sidecar_validation_code": (
                llm_result.validation_code if llm_result is not None else None
            ),
            "sidecar_failure_reason": (
                llm_result.failure_reason
                if llm_result is not None
                else "provider_exception"
            ),
            "sidecar_cache_replay_state": non_authoritative_explanation.get(
                "cache_replay_state"
            ),
            "sidecar_execution_path_state": non_authoritative_explanation.get(
                "execution_path_state"
            ),
            "sidecar_provider_reentry_blocked": non_authoritative_explanation.get(
                "provider_reentry_blocked"
            ),
            "sidecar_prewarm_assisted_cache_hit": (
                non_authoritative_explanation.get("prewarm_state", {}).get(
                    "assisted_cache_hit"
                )
            ),
            "sidecar_prewarm_triggered": (
                non_authoritative_explanation.get("prewarm_state", {}).get(
                    "triggered"
                )
            ),
        },
    )
    return {
        "authoritative_metric": authoritative_metric,
        "non_authoritative_explanation": non_authoritative_explanation,
    }
