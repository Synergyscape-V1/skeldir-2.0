import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.context import (
    set_request_correlation_id,
    set_business_correlation_id,
    set_tenant_id,
    get_request_correlation_id,
)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """
    Captures correlation_id from header (X-Correlation-ID) or generates one.
    Adds the correlation_id to response headers and initializes tenant_id context (filled later).
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        set_request_correlation_id(correlation_id)
        # business correlation is set later (idempotency key)
        set_business_correlation_id(None)
        set_tenant_id(None)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = get_request_correlation_id() or correlation_id
        return response
