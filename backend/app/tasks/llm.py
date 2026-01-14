"""
LLM worker stubs for B0.5.x foundation.

These tasks are deterministic, enforce tenant context, and record basic metadata
for routing/explanation/investigation/budget workflows without invoking LLMs.
"""

import hashlib
import logging
from typing import Optional
from uuid import UUID, uuid4

from app.celery_app import celery_app
from app.db.session import get_session
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


def _stable_request_id(tenant_id: UUID, endpoint: str, correlation_id: str) -> str:
    seed = f"{tenant_id}:{endpoint}:{correlation_id}"
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _resolve_request_context(
    *,
    tenant_id: UUID,
    endpoint: str,
    correlation_id: Optional[str],
    request_id: Optional[str],
) -> tuple[str, str]:
    correlation = correlation_id or str(uuid4())
    request = request_id or _stable_request_id(tenant_id, endpoint, correlation)
    return correlation, request


def _retry_kwargs(
    *,
    payload: dict,
    tenant_id: UUID,
    correlation_id: str,
    request_id: str,
    max_cost_cents: int,
) -> dict:
    return {
        "payload": payload,
        "tenant_id": tenant_id,
        "correlation_id": correlation_id,
        "request_id": request_id,
        "max_cost_cents": max_cost_cents,
    }


@celery_app.task(
    bind=True,
    name="app.tasks.llm.route",
    routing_key="llm.task",
    max_retries=3,
    default_retry_delay=30,
)
@tenant_task
def llm_routing_worker(
    self,
    payload: dict,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    max_cost_cents: int = 0,
    force_failure: bool = False,
):
    correlation, request_id = _resolve_request_context(
        tenant_id=tenant_id,
        endpoint="app.tasks.llm.route",
        correlation_id=correlation_id,
        request_id=request_id,
    )
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "request_id": request_id,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_routing_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    async def _execute():
        async with get_session(tenant_id=model.tenant_id) as session:
            return await route_request(model, session=session, force_failure=force_failure)

    try:
        return _run_async(_execute)
    except Exception as exc:
        raise self.retry(
            exc=exc,
            kwargs=_retry_kwargs(
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation,
                request_id=request_id,
                max_cost_cents=max_cost_cents,
            ),
        )


@celery_app.task(bind=True, name="app.tasks.llm.explanation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_explanation_worker(
    self,
    payload: dict,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    max_cost_cents: int = 0,
    force_failure: bool = False,
):
    correlation, request_id = _resolve_request_context(
        tenant_id=tenant_id,
        endpoint="app.tasks.llm.explanation",
        correlation_id=correlation_id,
        request_id=request_id,
    )
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "request_id": request_id,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_explanation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    async def _execute():
        async with get_session(tenant_id=model.tenant_id) as session:
            return await generate_explanation(
                model,
                session=session,
                force_failure=force_failure,
            )

    try:
        return _run_async(_execute)
    except Exception as exc:
        raise self.retry(
            exc=exc,
            kwargs=_retry_kwargs(
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation,
                request_id=request_id,
                max_cost_cents=max_cost_cents,
            ),
        )


@celery_app.task(bind=True, name="app.tasks.llm.investigation", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_investigation_worker(
    self,
    payload: dict,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    max_cost_cents: int = 0,
    force_failure: bool = False,
):
    correlation, request_id = _resolve_request_context(
        tenant_id=tenant_id,
        endpoint="app.tasks.llm.investigation",
        correlation_id=correlation_id,
        request_id=request_id,
    )
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "request_id": request_id,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_investigation_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    async def _execute():
        async with get_session(tenant_id=model.tenant_id) as session:
            return await run_investigation(
                model,
                session=session,
                force_failure=force_failure,
            )

    try:
        return _run_async(_execute)
    except Exception as exc:
        raise self.retry(
            exc=exc,
            kwargs=_retry_kwargs(
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation,
                request_id=request_id,
                max_cost_cents=max_cost_cents,
            ),
        )


@celery_app.task(bind=True, name="app.tasks.llm.budget_optimization", max_retries=3, default_retry_delay=30)
@tenant_task
def llm_budget_optimization_worker(
    self,
    payload: dict,
    tenant_id: UUID,
    correlation_id: Optional[str] = None,
    request_id: Optional[str] = None,
    max_cost_cents: int = 0,
    force_failure: bool = False,
):
    correlation, request_id = _resolve_request_context(
        tenant_id=tenant_id,
        endpoint="app.tasks.llm.budget_optimization",
        correlation_id=correlation_id,
        request_id=request_id,
    )
    model = LLMTaskPayload.model_validate(
        {
            "tenant_id": tenant_id,
            "correlation_id": correlation,
            "request_id": request_id,
            "prompt": payload,
            "max_cost_cents": max_cost_cents,
        }
    )
    correlation = _prepare_context(model)
    logger.info(
        "llm_budget_stub",
        extra={"task_id": self.request.id, "tenant_id": str(model.tenant_id), "correlation_id": correlation, "max_cost_cents": model.max_cost_cents},
    )
    async def _execute():
        async with get_session(tenant_id=model.tenant_id) as session:
            return await optimize_budget(
                model,
                session=session,
                force_failure=force_failure,
            )

    try:
        return _run_async(_execute)
    except Exception as exc:
        raise self.retry(
            exc=exc,
            kwargs=_retry_kwargs(
                payload=payload,
                tenant_id=tenant_id,
                correlation_id=correlation,
                request_id=request_id,
                max_cost_cents=max_cost_cents,
            ),
        )
