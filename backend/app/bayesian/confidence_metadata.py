"""Pydantic DTOs for the internal B2.4-P10 projection."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.bayesian.confidence_policy import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
)
from app.bayesian.schema import ARTIFACT_REF_PATTERN, SHA256_HEX_PATTERN


PROJECTION_POLICY_VERSION = "b24-p10-projection-policy-v1"


class DeterministicProjectionMetadata(BaseModel):
    """Authoritative deterministic-left revenue truth."""

    model_config = ConfigDict(extra="forbid")

    tenant_id: UUID
    source_window_start: datetime
    source_window_end: datetime
    deterministic_revenue_minor: int = Field(ge=0)
    currency_code: str = Field(min_length=3, max_length=3)
    deterministic_source_status: str
    deterministic_source_refs: dict[str, int]
    verification_coverage: dict[str, int | float | str | None]
    source_snapshot_hash: str = Field(pattern=SHA256_HEX_PATTERN)


class CredibleIntervalProjectionMetadata(BaseModel):
    """Conditional statistical interval metadata, never authoritative money."""

    model_config = ConfigDict(extra="forbid")

    lower: float | None = None
    upper: float | None = None
    unit: Literal["minor_units"] = "minor_units"
    level: float | None = Field(default=None, ge=0.0, le=1.0)
    source: Literal["bayesian_model_fit", "unavailable"] = "unavailable"
    status: str


class BayesianProjectionMetadata(BaseModel):
    """Optional B2.4 Bayesian enrichment over deterministic truth."""

    model_config = ConfigDict(extra="forbid")

    fit_id: UUID | None = None
    fit_status: str | None = None
    model_type: str
    model_version: str
    model_fit_version: str | None = None
    diagnostics_status: str | None = None
    credible_interval: CredibleIntervalProjectionMetadata
    fallback_applied: bool
    fallback_reason: str | None = None
    artifact_ref: str | None = Field(default=None, pattern=ARTIFACT_REF_PATTERN)
    artifact_hash: str | None = Field(default=None, pattern=SHA256_HEX_PATTERN)
    artifact_lifecycle_status: str | None = None


class ConfidenceProjectionMetadata(BaseModel):
    """Backend-owned confidence semantics for consumers."""

    model_config = ConfigDict(extra="forbid")

    confidence_available: bool
    confidence_bucket: Literal["high", "medium", "low", "unavailable"]
    confidence_bucket_reason: str
    confidence_policy_version: str = CONFIDENCE_POLICY_VERSION
    confidence_source: Literal["backend_b24_p10_policy"] = "backend_b24_p10_policy"
    confidence_semantics_version: str = CONFIDENCE_SEMANTICS_VERSION


class ProjectionAuditMetadata(BaseModel):
    """Read-only projection audit context."""

    model_config = ConfigDict(extra="forbid")

    projection_generated_at: datetime
    projection_policy_version: str = PROJECTION_POLICY_VERSION
    deterministic_left_join_used: bool = True
    projection_read_only: bool = True


class B24ConfidenceProjection(BaseModel):
    """Internal read-only B2.4 confidence projection."""

    model_config = ConfigDict(extra="forbid")

    deterministic: DeterministicProjectionMetadata
    bayesian: BayesianProjectionMetadata
    confidence: ConfidenceProjectionMetadata
    audit: ProjectionAuditMetadata
