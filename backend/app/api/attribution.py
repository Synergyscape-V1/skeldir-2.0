"""
Attribution API Routes.

Implements attribution operations defined in
api-contracts/dist/openapi/v1/attribution.bundled.yaml.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, Security, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.problem_details import problem_details_response
from app.core.config import settings
from app.db.deps import get_db_session
from app.llm.output_validation import ATTRIBUTION_FAST_EXPLANATION_VALIDATION_SPEC
from app.llm.provider_boundary import (
    ProviderBoundaryResult,
    get_llm_provider_boundary,
)
from app.schemas.attribution import AttributionExplanationResponse, RealtimeRevenueResponse
from app.schemas.llm_payloads import LLMTaskPayload
from app.security.auth import AuthContext, get_auth_context
from app.services.attribution_explanation_authority import (
    DETERMINISTIC_TRUTH_SOURCES,
    AttributionExplanationAuthorityNotFound,
    AttributionExplanationAuthorityRecord,
    AttributionExplanationAuthorityUnavailable,
    fetch_attribution_explanation_authority,
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
) -> dict[str, Any]:
    return {
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
        "cache_watermark": int(authority.metric_value_cents),
        # Stub-provider deterministic fallback for local/CI paths where external LLM is disabled.
        "simulated_output_text": (
            f"{authority.metric_key} shows metric_value_cents {authority.metric_value_cents} "
            f"against revenue_total_cents {authority.revenue_total_cents}; "
            f"use as non-authoritative context only."
        ),
    }


def _b17_validation_context(
    *,
    authority_metric: dict[str, Any],
    correlation_id: str,
    request_id: str,
) -> dict[str, Any]:
    revenue_context = authority_metric.get("revenue_context", {})
    return {
        "contract_version": "b1.6-p3",
        "feature_surface": "attribution_explanation",
        "request_id": request_id,
        "correlation_id": correlation_id,
        "deterministic_truth_sources": list(DETERMINISTIC_TRUTH_SOURCES),
        "deterministic_truth": {
            "metric_value_cents": authority_metric.get("metric_value_cents"),
            "revenue_total_cents": revenue_context.get("total_revenue_cents"),
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


def _degraded_synthesis_state(
    result: ProviderBoundaryResult | None,
) -> tuple[str, str]:
    if result is None:
        return "provider_failed", "provider_exception"

    failure_reason = str(result.failure_reason or "")
    validation_code = str(result.validation_code or "")
    block_reason = str(result.block_reason or "")
    if failure_reason == "provider_timeout":
        return "timeout", "provider_timeout"
    if result.status == "blocked":
        return "blocked", block_reason or "provider_blocked"
    if failure_reason == "validation_numeric_mismatch" or validation_code == "numeric_mismatch":
        return "validation_rejected", "numeric_mismatch"
    if failure_reason.startswith("validation_") or validation_code in {"schema_failed", "normalization_failed"}:
        return "validation_rejected", failure_reason or validation_code
    return "provider_failed", failure_reason or validation_code or "provider_failed"


def _validated_explanation_payload(
    *,
    summary: str,
    generated_at: datetime,
) -> dict[str, Any]:
    return {
        "explanation_class": "provider_fastpath_validated",
        "synthesis_state": "validated",
        "non_authoritative_summary": summary,
        "degraded": False,
        "degraded_reason": None,
        "generated_at": generated_at,
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
                "ETag": etag,
                "Cache-Control": "max-age=30",
            },
        )

    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "max-age=30"
    return response_data


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

    if (
        llm_result is not None
        and llm_result.status == "success"
        and str(llm_result.validation_code or "success") == "success"
    ):
        non_authoritative_explanation = _validated_explanation_payload(
            summary=str(llm_result.output_text),
            generated_at=explanation_generated_at,
        )
    else:
        synthesis_state, degraded_reason = _degraded_synthesis_state(llm_result)
        non_authoritative_explanation = _degraded_explanation_payload(
            generated_at=explanation_generated_at,
            synthesis_state=synthesis_state,
            degraded_reason=degraded_reason,
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
                llm_result.failure_reason if llm_result is not None else "provider_exception"
            ),
        },
    )
    return {
        "authoritative_metric": authoritative_metric,
        "non_authoritative_explanation": non_authoritative_explanation,
    }
