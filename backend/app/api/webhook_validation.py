"""
Webhook-specific validation error handling.

Routes malformed/schema-invalid webhook payloads to DLQ instead of returning
default FastAPI 422 responses, so ingestion invariants remain deterministic.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import request_validation_exception_handler

from app.core.config import settings
from app.core.tenant_context import get_tenant_with_webhook_secrets
from app.db.session import get_session
from app.ingestion.dlq_handler import DLQHandler


def _is_webhook_path(path: str) -> bool:
    return path.startswith("/api/webhooks/")


def _derive_vendor(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    # /api/webhooks/{vendor}/...
    if len(parts) >= 3:
        return parts[2]
    return "webhook"


def _parse_correlation_id(request: Request) -> UUID:
    value = request.headers.get("X-Correlation-ID")
    if not value:
        return uuid4()
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return uuid4()


async def handle_request_validation_error(request: Request, exc: RequestValidationError):
    """
    Webhook-only override:
    - malformed/schema-invalid payloads -> dead_events
    - non-webhook routes -> default FastAPI 422
    """
    if not _is_webhook_path(request.url.path):
        return await request_validation_exception_handler(request, exc)

    api_key = request.headers.get(settings.TENANT_API_KEY_HEADER)
    if not api_key:
        return JSONResponse(status_code=401, content={"status": "invalid_tenant_key"})

    try:
        tenant_info = await get_tenant_with_webhook_secrets(api_key)
    except Exception:
        return JSONResponse(status_code=401, content={"status": "invalid_tenant_key"})

    tenant_id = tenant_info["tenant_id"]
    correlation_id = _parse_correlation_id(request)
    idempotency_key = request.headers.get("X-Idempotency-Key")
    raw_body = getattr(request.state, "original_body", b"") or b""

    payload_for_dlq = {
        "event_type": "webhook_validation_error",
        "path": request.url.path,
        "method": request.method,
        "content_type": request.headers.get("content-type"),
        "validation_errors": exc.errors(),
        "correlation_id": str(correlation_id),
        "idempotency_key": idempotency_key,
        "raw_body_dropped": True,
        "raw_body_sha256": hashlib.sha256(raw_body).hexdigest(),
        "raw_body_size_bytes": len(raw_body),
    }

    async with get_session(tenant_id=tenant_id) as session:
        dead = await DLQHandler().route_to_dlq(
            session=session,
            tenant_id=tenant_id,
            original_payload=payload_for_dlq,
            error=ValueError("request_validation_error"),
            correlation_id=str(correlation_id),
            source=_derive_vendor(request.url.path),
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "dlq_routed",
            "dead_event_id": str(dead.id),
            "error": "request_validation_error",
        },
    )

