"""Typed authority contracts for investigation and budget payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

AUTHORITY_CONTRACT_VERSION = "b1.6-p3"


class NumericClaimBinding(BaseModel):
    """Worker-supplied numeric claim binding for boundary enforcement."""

    model_config = ConfigDict(extra="forbid")

    claim_path: str = Field(min_length=1)
    truth_path: str = Field(min_length=1)
    tolerance_ratio: float | None = Field(default=None, ge=0.0, le=1.0)


class ValidationContext(BaseModel):
    """Typed upstream deterministic truth context for downstream validation phases."""

    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["b1.6-p1", "b1.6-p3"] = AUTHORITY_CONTRACT_VERSION
    feature_surface: Literal["investigation", "budget"]
    request_id: str
    correlation_id: str
    deterministic_truth: dict[str, Any] = Field(default_factory=dict)
    deterministic_truth_sources: list[str] = Field(default_factory=list)
    numeric_claim_paths: list[str] = Field(default_factory=list)
    numeric_claim_bindings: list[NumericClaimBinding] = Field(default_factory=list)
    numeric_tolerance_ratio: float = Field(default=0.05, ge=0.0, le=1.0)


class InvestigationDeterministicAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["deterministic_authority"]
    deterministic_findings: list[dict[str, Any]] = Field(default_factory=list)


class BudgetDeterministicAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["deterministic_authority"]
    deterministic_recommendation: dict[str, Any] = Field(default_factory=dict)


class ValidatedSynthesisArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["validated_synthesis"]
    validation_state: Literal["pending_validation", "validated", "rejected"]
    non_authoritative_summary: str
    caveats: list[str] = Field(default_factory=list)
    model: str = "unknown"
    generated_at: str
    rejection_reason: str | None = None


class AuditOnlyRawProviderArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authority_class: Literal["audit_only_raw_provider_artifact"]
    provider_summary_raw: str


class InvestigationResultAuthorityPayload(BaseModel):
    """Worker-owned persisted authority contract for investigation results."""

    model_config = ConfigDict(extra="forbid")

    authority_contract_version: Literal["b1.6-p1", "b1.6-p3"] = AUTHORITY_CONTRACT_VERSION
    request_id: str
    deterministic_authority: InvestigationDeterministicAuthority
    llm_synthesis: ValidatedSynthesisArtifact
    llm_audit: AuditOnlyRawProviderArtifact
    validation_context: ValidationContext


class BudgetResultAuthorityPayload(BaseModel):
    """Worker-owned persisted authority contract for budget recommendation results."""

    model_config = ConfigDict(extra="forbid")

    authority_contract_version: Literal["b1.6-p1", "b1.6-p3"] = AUTHORITY_CONTRACT_VERSION
    request_id: str
    deterministic_authority: BudgetDeterministicAuthority
    llm_synthesis: ValidatedSynthesisArtifact
    llm_audit: AuditOnlyRawProviderArtifact
    validation_context: ValidationContext
