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
from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.context import run_in_worker_loop, tenant_task
from app.workers.llm import (
    generate_explanation,
    optimize_budget,
    route_request,
    run_investigation,
)

logger = logging.getLogger(__name__)


def _prepare_context(model: LLMTaskPayload) -> str:
    correlation = model.correlation_id or str(uuid4())
    set_request_correlation_id(correlation)
    set_tenant_id(model.tenant_id)
    return correlation


def _run_async(coro_factory, *args, **kwargs):
    return run_in_worker_loop(coro_factory(*args, **kwargs))


@celery_app.task(
    bind=True,
    name="app.tasks.llm.route",
    routing_key="llm.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def llm_routing_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    correlation = correlation_id or str(uuid4())
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_routing_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return _run_async(route_request, model)


@celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_explanation_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    correlation = correlation_id or str(uuid4())
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_explanation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return _run_async(generate_explanation, model)


@celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_investigation_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    correlation = correlation_id or str(uuid4())
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_investigation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return _run_async(run_investigation, model)


@celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_budget_optimization_worker(self, payload: dict, tenant_id: UUID, correlation_id: Optional[str] = None, max_cost_cents: int = 0):
    correlation = correlation_id or str(uuid4())
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_budget_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    return _run_async(optimize_budget, model)
