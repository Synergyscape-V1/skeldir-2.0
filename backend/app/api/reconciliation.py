from datetime import datetime, timezone, timedelta
from uuid import UUID, uuid4
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.problem_details import problem_details_response
from app.security.auth import AuthContext, get_auth_context

router = APIRouter()


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@router.get("/status", operation_id="getReconciliationStatus")
async def get_reconciliation_status(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    now = _utcnow_iso()
    return {
        "platforms": [
            {
                "platform_name": "Shopify",
                "connection_status": "verified",
                "last_sync": now,
                "events_processed": 0,
                "revenue_verified": 0.0,
            }
        ],
        "overall_status": "verified",
        "last_full_sync": now,
    }


@router.get("/platform/{platform_id}", operation_id="getPlatformReconciliationStatus")
async def get_platform_reconciliation_status(
    platform_id: str,
    request: Request,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    allowed = {
        "meta": "Meta",
        "google": "Google",
        "tiktok": "TikTok",
        "linkedin": "LinkedIn",
        "shopify": "Shopify",
        "woocommerce": "WooCommerce",
        "stripe": "Stripe",
        "paypal": "PayPal",
    }
    key = platform_id.strip().lower()
    if key not in allowed:
        return problem_details_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            title="Platform Not Found",
            detail=f"Unknown platform_id: {platform_id}",
            correlation_id=x_correlation_id,
            type_url="https://api.skeldir.com/problems/platform-not-found",
        )

    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    now = _utcnow_iso()
    return {
        "platform_name": allowed[key],
        "connection_status": "verified",
        "last_sync": now,
        "events_processed": 0,
        "revenue_verified": 0.0,
    }


@router.post("/sync", status_code=202, operation_id="triggerSync")
async def trigger_sync(
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    _: Annotated[AuthContext, Depends(get_auth_context)],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)
    eta = (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat().replace("+00:00", "Z")
    return {
        "sync_id": str(uuid4()),
        "status": "queued",
        "estimated_completion": eta,
    }
