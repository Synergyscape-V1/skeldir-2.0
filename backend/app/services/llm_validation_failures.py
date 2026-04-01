"""Structured write-path for llm_validation_failures sink."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMValidationFailure

logger = logging.getLogger(__name__)


def _coerce_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalized_validation_code(validation_error: str) -> str:
    raw = _coerce_text(validation_error) or "unknown"
    base = raw.split(":", 1)[0]
    if base.startswith("cache_"):
        base = base.removeprefix("cache_")
    if base.startswith("validation_"):
        base = base.removeprefix("validation_")
    return base or "unknown"


def _normalized_validation_stage(
    validation_error: str, request_payload: Mapping[str, Any]
) -> str:
    explicit = _coerce_text(request_payload.get("validation_stage"))
    if explicit:
        return explicit
    explicit_stage = _coerce_text(request_payload.get("stage"))
    if explicit_stage:
        return explicit_stage
    return "cache" if str(validation_error).startswith("cache_") else "provider"


class LLMValidationFailureService:
    """Persist validation failures in a tenant-scoped durable audit sink."""

    async def record_failure(
        self,
        session: AsyncSession,
        *,
        tenant_id: UUID,
        endpoint: str,
        validation_error: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None,
    ) -> UUID:
        request = dict(request_payload or {})
        response = dict(response_payload or {})
        validation_code = _normalized_validation_code(validation_error)
        validation_stage = _normalized_validation_stage(validation_error, request)
        request_id = _coerce_text(request.get("request_id"))
        correlation_id = _coerce_text(request.get("correlation_id"))
        model_name = _coerce_text(response.get("model")) or "unknown"

        request.setdefault("feature", endpoint)
        request.setdefault("validation_code", validation_code)
        request.setdefault("validation_stage", validation_stage)
        if request_id is not None:
            request["request_id"] = request_id
        if correlation_id is not None:
            request["correlation_id"] = correlation_id

        response.setdefault("feature", endpoint)
        response.setdefault("model", model_name)
        response.setdefault("validation_code", validation_code)
        response.setdefault("validation_stage", validation_stage)

        row = LLMValidationFailure(
            tenant_id=tenant_id,
            endpoint=endpoint,
            validation_error=validation_error,
            request_payload=request,
            response_payload=response,
        )
        session.add(row)
        await session.flush()
        logger.warning(
            "llm_validation_failure_recorded",
            extra={
                "tenant_id": str(tenant_id),
                "correlation_id": correlation_id,
                "endpoint": endpoint,
                "event_type": "llm.validation_failure",
                "validation_error": validation_error,
                "validation_code": validation_code,
                "validation_stage": validation_stage,
                "model": model_name,
                "validation_failure_id": str(row.id),
            },
        )
        return row.id
