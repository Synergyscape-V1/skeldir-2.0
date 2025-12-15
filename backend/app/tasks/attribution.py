"""
Attribution worker stubs for B0.5.3+ foundation.

These tasks are deterministic, enforce tenant context, and record basic metadata
for attribution workflows without implementing domain logic.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.celery_app import celery_app
from app.observability.context import set_request_correlation_id, set_tenant_id
from app.tasks.context import tenant_task

logger = logging.getLogger(__name__)


class AttributionTaskPayload(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant context for RLS")
    correlation_id: Optional[str] = Field(None, description="Correlation for observability")
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid4()), description="Idempotency/trace id")
    window_start: Optional[str] = Field(None, description="Attribution window start timestamp")
    window_end: Optional[str] = Field(None, description="Attribution window end timestamp")


def _prepare_context(model: AttributionTaskPayload) -> str:
    correlation = model.correlation_id or str(uuid4())
    set_request_correlation_id(correlation)
    set_tenant_id(model.tenant_id)
    return correlation


@celery_app.task(
    bind=True,
    name="app.tasks.attribution.recompute_window",
    routing_key="attribution.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def recompute_window(
    self,
    tenant_id: UUID,
    window_start: Optional[str] = None,
    window_end: Optional[str] = None,
    correlation_id: Optional[str] = None,
    fail: bool = False,
):
    """
    Attribution recompute window stub task.

    Args:
        tenant_id: Tenant context for RLS enforcement
        window_start: Start of attribution window (ISO timestamp)
        window_end: End of attribution window (ISO timestamp)
        correlation_id: Request correlation for observability
        fail: If True, deliberately raise an error for DLQ testing

    Returns:
        Dict with status and metadata

    Raises:
        ValueError: If fail=True (for DLQ testing)
    """
    model = AttributionTaskPayload(
        tenant_id=tenant_id,
        correlation_id=correlation_id,
        window_start=window_start,
        window_end=window_end,
    )
    correlation = _prepare_context(model)

    # B0.5.3.1: Deliberate failure path for DLQ testing
    if fail:
        logger.warning(
            "attribution_recompute_window_failure_requested",
            extra={
                "task_id": self.request.id,
                "tenant_id": str(model.tenant_id),
                "correlation_id": correlation,
            },
        )
        raise ValueError("attribution recompute failure requested")

    logger.info(
        "attribution_recompute_window_stub",
        extra={
            "task_id": self.request.id,
            "tenant_id": str(model.tenant_id),
            "correlation_id": correlation,
            "window_start": model.window_start,
            "window_end": model.window_end,
        },
    )

    return {
        "status": "accepted",
        "window_start": model.window_start,
        "window_end": model.window_end,
        "request_id": model.request_id,
        "correlation_id": correlation,
    }
