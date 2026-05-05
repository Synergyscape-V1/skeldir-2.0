"""Strict B2.3-P3 revenue verification read response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class B23VerdictStatus(str, Enum):
    pending = "pending"
    matched_provisional = "matched_provisional"
    matched_confirmed = "matched_confirmed"
    adjusted = "adjusted"
    unmatched = "unmatched"


class B23MatchQuality(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class B23DiscrepancyBand(str, Enum):
    exact = "exact"
    within_tolerance = "within_tolerance"
    over_tolerance = "over_tolerance"
    severe_gap = "severe_gap"


class B23ExceptionSeverity(str, Enum):
    flagged = "flagged"
    alert = "alert"


class B23ExceptionWorkflowState(str, Enum):
    open = "open"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class B23DiscrepancyContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discrepancy_amount_minor: int = Field(ge=0)
    discrepancy_ratio_bps: int = Field(ge=0)
    discrepancy_band: B23DiscrepancyBand
    discrepancy_basis: Literal["gross_expected_vs_gross_captured"]


class B23MatchVerdictDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    attribution_event_id: UUID | None
    webhook_ingress_identity_id: UUID | None
    provider: str
    canonical_commerce_reference: str
    provider_native_event_reference: str
    provider_native_commerce_reference: str
    status: B23VerdictStatus
    match_quality: B23MatchQuality
    canonical_gross_expected_amount_minor: int = Field(ge=0)
    canonical_gross_captured_amount_minor: int = Field(ge=0)
    canonical_net_verified_amount_minor: int = Field(ge=0)
    discrepancy: B23DiscrepancyContext
    adjustments_applied: bool
    pending_since: datetime
    provisional_expires_at: datetime | None
    confirmed_at: datetime | None
    adjusted_at: datetime | None
    unmatched_marked_at: datetime | None
    last_transition_at: datetime
    created_at: datetime
    updated_at: datetime


class B23ExceptionRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    tenant_id: UUID
    match_verdict_id: UUID
    provider: str
    canonical_commerce_reference: str
    severity: B23ExceptionSeverity
    workflow_state: B23ExceptionWorkflowState
    resolution_code: str | None
    discrepancy_reason: str
    discrepancy_context: B23DiscrepancyContext
    raised_at: datetime
    resolved_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class B23ExceptionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exceptions: list[B23ExceptionRecordResponse]
