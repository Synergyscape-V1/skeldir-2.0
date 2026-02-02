"""
Attribution API Routes

Implements attribution operations defined in api-contracts/dist/openapi/v1/attribution.bundled.yaml

Contract Operations:
- GET /api/attribution/revenue/realtime: Get realtime revenue attribution data

All routes use generated Pydantic models from backend/app/schemas/attribution.py
"""

from fastapi import APIRouter, Depends, Header, Request, Response, status
from uuid import UUID
from typing import Annotated

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
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
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
    
    from datetime import datetime

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

    now = datetime.now(tz=snapshot.data_as_of.tzinfo)
    data_freshness_seconds = max(
        0, int((now - snapshot.data_as_of).total_seconds())
    )

    response_data = {
        "total_revenue": snapshot.revenue_total_cents / 100.0,
        "event_count": snapshot.event_count,
        "last_updated": snapshot.data_as_of,
        "data_freshness_seconds": data_freshness_seconds,
        "verified": snapshot.verified,
        "tenant_id": str(tenant_id),
        "confidence_score": snapshot.confidence_score,
        "upgrade_notice": snapshot.upgrade_notice,
    }

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
