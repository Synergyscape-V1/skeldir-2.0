"""
LLM worker stubs for B0.5.x foundation.

These tasks are deterministic, enforce tenant context, and record basic metadata
for routing/explanation/investigation/budget workflows without invoking LLMs.
"""

import logging
from typing import Optional
from uuid import UUID, uuid4

from app.celery_app import celery_app
from app.observability.context import set_request_correlation_id, set_tenant_id
try:
    from backend.app.schemas.llm_payloads import LLMTaskPayload
except ModuleNotFoundError:  # pragma: no cover - runtime may only expose `app` on PYTHONPATH
    from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.context import tenant_task

logger = logging.getLogger(__name__)


def _prepare_context(model: LLMTaskPayload) -> str:
    correlation = model.correlation_id or str(uuid4())
    set_request_correlation_id(correlation)
    set_tenant_id(model.tenant_id)
    return correlation


@celery_app.task(
    bind=True,
    name="app.tasks.llm.route",
    routing_key="llm.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def llm_routing_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    model = LLMTaskPayload(tenant_id=tenant_id, correlation_id=correlation_id, prompt=payload, max_cost_cents=max_cost_cents)
    correlation = _prepare_context(model)
    logger.info(
        "llm_routing_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return {"status": "accepted", "route": "noop", "request_id": model.request_id, "correlation_id": correlation}


@celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_explanation_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    model = LLMTaskPayload(tenant_id=tenant_id, correlation_id=correlation_id, prompt=payload, max_cost_cents=max_cost_cents)
    correlation = _prepare_context(model)
    logger.info(
        "llm_explanation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return {"status": "accepted", "explanation": "not-implemented", "request_id": model.request_id, "correlation_id": correlation}


@celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_investigation_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    model = LLMTaskPayload(tenant_id=tenant_id, correlation_id=correlation_id, prompt=payload, max_cost_cents=max_cost_cents)
    correlation = _prepare_context(model)
    logger.info(
        "llm_investigation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return {"status": "accepted", "investigation": "queued", "request_id": model.request_id, "correlation_id": correlation}


@celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_budget_optimization_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    model = LLMTaskPayload(tenant_id=tenant_id, correlation_id=correlation_id, prompt=payload, max_cost_cents=max_cost_cents)
    correlation = _prepare_context(model)
    logger.info(
        "llm_budget_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return {"status": "accepted", "budget_action": "noop", "request_id": model.request_id, "correlation_id": correlation}
