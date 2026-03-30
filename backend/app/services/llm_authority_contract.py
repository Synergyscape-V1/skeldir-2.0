"""B1.6-P1 authority payload builders owned by service/worker layer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.llm.authority_contract import (
    AuditOnlyRawProviderArtifact,
    BudgetDeterministicAuthority,
    BudgetResultAuthorityPayload,
    InvestigationDeterministicAuthority,
    InvestigationResultAuthorityPayload,
    ValidationContext,
    ValidatedSynthesisArtifact,
)


def _observed_at_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def build_validation_context(
    *,
    feature_surface: str,
    request_id: str,
    correlation_id: str,
    deterministic_truth: dict[str, Any],
    deterministic_truth_sources: list[str],
    numeric_claim_paths: list[str] | None = None,
) -> ValidationContext:
    return ValidationContext(
        feature_surface=feature_surface,
        request_id=request_id,
        correlation_id=correlation_id,
        deterministic_truth=deterministic_truth,
        deterministic_truth_sources=deterministic_truth_sources,
        numeric_claim_paths=numeric_claim_paths or [],
    )


def build_investigation_authority_payload(
    *,
    request_id: str,
    correlation_id: str,
    authority_job_id: UUID,
    provider_summary: str,
    model_name: str,
) -> InvestigationResultAuthorityPayload:
    observed_at = _observed_at_iso()
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
                    "observed_at": observed_at,
                }
            ],
        }
    ]
    validation_context = build_validation_context(
        feature_surface="investigation",
        request_id=request_id,
        correlation_id=correlation_id,
        deterministic_truth={
            "authority_status": 1,
            "authority_job_id": str(authority_job_id),
        },
        deterministic_truth_sources=["investigation_jobs"],
    )
    return InvestigationResultAuthorityPayload(
        request_id=request_id,
        deterministic_authority=InvestigationDeterministicAuthority(
            authority_class="deterministic_authority",
            deterministic_findings=deterministic_findings,
        ),
        llm_synthesis=ValidatedSynthesisArtifact(
            authority_class="validated_synthesis",
            validation_state="pending_validation",
            non_authoritative_summary=provider_summary,
            caveats=[
                "Synthesis is explanatory only and cannot override deterministic findings.",
                "Numeric authority remains deterministic until B1.6 validation acceptance.",
            ],
            model=model_name,
            generated_at=observed_at,
        ),
        llm_audit=AuditOnlyRawProviderArtifact(
            authority_class="audit_only_raw_provider_artifact",
            provider_summary_raw=provider_summary,
        ),
        validation_context=validation_context,
    )


def build_budget_authority_payload(
    *,
    request_id: str,
    correlation_id: str,
    authority_job_id: UUID,
    provider_summary: str,
    model_name: str,
    optimization_goal: str,
) -> BudgetResultAuthorityPayload:
    observed_at = _observed_at_iso()
    deterministic_recommendation = {
        "optimization_goal": optimization_goal,
        "allocations": [],
        "evidence": [
            {
                "metric_name": "authority_status",
                "channel": "aggregate",
                "metric_value": 1,
                "source_table": "budget_jobs",
                "observed_at": observed_at,
            }
        ],
        "generated_at": observed_at,
    }
    validation_context = build_validation_context(
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
    return BudgetResultAuthorityPayload(
        request_id=request_id,
        deterministic_authority=BudgetDeterministicAuthority(
            authority_class="deterministic_authority",
            deterministic_recommendation=deterministic_recommendation,
        ),
        llm_synthesis=ValidatedSynthesisArtifact(
            authority_class="validated_synthesis",
            validation_state="pending_validation",
            non_authoritative_summary=provider_summary,
            caveats=[
                "Synthesis is explanatory only and cannot override deterministic recommendation fields.",
                "Numeric authority remains deterministic until B1.6 validation acceptance.",
            ],
            model=model_name,
            generated_at=observed_at,
        ),
        llm_audit=AuditOnlyRawProviderArtifact(
            authority_class="audit_only_raw_provider_artifact",
            provider_summary_raw=provider_summary,
        ),
        validation_context=validation_context,
    )
