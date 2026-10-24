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
    # XVIII (H-XVIII-R7/R9): current P2 authority of the verdict's
    # source ingress at read time. 'current' verdicts may conduct;
    # any other state is explicitly non-authoritative history.
    source_authority_state: str = "unknown"
    # XXI P1: the event-family law that established this verdict's
    # meaning (latest law publication at or before the backing ingress
    # mint). 'unknown' when no law is recorded at the mint. None when
    # the law does not govern the provider (non-Shopify).
    event_family_law_version: str | None = None
    # XXI P1: False when a later event-family law publication
    # supersedes the establishing law (the verdict must not read as
    # current-law verified meaning). None when the law does not govern
    # the provider.
    event_family_law_current: bool | None = None


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


class B23P2CandidateClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_raw: str
    currency_raw: str
    event_time: datetime
    window_start: datetime
    window_end: datetime
    scope_policy_version: str
    source_reference: str | None = None
    source_verified_gross_amount_minor: int | None = Field(
        default=None, ge=0
    )


class B23P2CandidateClassificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disposition: Literal[
        "SUPPORTED_AND_IN_SCOPE",
        "SUPPORTED_BUT_UNRESOLVED",
        "EXPLICITLY_EXCLUDED",
        "INVALID_OR_REFUSED",
    ]
    reason: str
    provider: str
    rail: str
    currency_code: str
    window_start: datetime
    window_end: datetime
    scope_policy_version: str
    source_verified_gross_amount_minor: int | None


class B23PostCaptureCorrectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["stripe", "paypal", "shopify", "woocommerce"]
    event_type: Literal[
        "payment_capture",
        "partial_refund",
        "full_refund",
        "chargeback_opened",
        "chargeback_won",
        "chargeback_lost",
        "reversal",
    ]
    provider_native_event_reference: str = Field(min_length=1)
    is_gross_capture_correction: bool = False


class B23PostCaptureCorrectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted", "applied", "unresolved"]
    match_verdict_id: UUID
    revenue_event_written: bool
    net_verified_amount_minor: int = Field(ge=0)
