"""
Custom Celery base task for tenant-scoped worker execution.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from celery import Task

from app.core.identity import resolve_user_id
from app.observability.context import set_request_correlation_id, set_tenant_id, set_user_id
from app.tasks.authority import (
    AUTHORITY_ENVELOPE_HEADER,
    SessionAuthorityEnvelope,
    parse_authority_envelope,
)
from app.tasks.context import (
    _set_tenant_guc_global,
    assert_worker_session_claims_active,
    run_in_worker_loop,
)


class TenantTask(Task):
    abstract = True
    typing = False

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        prohibited = {"authority_envelope", "tenant_id", "user_id", "jti", "iat"}
        overlap = sorted(prohibited.intersection(kwargs.keys()))
        if overlap:
            joined = ", ".join(overlap)
            raise ValueError(f"tenant authority fields must not be task kwargs: {joined}")

        headers = getattr(self.request, "headers", None) or {}
        envelope_raw = headers.get(AUTHORITY_ENVELOPE_HEADER)
        if envelope_raw is None:
            envelope_raw = headers.get("authority_envelope")
        if envelope_raw is None:
            raise ValueError("authority_envelope header is required for tenant-scoped tasks")

        envelope = parse_authority_envelope(envelope_raw)
        correlation_id = (
            kwargs.get("correlation_id")
            or getattr(self.request, "correlation_id", None)
            or getattr(self.request, "id", None)
            or "unknown"
        )

        tenant_id = envelope.tenant_id
        if isinstance(envelope, SessionAuthorityEnvelope):
            user_id = envelope.user_id
            assert_worker_session_claims_active(
                tenant_id=envelope.tenant_id,
                user_id=envelope.user_id,
                jti=envelope.jti,
                iat=envelope.iat,
            )
        else:
            user_id = resolve_user_id(None)

        setattr(self.request, "tenant_id", str(tenant_id))
        setattr(self.request, "user_id", str(user_id))
        setattr(self.request, "authority_envelope", envelope.model_dump(mode="json"))

        set_tenant_id(tenant_id)
        set_user_id(user_id)
        set_request_correlation_id(correlation_id)

        is_eager = getattr(self.app.conf, "task_always_eager", False) if hasattr(self, "app") else False
        if not is_eager:
            run_in_worker_loop(_set_tenant_guc_global(tenant_id, user_id))

        try:
            return super().__call__(*args, **kwargs)
        finally:
            set_tenant_id(None)
            set_user_id(None)
            set_request_correlation_id(None)


def task_tenant_id(task: Task) -> UUID:
    raw_tenant_id = getattr(task.request, "tenant_id", None)
    if raw_tenant_id is None:
        raise ValueError("tenant_id missing from tenant task request context")
    return UUID(str(raw_tenant_id))


def task_user_id(task: Task) -> UUID:
    raw_user_id = getattr(task.request, "user_id", None)
    return resolve_user_id(raw_user_id)
