"""
Canonical producer for enqueueing LLM tasks (API-equivalent entrypoint).
"""
from __future__ import annotations

from typing import Dict

from app.schemas.llm_payloads import LLMTaskPayload
from app.tasks.authority import SessionAuthorityEnvelope, SystemAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task
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
        "correlation_id": payload.correlation_id,
        "request_id": payload.request_id,
        "max_cost_cents": payload.max_cost_cents,
    }


def _payload_to_envelope(payload: LLMTaskPayload):
    if payload.jti is not None and payload.iat is not None:
        return SessionAuthorityEnvelope(
            tenant_id=payload.tenant_id,
            user_id=payload.user_id,
            jti=payload.jti,
            iat=payload.iat,
        )
    return SystemAuthorityEnvelope(tenant_id=payload.tenant_id)


def enqueue_llm_task(task_name: str, payload: LLMTaskPayload):
    """
    Enqueue a deterministic LLM task using the canonical payload contract.
    """
    task = _TASK_MAP.get(task_name)
    if task is None:
        raise ValueError(f"Unknown LLM task name: {task_name}")
    return enqueue_tenant_task(
        task,
        envelope=_payload_to_envelope(payload),
        kwargs=_payload_to_kwargs(payload),
        correlation_id=payload.correlation_id,
    )
