"""Canonical payload contracts for LLM task stubs."""
from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class LLMTaskPayload(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant context for RLS")
    correlation_id: Optional[str] = Field(None, description="Correlation for observability")
    request_id: Optional[str] = Field(default_factory=lambda: str(uuid4()), description="Idempotency/trace id")
    prompt: Dict[str, Any] = Field(default_factory=dict, description="Opaque prompt/payload structure")
    max_cost_cents: int = Field(0, description="Budget cap in cents")
