"""Pydantic DTOs for the internal B2.4-P10 projection."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.bayesian.confidence_policy import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
)
from app.bayesian.schema import ARTIFACT_REF_PATTERN, SHA256_HEX_PATTERN


PROJECTION_POLICY_VERSION = "b24-p10-projection-policy-v1"
_PROMPT_CONTROL_TOKENS = ("<|", "|>", "```", "\n", "\r", "<system", "</system")
_SAFE_CODE_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "_-.:/"
)


def _validate_safe_code(value: str | None, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not (1 <= len(value) <= 128):
        raise ValueError(f"{field_name} must be 1..128 characters")
    lowered = value.lower()
    if any(token in lowered for token in _PROMPT_CONTROL_TOKENS):
        raise ValueError(f"{field_name} contains prompt-control syntax")
    if any(char not in _SAFE_CODE_CHARS for char in value):
        raise ValueError(f"{field_name} must be a bounded code value")
    return value


def _validate_safe_mapping(value: dict[str, object], *, field_name: str) -> dict[str, object]:
    for key, item in value.items():
        _validate_safe_code(str(key), field_name=f"{field_name} key")
        if isinstance(item, str):
            _validate_safe_code(item, field_name=f"{field_name} value")
    return value


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

    @field_validator("deterministic_source_status", "currency_code")
    @classmethod
    def _safe_code_field(cls, value: str) -> str:
        return _validate_safe_code(value, field_name="deterministic projection field") or value

    @field_validator("deterministic_source_refs", "verification_coverage")
    @classmethod
    def _safe_mapping_field(cls, value: dict[str, object]) -> dict[str, object]:
        return _validate_safe_mapping(value, field_name="deterministic projection mapping")


class CredibleIntervalProjectionMetadata(BaseModel):
    """Conditional statistical interval metadata, never authoritative money."""

    model_config = ConfigDict(extra="forbid")

    lower: float | None = None
    upper: float | None = None
    unit: Literal["minor_units"] = "minor_units"
    level: float | None = Field(default=None, ge=0.0, le=1.0)
    source: Literal["bayesian_model_fit", "unavailable"] = "unavailable"
    status: str

    @field_validator("status")
    @classmethod
    def _safe_status(cls, value: str) -> str:
        return _validate_safe_code(value, field_name="credible interval status") or value


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

    @field_validator(
        "fit_status",
        "model_type",
        "model_version",
        "model_fit_version",
        "diagnostics_status",
        "fallback_reason",
        "artifact_lifecycle_status",
    )
    @classmethod
    def _safe_optional_code_field(cls, value: str | None) -> str | None:
        return _validate_safe_code(value, field_name="bayesian projection field")


class ConfidenceProjectionMetadata(BaseModel):
    """Backend-owned confidence semantics for consumers."""

    model_config = ConfigDict(extra="forbid")

    confidence_available: bool
    confidence_bucket: Literal["high", "medium", "low", "unavailable"]
    confidence_bucket_reason: str
    confidence_policy_version: str = CONFIDENCE_POLICY_VERSION
    confidence_source: Literal["backend_b24_p10_policy"] = "backend_b24_p10_policy"
    confidence_semantics_version: str = CONFIDENCE_SEMANTICS_VERSION

    @field_validator("confidence_bucket_reason", "confidence_policy_version", "confidence_semantics_version")
    @classmethod
    def _safe_confidence_code_field(cls, value: str) -> str:
        return _validate_safe_code(value, field_name="confidence projection field") or value


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
