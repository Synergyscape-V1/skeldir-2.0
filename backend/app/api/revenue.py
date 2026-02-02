"""
Revenue API Routes (B0.6 Interim)

Canonical v1 surface for realtime revenue. Interim semantics: verified=false,
Postgres-backed cache + singleflight to prevent platform stampede.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db_session
from app.schemas.revenue import RealtimeRevenueV1Response
from app.security.auth import AuthContext, get_auth_context
from app.services.realtime_revenue_cache import (
    RealtimeRevenueUnavailable,
    get_realtime_revenue_snapshot,
)
from app.services.realtime_revenue_providers import build_realtime_revenue_fetcher
from app.api.problem_details import problem_details_response

router = APIRouter()


@router.get(
    "/revenue/realtime",
    response_model=RealtimeRevenueV1Response,
    status_code=200,
    operation_id="getRealtimeRevenueV1",
    summary="Get realtime revenue (v1, interim)",
    description="Return interim realtime revenue payload aligned to B0.6 contract.",
)
async def get_realtime_revenue_v1(
    request: Request,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
):
    """
    Canonical v1 realtime revenue endpoint.

    Contract: GET /api/v1/revenue/realtime
    Spec: api-contracts/dist/openapi/v1/revenue.bundled.yaml
    """
    tenant_id = auth_context.tenant_id
    try:
        snapshot, _, _ = await get_realtime_revenue_snapshot(
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

    response.headers["Cache-Control"] = "max-age=30"
    return {
        "tenant_id": str(tenant_id),
        "interval": snapshot.interval,
        "currency": snapshot.currency,
        "revenue_total": snapshot.revenue_total_cents / 100.0,
        "verified": snapshot.verified,
        "data_as_of": snapshot.data_as_of,
        "sources": snapshot.sources,
    }
