"""
Canonical producer for enqueueing LLM tasks (API-equivalent entrypoint).
"""
from __future__ import annotations

from typing import Dict

from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.llm import (
    llm_budget_optimization_worker,
    llm_explanation_worker,
    llm_investigation_worker,
    llm_routing_worker,
)

_TASK_MAP = {
    "route": llm_routing_worker,
    "explanation": llm_explanation_worker,
    "investigation": llm_investigation_worker,
    "budget_optimization": llm_budget_optimization_worker,
}


def _payload_to_kwargs(payload: LLMTaskPayload) -> Dict[str, object]:
    return {
        "payload": payload.prompt,
        "tenant_id": payload.tenant_id,
        "correlation_id": payload.correlation_id,
        "request_id": payload.request_id,
        "max_cost_cents": payload.max_cost_cents,
    }


def enqueue_llm_task(task_name: str, payload: LLMTaskPayload):
    """
    Enqueue a deterministic LLM task using the canonical payload contract.
    """
    task = _TASK_MAP.get(task_name)
    if task is None:
        raise ValueError(f"Unknown LLM task name: {task_name}")
    return task.apply_async(kwargs=_payload_to_kwargs(payload))
"""
Canonical producer for enqueueing LLM tasks (API-equivalent entrypoint).
"""
from __future__ import annotations

from typing import Dict

from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.llm import (
    llm_budget_optimization_worker,
    llm_explanation_worker,
    llm_investigation_worker,
    llm_routing_worker,
)

_TASK_MAP = {
    "route": llm_routing_worker,
    "explanation": llm_explanation_worker,
    "investigation": llm_investigation_worker,
    "budget_optimization": llm_budget_optimization_worker,
}


def _payload_to_kwargs(payload: LLMTaskPayload) -> Dict[str, object]:
    return {
        "payload": payload.prompt,
        "tenant_id": payload.tenant_id,
        "correlation_id": payload.correlation_id,
        "request_id": payload.request_id,
        "max_cost_cents": payload.max_cost_cents,
    }


def enqueue_llm_task(task_name: str, payload: LLMTaskPayload):
    """
    Enqueue a deterministic LLM task using the canonical payload contract.
    """
    task = _TASK_MAP.get(task_name)
    if task is None:
        raise ValueError(f"Unknown LLM task name: {task_name}")
    return task.apply_async(kwargs=_payload_to_kwargs(payload))

"""
Canonical LLM task dispatch helpers (producer-side mapping).

This module maps the canonical LLMTaskPayload into Celery task kwargs without
performing any network or provider calls.
"""
from __future__ import annotations

from typing import Any, Dict

from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.llm import (
    llm_budget_optimization_worker,
    llm_explanation_worker,
    llm_investigation_worker,
    llm_routing_worker,
)


_ENDPOINTS = {
    "app.tasks.llm.route": llm_routing_worker,
    "app.tasks.llm.explanation": llm_explanation_worker,
    "app.tasks.llm.investigation": llm_investigation_worker,
    "app.tasks.llm.budget_optimization": llm_budget_optimization_worker,
}


def build_llm_task_kwargs(payload: LLMTaskPayload, *, endpoint: str) -> Dict[str, Any]:
    """
    Build Celery kwargs for the given endpoint using the canonical payload.
    """
    if endpoint not in _ENDPOINTS:
        raise ValueError(f"Unknown LLM endpoint: {endpoint}")

    data = payload.model_dump(mode="json")
    return {
        "payload": data["prompt"],
        "tenant_id": data["tenant_id"],
        "correlation_id": data["correlation_id"],
        "request_id": data["request_id"],
        "max_cost_cents": data["max_cost_cents"],
    }


def enqueue_llm_task(payload: LLMTaskPayload, *, endpoint: str):
    """
    Enqueue an LLM task using the canonical payload mapping.
    """
    task = _ENDPOINTS.get(endpoint)
    if task is None:
        raise ValueError(f"Unknown LLM endpoint: {endpoint}")
    kwargs = build_llm_task_kwargs(payload, endpoint=endpoint)
    return task.apply_async(kwargs=kwargs)
