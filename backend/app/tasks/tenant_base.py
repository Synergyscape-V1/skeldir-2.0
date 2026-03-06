"""
Custom Celery base task for tenant-scoped worker execution.
"""

from __future__ import annotations

import os
from typing import Any

from celery import Task

from app.core.identity import resolve_user_id
from app.observability.context import set_request_correlation_id, set_tenant_id, set_user_id
from app.tasks.authority import SessionAuthorityEnvelope, SystemAuthorityEnvelope, parse_authority_envelope
from app.tasks.context import (
    _set_tenant_guc_global,
    assert_worker_session_claims_active,
    run_in_worker_loop,
)


class TenantTask(Task):
    abstract = True

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        envelope_raw = kwargs.pop("authority_envelope", None)
        if envelope_raw is None:
            legacy_mode = os.getenv("TESTING") == "1" and os.getenv("SKELDIR_B12_P7_STRICT_ENVELOPE") != "1"
            if not legacy_mode:
                raise ValueError("authority_envelope is required for tenant-scoped tasks")
            tenant_id = kwargs.get("tenant_id")
            if tenant_id is None:
                raise ValueError("authority_envelope is required for tenant-scoped tasks")
            envelope_raw = SystemAuthorityEnvelope(tenant_id=tenant_id).model_dump(mode="json")

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

        set_tenant_id(tenant_id)
        set_user_id(user_id)
        set_request_correlation_id(correlation_id)
        kwargs["tenant_id"] = tenant_id
        kwargs["user_id"] = resolve_user_id(kwargs.get("user_id") or user_id)
        kwargs["correlation_id"] = correlation_id

        is_eager = getattr(self.app.conf, "task_always_eager", False) if hasattr(self, "app") else False
        if not is_eager:
            run_in_worker_loop(_set_tenant_guc_global(tenant_id, kwargs["user_id"]))

        try:
            return super().__call__(*args, **kwargs)
        finally:
            set_tenant_id(None)
            set_user_id(None)
            set_request_correlation_id(None)
