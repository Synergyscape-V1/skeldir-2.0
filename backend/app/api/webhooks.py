"""
Webhook ingress endpoints for Shopify, Stripe, PayPal, WooCommerce.

Responsibilities:
- Resolve tenant via API key header (X-Skeldir-Tenant-Key)
- Verify vendor signatures using per-tenant secrets
- Apply PII stripping (handled by middleware) and ingest via EventIngestionService
- Return 200 for success and DLQ-routed validation failures; 401 for signature/tenant failures
"""
import logging
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi import Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Optional

from app.core.config import settings
from app.core.tenant_context import get_tenant_with_webhook_secrets
from app.db.session import get_session
from app.ingestion.dlq_handler import DLQHandler
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
logger = logging.getLogger(__name__)


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


def _pii_redacted_paths(request: Request) -> list[str]:
    paths = getattr(request.state, "pii_redacted_paths", None)
    if not paths:
        return []
    if isinstance(paths, list):
        return [str(p) for p in paths]
    return []


def _coerce_event_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _compute_recompute_window(event_timestamp: str) -> tuple[str, str]:
    """
    Normalize an event timestamp into a UTC day window (start inclusive, end exclusive).
    """
    event_dt = _coerce_event_timestamp(event_timestamp)
    window_start = event_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    window_end = window_start + timedelta(days=1)
    return (
        window_start.isoformat().replace("+00:00", "Z"),
        window_end.isoformat().replace("+00:00", "Z"),
    )


def _schedule_downstream_tasks(
    *, tenant_id, event_timestamp: str, correlation_id: str
) -> None:
    try:
        from celery import chain

        from app.tasks.attribution import recompute_window
        from app.tasks.matviews import matview_refresh_all_for_tenant

        window_start, window_end = _compute_recompute_window(event_timestamp)
        chain(
            recompute_window.s(
                tenant_id=tenant_id,
                window_start=window_start,
                window_end=window_end,
                correlation_id=correlation_id,
                model_version="1.0.0",
            ).set(correlation_id=correlation_id),
            matview_refresh_all_for_tenant.si(
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                schedule_class="realtime",
            ).set(correlation_id=correlation_id),
        ).apply_async()
        logger.info(
            "ingestion_followup_tasks_enqueued",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "window_start": window_start,
                "window_end": window_end,
            },
        )
    except Exception:
        logger.exception(
            "ingestion_followup_tasks_failed",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "event_timestamp": event_timestamp,
            },
        )


async def _route_to_dlq_direct(
    tenant_id,
    source: str,
    correlation_id: str,
    payload: dict,
    error_message: str,
    error_type: str = "validation_error",
):
    async with get_session(tenant_id=tenant_id) as session:
        handler = DLQHandler()
        error: Exception
        if error_type == "pii_violation":
            # Trigger DLQHandler's PII classification (string match).
            error = Exception(f"PII detected: {error_message}")
        else:
            error = ValueError(error_message)
        dead = await handler.route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload,
            error=error,
            correlation_id=correlation_id,
            source=source,
        )
        return dead


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
        correlation_id = get_request_correlation_id() or idempotency_key
        event_timestamp = event_data.get("event_timestamp")
        if event_timestamp:
            _schedule_downstream_tasks(
                tenant_id=tenant_id,
                event_timestamp=str(event_timestamp),
                correlation_id=str(correlation_id),
            )
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
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(tenant_secrets),
):
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    stripped_body = await request.body()
    if not verify_stripe_signature(raw_body, tenant_info["stripe_webhook_secret"], stripe_signature):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "stripe"},
        )

    if not payload.id and not x_idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing payment intent id")

    idempotency_key = x_idempotency_key or str(uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    ts = datetime.fromtimestamp(payload.created) if payload.created else datetime.now(timezone.utc)
    # Avoid float conversion issues; ingestion service converts Decimal-string -> cents.
    revenue_amount = "0"
    if payload.amount is not None:
        revenue_amount = str((Decimal(payload.amount) / Decimal(100)).quantize(Decimal("0.01")))
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": revenue_amount,
        "currency": payload.currency.upper() if payload.currency else "USD",
        "session_id": str(uuid5(NAMESPACE_URL, f"stripe:{payload.id or idempotency_key}")),
        "vendor": "stripe",
        "utm_source": "stripe",
        "external_event_id": payload.id,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(tenant_info["tenant_id"], event_data, idempotency_key, source="stripe")


@router.post(
    "/webhooks/stripe/payment_intent/succeeded",
    response_model=WebhookResponse,
    responses={401: {"model": WebhookErrorResponse}},
)
async def stripe_payment_intent_succeeded_v2(
    request: Request,
    stripe_signature: str = Header(None, alias="Stripe-Signature"),
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(tenant_secrets),
):
    """
    Stripe payment_intent.succeeded webhook (contract path).

    R3 semantics:
    - Signature/tenant failures: 401 (never DLQ)
    - PII present (keys stripped by middleware): DLQ with sanitized payload, no canonical insert
    - Malformed payload: DLQ with sanitized payload, no canonical insert
    - Duplicate valid events: idempotent success (no 5xx)
    """
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if not verify_stripe_signature(raw_body, tenant_info["stripe_webhook_secret"], stripe_signature):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"status": "invalid_signature", "vendor": "stripe"},
        )
    stripped_body = await request.body()

    payload: dict[str, Any] = {}
    payload_parse_error: str | None = None
    try:
        parsed_payload = json.loads(stripped_body.decode("utf-8"))
        if not isinstance(parsed_payload, dict):
            raise ValueError("payload root must be a JSON object")
        payload = parsed_payload
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        payload_parse_error = str(exc)

    idempotency_key = x_idempotency_key
    pi_id = None
    amount_cents = None
    currency = None
    created_epoch = None
    event_id = None
    if payload_parse_error is None:
        try:
            event_id = payload.get("id")
            created_epoch = payload.get("created")
            obj = (payload.get("data") or {}).get("object") or {}
            pi_id = obj.get("id")
            amount_cents = obj.get("amount")
            currency = obj.get("currency")
            if not idempotency_key and pi_id:
                idempotency_key = str(uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_{pi_id}"))
        except Exception:
            # Handled as malformed below (routes to DLQ).
            pass
    elif not idempotency_key:
        # Keep malformed-body routing deterministic even without a client idempotency key.
        body_sha256 = hashlib.sha256(raw_body).hexdigest()
        idempotency_key = str(uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_invalid_json_{body_sha256}"))

    if not idempotency_key:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"status": "missing_idempotency_key", "vendor": "stripe"},
        )

    set_business_correlation_id(idempotency_key)
    correlation_uuid = str(_make_correlation_uuid(idempotency_key))

    if payload_parse_error is not None:
        dead = await _route_to_dlq_direct(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            correlation_id=correlation_uuid,
            payload={
                "event_type": "purchase",
                "vendor": "stripe",
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_uuid,
                "vendor_payload": {
                    "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
                    "raw_body_bytes": len(raw_body),
                    "parse_error": payload_parse_error,
                },
            },
            error_message="invalid_json_payload",
            error_type="validation_error",
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "validation_error",
        }

    pii_paths = _pii_redacted_paths(request)
    if pii_paths:
        dead = await _route_to_dlq_direct(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            correlation_id=correlation_uuid,
            payload={
                "event_type": "purchase",
                "vendor": "stripe",
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_uuid,
                "vendor_payload": payload,
                "pii_redacted_paths": pii_paths,
            },
            error_message="PII keys detected and stripped at ingestion boundary",
            error_type="pii_violation",
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "pii_violation",
        }

    # Validate minimal required shape; route any failure to DLQ (never 5xx)
    try:
        if not isinstance(created_epoch, int):
            raise ValueError("created must be an integer unix timestamp")
        if not isinstance(amount_cents, int):
            raise ValueError("amount must be an integer cents value")
        if not isinstance(currency, str) or len(currency) != 3:
            raise ValueError("currency must be a 3-letter code")
        if not pi_id or not isinstance(pi_id, str):
            raise ValueError("payment_intent id is required")
    except Exception as e:
        dead = await _route_to_dlq_direct(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            correlation_id=correlation_uuid,
            payload={
                "event_type": "purchase",
                "vendor": "stripe",
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_uuid,
                "vendor_payload": payload,
            },
            error_message=str(e),
            error_type="validation_error",
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "validation_error",
        }

    ts = datetime.fromtimestamp(created_epoch, tz=timezone.utc)
    revenue_amount = str((Decimal(amount_cents) / Decimal(100)).quantize(Decimal("0.01")))
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": revenue_amount,
        "currency": currency.upper(),
        "session_id": str(uuid5(NAMESPACE_URL, f"stripe:{idempotency_key}")),
        "vendor": "stripe",
        "utm_source": "stripe",
        "external_event_id": pi_id,
        "correlation_id": correlation_uuid,
        "vendor_payload": payload,
    }

    result = await ingest_with_transaction(
        tenant_id=tenant_info["tenant_id"],
        event_data={**event_data, "idempotency_key": idempotency_key},
        idempotency_key=idempotency_key,
        source="stripe",
    )

    if result.get("status") == "success":
        return {
            "status": "success",
            "event_id": result.get("event_id"),
            "idempotency_key": idempotency_key,
            "channel": result.get("channel"),
        }

    # Validation errors routed to DLQ by service: locate via correlation_id for response
    async with get_session(tenant_id=tenant_info["tenant_id"]) as session:
        from sqlalchemy import select
        res = await session.execute(
            select(DeadEvent).where(DeadEvent.correlation_id == uuid5(NAMESPACE_URL, idempotency_key))
        )
        dead_event = res.scalar_one_or_none()

    return {
        "status": "dlq_routed",
        "dead_event_id": str(dead_event.id) if dead_event else None,
        "error": result.get("error_type") or result.get("error"),
    }


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
