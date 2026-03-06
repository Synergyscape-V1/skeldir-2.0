"""
Tenant task enqueue choke points.
"""

from __future__ import annotations

from typing import Any, Mapping

from celery.canvas import Signature

from app.tasks.authority import AuthorityEnvelope, authority_envelope_payload, parse_authority_envelope

TENANT_SCOPED_TASK_NAMES: frozenset[str] = frozenset(
    {
        "app.tasks.attribution.recompute_window",
        "app.tasks.llm.route",
        "app.tasks.llm.explanation",
        "app.tasks.llm.investigation",
        "app.tasks.llm.budget_optimization",
        "app.tasks.maintenance.refresh_matview_for_tenant",
        "app.tasks.maintenance.scan_for_pii_contamination",
        "app.tasks.maintenance.enforce_data_retention",
        "app.tasks.matviews.refresh_single",
        "app.tasks.matviews.refresh_all_for_tenant",
    }
)


def _assert_tenant_scoped(task_name: str) -> None:
    if task_name not in TENANT_SCOPED_TASK_NAMES:
        raise ValueError(f"Task is not registered as tenant-scoped: {task_name}")


def _build_task_kwargs(
    *,
    envelope: AuthorityEnvelope,
    kwargs: Mapping[str, Any] | None,
) -> dict[str, Any]:
    task_kwargs = dict(kwargs or {})
    if "authority_envelope" in task_kwargs:
        raise ValueError("authority_envelope must be supplied via enqueue_tenant_task only")
    task_kwargs["authority_envelope"] = authority_envelope_payload(envelope)
    return task_kwargs


def tenant_task_signature(
    task,
    *,
    envelope: AuthorityEnvelope | Mapping[str, Any],
    kwargs: Mapping[str, Any] | None = None,
    immutable: bool = False,
) -> Signature:
    parsed = parse_authority_envelope(envelope)
    _assert_tenant_scoped(task.name)
    task_kwargs = _build_task_kwargs(envelope=parsed, kwargs=kwargs)
    if immutable:
        return task.si(**task_kwargs)
    return task.s(**task_kwargs)


def enqueue_tenant_task(
    task,
    *,
    envelope: AuthorityEnvelope | Mapping[str, Any],
    kwargs: Mapping[str, Any] | None = None,
    queue: str | None = None,
    correlation_id: str | None = None,
):
    parsed = parse_authority_envelope(envelope)
    _assert_tenant_scoped(task.name)
    task_kwargs = _build_task_kwargs(envelope=parsed, kwargs=kwargs)
    return task.apply_async(
        kwargs=task_kwargs,
        queue=queue,
        correlation_id=correlation_id,
    )
