"""
Attribution API Routes

Implements attribution operations defined in api-contracts/dist/openapi/v1/attribution.bundled.yaml

Contract Operations:
- GET /api/attribution/revenue/realtime: Get realtime revenue attribution data

All routes use generated Pydantic models from backend/app/schemas/attribution.py
"""

import logging
from fastapi import APIRouter, Depends, Header, Request, Response, Security, status
from uuid import UUID
from typing import Annotated, Literal

# Import generated Pydantic models
from app.schemas.attribution import AttributionExplanationResponse, RealtimeRevenueResponse
from app.api.problem_details import problem_details_response
from app.db.deps import get_db_session
from app.security.auth import AuthContext, get_auth_context
from app.services.attribution_explanation_authority import (
    DETERMINISTIC_TRUTH_SOURCES,
    AttributionExplanationAuthorityNotFound,
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
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/revenue/realtime",
    response_model=RealtimeRevenueResponse,
    status_code=200,
    operation_id="getRealtimeRevenue",
    summary="Get realtime revenue attribution data",
    description="Retrieve realtime revenue attribution data with verification status and data freshness"
)
async def get_realtime_revenue(
    request: Request,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
):
    """
    Get realtime revenue attribution data.
    
    Phase B0.6: Cached realtime revenue semantics (interim, unverified).
    
    Contract: GET /api/attribution/revenue/realtime
    Spec: api-contracts/dist/openapi/v1/attribution.bundled.yaml
    
    Returns:
        RealtimeRevenueResponse: Revenue data with verification status
    """
    # Phase B0.6: Cached interim data with unverified semantics.

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
        }
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
    """
    Mounted canonical explanation endpoint for B1.7-P1.

    Route -> service -> DB deterministic authority chain:
      - attribution_allocations (entity-scoped deterministic metric row)
      - revenue_cache_entries (tenant-scoped deterministic revenue context)
    """
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
    summary = (
        "Non-authoritative explanation: deterministic authority reports "
        f"{authority.metric_key}=${authority.metric_value_usd:.2f} for {entity_type} "
        f"{entity_id} using {authority.model_type}/{authority.model_version}."
    )
    return {
        "authoritative_metric": {
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
        },
        "non_authoritative_explanation": {
            "explanation_class": "deterministic_placeholder",
            "non_authoritative_summary": summary,
            "generated_at": authority.last_updated,
            "caveats": [
                "Explanation text is non-authoritative and cannot override deterministic metrics.",
                "Numeric authority comes only from deterministic DB-backed truth sources.",
            ],
        },
    }
