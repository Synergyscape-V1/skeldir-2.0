"""
Attribution API Routes

Implements attribution operations defined in api-contracts/dist/openapi/v1/attribution.bundled.yaml

Contract Operations:
- GET /api/attribution/revenue/realtime: Get realtime revenue attribution data

All routes use generated Pydantic models from backend/app/schemas/attribution.py
"""

from fastapi import APIRouter, Depends, Header, Request, Response, Security, status
from uuid import UUID
from typing import Annotated, Literal

# Import generated Pydantic models
from app.schemas.attribution import RealtimeRevenueResponse
from app.api.problem_details import problem_details_response
from app.db.deps import get_db_session
from app.security.auth import AuthContext, get_auth_context
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
    operation_id="explainAttributionEntity",
    summary="Get natural language explanation for attribution entities",
    description=(
        "Canonical B1.7 explanation surface. In P0 this route is intentionally mounted "
        "but non-operational for deterministic explanation serving."
    ),
    responses={
        401: {"description": "Unauthorized - invalid or missing authentication"},
        403: {"description": "Forbidden - authenticated but insufficient permissions"},
        404: {"description": "Resource not found"},
        500: {"description": "Internal server error"},
        503: {"description": "Explanation surface exists but is not yet operational"},
    },
    openapi_extra={
        "x-skeldir-b17-p0": {
            "implementation_status": "mounted_not_operational",
            "runtime_contract_mode": {
                "type": "problem_details",
                "status_code": 503,
                "code": "EXPLAIN_SURFACE_NOT_READY",
                "mounted_route_required": True,
                "runtime_openapi_presence_required": True,
            },
        }
    },
)
async def explain_attribution_entity(
    request: Request,
    entity_type: Literal[
        "attribution_score",
        "channel_performance",
        "reconciliation_discrepancy",
    ],
    entity_id: UUID,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
):
    """
    Mounted canonical explanation endpoint for B1.7-P0.

    The surface exists to lock contract/runtime authority convergence. Financially
    authoritative deterministic explanation serving is not enabled in P0.
    """
    _ = (entity_type, entity_id, auth_context.tenant_id)
    error_response = problem_details_response(
        request,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        title="Explanation Surface Not Ready",
        detail=(
            "The canonical explanation endpoint is mounted but deterministic explanation "
            "serving is not operational in B1.7-P0."
        ),
        correlation_id=x_correlation_id,
        type_url="https://api.skeldir.com/problems/explanation-surface-not-ready",
        code="EXPLAIN_SURFACE_NOT_READY",
    )
    error_response.headers["Retry-After"] = "60"
    error_response.headers["Cache-Control"] = "no-store"
    return error_response
