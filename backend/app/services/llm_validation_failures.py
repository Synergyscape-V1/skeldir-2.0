"""Structured write-path for llm_validation_failures sink."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import LLMValidationFailure

logger = logging.getLogger(__name__)


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
        row = LLMValidationFailure(
            tenant_id=tenant_id,
            endpoint=endpoint,
            validation_error=validation_error,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        session.add(row)
        await session.flush()
        logger.warning(
            "llm_validation_failure_recorded",
            extra={
                "tenant_id": str(tenant_id),
                "endpoint": endpoint,
                "event_type": "llm.validation_failure",
                "validation_error": validation_error,
                "validation_failure_id": str(row.id),
            },
        )
        return row.id
