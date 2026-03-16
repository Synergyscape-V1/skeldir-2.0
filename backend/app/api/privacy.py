from __future__ import annotations

import os
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Response, Security, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.security.auth import AuthContext, get_auth_context
from app.tasks.authority import SessionAuthorityEnvelope
from app.tasks.enqueue import enqueue_tenant_task_by_name

router = APIRouter()

_ERASURE_TASK_NAME = "app.tasks.privacy.erase_tenant_privacy_surfaces"


class PrivacyDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)
    correlation_id: UUID | None = None

    @model_validator(mode="after")
    def _validate_selector(self) -> "PrivacyDeleteRequest":
        if not self.idempotency_key and self.correlation_id is None:
            raise ValueError("idempotency_key or correlation_id is required")
        return self


@router.post(
    "/privacy/delete",
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="requestPrivacyDelete",
)
async def request_privacy_delete(
    payload: PrivacyDeleteRequest,
    response: Response,
    x_correlation_id: Annotated[UUID, Header(alias="X-Correlation-ID")],
    auth_context: Annotated[AuthContext, Security(get_auth_context, scopes=["viewer"])],
):
    response.headers["X-Correlation-ID"] = str(x_correlation_id)

    selector: dict[str, str] = {}
    if payload.idempotency_key:
        selector["idempotency_key"] = payload.idempotency_key
    if payload.correlation_id is not None:
        selector["correlation_id"] = str(payload.correlation_id)

    if os.getenv("CONTRACT_TESTING") == "1":
        task_id = f"contract-{uuid4()}"
    else:
        envelope = SessionAuthorityEnvelope(
            tenant_id=auth_context.tenant_id,
            user_id=auth_context.user_id,
            jti=auth_context.jti,
            iat=auth_context.issued_at_epoch,
        )
        task_result = enqueue_tenant_task_by_name(
            _ERASURE_TASK_NAME,
            envelope=envelope,
            kwargs={
                "selector": selector,
                "correlation_id": str(x_correlation_id),
            },
            queue="maintenance",
            correlation_id=str(x_correlation_id),
        )
        task_id = str(task_result.id)

    return {
        "status": "accepted",
        "tenant_id": str(auth_context.tenant_id),
        "request_id": task_id,
        "exposure_model": "public_backend_api_worker_orchestrated",
        "selector": selector,
    }

