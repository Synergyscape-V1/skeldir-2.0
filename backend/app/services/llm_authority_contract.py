"""B1.6-P1 authority payload builders owned by service/worker layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from app.llm.authority_contract import (
    AuditOnlyRawProviderArtifact,
    BudgetDeterministicAuthority,
    BudgetResultAuthorityPayload,
    InvestigationDeterministicAuthority,
    InvestigationResultAuthorityPayload,
    NumericClaimBinding,
    ValidationContext,
    ValidatedSynthesisArtifact,
)


def _normalized_observed_at(observed_at: datetime | str) -> str:
    if isinstance(observed_at, str):
        return observed_at
    if observed_at.tzinfo is None:
        return observed_at.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    return observed_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_validation_context(
    *,
    feature_surface: str,
    request_id: str,
    correlation_id: str,
    deterministic_truth: dict[str, Any],
    deterministic_truth_sources: list[str],
    numeric_claim_paths: list[str] | None = None,
    numeric_claim_bindings: list[dict[str, Any] | NumericClaimBinding] | None = None,
    numeric_tolerance_ratio: float = 0.05,
) -> ValidationContext:
    parsed_bindings: list[NumericClaimBinding] = []
    for raw_binding in numeric_claim_bindings or []:
        if isinstance(raw_binding, NumericClaimBinding):
            parsed_bindings.append(raw_binding)
            continue
        if isinstance(raw_binding, dict):
            parsed_bindings.append(NumericClaimBinding.model_validate(raw_binding))
    claim_paths = list(numeric_claim_paths or [])
    if not claim_paths:
        claim_paths = [binding.claim_path for binding in parsed_bindings]
    return ValidationContext(
        feature_surface=feature_surface,
        request_id=request_id,
        correlation_id=correlation_id,
        deterministic_truth=deterministic_truth,
        deterministic_truth_sources=deterministic_truth_sources,
        numeric_claim_paths=claim_paths,
        numeric_claim_bindings=parsed_bindings,
        numeric_tolerance_ratio=float(numeric_tolerance_ratio),
    )


def build_investigation_authority_payload(
    *,
    request_id: str,
    correlation_id: str,
    authority_job_id: UUID,
    observed_at: datetime | str,
    provider_summary: str,
    model_name: str,
    validation_context: ValidationContext | None = None,
    synthesis_validation_state: Literal["pending_validation", "validated", "rejected"] = "validated",
    synthesis_caveats: list[str] | None = None,
    rejection_reason: str | None = None,
    audit_provider_summary_raw: str | None = None,
) -> InvestigationResultAuthorityPayload:
    observed_at_iso = _normalized_observed_at(observed_at)
    deterministic_findings = [
        {
            "finding_id": f"investigation-{authority_job_id}",
            "title": "Deterministic investigation artifact captured",
            "severity": "medium",
            "deterministic_confidence_score": 1.0,
            "evidence": [
                {
                    "metric_name": "authority_status",
                    "metric_value": 1,
                    "source_table": "investigation_jobs",
                    "observed_at": observed_at_iso,
                }
            ],
        }
    ]
    validation_context = validation_context or build_validation_context(
        feature_surface="investigation",
        request_id=request_id,
        correlation_id=correlation_id,
        deterministic_truth={
            "authority_status": 1,
            "authority_job_id": str(authority_job_id),
        },
        deterministic_truth_sources=["investigation_jobs"],
    )
    caveats = synthesis_caveats or [
        "Synthesis is explanatory only and cannot override deterministic findings.",
        "Numeric authority is enforced against deterministic truth.",
    ]
    return InvestigationResultAuthorityPayload(
        request_id=request_id,
        deterministic_authority=InvestigationDeterministicAuthority(
            authority_class="deterministic_authority",
            deterministic_findings=deterministic_findings,
        ),
        llm_synthesis=ValidatedSynthesisArtifact(
            authority_class="validated_synthesis",
            validation_state=synthesis_validation_state,
            non_authoritative_summary=provider_summary,
            caveats=caveats,
            model=model_name,
            generated_at=observed_at_iso,
            rejection_reason=rejection_reason,
        ),
        llm_audit=AuditOnlyRawProviderArtifact(
            authority_class="audit_only_raw_provider_artifact",
            provider_summary_raw=audit_provider_summary_raw or provider_summary,
        ),
        validation_context=validation_context,
    )


def build_budget_authority_payload(
    *,
    request_id: str,
    correlation_id: str,
    authority_job_id: UUID,
    observed_at: datetime | str,
    provider_summary: str,
    model_name: str,
    optimization_goal: str,
    validation_context: ValidationContext | None = None,
    synthesis_validation_state: Literal["pending_validation", "validated", "rejected"] = "validated",
    synthesis_caveats: list[str] | None = None,
    rejection_reason: str | None = None,
    audit_provider_summary_raw: str | None = None,
) -> BudgetResultAuthorityPayload:
    observed_at_iso = _normalized_observed_at(observed_at)
    deterministic_recommendation = {
        "optimization_goal": optimization_goal,
        "allocations": [],
        "evidence": [
            {
                "metric_name": "authority_status",
                "channel": "aggregate",
                "metric_value": 1,
                "source_table": "budget_jobs",
                "observed_at": observed_at_iso,
            }
        ],
        "generated_at": observed_at_iso,
    }
    validation_context = validation_context or build_validation_context(
        feature_surface="budget",
        request_id=request_id,
        correlation_id=correlation_id,
        deterministic_truth={
            "authority_status": 1,
            "authority_job_id": str(authority_job_id),
            "optimization_goal": optimization_goal,
        },
        deterministic_truth_sources=["budget_jobs"],
    )
    caveats = synthesis_caveats or [
        "Synthesis is explanatory only and cannot override deterministic recommendation fields.",
        "Numeric authority is enforced against deterministic truth.",
    ]
    return BudgetResultAuthorityPayload(
        request_id=request_id,
        deterministic_authority=BudgetDeterministicAuthority(
            authority_class="deterministic_authority",
            deterministic_recommendation=deterministic_recommendation,
        ),
        llm_synthesis=ValidatedSynthesisArtifact(
            authority_class="validated_synthesis",
            validation_state=synthesis_validation_state,
            non_authoritative_summary=provider_summary,
            caveats=caveats,
            model=model_name,
            generated_at=observed_at_iso,
            rejection_reason=rejection_reason,
        ),
        llm_audit=AuditOnlyRawProviderArtifact(
            authority_class="audit_only_raw_provider_artifact",
            provider_summary_raw=audit_provider_summary_raw or provider_summary,
        ),
        validation_context=validation_context,
    )
