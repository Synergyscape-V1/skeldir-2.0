"""
Webhook ingress endpoints for Shopify, Stripe, PayPal, WooCommerce.

Responsibilities:
- Resolve tenant via API key header (X-Skeldir-Tenant-Key)
- Verify vendor signatures using per-tenant secrets
- Apply PII stripping (handled by middleware) and ingest via EventIngestionService
- Return 200 for success and DLQ-routed validation failures; 401 for signature/tenant failures
"""
from datetime import datetime, timezone
from uuid import uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi import Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.tenant_context import get_tenant_with_webhook_secrets
from app.db.session import get_session
from app.ingestion.event_service import ingest_with_transaction
from app.models import DeadEvent
from app.schemas.webhooks_shopify import ShopifyOrderCreateRequest
from app.schemas.webhooks_stripe import StripePaymentIntentSucceededRequest
from app.schemas.webhooks_paypal import PayPalSaleCompletedRequest
from app.schemas.webhooks_woocommerce import WooCommerceOrderCompletedRequest
from app.observability.context import (
    set_tenant_id,
    set_business_correlation_id,
    get_request_correlation_id,
)
from app.webhooks.signatures import (
    verify_shopify_signature,
    verify_stripe_signature,
    verify_paypal_signature,
    verify_woocommerce_signature,
)

router = APIRouter()


class WebhookResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    dead_event_id: Optional[str] = None
    channel: Optional[str] = None
    error: Optional[str] = None


class WebhookErrorResponse(BaseModel):
    status: str
    vendor: Optional[str] = None


async def tenant_secrets(request: Request):
    api_key = request.headers.get(settings.TENANT_API_KEY_HEADER)
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "invalid_tenant_key"},
        )
    tenant_info = await get_tenant_with_webhook_secrets(api_key)
    set_tenant_id(tenant_info["tenant_id"])
    return tenant_info


def _make_correlation_uuid(idempotency_key: str):
    return uuid5(NAMESPACE_URL, idempotency_key)


async def _handle_ingestion(tenant_id, event_data: dict, idempotency_key: str, source: str):
    event_data = {**event_data, "idempotency_key": idempotency_key}
    # Use transactional helper to preserve DLQ commits on validation errors
    result = await ingest_with_transaction(
        tenant_id=tenant_id,
        event_data=event_data,
        idempotency_key=idempotency_key,
        source=source,
    )
    if result.get("status") == "success":
        return {
            "status": "success",
            "event_id": result.get("event_id"),
            "idempotency_key": idempotency_key,
            "channel": result.get("channel"),
        }

    # Validation errors routed to DLQ: locate the dead_event using correlation_id
    correlation_id = _make_correlation_uuid(idempotency_key)
    async with get_session(tenant_id=tenant_id) as session:
        from sqlalchemy import select
        res = await session.execute(
            select(DeadEvent).where(DeadEvent.correlation_id == correlation_id)
        )
        dead_event = res.scalar_one_or_none()
        if not dead_event:
            res2 = await session.execute(
                select(DeadEvent).order_by(DeadEvent.ingested_at.desc())
            )
            dead_event = res2.scalars().first()

    return {
        "status": "dlq_routed",
        "dead_event_id": str(dead_event.id) if dead_event else None,
        "error": result.get("error"),
    }


@router.post(
    "/webhooks/shopify/order_create",
    response_model=WebhookResponse,
    responses={401: {"model": WebhookErrorResponse}},
)
async def shopify_order_create(
    request: Request,
    payload: ShopifyOrderCreateRequest = Body(...),
    x_shopify_hmac_sha256: str = Header(None, alias="X-Shopify-Hmac-Sha256"),
    tenant_info=Depends(tenant_secrets),
):
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if not verify_shopify_signature(raw_body, tenant_info["shopify_webhook_secret"], x_shopify_hmac_sha256):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "shopify"},
        )

    if not payload.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing order id")

    idempotency_key = str(uuid5(NAMESPACE_URL, f"shopify_order_create_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    event_data = {
        "event_type": "purchase",
        "event_timestamp": (payload.created_at or datetime.now(timezone.utc)).isoformat(),
        "revenue_amount": payload.total_price or "0",
        "currency": payload.currency or "USD",
        "session_id": str(uuid5(NAMESPACE_URL, f"shopify:{payload.id}")),
        "vendor": "shopify",
        "utm_source": "shopify",
        "external_event_id": str(payload.id),
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(tenant_info["tenant_id"], event_data, idempotency_key, source="shopify")


@router.post(
    "/webhooks/stripe/payment_intent_succeeded",
    response_model=WebhookResponse,
    responses={401: {"model": WebhookErrorResponse}},
)
async def stripe_payment_intent_succeeded(
    request: Request,
    payload: StripePaymentIntentSucceededRequest = Body(...),
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    tenant_info=Depends(tenant_secrets),
):
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if not verify_stripe_signature(raw_body, tenant_info["stripe_webhook_secret"], stripe_signature):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "stripe"},
        )

    if not payload.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing payment intent id")

    idempotency_key = str(uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    ts = datetime.fromtimestamp(payload.created) if payload.created else datetime.now(timezone.utc)
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": str((payload.amount or 0) / 100),
        "currency": payload.currency.upper() if payload.currency else "USD",
        "session_id": str(uuid5(NAMESPACE_URL, f"stripe:{payload.id}")),
        "vendor": "stripe",
        "utm_source": "stripe",
        "external_event_id": payload.id,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(tenant_info["tenant_id"], event_data, idempotency_key, source="stripe")


@router.post(
    "/webhooks/paypal/sale_completed",
    response_model=WebhookResponse,
    responses={401: {"model": WebhookErrorResponse}},
)
async def paypal_sale_completed(
    request: Request,
    payload: PayPalSaleCompletedRequest = Body(...),
    transmission_sig: str = Header(None, alias="PayPal-Transmission-Sig"),
    tenant_info=Depends(tenant_secrets),
):
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if not verify_paypal_signature(raw_body, tenant_info["paypal_webhook_secret"], transmission_sig):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "paypal"},
        )

    if not payload.id or not payload.amount:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing transaction id or amount")

    idempotency_key = str(uuid5(NAMESPACE_URL, f"paypal_sale_completed_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    ts = payload.create_time or datetime.now(timezone.utc)
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": payload.amount.total or "0",
        "currency": payload.amount.currency or "USD",
        "session_id": str(uuid5(NAMESPACE_URL, f"paypal:{payload.id}")),
        "vendor": "paypal",
        "utm_source": "paypal",
        "external_event_id": payload.id,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(tenant_info["tenant_id"], event_data, idempotency_key, source="paypal")


@router.post(
    "/webhooks/woocommerce/order_completed",
    response_model=WebhookResponse,
    responses={401: {"model": WebhookErrorResponse}},
)
async def woocommerce_order_completed(
    request: Request,
    payload: WooCommerceOrderCompletedRequest = Body(...),
    x_wc_webhook_signature: str = Header(None, alias="X-WC-Webhook-Signature"),
    tenant_info=Depends(tenant_secrets),
):
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if not verify_woocommerce_signature(raw_body, tenant_info["woocommerce_webhook_secret"], x_wc_webhook_signature):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "woocommerce"},
        )

    if not payload.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing order id")

    idempotency_key = str(uuid5(NAMESPACE_URL, f"woocommerce_order_completed_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    ts = payload.date_completed or datetime.now(timezone.utc)
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": payload.total or "0",
        "currency": payload.currency or "USD",
        "session_id": str(uuid5(NAMESPACE_URL, f"woocommerce:{payload.id}")),
        "vendor": "woocommerce",
        "utm_source": "woocommerce",
        "external_event_id": str(payload.id),
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(tenant_info["tenant_id"], event_data, idempotency_key, source="woocommerce")
