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
import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from collections.abc import Callable
from types import MappingProxyType
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from typing import Any, Mapping, Optional

from app.api.problem_details import ProblemDetails
from app.attribution.strategy_kernel import LAST_TOUCH_MODEL
from app.core.config import settings
from app.core.tenant_context import get_tenant_with_webhook_secrets
from app.db.session import get_session
from app.ingestion.dlq_handler import DLQHandler
from app.ingestion.event_service import (
    ValidationError as IngestionValidationError,
)
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
from app.tasks.authority import SystemAuthorityEnvelope
from app.tasks.enqueue import tenant_task_signature
from app.tasks.revenue_verification import execute_b23_batch_match_engine_task
from app.core.queues import QUEUE_B23_MATCH_ENGINE
from app.security.auth import AuthError, unauthorized_auth_error
from app.privacy.authority import generate_privacy_session_id
from app.revenue_verification.failure_boundary import (
    B23FailureBoundaryClass,
    classify_b23_failure_boundary,
)
from app.webhooks.signatures import (
    verify_shopify_signature,
    verify_stripe_signature,
    verify_paypal_signature,
    verify_woocommerce_signature,
)

router = APIRouter()
logger = logging.getLogger(__name__)
tenant_key_auth = APIKeyHeader(
    name=settings.TENANT_API_KEY_HEADER,
    scheme_name="tenantKeyAuth",
    auto_error=False,
)


class WebhookResponse(BaseModel):
    status: str
    event_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    dead_event_id: Optional[str] = None
    channel: Optional[str] = None
    error: Optional[str] = None


UNAUTHORIZED_PROBLEM_RESPONSE = {
    "description": "Unauthorized - invalid or missing authentication",
    "content": {
        "application/problem+json": {
            "schema": ProblemDetails.model_json_schema(),
        },
    },
}

WEBHOOK_DUMMY_SECRET = "skeldir_webhook_dummy_secret_constant_work"
WEBHOOK_PAYLOAD_TOO_LARGE_DETAIL = "Request payload too large."
WEBHOOK_INVALID_PAYLOAD_DETAIL = "Invalid request payload."
WEBHOOK_UNSUPPORTED_EVENT_FAMILY_STATUS = "unsupported_event_family_ignored"
B23_NATURAL_DISPATCH_DISABLE_ENV = "SKELDIR_B23_P6_DISABLE_NATURAL_DISPATCH"

WebhookVerifier = Callable[[bytes, Optional[str], Optional[str]], bool]
WEBHOOK_VERIFIERS: dict[str, tuple[str, WebhookVerifier]] = {
    "shopify": ("shopify_webhook_secret", verify_shopify_signature),
    "stripe": ("stripe_webhook_secret", verify_stripe_signature),
    "paypal": ("paypal_webhook_secret", verify_paypal_signature),
    "woocommerce": ("woocommerce_webhook_secret", verify_woocommerce_signature),
}
_SUPPORTED_EVENT_FAMILY_HINTS = MappingProxyType(
    {
        "shopify": frozenset({"orders.create", "order_create"}),
        "stripe": frozenset(
            {
                "payment_intent.succeeded",
                "payment_intent_succeeded",
            }
        ),
        "paypal": frozenset({"payment.sale.completed", "sale_completed"}),
        "woocommerce": frozenset({"order.completed", "order_completed"}),
    }
)


def _canonical_money_scale(currency: str | None) -> int:
    # XVI: single scale authority. The sovereign ISO 4217 table lives in
    # app.webhooks.commerce_derivation; this relay path must not carry a
    # parallel table that can silently diverge from it.
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        canonical_money_scale as _sovereign_money_scale,
    )

    return _sovereign_money_scale(currency)


def _paypal_auth_envelope_header(
    *,
    transmission_id: str | None,
    transmission_time: str | None,
    transmission_sig: str | None,
    auth_algo: str | None,
    cert_url: str | None,
    webhook_id: str | None,
) -> str:
    envelope = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "transmission_sig": transmission_sig,
        "auth_algo": auth_algo,
        "cert_url": cert_url,
    }
    if webhook_id is not None:
        envelope["webhook_id"] = webhook_id
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True)


def _parse_content_length_header(request: Request) -> int | None:
    raw = request.headers.get("content-length")
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=WEBHOOK_INVALID_PAYLOAD_DETAIL,
        ) from exc
    if parsed < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=WEBHOOK_INVALID_PAYLOAD_DETAIL,
        )
    return parsed


def _enforce_webhook_body_size_limit(*, request: Request, raw_body: bytes) -> None:
    max_body_bytes = settings.WEBHOOK_AUTH_MAX_BODY_BYTES
    parsed_content_length = _parse_content_length_header(request)
    if parsed_content_length is not None and parsed_content_length > max_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=WEBHOOK_PAYLOAD_TOO_LARGE_DETAIL,
        )
    if len(raw_body) > max_body_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=WEBHOOK_PAYLOAD_TOO_LARGE_DETAIL,
        )


async def _resolve_raw_body_for_webhook_auth(request: Request) -> bytes:
    raw_body = getattr(request.state, "original_body", None)
    if raw_body is None:
        raw_body = await request.body()
    if isinstance(raw_body, bytearray):
        raw_body = bytes(raw_body)
    if not isinstance(raw_body, bytes):
        raw_body = bytes(raw_body or b"")
    _enforce_webhook_body_size_limit(request=request, raw_body=raw_body)
    return raw_body


async def _resolve_tenant_info_for_webhook_auth(
    api_key: str | None,
) -> dict[str, Any] | None:
    if not api_key or not api_key.strip():
        return None
    try:
        return await get_tenant_with_webhook_secrets(api_key)
    except AuthError:
        return None


_PROVIDER_AUTH_METHOD = MappingProxyType(
    {
        "shopify": "hmac-sha256-base64",
        "stripe": "hmac-sha256-timestamped-hex",
        "paypal": "rsa-sha256-transmission",
        "woocommerce": "hmac-sha256-base64",
    }
)


def _provider_auth_method(provider: str) -> str:
    return _PROVIDER_AUTH_METHOD.get(provider.strip().lower(), "unknown")


def _provider_topic_for_family(
    *, provider: str, request_headers: Mapping[str, str] | None
) -> str | None:
    """Extract the provider-transported family topic (XIX, H-XIX-R7).

    In-memory only: the topic is carried through the relay envelope to
    the authentication root, which derives the family from it for
    providers whose protocol conveys family outside the signed body
    (shopify; fallback for woocommerce). The topic itself is never
    persisted -- only the derived family and its evidence source are.
    """
    headers = request_headers or {}
    if provider == "shopify":
        return _normalize_event_family_hint(headers.get("x-shopify-topic"))
    if provider == "woocommerce":
        return _normalize_event_family_hint(headers.get("x-wc-webhook-topic"))
    return None


def _build_provider_auth_consequence(
    *,
    tenant_info: Mapping[str, Any],
    provider: str,
    provider_event_reference: str,
    provider_topic: str | None = None,
) -> dict[str, Any]:
    """Snapshot predecessor event P for the post-commit finalizer.

    B2.6-P2 Corrective XII: called only after a successful
    provider-signature verification in this task. Binds the raw-body
    digest, a digest of the presented signature envelope (never the
    secret), the provider/event identities, and the method/version.
    XIX: carries the provider-transported family topic (in memory) for
    protocols that convey family outside the signed body.
    """
    auth_snapshot = tenant_info.get("provider_auth_snapshot") or {}
    event_ref = (provider_event_reference or "").strip()
    if not event_ref:
        raise ValueError("provider_event_reference is required for auth consequence")
    consequence = {
        "provider": provider.strip().lower(),
        "provider_event_reference": event_ref,
        "body_sha256": str(auth_snapshot.get("body_sha256") or ""),
        "signature_envelope_sha256": str(
            auth_snapshot.get("signature_envelope_sha256") or ""
        ),
        "auth_method": str(
            auth_snapshot.get("auth_method") or _provider_auth_method(provider)
        ),
        "auth_version": "v1",
        # XIX: provider-transported family topic (in memory only; the
        # root derives the family from it, never from the route).
        "provider_topic": provider_topic,
    }
    # XIV relay: carry the in-memory relay envelope (raw bytes + sig +
    # routing key) alongside the digest consequence. Transient only.
    relay = tenant_info.get("relay_envelope")
    if isinstance(relay, dict) and relay.get("raw_body_b64"):
        consequence["relay_envelope"] = {
            "raw_body_b64": str(relay.get("raw_body_b64") or ""),
            "signature_header": str(relay.get("signature_header") or ""),
            "api_key": str(relay.get("api_key") or ""),
        }
    return consequence


async def _authorize_webhook_request(
    *,
    request: Request,
    provider: str,
    signature_header: str | None,
    api_key: str | None,
) -> dict[str, Any]:
    raw_body = await _resolve_raw_body_for_webhook_auth(request)
    verification_material_field, verifier = WEBHOOK_VERIFIERS[provider]
    tenant_info = await _resolve_tenant_info_for_webhook_auth(api_key)
    material_found = tenant_info is not None and bool(
        tenant_info.get(verification_material_field)
    )
    material_for_compute = (
        str(tenant_info[verification_material_field])
        if material_found
        else WEBHOOK_DUMMY_SECRET
    )
    signature_valid = verifier(raw_body, material_for_compute, signature_header)

    if not (material_found and signature_valid):
        raise unauthorized_auth_error()

    set_tenant_id(tenant_info["tenant_id"])
    tenant_info["verified_at"] = datetime.now(timezone.utc)
    # B2.6-P2 Corrective XII: snapshot the predecessor event P at the
    # moment authentication succeeds. Only digests travel downstream;
    # raw secrets and raw signatures never persist.
    tenant_info["provider_auth_snapshot"] = {
        "body_sha256": hashlib.sha256(raw_body).hexdigest(),
        "signature_envelope_sha256": hashlib.sha256(
            str(signature_header or "").encode("utf-8")
        ).hexdigest(),
        "auth_method": _provider_auth_method(provider),
        "auth_version": "v1",
    }
    # XIV (Architecture B relay): retain the exact raw bytes + presented
    # signature envelope + tenant routing key IN MEMORY ONLY so the
    # post-commit finalizer can relay the non-authoritative arrival to
    # the dedicated authentication trust root, which independently
    # re-verifies the provider signature before persisting any authority.
    # This envelope is never persisted (no PII persistence) and never
    # logged; it travels only to the root over the relay call.
    import base64 as _b64  # noqa: PLC0415

    tenant_info["relay_envelope"] = {
        "raw_body_b64": _b64.b64encode(raw_body).decode("ascii"),
        "signature_header": str(signature_header or ""),
        "api_key": str(api_key or ""),
    }
    return tenant_info


async def shopify_webhook_auth(
    request: Request,
    x_shopify_hmac_sha256: str | None = Header(None, alias="X-Shopify-Hmac-Sha256"),
    api_key: str | None = Security(tenant_key_auth),
) -> dict[str, Any]:
    return await _authorize_webhook_request(
        request=request,
        provider="shopify",
        signature_header=x_shopify_hmac_sha256,
        api_key=api_key,
    )


async def stripe_webhook_auth(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    api_key: str | None = Security(tenant_key_auth),
) -> dict[str, Any]:
    return await _authorize_webhook_request(
        request=request,
        provider="stripe",
        signature_header=stripe_signature,
        api_key=api_key,
    )


async def paypal_webhook_auth(
    request: Request,
    transmission_sig: str | None = Header(None, alias="PayPal-Transmission-Sig"),
    transmission_id: str | None = Header(None, alias="PayPal-Transmission-Id"),
    transmission_time: str | None = Header(None, alias="PayPal-Transmission-Time"),
    webhook_id: str | None = Header(None, alias="PayPal-Webhook-Id"),
    auth_algo: str | None = Header(None, alias="PayPal-Auth-Algo"),
    cert_url: str | None = Header(None, alias="PayPal-Cert-Url"),
    api_key: str | None = Security(tenant_key_auth),
) -> dict[str, Any]:
    envelope = _paypal_auth_envelope_header(
        transmission_id=transmission_id,
        transmission_time=transmission_time,
        transmission_sig=transmission_sig,
        webhook_id=webhook_id,
        auth_algo=auth_algo,
        cert_url=cert_url,
    )
    return await _authorize_webhook_request(
        request=request,
        provider="paypal",
        signature_header=envelope,
        api_key=api_key,
    )


async def woocommerce_webhook_auth(
    request: Request,
    x_wc_webhook_signature: str | None = Header(None, alias="X-WC-Webhook-Signature"),
    api_key: str | None = Security(tenant_key_auth),
) -> dict[str, Any]:
    return await _authorize_webhook_request(
        request=request,
        provider="woocommerce",
        signature_header=x_wc_webhook_signature,
        api_key=api_key,
    )


async def tenant_secrets(
    api_key: str | None = Security(tenant_key_auth),
):
    if not api_key:
        raise unauthorized_auth_error()
    tenant_info = await get_tenant_with_webhook_secrets(api_key)
    set_tenant_id(tenant_info["tenant_id"])
    return tenant_info


def _make_correlation_uuid(idempotency_key: str):
    return uuid5(NAMESPACE_URL, idempotency_key)


def _coerce_event_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolution_token(value: Any) -> str | None:
    if value is None:
        return None
    token = str(value).strip()
    return token if token else None


def _normalize_event_family_hint(value: Any) -> str | None:
    token = _resolution_token(value)
    if token is None:
        return None
    return token.lower().replace("/", ".")


def _unsupported_event_family_reason(
    *,
    provider: str,
    payload: Mapping[str, Any],
    request_headers: Mapping[str, str],
) -> str | None:
    """Relay-side family hint check (defense in depth, never authority).

    Returns a refusal reason when the arrival observably carries an
    unsupported family OR no usable family fact at all (XIX:
    familyless shapes are DLQ-routed here with an explicit reason
    instead of dying later with an unclassified 500). The sovereign
    decision stays downstream (root derivation, transition allowlist):
    this hint can only refuse, never confer.
    """
    supported_hints = _SUPPORTED_EVENT_FAMILY_HINTS[provider]

    if provider in {"stripe", "paypal"}:
        from app.webhooks.commerce_derivation import (  # noqa: PLC0415
            terminal_lifecycle_refusal,
        )

        terminal = terminal_lifecycle_refusal(provider, payload)
        if terminal is not None:
            return f"terminal-lifecycle={terminal}"

    if provider == "shopify":
        observed_topic = _normalize_event_family_hint(
            request_headers.get("x-shopify-topic")
        )
        if observed_topic is not None and observed_topic not in supported_hints:
            return f"x-shopify-topic={observed_topic}"
        if observed_topic is None:
            return "familyless:no-provider-topic"
        return None

    if provider == "woocommerce":
        observed_topic = _normalize_event_family_hint(
            request_headers.get("x-wc-webhook-topic")
        )
        if observed_topic is not None and observed_topic not in supported_hints:
            return f"x-wc-webhook-topic={observed_topic}"
        observed_status = _normalize_event_family_hint(payload.get("status"))
        if observed_status is not None and observed_status != "completed":
            return f"status={observed_status}"
        # XX (H-XX-B): the transported topic is routing information,
        # never a family fact. A status-less body is familyless even
        # when a topic header is present; the sovereign root refuses
        # it and this hint routes it to DLQ here.
        if observed_status is None:
            return "familyless:no-body-status"
        return None

    if provider == "paypal":
        observed_type = _normalize_event_family_hint(payload.get("event_type"))
        if observed_type is not None and observed_type not in supported_hints:
            return f"event_type={observed_type}"
        if observed_type is None:
            return "familyless:no-event-type"
        return None

    if provider == "stripe":
        for key in ("type", "event_type"):
            observed_type = _normalize_event_family_hint(payload.get(key))
            if observed_type is not None and observed_type not in supported_hints:
                return f"{key}={observed_type}"
            if observed_type is not None:
                return None
        observed_status = _normalize_event_family_hint(payload.get("status"))
        if observed_status is not None and observed_status != "succeeded":
            return f"status={observed_status}"
        if observed_status is None:
            return "familyless:no-type-or-status"
        return None

    return None


def _request_headers_for_privacy_boundary(request: Request) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in request.headers.items()}


def _verified_revenue_state() -> dict[str, str]:
    return {
        "verified_revenue_state": "authenticity_verified",
        "verified_commerce_ingress_state": "authenticity_verified",
    }


def _resolve_verified_at(tenant_info: Mapping[str, Any]) -> datetime:
    raw_value = tenant_info.get("verified_at")
    if isinstance(raw_value, datetime):
        return (
            raw_value.astimezone(timezone.utc)
            if raw_value.tzinfo is not None
            else raw_value.replace(tzinfo=timezone.utc)
        )
    return datetime.now(timezone.utc)


def _decimal_to_minor_units(value: str | int | Decimal, *, scale: int = 2) -> int:
    """Relay-side money conversion under the governed exact-precision law.

    XVII (H-XVII-R11): delegates to the sovereign derivation helper so the
    relay handoff can never round a value the authoritative derivation
    refuses. Any divergence fails closed here (400/DLQ) instead of
    surfacing later as a binding mismatch.
    """
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        CommerceDerivationError,
        decimal_to_minor_units as _sovereign_to_minor,
    )

    try:
        return _sovereign_to_minor(value, scale=scale)
    except CommerceDerivationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid canonical monetary amount.",
        ) from exc


def _minor_units_to_decimal_string(minor: int, *, scale: int = 2) -> str:
    divisor = Decimal(10) ** scale
    return str((Decimal(minor) / divisor).quantize(Decimal(10) ** (-scale)))


def _try_decimal_to_minor_units(
    value: str | int | Decimal, *, scale: int = 2
) -> int | None:
    try:
        return _decimal_to_minor_units(value, scale=scale)
    except HTTPException:
        return None


def _identity_payload_from_request(request: Request) -> dict[str, Any] | None:
    raw_body = getattr(request.state, "original_body", None)
    if raw_body is None:
        return None
    if isinstance(raw_body, bytearray):
        raw_body = bytes(raw_body)
    if not isinstance(raw_body, bytes):
        raw_body = bytes(raw_body or b"")
    if not raw_body:
        return None
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _parse_json_object(raw_body: bytes) -> tuple[dict[str, Any] | None, str | None]:
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(parsed, dict):
        return None, "payload root must be a JSON object"
    return parsed, None


def _malformed_idempotency_key(*, source: str, raw_body: bytes, suffix: str) -> str:
    body_sha256 = hashlib.sha256(raw_body).hexdigest()
    return str(uuid5(NAMESPACE_URL, f"{source}_{suffix}_{body_sha256}"))


async def _route_unsupported_event_family(
    *,
    source: str,
    raw_body: bytes,
    reason: str,
    tenant_id: UUID | str | None = None,
    identity_payload: dict[str, Any] | None = None,
    request_headers: dict[str, str] | None = None,
) -> dict[str, str | None]:
    boundary = classify_b23_failure_boundary(
        B23FailureBoundaryClass.UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE
    )
    idempotency_key = _malformed_idempotency_key(
        source=source,
        raw_body=raw_body,
        suffix="unsupported_event_family",
    )
    set_business_correlation_id(idempotency_key)
    logger.info(
        "webhook_unsupported_event_family_ignored",
        extra={
            "provider": source,
            "reason": reason,
            "idempotency_key": idempotency_key,
            "payload_sha256": hashlib.sha256(raw_body).hexdigest(),
            "b23_failure_boundary": boundary.boundary_class.value,
        },
    )
    dead_event_id: str | None = None
    if tenant_id is not None:
        correlation_id = str(_make_correlation_uuid(idempotency_key))
        dead = await _route_to_dlq_direct(
            tenant_id=tenant_id,
            source=source,
            correlation_id=correlation_id,
            payload={
                "event_type": "purchase",
                "vendor": source,
                "idempotency_key": idempotency_key,
                "correlation_id": correlation_id,
                "vendor_payload": identity_payload
                or {"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
                "b23_failure_boundary": boundary.boundary_class.value,
            },
            error_message=f"unsupported_event_family:{reason}",
            error_type="validation_error",
            identity_payload=identity_payload
            or {"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
            request_headers=request_headers,
        )
        dead_event_id = str(dead.id)
    return {
        "status": WEBHOOK_UNSUPPORTED_EVENT_FAMILY_STATUS,
        "error": "unsupported_event_family",
        "idempotency_key": idempotency_key,
        "dead_event_id": dead_event_id,
    }


async def _route_authenticated_malformed_payload(
    *,
    tenant_id: UUID | str,
    source: str,
    idempotency_key: str,
    error_message: str,
    vendor_payload: dict[str, Any],
    identity_payload: dict[str, Any],
    request_headers: dict[str, str],
) -> dict[str, str | None]:
    boundary = classify_b23_failure_boundary(
        B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD
    )
    correlation_id = str(_make_correlation_uuid(idempotency_key))
    dead = await _route_to_dlq_direct(
        tenant_id=tenant_id,
        source=source,
        correlation_id=correlation_id,
        payload={
            "event_type": "purchase",
            "vendor": source,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id,
            "vendor_payload": vendor_payload,
            "b23_failure_boundary": boundary.boundary_class.value,
        },
        error_message=error_message,
        error_type="validation_error",
        identity_payload=identity_payload,
        request_headers=request_headers,
    )
    return {
        "status": "dlq_routed",
        "dead_event_id": str(dead.id),
        "error": "validation_error",
    }


def _compute_recompute_window(event_timestamp: str) -> tuple[str, str]:
    """Normalize an event timestamp into a UTC day window.

    Single-implementation law: day quantization is executed once in
    ``app.core.day_window``; this façade delegates to it so the webhook
    dispatch window and the worker scope window cannot silently diverge.
    B2.3 matching and later scope use remain distinct authorities sharing
    one quantization function, not one implicit window.
    """
    from app.core.day_window import (  # noqa: PLC0415
        quantize_utc_day_iso,
    )

    return quantize_utc_day_iso(event_timestamp)


def _schedule_downstream_tasks(
    *, tenant_id, event_timestamp: str, session_id: str, correlation_id: str
) -> None:
    try:
        from celery import chain

        from app.tasks.attribution import recompute_window
        from app.tasks.matviews import matview_refresh_all_for_tenant

        window_start, window_end = _compute_recompute_window(event_timestamp)
        system_envelope = SystemAuthorityEnvelope(tenant_id=tenant_id)
        chain(
            tenant_task_signature(
                recompute_window,
                envelope=system_envelope,
                kwargs={
                    "window_start": window_start,
                    "window_end": window_end,
                    "session_id": session_id,
                    "correlation_id": correlation_id,
                    "model_version": "1.0.0",
                    "model_type": LAST_TOUCH_MODEL,
                },
            ).set(correlation_id=correlation_id),
            tenant_task_signature(
                matview_refresh_all_for_tenant,
                envelope=system_envelope,
                kwargs={
                    "correlation_id": correlation_id,
                    "schedule_class": "realtime",
                },
                immutable=True,
            ).set(correlation_id=correlation_id),
        ).apply_async()
        logger.info(
            "ingestion_followup_tasks_enqueued",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "window_start": window_start,
                "window_end": window_end,
                "session_id": session_id,
            },
        )
    except Exception:
        logger.exception(
            "ingestion_followup_tasks_failed",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "event_timestamp": event_timestamp,
                "session_id": session_id,
            },
        )
        # Corrective IV: a faulted publish poisons its pooled producer
        # (kombu never closes it); drop pooled broker state so the next
        # publish rebuilds instead of reusing the poisoned session.
        from app.celery_app import reset_broker_pools_after_fault  # noqa: PLC0415

        reset_broker_pools_after_fault(reason="ingestion_followup_publish")


async def _redrive_pending_dispatch_for_ingress(
    *, tenant_id, event_id: str, correlation_id: str
) -> None:
    """Re-drive publication for a duplicate webhook when intent is pending.

    Corrective III (H-III-A02): provider retry must recover a stranded
    legitimate dispatch instead of silently returning success. The stable
    logical task identity is reused; duplicate physical delivery remains
    logically idempotent via B2.3 upserts and deterministic P2 recomputation.
    """
    try:
        async with get_session(tenant_id=tenant_id) as session:
            row = (
                (
                    await session.execute(
                        text(
                            """
                            SELECT d.task_id AS task_id,
                                   d.delivery_state AS delivery_state,
                                   d.window_start AS window_start,
                                   d.window_end AS window_end,
                                   d.correlation_id AS dispatch_correlation,
                                   o.state AS outbox_state
                            FROM public.b23_match_task_dispatches AS d
                            JOIN public.webhook_ingress_identities AS i
                              ON i.id = d.webhook_ingress_identity_id
                             AND i.tenant_id = d.tenant_id
                            LEFT JOIN public.b26_p2_execution_outbox AS o
                              ON o.dispatch_task_id = d.task_id
                            WHERE d.tenant_id = :tenant_id
                              AND i.event_id = :event_id
                              AND i.verified_commerce_ingress_state = 'authenticity_verified'
                              AND public.b26_p2_ingress_has_current_authority(i.id)
                              AND EXISTS (
                                    SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                                     WHERE w.webhook_ingress_identity_id = i.id
                              )
                            """
                        ),
                        {"tenant_id": str(tenant_id), "event_id": event_id},
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return
            if (
                str(row["delivery_state"] or "") == "published"
                and str(row["outbox_state"] or "published") == "published"
            ):
                return
            task_id = str(row["task_id"])
            ws = row["window_start"]
            we = row["window_end"]
            if ws is None or we is None:
                return
            ws_iso = ws.isoformat() if hasattr(ws, "isoformat") else str(ws)
            we_iso = we.isoformat() if hasattr(we, "isoformat") else str(we)
        try:
            execute_b23_batch_match_engine_task.apply_async(
                args=[str(tenant_id), ws_iso, we_iso, 100, str(correlation_id)],
                task_id=task_id,
                queue=QUEUE_B23_MATCH_ENGINE,
                routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
            )
        except Exception as exc:
            logger.warning(
                "b23_match_task_redrive_publish_failed",
                extra={
                    "tenant_id": str(tenant_id),
                    "event_id": event_id,
                    "task_id": task_id,
                    "error": str(exc)[:500],
                },
            )
            from app.celery_app import reset_broker_pools_after_fault  # noqa: PLC0415

            reset_broker_pools_after_fault(reason="redrive_publish")
            return
        async with get_session(tenant_id=tenant_id) as mark:
            await mark.execute(
                text(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'published',"
                    " publish_attempts = publish_attempts + 1,"
                    " updated_at = now() WHERE task_id = :task_id"
                ),
                {"task_id": task_id},
            )
            await mark.execute(
                text(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET state = 'published', updated_at = now()"
                    " WHERE dispatch_task_id = :task_id"
                ),
                {"task_id": task_id},
            )
        logger.info(
            "b23_match_task_redriven_from_duplicate",
            extra={
                "tenant_id": str(tenant_id),
                "event_id": event_id,
                "task_id": task_id,
            },
        )
    except Exception:
        logger.exception(
            "b23_match_task_redrive_failed",
            extra={"tenant_id": str(tenant_id), "event_id": event_id},
        )


async def _dispatch_b23_match_task_from_persisted_ingress(
    *,
    tenant_id,
    event_id: str,
    event_timestamp: str,
    correlation_id: str,
) -> None:
    if os.getenv(B23_NATURAL_DISPATCH_DISABLE_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        logger.info(
            "b23_match_task_natural_dispatch_disabled",
            extra={"tenant_id": str(tenant_id), "event_id": event_id},
        )
        return

    window_start, window_end = _compute_recompute_window(event_timestamp)
    # Corrective III durable execution intent: acceptance and recoverable
    # delivery intent share one commit (dispatch + outbox atomically), the
    # stable logical task identity never rotates (ON CONFLICT DO NOTHING),
    # and publication may retry indefinitely via duplicate re-drive and the
    # deployed relay sweeper. Process death between commit and publish
    # leaves observable pending state, never silent stranding.
    import uuid as _dispatch_uuid  # noqa: PLC0415  (task identity only)
    from datetime import datetime as _ws_datetime  # noqa: PLC0415

    def _ws_parse(iso: str) -> object:
        try:
            return _ws_datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except (ValueError, TypeError, AttributeError):
            return iso

    _ws_dt = _ws_parse(window_start)
    _we_dt = _ws_parse(window_end)

    dispatch_task_id = str(_dispatch_uuid.uuid4())
    async with get_session(tenant_id=tenant_id) as session:
        # XIII dispatch law: dispatch may not select on verified-alone.
        # It requires the exact terminal authentication state
        # (provenance IS NOT DISTINCT FROM 'authenticated_known') AND
        # witness existence. Pending rows (including INSERT-time
        # partials with zero consequence/witness) are non-dispatchable
        # by law; the database trigger enforces the same predicate.
        ingress = (
            (
                await session.execute(
                    text(
                        """
                        SELECT
                            i.id,
                            i.provider,
                            i.provider_native_event_reference,
                            i.provider_native_commerce_reference,
                            i.normalized_commerce_reference_value
                        FROM public.webhook_ingress_identities AS i
                        WHERE i.tenant_id = :tenant_id
                          AND i.event_id = :event_id
                          AND i.verified_commerce_ingress_state = 'authenticity_verified'
                          AND public.b26_p2_ingress_has_current_authority(i.id)
                          AND EXISTS (
                                SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                                 WHERE w.webhook_ingress_identity_id = i.id
                          )
                          AND EXISTS (
                                SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                                 WHERE c.webhook_ingress_identity_id = i.id
                          )
                          -- XXV-2 (A2/B10): a provider amendment (a later
                          -- authenticated event over the same commerce
                          -- identity) is a source for the shipping correction
                          -- surface, not a second capture. It must not create
                          -- its own B2.3 dispatch: the correction task relinks
                          -- the existing verdict to it. The first authenticated
                          -- row has no earlier authenticated sibling and
                          -- remains dispatchable.
                          AND NOT EXISTS (
                                SELECT 1
                                  FROM public.webhook_ingress_identities AS prior
                                 WHERE prior.tenant_id = i.tenant_id
                                   AND prior.provider = i.provider
                                   AND prior.normalized_commerce_reference_kind
                                       IS NOT DISTINCT FROM
                                       i.normalized_commerce_reference_kind
                                   AND prior.normalized_commerce_reference_value
                                       IS NOT DISTINCT FROM
                                       i.normalized_commerce_reference_value
                                   AND prior.b26_p2_provenance_status =
                                       'authenticated_known'
                                   AND prior.id <> i.id
                                   AND (prior.created_at, prior.id)
                                       < (i.created_at, i.id)
                          )
                        """
                    ),
                    {"tenant_id": str(tenant_id), "event_id": event_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if ingress is None:
            logger.info(
                "b23_match_task_natural_dispatch_skipped_no_ingress_identity",
                extra={"tenant_id": str(tenant_id), "event_id": event_id},
            )
            return

        await session.execute(
            text(
                """
                INSERT INTO public.b23_match_task_dispatches (
                    tenant_id,
                    webhook_ingress_identity_id,
                    task_id,
                    task_name,
                    queue,
                    routing_key,
                    correlation_id,
                    provider,
                    provider_native_event_reference,
                    provider_native_commerce_reference,
                    normalized_commerce_reference_value,
                    status,
                    delivery_state,
                    publish_attempts,
                    window_start,
                    window_end,
                    dispatched_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    :tenant_id,
                    :webhook_ingress_identity_id,
                    :task_id,
                    :task_name,
                    :queue,
                    :routing_key,
                    :correlation_id,
                    :provider,
                    :provider_native_event_reference,
                    :provider_native_commerce_reference,
                    :normalized_commerce_reference_value,
                    'dispatched',
                    'pending_publish',
                    0,
                    :window_start,
                    :window_end,
                    now(),
                    now(),
                    now()
                )
                ON CONFLICT (tenant_id, webhook_ingress_identity_id) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "webhook_ingress_identity_id": str(ingress["id"]),
                "task_id": dispatch_task_id,
                "task_name": execute_b23_batch_match_engine_task.name,
                "queue": QUEUE_B23_MATCH_ENGINE,
                "routing_key": f"{QUEUE_B23_MATCH_ENGINE}.task",
                "correlation_id": str(correlation_id),
                "provider": ingress["provider"],
                "provider_native_event_reference": ingress[
                    "provider_native_event_reference"
                ],
                "provider_native_commerce_reference": ingress[
                    "provider_native_commerce_reference"
                ],
                "normalized_commerce_reference_value": ingress[
                    "normalized_commerce_reference_value"
                ],
                "window_start": _ws_dt,
                "window_end": _we_dt,
            },
        )
        # Stable identity: on conflict the first task_id wins; reuse it so
        # duplicate physical delivery cannot create duplicate logical truth.
        existing = (
            (
                await session.execute(
                    text(
                        "SELECT task_id FROM public.b23_match_task_dispatches"
                        " WHERE tenant_id = :tenant_id"
                        " AND webhook_ingress_identity_id = :ingress_id"
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "ingress_id": str(ingress["id"]),
                    },
                )
            )
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            dispatch_task_id = str(existing["task_id"])
        await session.execute(
            text(
                """
                INSERT INTO public.b26_p2_execution_outbox (
                    tenant_id, dispatch_task_id, webhook_ingress_identity_id,
                    state, publish_attempts, payload
                )
                VALUES (:tenant_id, :task_id, :ingress_id, 'pending_publish', 0,
                        CAST(:payload AS jsonb))
                ON CONFLICT (dispatch_task_id) DO NOTHING
                """
            ),
            {
                "tenant_id": str(tenant_id),
                "task_id": dispatch_task_id,
                "ingress_id": str(ingress["id"]),
                "payload": (
                    '{"window_start": "' + window_start + '",'
                    ' "window_end": "' + window_end + '",'
                    ' "correlation_id": "' + str(correlation_id) + '"}'
                ),
            },
        )
        # GUC-independent admission directory (no RLS): stable task identity
        # to authoritative tenant/window binding for pre-B2.3 admission.
        await session.execute(
            text(
                """
                INSERT INTO public.b26_p2_task_authority_directory (
                    task_id, tenant_id, webhook_ingress_identity_id,
                    window_start, window_end
                )
                VALUES (:task_id, :tenant_id, :ingress_id,
                        :window_start, :window_end)
                ON CONFLICT (task_id) DO NOTHING
                """
            ),
            {
                "task_id": dispatch_task_id,
                "tenant_id": str(tenant_id),
                "ingress_id": str(ingress["id"]),
                "window_start": _ws_dt,
                "window_end": _we_dt,
            },
        )
        dispatch_ingress_id = str(ingress["id"])
    try:
        async_result = execute_b23_batch_match_engine_task.apply_async(
            args=[
                str(tenant_id),
                window_start,
                window_end,
                100,
                str(correlation_id),
            ],
            task_id=dispatch_task_id,
            queue=QUEUE_B23_MATCH_ENGINE,
            routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
        )
    except Exception as exc:
        # Broker unavailable after durable commit: leave observable pending
        # state for duplicate re-drive and the deployed relay sweeper.
        logger.warning(
            "b23_match_task_publish_deferred_pending",
            extra={
                "tenant_id": str(tenant_id),
                "event_id": event_id,
                "task_id": dispatch_task_id,
                "dispatch_ingress_id": dispatch_ingress_id,
                "error": str(exc)[:500],
            },
        )
        from app.celery_app import reset_broker_pools_after_fault  # noqa: PLC0415

        reset_broker_pools_after_fault(reason="immediate_publish")
        return
    # Best-effort immediate mark; a crash here still leaves the outbox
    # pending for the relay, and duplicate delivery reuses the same task_id.
    try:
        async with get_session(tenant_id=tenant_id) as mark:
            await mark.execute(
                text(
                    "UPDATE public.b23_match_task_dispatches"
                    " SET delivery_state = 'published',"
                    " publish_attempts = publish_attempts + 1,"
                    " updated_at = now() WHERE task_id = :task_id"
                ),
                {"task_id": dispatch_task_id},
            )
            await mark.execute(
                text(
                    "UPDATE public.b26_p2_execution_outbox"
                    " SET state = 'published', updated_at = now()"
                    " WHERE dispatch_task_id = :task_id"
                ),
                {"task_id": dispatch_task_id},
            )
    except Exception:
        logger.exception(
            "b23_match_task_publish_mark_failed_pending",
            extra={"tenant_id": str(tenant_id), "task_id": dispatch_task_id},
        )
        return
    logger.info(
        "b23_match_task_naturally_dispatched",
        extra={
            "tenant_id": str(tenant_id),
            "event_id": event_id,
            "task_id": str(async_result.id),
            "dispatch_ingress_id": dispatch_ingress_id,
            "queue": QUEUE_B23_MATCH_ENGINE,
            "correlation_id": correlation_id,
        },
    )


_INGRESS_FUTURE_TOLERANCE_SECONDS = 300


def _ingress_clock_refusal(event_timestamp: datetime) -> str | None:
    """Return the governed refusal for an implausible provider instant.

    XXIV (A9/B7): the database trigger already refuses future instants,
    but only after the relay has started persistence, which surfaces as
    an ungoverned HTTP 500. The relay must reach the same verdict before
    any write and route the arrival to durable DLQ. Stale arrivals are
    also outside the governed financial horizon: they must not
    persist as authenticated money with no possible consequence.
    """
    moment = (
        event_timestamp.astimezone(timezone.utc)
        if event_timestamp.tzinfo is not None
        else event_timestamp.replace(tzinfo=timezone.utc)
    )
    now = datetime.now(timezone.utc)
    if moment > now + timedelta(seconds=_INGRESS_FUTURE_TOLERANCE_SECONDS):
        return "event_timestamp_future_refused"
    horizon = timedelta(
        days=int(settings.ATTRIBUTION_DETERMINISTIC_DEFAULT_LOOKBACK_DAYS)
    )
    if moment < now - horizon:
        return "event_timestamp_outside_governed_horizon"
    return None


async def _route_governed_ingress_refusal(
    *,
    tenant_id,
    source: str,
    reason: str,
    idempotency_key: str,
    raw_body: bytes,
    identity_payload: dict[str, Any] | None,
    request_headers: dict[str, str] | None,
):
    set_business_correlation_id(idempotency_key)
    correlation_uuid = str(_make_correlation_uuid(idempotency_key))
    dead = await _route_to_dlq_direct(
        tenant_id,
        source,
        correlation_uuid,
        {
            "event_type": "purchase",
            "vendor": source,
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_uuid,
            "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
            "raw_body_bytes": len(raw_body),
            "refusal": reason,
        },
        reason,
        error_type="validation_error",
        identity_payload=identity_payload
        or {"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
        request_headers=request_headers,
    )
    return {
        "status": "dlq_routed",
        "dead_event_id": str(dead.id) if dead is not None else None,
        "error": reason,
    }


async def _route_to_dlq_direct(
    tenant_id,
    source: str,
    correlation_id: str,
    payload: dict,
    error_message: str,
    error_type: str = "validation_error",
    identity_payload: dict[str, Any] | None = None,
    request_headers: dict[str, str] | None = None,
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
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
        return dead


async def _handle_ingestion(
    tenant_id,
    event_data: dict,
    idempotency_key: str,
    source: str,
    verified_at: datetime,
    identity_payload: dict[str, Any] | None = None,
    request_headers: dict[str, str] | None = None,
    auth_consequence: dict[str, Any] | None = None,
):
    verification_decision_time = (
        verified_at.astimezone(timezone.utc)
        if verified_at.tzinfo is not None
        else verified_at.replace(tzinfo=timezone.utc)
    )
    event_data = {
        **event_data,
        **_verified_revenue_state(),
        "verified_at": verification_decision_time,
        "idempotency_key": idempotency_key,
    }
    # Use transactional helper to preserve DLQ commits on validation errors
    # XVI (H-XVI-R13/R16): canonical persistence is USD-only. A non-USD
    # event that survives schema validation would otherwise reach the
    # post-commit finalizer, be refused there, and surface as HTTP 500
    # with no durable record -- a pointless provider retry storm over a
    # request that can never authenticate, and no DLQ continuation.
    # Route governed currency exclusion to durable DLQ instead (same
    # honesty class as timestamp-less DLQ: preserved, visible, retryable
    # via the DLQ remediation path, explicitly not authenticated). True
    # parser divergence still propagates as 500 (deployment defect that
    # must page, with redelivery succeeding after the fix).
    try:
        result = await ingest_with_transaction(
            tenant_id=tenant_id,
            event_data=event_data,
            idempotency_key=idempotency_key,
            source=source,
            identity_payload=identity_payload,
            request_headers=request_headers,
            auth_consequence=auth_consequence,
        )
    except IngestionValidationError as txn_exc:
        refusal = str(txn_exc)
        if (
            "b26_p2_ingress_relay_refused" in refusal
            or "b26_p2_ingress_authority_refused" in refusal
        ):
            logger.warning(
                "b26_p2_ingress_authority_refused",
                extra={
                    "tenant_id": str(tenant_id),
                    "source": source,
                    "event_type": "ingestion",
                    "correlation_id": get_request_correlation_id()
                    or idempotency_key,
                    "refusal": refusal,
                },
            )
            return {
                "status": "authority_refused",
                "idempotency_key": idempotency_key,
                "error": refusal,
            }
        if "b26_p2_ingress_relay_unreachable" in refusal or (
            "b26_p2_ingress_relay_bad_response" in refusal
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=refusal,
            ) from txn_exc
        if "b26_p2_handoff_binding_refused" in refusal:
            dead = await _route_to_dlq_direct(
                tenant_id,
                source,
                get_request_correlation_id() or idempotency_key,
                {
                    "event_data": event_data,
                    "idempotency_key": idempotency_key,
                    "identity_payload": identity_payload,
                },
                f"handoff_binding_refused:{refusal}"[:500],
                error_type="validation_error",
                identity_payload=identity_payload,
                request_headers=request_headers,
            )
            return {
                "status": "dlq_routed",
                "dead_event_id": str(dead.id) if dead else None,
                "error": "b26_p2_handoff_binding_refused",
            }
        if (
            "b26_p2_unsupported_currency_refused" not in refusal
            and "b26_p2_ingress_event_future_refused" not in refusal
        ):
            raise
        dead = await _route_to_dlq_direct(
            tenant_id,
            source,
            get_request_correlation_id() or idempotency_key,
            {
                "event_data": event_data,
                "idempotency_key": idempotency_key,
                "identity_payload": identity_payload,
            },
            f"unsupported_currency_excluded:{txn_exc}"
            if "b26_p2_unsupported_currency_refused" in refusal
            else "event_timestamp_future_refused",
            error_type="validation_error",
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id) if dead else None,
            "error": str(txn_exc),
        }
    if result.status == "success":
        correlation_id = get_request_correlation_id() or idempotency_key
        event_timestamp = event_data.get("event_timestamp")
        session_id = result.session_id
        if event_timestamp and session_id and not result.is_duplicate:
            _schedule_downstream_tasks(
                tenant_id=tenant_id,
                event_timestamp=str(event_timestamp),
                session_id=str(session_id),
                correlation_id=str(correlation_id),
            )
        if event_timestamp and result.event_id and not result.is_duplicate:
            await _dispatch_b23_match_task_from_persisted_ingress(
                tenant_id=tenant_id,
                event_id=str(result.event_id),
                event_timestamp=str(event_timestamp),
                correlation_id=str(correlation_id),
            )
        if event_timestamp and result.event_id and result.is_duplicate:
            # Provider retry recovery: a duplicate webhook re-drives a
            # stranded pending intent with the stable task identity instead
            # of reporting success while the intent remains unconducted.
            await _redrive_pending_dispatch_for_ingress(
                tenant_id=tenant_id,
                event_id=str(result.event_id),
                correlation_id=str(correlation_id),
            )
        return {
            "status": "success",
            "event_id": result.event_id,
            "idempotency_key": idempotency_key,
            "channel": result.channel,
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
        "error": result.error,
    }


@router.post(
    "/webhooks/shopify/order_create",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
)
async def shopify_order_create(
    request: Request,
    tenant_info=Depends(shopify_webhook_auth),
):
    raw_body = await _resolve_raw_body_for_webhook_auth(request)
    request_headers = _request_headers_for_privacy_boundary(request)
    identity_payload, parse_error = _parse_json_object(raw_body)
    if parse_error is not None:
        idempotency_key = _malformed_idempotency_key(
            source="shopify",
            raw_body=raw_body,
            suffix="order_create_invalid_json",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message=f"invalid_json_payload:{parse_error}",
            vendor_payload={
                "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
                "raw_body_bytes": len(raw_body),
                "parse_error": parse_error,
            },
            identity_payload={"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
            request_headers=request_headers,
        )

    unsupported_reason = _unsupported_event_family_reason(
        provider="shopify",
        payload=identity_payload,
        request_headers=request_headers,
    )
    if unsupported_reason is not None:
        return await _route_unsupported_event_family(
            source="shopify",
            raw_body=raw_body,
            reason=unsupported_reason,
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    try:
        payload = ShopifyOrderCreateRequest.model_validate(identity_payload)
        if not payload.id:
            raise ValueError("Missing order id")
    except (ValidationError, ValueError) as exc:
        idempotency_key = _malformed_idempotency_key(
            source="shopify",
            raw_body=raw_body,
            suffix="order_create_schema_invalid",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message=f"schema_validation_error:{exc}",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    idempotency_key = str(uuid5(NAMESPACE_URL, f"shopify_order_create_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    if payload.currency is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_currency",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.total_price is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_total_price",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_currency = payload.currency.upper()
    verified_amount_scale = _canonical_money_scale(verified_amount_currency)
    raw_amount = payload.total_price
    parsed_minor = _try_decimal_to_minor_units(raw_amount, scale=verified_amount_scale)
    if parsed_minor is None or parsed_minor <= 0:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:invalid_total_price",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_minor = parsed_minor
    # XV (H-XV-R1): the authoritative timestamp must come from the
    # provider-signed bytes, never from the verifier's wall clock. A
    # missing provider instant is malformed (DLQ), not now().
    if payload.created_at is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_created_at",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        CommerceDerivationError,
        derive_commerce,
    )

    try:
        derive_commerce("shopify", raw_body)
    except CommerceDerivationError as exc:
        return await _route_unsupported_event_family(
            source="shopify",
            raw_body=raw_body,
            reason=str(exc),
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    clock_refusal = _ingress_clock_refusal(payload.created_at)
    if clock_refusal is not None:
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            reason=clock_refusal,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if verified_amount_currency != "USD":
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="shopify",
            reason=f"unsupported_currency_excluded:{verified_amount_currency}",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    event_data = {
        "event_type": "purchase",
        "event_timestamp": payload.created_at.isoformat(),
        "revenue_amount": _minor_units_to_decimal_string(
            verified_amount_minor, scale=verified_amount_scale
        ),
        "currency": verified_amount_currency,
        "session_id": str(generate_privacy_session_id()),
        "vendor": "shopify",
        "utm_source": "shopify",
        "external_event_id": str(payload.id),
        "order_id": str(payload.id),
        "provider": "shopify",
        "provider_native_event_reference": str(payload.id),
        "provider_native_commerce_reference": str(payload.id),
        "normalized_commerce_reference_kind": "shopify_order_id",
        "normalized_commerce_reference_value": str(payload.id),
        "verified_amount_minor": verified_amount_minor,
        "verified_amount_currency": verified_amount_currency,
        "verified_amount_scale": verified_amount_scale,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(
        tenant_info["tenant_id"],
        event_data,
        idempotency_key,
        source="shopify",
        verified_at=_resolve_verified_at(tenant_info),
        identity_payload=identity_payload,
        request_headers=request_headers,
        auth_consequence=_build_provider_auth_consequence(
            tenant_info=tenant_info,
            provider="shopify",
            provider_event_reference=str(payload.id),
            provider_topic=_provider_topic_for_family(
                provider="shopify", request_headers=request_headers
            ),
        ),
    )


async def _conduct_adjustment_events(
    *,
    tenant_info: dict[str, Any],
    provider: str,
    x_idempotency_key: str | None,
) -> WebhookResponse:
    """Authenticate every completed effect in one provider notification.

    A WooCommerce order snapshot can carry several unseen refunds and a Stripe
    charge.refunded snapshot can carry a cumulative refunds collection. The
    authentication root verifies the original signed bytes once per selected
    refund identity; each effect is persisted and enqueued separately. No
    effect is selected by "latest" and silently dropped.
    """
    import base64  # noqa: PLC0415

    import httpx  # noqa: PLC0415

    from app.webhooks.commerce_derivation import (  # noqa: PLC0415
        adjustment_event_references,
    )

    envelope = tenant_info.get("relay_envelope") or {}
    raw_body_b64 = str(envelope.get("raw_body_b64") or "")
    signature_header = str(envelope.get("signature_header") or "")
    api_key = str(envelope.get("api_key") or "")
    if not raw_body_b64 or not signature_header or not api_key:
        raise HTTPException(status_code=500, detail="adjustment relay envelope missing")
    try:
        raw_body = base64.b64decode(raw_body_b64, validate=True)
        references = adjustment_event_references(provider, raw_body)
    except Exception:  # noqa: BLE001
        references = []
    if not references:
        references = [None]
    root_url = os.getenv("B26_P2_AUTH_ROOT_URL", "").strip().rstrip("/")
    if not root_url:
        raise HTTPException(status_code=503, detail="authentication root unavailable")
    adjustments: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for reference in references:
                payload = {
                    "api_key": api_key,
                    "provider": provider,
                    "raw_body_b64": raw_body_b64,
                    "signature_header": signature_header,
                }
                if reference is not None:
                    payload["provider_event_reference"] = reference
                response = await client.post(
                    root_url + "/v1/authenticate-adjustment", json=payload
                )
                if response.status_code != 200:
                    detail = "adjustment_authentication_refused"
                    try:
                        parsed = response.json()
                        detail = str(parsed.get("detail") or detail)
                    except Exception:  # noqa: BLE001
                        pass
                    raise HTTPException(status_code=409, detail=detail)
                try:
                    adjustments.append(response.json())
                except Exception as exc:  # noqa: BLE001
                    raise HTTPException(
                        status_code=502, detail="adjustment response invalid"
                    ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503, detail="authentication root unavailable"
        ) from exc
    if not adjustments:
        raise HTTPException(status_code=409, detail="no completed adjustment")
    try:
        from app.tasks.revenue_verification import (  # noqa: PLC0415
            register_b23_post_capture_correction_task,
        )

        for adjustment in adjustments:
            register_b23_post_capture_correction_task.apply_async(
                args=[
                    str(tenant_info["tenant_id"]),
                    str(adjustment["verdict_id"]),
                    provider,
                    str(adjustment["event_type"]),
                    str(adjustment["provider_native_event_reference"]),
                    False,
                    str(uuid4()),
                ],
                queue=QUEUE_B23_MATCH_ENGINE,
                routing_key=f"{QUEUE_B23_MATCH_ENGINE}.task",
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("adjustment_enqueue_failed")
        raise HTTPException(
            status_code=503,
            detail=f"adjustment queue unavailable:{type(exc).__name__}",
        ) from exc
    return WebhookResponse(
        status="success",
        event_id=str(adjustments[0]["adjustment_evidence_id"]),
        idempotency_key=(
            x_idempotency_key
            or str(adjustments[0]["provider_native_event_reference"])
        ),
    )


@router.post(
    "/webhooks/stripe/charge_refunded",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
    include_in_schema=False,
)
async def stripe_charge_refunded(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(stripe_webhook_auth),
):
    """Authenticate a Stripe refund adjustment and conduct each completed effect."""
    return await _conduct_adjustment_events(
        tenant_info=tenant_info,
        provider="stripe",
        x_idempotency_key=x_idempotency_key,
    )


@router.post(
    "/webhooks/shopify/refunds_create",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
    include_in_schema=False,
)
async def shopify_refund(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(shopify_webhook_auth),
):
    """Authenticate a Shopify refund adjustment and conduct it."""
    return await _conduct_adjustment_events(
        tenant_info=tenant_info,
        provider="shopify",
        x_idempotency_key=x_idempotency_key,
    )


@router.post(
    "/webhooks/woocommerce/order_refunded",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
    include_in_schema=False,
)
async def woocommerce_order_refunded(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(woocommerce_webhook_auth),
):
    """Authenticate every completed WooCommerce refund in an order snapshot."""
    return await _conduct_adjustment_events(
        tenant_info=tenant_info,
        provider="woocommerce",
        x_idempotency_key=x_idempotency_key,
    )


@router.post(
    "/webhooks/paypal/payment_capture_refunded",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
    include_in_schema=False,
)
async def paypal_payment_capture_refunded(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(paypal_webhook_auth),
):
    """Authenticate every completed WooCommerce refund in an order snapshot."""
    return await _conduct_adjustment_events(
        tenant_info=tenant_info,
        provider="woocommerce",
        x_idempotency_key=x_idempotency_key,
    )


@router.post(
    "/webhooks/stripe/payment_intent_succeeded",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
    include_in_schema=False,
)
async def stripe_payment_intent_succeeded(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(stripe_webhook_auth),
):
    raw_body = await _resolve_raw_body_for_webhook_auth(request)
    request_headers = _request_headers_for_privacy_boundary(request)
    identity_payload, parse_error = _parse_json_object(raw_body)
    if parse_error is not None:
        idempotency_key = x_idempotency_key or _malformed_idempotency_key(
            source="stripe",
            raw_body=raw_body,
            suffix="payment_intent_succeeded_invalid_json",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message=f"invalid_json_payload:{parse_error}",
            vendor_payload={
                "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
                "raw_body_bytes": len(raw_body),
                "parse_error": parse_error,
            },
            identity_payload={"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
            request_headers=request_headers,
        )

    unsupported_reason = _unsupported_event_family_reason(
        provider="stripe",
        payload=identity_payload,
        request_headers=request_headers,
    )
    if unsupported_reason is not None:
        return await _route_unsupported_event_family(
            source="stripe",
            raw_body=raw_body,
            reason=unsupported_reason,
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    try:
        payload = StripePaymentIntentSucceededRequest.model_validate(identity_payload)
        if not payload.id and not x_idempotency_key:
            raise ValueError("Missing payment intent id")
    except (ValidationError, ValueError) as exc:
        idempotency_key = x_idempotency_key or _malformed_idempotency_key(
            source="stripe",
            raw_body=raw_body,
            suffix="payment_intent_succeeded_schema_invalid",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message=f"schema_validation_error:{exc}",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    idempotency_key = x_idempotency_key or str(
        uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_{payload.id}")
    )
    set_business_correlation_id(idempotency_key)
    if payload.amount is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_amount_minor",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.amount <= 0:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:non_positive_amount_minor",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.currency is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_currency",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    ts = (
        datetime.fromtimestamp(payload.created, tz=timezone.utc)
        if payload.created
        else None
    )
    # XV (H-XV-R1): provider instant required; wall-clock substitution
    # would detach authenticated meaning from authenticated bytes.
    if ts is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_created",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_minor = int(payload.amount)
    verified_amount_currency = payload.currency.upper()
    verified_amount_scale = _canonical_money_scale(verified_amount_currency)
    clock_refusal = _ingress_clock_refusal(ts)
    if clock_refusal is not None:
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            reason=clock_refusal,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if verified_amount_currency != "USD":
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            reason=f"unsupported_currency_excluded:{verified_amount_currency}",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": _minor_units_to_decimal_string(
            verified_amount_minor, scale=verified_amount_scale
        ),
        "currency": verified_amount_currency,
        "session_id": str(generate_privacy_session_id()),
        "vendor": "stripe",
        "utm_source": "stripe",
        "external_event_id": payload.id,
        "order_id": payload.id,
        "provider": "stripe",
        "provider_native_event_reference": payload.id,
        "provider_native_commerce_reference": payload.id,
        "normalized_commerce_reference_kind": "stripe_payment_intent_id",
        "normalized_commerce_reference_value": payload.id,
        "verified_amount_minor": verified_amount_minor,
        "verified_amount_currency": verified_amount_currency,
        "verified_amount_scale": verified_amount_scale,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(
        tenant_info["tenant_id"],
        event_data,
        idempotency_key,
        source="stripe",
        verified_at=_resolve_verified_at(tenant_info),
        identity_payload=identity_payload,
        request_headers=request_headers,
        auth_consequence=_build_provider_auth_consequence(
            tenant_info=tenant_info,
            provider="stripe",
            provider_event_reference=str(payload.id),
            provider_topic=None,
        ),
    )


@router.post(
    "/webhooks/stripe/payment_intent/succeeded",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
)
async def stripe_payment_intent_succeeded_v2(
    request: Request,
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
    tenant_info=Depends(stripe_webhook_auth),
):
    """
    Stripe payment_intent.succeeded webhook (contract path).

    R3 semantics:
    - Signature/tenant failures: 401 (never DLQ)
    - PII present in provider payload: accepted, pseudonymized, sanitized before durable write
    - Malformed payload: DLQ with sanitized payload, no canonical insert
    - Duplicate valid events: idempotent success (no 5xx)
    """
    raw_body = getattr(request.state, "original_body", None) or await request.body()
    if isinstance(raw_body, bytearray):
        raw_body = bytes(raw_body)
    if not isinstance(raw_body, bytes):
        raw_body = bytes(raw_body or b"")
    stripped_body = await request.body()
    request_headers = _request_headers_for_privacy_boundary(request)

    identity_payload: dict[str, Any] = {}
    payload: dict[str, Any] = {}
    payload_parse_error: str | None = None
    try:
        parsed_identity = json.loads(raw_body.decode("utf-8"))
        if not isinstance(parsed_identity, dict):
            raise ValueError("payload root must be a JSON object")
        identity_payload = parsed_identity
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        payload_parse_error = str(exc)
    if payload_parse_error is None:
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
    vendor_for_normalization = "stripe"
    utm_source_for_normalization = "stripe"
    utm_medium_for_normalization: str | None = None
    session_hint_for_authority: str | None = None
    order_id_for_resolution: str | None = None
    click_id_for_resolution: str | None = None
    if payload_parse_error is None:
        try:
            event_id = payload.get("id")
            created_epoch = payload.get("created")
            obj = (payload.get("data") or {}).get("object") or {}
            pi_id = obj.get("id")
            amount_cents = obj.get("amount")
            currency = obj.get("currency")
            metadata = (
                obj.get("metadata") if isinstance(obj.get("metadata"), dict) else {}
            )
            if metadata:
                vendor_candidate = metadata.get("vendor")
                if isinstance(vendor_candidate, str) and vendor_candidate.strip():
                    vendor_for_normalization = vendor_candidate.strip().lower()
                utm_source_candidate = metadata.get("utm_source")
                if (
                    isinstance(utm_source_candidate, str)
                    and utm_source_candidate.strip()
                ):
                    utm_source_for_normalization = utm_source_candidate.strip()
                utm_medium_candidate = metadata.get("utm_medium")
                if (
                    isinstance(utm_medium_candidate, str)
                    and utm_medium_candidate.strip()
                ):
                    utm_medium_for_normalization = utm_medium_candidate.strip()
                session_id_candidate = metadata.get("session_id") or metadata.get(
                    "skeldir_session_id"
                )
                if (
                    isinstance(session_id_candidate, str)
                    and session_id_candidate.strip()
                ):
                    parsed_session_hint = session_id_candidate.strip()
                    try:
                        UUID(parsed_session_hint)
                    except ValueError:
                        session_hint_for_authority = None
                    else:
                        session_hint_for_authority = parsed_session_hint
                order_id_for_resolution = _resolution_token(
                    metadata.get("order_id") or metadata.get("order")
                )
                click_id_for_resolution = _resolution_token(
                    metadata.get("click_id")
                    or metadata.get("gclid")
                    or metadata.get("fbclid")
                )
            if order_id_for_resolution is None:
                order_id_for_resolution = _resolution_token(pi_id)
            if not idempotency_key and pi_id:
                idempotency_key = str(
                    uuid5(NAMESPACE_URL, f"stripe_payment_intent_succeeded_{pi_id}")
                )
        except Exception:
            # Handled as malformed below (routes to DLQ).
            pass
    elif not idempotency_key:
        # Keep malformed-body routing deterministic even without a client idempotency key.
        body_sha256 = hashlib.sha256(raw_body).hexdigest()
        idempotency_key = str(
            uuid5(
                NAMESPACE_URL,
                f"stripe_payment_intent_succeeded_invalid_json_{body_sha256}",
            )
        )

    unsupported_reason = None
    if payload_parse_error is None:
        # XIX: parseable but familyless shapes are refused here with an
        # explicit DLQ disposition (unparseable bodies are handled as
        # malformed below, preserving request-key accounting).
        unsupported_reason = _unsupported_event_family_reason(
            provider="stripe",
            payload=identity_payload or payload,
            request_headers=request_headers,
        )
    if unsupported_reason is not None:
        return await _route_unsupported_event_family(
            source="stripe",
            raw_body=raw_body,
            reason=unsupported_reason,
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload or payload,
            request_headers=request_headers,
        )

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
            identity_payload=identity_payload
            or {
                "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
            },
            request_headers=request_headers,
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "validation_error",
        }

    # Validate minimal required shape; route any failure to DLQ (never 5xx)
    try:
        if not isinstance(created_epoch, int):
            raise ValueError("created must be an integer unix timestamp")
        if not isinstance(amount_cents, int):
            raise ValueError("amount must be an integer cents value")
        if amount_cents <= 0:
            raise ValueError("amount must be a positive integer cents value")
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
            identity_payload=identity_payload or payload,
            request_headers=request_headers,
        )
        return {
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "validation_error",
        }

    ts = datetime.fromtimestamp(created_epoch, tz=timezone.utc)
    verified_amount_minor = int(amount_cents)
    verified_amount_currency = currency.upper()
    verified_amount_scale = _canonical_money_scale(verified_amount_currency)
    clock_refusal = _ingress_clock_refusal(ts)
    if clock_refusal is not None:
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            reason=clock_refusal,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload or payload,
            request_headers=request_headers,
        )
    if verified_amount_currency != "USD":
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="stripe",
            reason=f"unsupported_currency_excluded:{verified_amount_currency}",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload or payload,
            request_headers=request_headers,
        )
    verification_decision_time = _resolve_verified_at(tenant_info)
    provider_event_reference = _resolution_token(event_id) or pi_id
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": _minor_units_to_decimal_string(
            verified_amount_minor, scale=verified_amount_scale
        ),
        "currency": verified_amount_currency,
        "session_id": session_hint_for_authority or str(generate_privacy_session_id()),
        "vendor": vendor_for_normalization,
        "utm_source": utm_source_for_normalization,
        "external_event_id": pi_id,
        "order_id": order_id_for_resolution or pi_id,
        "provider": "stripe",
        "provider_native_event_reference": provider_event_reference,
        "provider_native_commerce_reference": pi_id,
        "normalized_commerce_reference_kind": "stripe_payment_intent_id",
        "normalized_commerce_reference_value": pi_id,
        "verified_amount_minor": verified_amount_minor,
        "verified_amount_currency": verified_amount_currency,
        "verified_amount_scale": verified_amount_scale,
        "correlation_id": correlation_uuid,
        "vendor_payload": payload,
        **_verified_revenue_state(),
        "verified_at": verification_decision_time,
    }
    if utm_medium_for_normalization:
        event_data["utm_medium"] = utm_medium_for_normalization
    if click_id_for_resolution:
        event_data["click_id"] = click_id_for_resolution

    try:
        result = await ingest_with_transaction(
            tenant_id=tenant_info["tenant_id"],
            event_data={**event_data, "idempotency_key": idempotency_key},
            idempotency_key=idempotency_key,
            source="stripe",
            identity_payload=identity_payload or payload,
            request_headers=request_headers,
            auth_consequence=_build_provider_auth_consequence(
                tenant_info=tenant_info,
                provider="stripe",
                provider_event_reference=str(provider_event_reference),
                provider_topic=None,
            ),
        )
    except IngestionValidationError as txn_exc:
        refusal = str(txn_exc)
        if (
            "b26_p2_unsupported_currency_refused" in refusal
            or "b26_p2_ingress_event_future_refused" in refusal
        ):
            return await _route_governed_ingress_refusal(
                tenant_id=tenant_info["tenant_id"],
                source="stripe",
                reason=(
                    f"unsupported_currency_excluded:{refusal}"
                    if "b26_p2_unsupported_currency_refused" in refusal
                    else "event_timestamp_future_refused"
                ),
                idempotency_key=idempotency_key,
                raw_body=raw_body,
                identity_payload=identity_payload or payload,
                request_headers=request_headers,
            )
        if (
            "b26_p2_ingress_relay_refused" in refusal
            or "b26_p2_ingress_authority_refused" in refusal
        ):
            logger.warning(
                "b26_p2_ingress_authority_refused",
                extra={
                    "tenant_id": str(tenant_info["tenant_id"]),
                    "source": "stripe",
                    "event_type": "ingestion",
                    "correlation_id": get_request_correlation_id()
                    or idempotency_key,
                    "refusal": refusal,
                },
            )
            return {
                "status": "authority_refused",
                "idempotency_key": idempotency_key,
                "error": refusal,
            }
        if "b26_p2_handoff_binding_refused" in refusal:
            return await _route_authenticated_malformed_payload(
                tenant_id=tenant_info["tenant_id"],
                source="stripe",
                idempotency_key=idempotency_key,
                error_message=f"handoff_binding_refused:{refusal}"[:500],
                vendor_payload=identity_payload or payload,
                identity_payload=identity_payload or payload,
                request_headers=request_headers,
            )
        if "b26_p2_ingress_relay_unreachable" in refusal or (
            "b26_p2_ingress_relay_bad_response" in refusal
        ):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=refusal,
            ) from txn_exc
        raise

    if result.status == "success":
        correlation_id = get_request_correlation_id() or idempotency_key
        event_timestamp = event_data.get("event_timestamp")
        session_id = result.session_id
        if event_timestamp and session_id and not result.is_duplicate:
            _schedule_downstream_tasks(
                tenant_id=tenant_info["tenant_id"],
                event_timestamp=str(event_timestamp),
                session_id=str(session_id),
                correlation_id=str(correlation_id),
            )
        if event_timestamp and result.event_id and not result.is_duplicate:
            await _dispatch_b23_match_task_from_persisted_ingress(
                tenant_id=tenant_info["tenant_id"],
                event_id=str(result.event_id),
                event_timestamp=str(event_timestamp),
                correlation_id=str(correlation_id),
            )
        return {
            "status": "success",
            "event_id": result.event_id,
            "idempotency_key": idempotency_key,
            "channel": result.channel,
        }

    # Validation errors routed to DLQ by service: locate via correlation_id for response
    async with get_session(tenant_id=tenant_info["tenant_id"]) as session:
        from sqlalchemy import select

        res = await session.execute(
            select(DeadEvent).where(
                DeadEvent.correlation_id == uuid5(NAMESPACE_URL, idempotency_key)
            )
        )
        dead_event = res.scalar_one_or_none()

    return {
        "status": "dlq_routed",
        "dead_event_id": str(dead_event.id) if dead_event else None,
        "error": result.error_type or result.error,
    }


@router.post(
    "/webhooks/paypal/sale_completed",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
)
async def paypal_sale_completed(
    request: Request,
    tenant_info=Depends(paypal_webhook_auth),
):
    raw_body = await _resolve_raw_body_for_webhook_auth(request)
    request_headers = _request_headers_for_privacy_boundary(request)
    identity_payload, parse_error = _parse_json_object(raw_body)
    if parse_error is not None:
        idempotency_key = _malformed_idempotency_key(
            source="paypal",
            raw_body=raw_body,
            suffix="sale_completed_invalid_json",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message=f"invalid_json_payload:{parse_error}",
            vendor_payload={
                "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
                "raw_body_bytes": len(raw_body),
                "parse_error": parse_error,
            },
            identity_payload={"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
            request_headers=request_headers,
        )

    unsupported_reason = _unsupported_event_family_reason(
        provider="paypal",
        payload=identity_payload,
        request_headers=request_headers,
    )
    if unsupported_reason is not None:
        return await _route_unsupported_event_family(
            source="paypal",
            raw_body=raw_body,
            reason=unsupported_reason,
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    try:
        payload = PayPalSaleCompletedRequest.model_validate(identity_payload)
        if not payload.id or not payload.amount:
            raise ValueError("Missing transaction id or amount")
    except (ValidationError, ValueError) as exc:
        idempotency_key = _malformed_idempotency_key(
            source="paypal",
            raw_body=raw_body,
            suffix="sale_completed_schema_invalid",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message=f"schema_validation_error:{exc}",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    idempotency_key = str(uuid5(NAMESPACE_URL, f"paypal_sale_completed_{payload.id}"))
    set_business_correlation_id(idempotency_key)
    if payload.amount is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_amount",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.amount.currency is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_currency",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.amount.total is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_amount_total",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    ts = payload.create_time
    # XV (H-XV-R1): provider instant required; wall-clock substitution
    # would detach authenticated meaning from authenticated bytes.
    if ts is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_create_time",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_currency = payload.amount.currency.upper()
    verified_amount_scale = _canonical_money_scale(verified_amount_currency)
    raw_amount = payload.amount.total
    parsed_minor = _try_decimal_to_minor_units(raw_amount, scale=verified_amount_scale)
    if parsed_minor is None or parsed_minor <= 0:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:invalid_amount_total",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_minor = parsed_minor
    clock_refusal = _ingress_clock_refusal(ts)
    if clock_refusal is not None:
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            reason=clock_refusal,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if verified_amount_currency != "USD":
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="paypal",
            reason=f"unsupported_currency_excluded:{verified_amount_currency}",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": _minor_units_to_decimal_string(
            verified_amount_minor, scale=verified_amount_scale
        ),
        "currency": verified_amount_currency,
        "session_id": str(generate_privacy_session_id()),
        "vendor": "paypal",
        "utm_source": "paypal",
        "external_event_id": payload.id,
        "order_id": payload.id,
        "provider": "paypal",
        "provider_native_event_reference": payload.id,
        "provider_native_commerce_reference": payload.id,
        "normalized_commerce_reference_kind": "paypal_transaction_id",
        "normalized_commerce_reference_value": payload.id,
        "verified_amount_minor": verified_amount_minor,
        "verified_amount_currency": verified_amount_currency,
        "verified_amount_scale": verified_amount_scale,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(
        tenant_info["tenant_id"],
        event_data,
        idempotency_key,
        source="paypal",
        verified_at=_resolve_verified_at(tenant_info),
        identity_payload=identity_payload,
        request_headers=request_headers,
        auth_consequence=_build_provider_auth_consequence(
            tenant_info=tenant_info,
            provider="paypal",
            provider_event_reference=str(payload.id),
            provider_topic=None,
        ),
    )


@router.post(
    "/webhooks/woocommerce/order_completed",
    response_model=WebhookResponse,
    responses={401: UNAUTHORIZED_PROBLEM_RESPONSE},
)
async def woocommerce_order_completed(
    request: Request,
    tenant_info=Depends(woocommerce_webhook_auth),
):
    raw_body = await _resolve_raw_body_for_webhook_auth(request)
    request_headers = _request_headers_for_privacy_boundary(request)
    identity_payload, parse_error = _parse_json_object(raw_body)
    if parse_error is not None:
        idempotency_key = _malformed_idempotency_key(
            source="woocommerce",
            raw_body=raw_body,
            suffix="order_completed_invalid_json",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message=f"invalid_json_payload:{parse_error}",
            vendor_payload={
                "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
                "raw_body_bytes": len(raw_body),
                "parse_error": parse_error,
            },
            identity_payload={"raw_body_sha256": hashlib.sha256(raw_body).hexdigest()},
            request_headers=request_headers,
        )

    unsupported_reason = _unsupported_event_family_reason(
        provider="woocommerce",
        payload=identity_payload,
        request_headers=request_headers,
    )
    if unsupported_reason is not None:
        return await _route_unsupported_event_family(
            source="woocommerce",
            raw_body=raw_body,
            reason=unsupported_reason,
            tenant_id=tenant_info["tenant_id"],
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    try:
        payload = WooCommerceOrderCompletedRequest.model_validate(identity_payload)
        if not payload.id:
            raise ValueError("Missing order id")
    except (ValidationError, ValueError) as exc:
        idempotency_key = _malformed_idempotency_key(
            source="woocommerce",
            raw_body=raw_body,
            suffix="order_completed_schema_invalid",
        )
        set_business_correlation_id(idempotency_key)
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message=f"schema_validation_error:{exc}",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )

    idempotency_key = str(
        uuid5(NAMESPACE_URL, f"woocommerce_order_completed_{payload.id}")
    )
    set_business_correlation_id(idempotency_key)
    if payload.currency is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_currency",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if payload.total is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_total",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    ts = payload.date_completed
    # XV (H-XV-R1): provider instant required; wall-clock substitution
    # would detach authenticated meaning from authenticated bytes.
    if ts is None:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:missing_date_completed",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_currency = payload.currency.upper()
    verified_amount_scale = _canonical_money_scale(verified_amount_currency)
    raw_amount = payload.total
    parsed_minor = _try_decimal_to_minor_units(raw_amount, scale=verified_amount_scale)
    if parsed_minor is None or parsed_minor <= 0:
        return await _route_authenticated_malformed_payload(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            idempotency_key=idempotency_key,
            error_message="schema_validation_error:invalid_total",
            vendor_payload=identity_payload,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    verified_amount_minor = parsed_minor
    clock_refusal = _ingress_clock_refusal(ts)
    if clock_refusal is not None:
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            reason=clock_refusal,
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    if verified_amount_currency != "USD":
        return await _route_governed_ingress_refusal(
            tenant_id=tenant_info["tenant_id"],
            source="woocommerce",
            reason=f"unsupported_currency_excluded:{verified_amount_currency}",
            idempotency_key=idempotency_key,
            raw_body=raw_body,
            identity_payload=identity_payload,
            request_headers=request_headers,
        )
    event_data = {
        "event_type": "purchase",
        "event_timestamp": ts.isoformat(),
        "revenue_amount": _minor_units_to_decimal_string(
            verified_amount_minor, scale=verified_amount_scale
        ),
        "currency": verified_amount_currency,
        "session_id": str(generate_privacy_session_id()),
        "vendor": "woocommerce",
        "utm_source": "woocommerce",
        "external_event_id": str(payload.id),
        "order_id": str(payload.id),
        "provider": "woocommerce",
        "provider_native_event_reference": str(payload.id),
        "provider_native_commerce_reference": str(payload.id),
        "normalized_commerce_reference_kind": "woocommerce_order_id",
        "normalized_commerce_reference_value": str(payload.id),
        "verified_amount_minor": verified_amount_minor,
        "verified_amount_currency": verified_amount_currency,
        "verified_amount_scale": verified_amount_scale,
        "correlation_id": str(_make_correlation_uuid(idempotency_key)),
    }
    return await _handle_ingestion(
        tenant_info["tenant_id"],
        event_data,
        idempotency_key,
        source="woocommerce",
        verified_at=_resolve_verified_at(tenant_info),
        identity_payload=identity_payload,
        request_headers=request_headers,
        auth_consequence=_build_provider_auth_consequence(
            tenant_info=tenant_info,
            provider="woocommerce",
            provider_event_reference=str(payload.id),
            provider_topic=_provider_topic_for_family(
                provider="woocommerce", request_headers=request_headers
            ),
        ),
    )
