"""Exact-fit, read-only B2.4 confidence projection for trust composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.confidence_projection.policy import (
    ConfidencePolicyDecision,
    classify_confidence,
)


class ConfidenceProjectionReadError(ValueError):
    """Raised when one fit cannot be projected without inventing semantics."""


@dataclass(frozen=True)
class B24ConfidenceProjectionRead:
    """B2.4-owned classification plus its exact persisted authority identity."""

    tenant_id: UUID
    fit_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    source_snapshot_hash: str
    fit_status: str
    data_completeness_status: str
    fallback_applied: bool
    fallback_reason: str | None
    diagnostic_status: str | None
    diagnostic_failure_reason: str | None
    artifact_ref: str | None
    artifact_hash: str | None
    artifact_lifecycle_status: str | None
    observed_at: datetime
    deterministic_revenue_minor: int
    deterministic_row_count: int
    match_verdict_count: int
    source_snapshot_mismatch: bool
    decision: ConfidencePolicyDecision


_EXACT_FIT_PROJECTION_SQL = text(
    """
    WITH requested_fit AS (
        SELECT
            fit.id AS fit_id,
            fit.tenant_id,
            fit.model_type,
            fit.model_version,
            fit.source_window_start,
            fit.source_window_end,
            fit.source_snapshot_hash,
            fit.status AS fit_status,
            fit.data_completeness_status,
            fit.fallback_applied,
            fit.fallback_reason,
            fit.completed_at,
            fit.updated_at,
            fit.hdi_lower,
            fit.hdi_upper,
            fit.credible_interval_status,
            fit.diagnostic_status,
            fit.diagnostic_failure_reason,
            fit.artifact_ref AS fit_artifact_ref,
            fit.artifact_hash AS fit_artifact_hash
        FROM public.bayesian_model_fits fit
        WHERE fit.tenant_id = :tenant_id
          AND fit.id = :fit_id
    ),
    deterministic_summary AS (
        SELECT
            requested_fit.fit_id,
            CAST(
                COALESCE(
                    SUM(
                        CASE
                            WHEN revenue.net_effect_sign < 0 THEN
                                COALESCE(
                                    revenue.refund_amount_minor,
                                    revenue.chargeback_amount_minor,
                                    revenue.reversal_amount_minor,
                                    revenue.captured_amount_minor,
                                    0
                                ) * -1
                            ELSE COALESCE(revenue.captured_amount_minor, 0)
                        END
                    ),
                    0
                ) AS bigint
            ) AS deterministic_revenue_minor,
            COUNT(revenue.id) AS deterministic_row_count,
            COUNT(DISTINCT revenue.match_verdict_id) AS match_verdict_count,
            COUNT(DISTINCT UPPER(TRIM(revenue.currency_code))) AS currency_count
        FROM requested_fit
        LEFT OUTER JOIN public.b23_revenue_events revenue
          ON revenue.tenant_id = requested_fit.tenant_id
         AND revenue.event_occurred_at >= requested_fit.source_window_start
         AND revenue.event_occurred_at < requested_fit.source_window_end
        GROUP BY requested_fit.fit_id
    ),
    artifact_summary AS (
        SELECT DISTINCT ON (artifact.tenant_id, artifact.fit_id)
            artifact.tenant_id,
            artifact.fit_id,
            artifact.artifact_ref,
            artifact.artifact_hash,
            artifact.lifecycle_status AS artifact_lifecycle_status
        FROM public.bayesian_artifacts artifact
        JOIN requested_fit
          ON requested_fit.tenant_id = artifact.tenant_id
         AND requested_fit.fit_id = artifact.fit_id
        WHERE artifact.artifact_type IN ('posterior_summary', 'diagnostics', 'summary')
          AND artifact.lifecycle_status IN ('active', 'pruned', 'rejected')
        ORDER BY
            artifact.tenant_id,
            artifact.fit_id,
            CASE artifact.artifact_type
                WHEN 'posterior_summary' THEN 0
                WHEN 'diagnostics' THEN 1
                ELSE 2
            END,
            CASE artifact.lifecycle_status
                WHEN 'active' THEN 0
                WHEN 'pruned' THEN 1
                ELSE 2
            END,
            artifact.created_at DESC,
            artifact.id DESC
    )
    SELECT
        requested_fit.*,
        deterministic_summary.deterministic_revenue_minor,
        deterministic_summary.deterministic_row_count,
        deterministic_summary.match_verdict_count,
        deterministic_summary.currency_count,
        COALESCE(
            artifact_summary.artifact_ref,
            requested_fit.fit_artifact_ref
        ) AS artifact_ref,
        COALESCE(
            artifact_summary.artifact_hash,
            requested_fit.fit_artifact_hash
        ) AS artifact_hash,
        artifact_summary.artifact_lifecycle_status,
        COALESCE(
            execution_lease.latest_desired_source_snapshot_hash
                <> requested_fit.source_snapshot_hash,
            false
        ) AS source_snapshot_mismatch
    FROM requested_fit
    JOIN deterministic_summary
      ON deterministic_summary.fit_id = requested_fit.fit_id
    LEFT OUTER JOIN artifact_summary
      ON artifact_summary.tenant_id = requested_fit.tenant_id
     AND artifact_summary.fit_id = requested_fit.fit_id
    LEFT OUTER JOIN public.b24_active_execution_leases execution_lease
      ON execution_lease.tenant_id = requested_fit.tenant_id
     AND execution_lease.model_type = requested_fit.model_type
     AND execution_lease.model_version = requested_fit.model_version
     AND execution_lease.source_window_start = requested_fit.source_window_start
     AND execution_lease.source_window_end = requested_fit.source_window_end
    """
)


async def read_b24_confidence_projection_for_fit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    fit_id: UUID,
) -> B24ConfidenceProjectionRead | None:
    """Read one exact tenant-bound fit and classify only its persisted state."""

    result = await session.execute(
        _EXACT_FIT_PROJECTION_SQL,
        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    mapping = dict(row)
    if int(mapping.get("currency_count") or 0) > 1:
        raise ConfidenceProjectionReadError(
            "confidence_projection_multi_currency_window_unsupported"
        )
    decision = classify_confidence(mapping)
    observed_at = mapping.get("completed_at") or mapping["updated_at"]
    return B24ConfidenceProjectionRead(
        tenant_id=UUID(str(mapping["tenant_id"])),
        fit_id=UUID(str(mapping["fit_id"])),
        model_type=str(mapping["model_type"]),
        model_version=str(mapping["model_version"]),
        source_window_start=mapping["source_window_start"],
        source_window_end=mapping["source_window_end"],
        source_snapshot_hash=str(mapping["source_snapshot_hash"]),
        fit_status=str(mapping["fit_status"]),
        data_completeness_status=str(mapping["data_completeness_status"]),
        fallback_applied=bool(mapping.get("fallback_applied")),
        fallback_reason=(
            str(mapping["fallback_reason"])
            if mapping.get("fallback_reason") is not None
            else None
        ),
        diagnostic_status=(
            str(mapping["diagnostic_status"])
            if mapping.get("diagnostic_status") is not None
            else None
        ),
        diagnostic_failure_reason=(
            str(mapping["diagnostic_failure_reason"])
            if mapping.get("diagnostic_failure_reason") is not None
            else None
        ),
        artifact_ref=(
            str(mapping["artifact_ref"])
            if mapping.get("artifact_ref") is not None
            else None
        ),
        artifact_hash=(
            str(mapping["artifact_hash"])
            if mapping.get("artifact_hash") is not None
            else None
        ),
        artifact_lifecycle_status=(
            str(mapping["artifact_lifecycle_status"])
            if mapping.get("artifact_lifecycle_status") is not None
            else None
        ),
        observed_at=observed_at,
        deterministic_revenue_minor=int(
            mapping.get("deterministic_revenue_minor") or 0
        ),
        deterministic_row_count=int(mapping.get("deterministic_row_count") or 0),
        match_verdict_count=int(mapping.get("match_verdict_count") or 0),
        source_snapshot_mismatch=bool(mapping.get("source_snapshot_mismatch")),
        decision=decision,
    )
