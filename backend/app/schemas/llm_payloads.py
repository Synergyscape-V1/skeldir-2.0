"""
Canonical payload contract for LLM tasks.

This module is the single source of truth for LLMTaskPayload.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class LLMTaskPayload(BaseModel):
    tenant_id: UUID = Field(..., description="Tenant context for RLS")
    correlation_id: Optional[str] = Field(None, description="Correlation for observability")
    request_id: Optional[str] = Field(
        None,
        description="Idempotency/trace id",
    )
    prompt: Dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque prompt/payload structure",
    )
    max_cost_cents: int = Field(0, description="Budget cap in cents")
