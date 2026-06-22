"""Internal read-only B2.4-P10 confidence projection."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import TextClause

from app.bayesian.confidence_metadata import (
    B24ConfidenceProjection,
    BayesianProjectionMetadata,
    CredibleIntervalProjectionMetadata,
    DeterministicProjectionMetadata,
    ProjectionAuditMetadata,
)
from app.bayesian.confidence_policy import classify_confidence


DEFAULT_PROJECTION_MODEL_TYPE = "bayesian_attribution_confidence"
DEFAULT_PROJECTION_MODEL_VERSION = "b24-p10"


def build_b24_confidence_projection_query() -> TextClause:
    """Return the deterministic-left SQL used by the internal projection."""

    return text(
        """
        WITH deterministic_left AS (
            SELECT
                revenue.tenant_id,
                CAST(:source_window_start AS timestamptz) AS source_window_start,
                CAST(:source_window_end AS timestamptz) AS source_window_end,
                UPPER(TRIM(revenue.currency_code)) AS currency_code,
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
                COUNT(*) AS deterministic_row_count,
                COUNT(DISTINCT revenue.match_verdict_id) AS match_verdict_count,
                COUNT(DISTINCT revenue.provider_native_event_reference) AS verification_event_count
            FROM public.b23_revenue_events revenue
            WHERE revenue.tenant_id = :tenant_id
              AND revenue.event_occurred_at >= :source_window_start
              AND revenue.event_occurred_at < :source_window_end
            GROUP BY revenue.tenant_id, UPPER(TRIM(revenue.currency_code))
        ),
        latest_matching_fit AS (
            SELECT DISTINCT ON (
                fit.tenant_id,
                fit.model_type,
                fit.model_version,
                fit.source_window_start,
                fit.source_window_end,
                fit.source_snapshot_hash
            )
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
                fit.last_fit_at,
                fit.completed_at,
                fit.n_chains,
                fit.n_samples_actual,
                fit.r_hat_max,
                fit.ess_min,
                fit.divergence_count,
                fit.hdi_lower,
                fit.hdi_upper,
                fit.credible_interval_status,
                fit.diagnostic_status,
                fit.diagnostic_failure_reason,
                fit.diagnostic_policy_version,
                fit.interval_policy_version,
                fit.hdi_probability,
                fit.artifact_ref,
                fit.artifact_hash
            FROM public.bayesian_model_fits fit
            WHERE fit.tenant_id = :tenant_id
              AND fit.model_type = :model_type
              AND fit.model_version = :model_version
              AND fit.source_window_start = :source_window_start
              AND fit.source_window_end = :source_window_end
              AND fit.source_snapshot_hash = :source_snapshot_hash
            ORDER BY
                fit.tenant_id,
                fit.model_type,
                fit.model_version,
                fit.source_window_start,
                fit.source_window_end,
                fit.source_snapshot_hash,
                CASE fit.status
                    WHEN 'succeeded' THEN 0
                    WHEN 'fallback_only' THEN 1
                    WHEN 'failed' THEN 2
                    WHEN 'timeout' THEN 3
                    ELSE 4
                END,
                fit.completed_at DESC NULLS LAST,
                fit.last_fit_at DESC NULLS LAST,
                fit.id DESC
        ),
        mismatch_probe AS (
            SELECT
                fit.tenant_id,
                COUNT(*) > 0 AS source_snapshot_mismatch
            FROM public.bayesian_model_fits fit
            WHERE fit.tenant_id = :tenant_id
              AND fit.model_type = :model_type
              AND fit.model_version = :model_version
              AND fit.source_window_start = :source_window_start
              AND fit.source_window_end = :source_window_end
              AND fit.source_snapshot_hash <> :source_snapshot_hash
            GROUP BY fit.tenant_id
        ),
        artifact_summary AS (
            SELECT DISTINCT ON (artifact.tenant_id, artifact.fit_id)
                artifact.tenant_id,
                artifact.fit_id,
                artifact.artifact_ref,
                artifact.artifact_hash,
                artifact.artifact_type,
                artifact.lifecycle_status AS artifact_lifecycle_status,
                artifact.policy_version AS artifact_policy_version
            FROM public.bayesian_artifacts artifact
            WHERE artifact.tenant_id = :tenant_id
              AND artifact.artifact_type IN ('posterior_summary', 'diagnostics', 'summary')
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
            deterministic_left.tenant_id,
            deterministic_left.source_window_start,
            deterministic_left.source_window_end,
            deterministic_left.currency_code,
            deterministic_left.deterministic_revenue_minor,
            deterministic_left.deterministic_row_count,
            deterministic_left.match_verdict_count,
            deterministic_left.verification_event_count,
            :source_snapshot_hash AS projected_source_snapshot_hash,
            COALESCE(mismatch_probe.source_snapshot_mismatch, false) AS source_snapshot_mismatch,
            latest_matching_fit.fit_id,
            latest_matching_fit.fit_status,
            latest_matching_fit.model_type,
            latest_matching_fit.model_version,
            latest_matching_fit.data_completeness_status,
            latest_matching_fit.fallback_applied,
            latest_matching_fit.fallback_reason,
            latest_matching_fit.last_fit_at,
            latest_matching_fit.completed_at,
            latest_matching_fit.n_chains,
            latest_matching_fit.n_samples_actual,
            latest_matching_fit.r_hat_max,
            latest_matching_fit.ess_min,
            latest_matching_fit.divergence_count,
            latest_matching_fit.hdi_lower,
            latest_matching_fit.hdi_upper,
            latest_matching_fit.credible_interval_status,
            latest_matching_fit.diagnostic_status,
            latest_matching_fit.diagnostic_failure_reason,
            latest_matching_fit.diagnostic_policy_version,
            latest_matching_fit.interval_policy_version,
            latest_matching_fit.hdi_probability,
            COALESCE(artifact_summary.artifact_ref, latest_matching_fit.artifact_ref) AS artifact_ref,
            COALESCE(artifact_summary.artifact_hash, latest_matching_fit.artifact_hash) AS artifact_hash,
            artifact_summary.artifact_lifecycle_status,
            artifact_summary.artifact_policy_version
        FROM deterministic_left
        LEFT OUTER JOIN latest_matching_fit
          ON latest_matching_fit.tenant_id = deterministic_left.tenant_id
         AND latest_matching_fit.source_window_start = deterministic_left.source_window_start
         AND latest_matching_fit.source_window_end = deterministic_left.source_window_end
         AND latest_matching_fit.source_snapshot_hash = :source_snapshot_hash
        LEFT OUTER JOIN artifact_summary
          ON artifact_summary.tenant_id = latest_matching_fit.tenant_id
         AND artifact_summary.fit_id = latest_matching_fit.fit_id
        LEFT OUTER JOIN mismatch_probe
          ON mismatch_probe.tenant_id = deterministic_left.tenant_id
        ORDER BY deterministic_left.currency_code
        """
    )


async def project_b24_confidence(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    model_type: str = DEFAULT_PROJECTION_MODEL_TYPE,
    model_version: str = DEFAULT_PROJECTION_MODEL_VERSION,
) -> list[B24ConfidenceProjection]:
    """Read internal B2.4 confidence metadata without triggering compute."""

    result = await session.execute(
        build_b24_confidence_projection_query(),
        {
            "tenant_id": tenant_id,
            "source_window_start": source_window_start,
            "source_window_end": source_window_end,
            "source_snapshot_hash": source_snapshot_hash,
            "model_type": model_type,
            "model_version": model_version,
        },
    )
    return build_projection_models(
        result.mappings().all(),
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        source_snapshot_hash=source_snapshot_hash,
        model_type=model_type,
        model_version=model_version,
    )


def build_projection_models(
    rows: list[dict[str, Any]] | Any,
    *,
    source_window_start: datetime,
    source_window_end: datetime,
    source_snapshot_hash: str,
    model_type: str = DEFAULT_PROJECTION_MODEL_TYPE,
    model_version: str = DEFAULT_PROJECTION_MODEL_VERSION,
    generated_at: datetime | None = None,
) -> list[B24ConfidenceProjection]:
    """Convert query rows into governed P10 DTOs."""

    generated = generated_at or datetime.now(timezone.utc)
    projections: list[B24ConfidenceProjection] = []
    for row in rows:
        mapping = dict(row)
        deterministic_revenue_minor = int(
            mapping.get("deterministic_revenue_minor") or 0
        )
        decision = classify_confidence(
            {
                **mapping,
                "deterministic_revenue_minor": deterministic_revenue_minor,
            }
        )
        interval_available = decision.confidence_available
        interval = CredibleIntervalProjectionMetadata(
            lower=_nullable_float(mapping.get("hdi_lower")) if interval_available else None,
            upper=_nullable_float(mapping.get("hdi_upper")) if interval_available else None,
            level=_nullable_float(mapping.get("hdi_probability")) if interval_available else None,
            source="bayesian_model_fit" if interval_available else "unavailable",
            status=(
                str(mapping.get("credible_interval_status") or "unavailable")
                if interval_available
                else "unavailable"
            ),
        )
        fallback_applied = bool(mapping.get("fallback_applied") or False)
        if mapping.get("fit_id") is None or bool(mapping.get("source_snapshot_mismatch")):
            fallback_applied = False
        deterministic = DeterministicProjectionMetadata(
            tenant_id=mapping["tenant_id"],
            source_window_start=source_window_start,
            source_window_end=source_window_end,
            deterministic_revenue_minor=deterministic_revenue_minor,
            currency_code=str(mapping.get("currency_code") or "USD"),
            deterministic_source_status="available",
            deterministic_source_refs={
                "b23_revenue_events": int(mapping.get("deterministic_row_count") or 0),
                "b23_match_verdicts": int(mapping.get("match_verdict_count") or 0),
                "webhook_verification_refs": int(
                    mapping.get("verification_event_count") or 0
                ),
            },
            verification_coverage={
                "source": "b23_revenue_events",
                "row_count": int(mapping.get("deterministic_row_count") or 0),
                "currency_code": str(mapping.get("currency_code") or "USD"),
            },
            source_snapshot_hash=source_snapshot_hash,
        )
        bayesian = BayesianProjectionMetadata(
            fit_id=mapping.get("fit_id"),
            fit_status=mapping.get("fit_status"),
            model_type=str(mapping.get("model_type") or model_type),
            model_version=str(mapping.get("model_version") or model_version),
            model_fit_version=mapping.get("diagnostic_policy_version")
            or mapping.get("interval_policy_version"),
            diagnostics_status=mapping.get("diagnostic_status"),
            credible_interval=interval,
            fallback_applied=fallback_applied,
            fallback_reason=mapping.get("fallback_reason"),
            artifact_ref=mapping.get("artifact_ref"),
            artifact_hash=mapping.get("artifact_hash"),
            artifact_lifecycle_status=mapping.get("artifact_lifecycle_status"),
        )
        projections.append(
            B24ConfidenceProjection(
                deterministic=deterministic,
                bayesian=bayesian,
                confidence={
                    "confidence_available": decision.confidence_available,
                    "confidence_bucket": decision.confidence_bucket.value,
                    "confidence_bucket_reason": decision.confidence_bucket_reason.value,
                    "confidence_policy_version": decision.confidence_policy_version,
                    "confidence_semantics_version": decision.confidence_semantics_version,
                },
                audit=ProjectionAuditMetadata(projection_generated_at=generated),
            )
        )
    return projections


def _nullable_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
