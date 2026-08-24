"""Exact-fit, snapshot-coherent B2.4 confidence projection for Trust."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.confidence_projection.policy import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    ConfidenceBucket,
    ConfidenceBucketReason,
    ConfidencePolicyDecision,
    persisted_confidence_decision,
)
from app.confidence_projection.sql_authority import assert_executable_read_authority
from app.trust.subject_authority import subject_authority_definition


SnapshotFreshness = Literal["current", "stale", "unknown"]
# The families Trust may project. This is deliberately a literal and NOT an
# import of app.bayesian.model_identity: B2.5-P12 forbids the Trust path from
# reaching Bayesian modules at all, and that isolation is worth more than
# import-time deduplication. The single authority is still
# app.bayesian.model_identity.MODEL_IDENTITY_REGISTRY -- the C8 closure gate
# asserts this set equals its trust-eligible members, so the two cannot diverge
# without turning required CI red.
SUPPORTED_CONFIDENCE_MODEL_TYPES = frozenset({"bayesian_attribution_confidence"})


class ConfidenceProjectionReadError(ValueError):
    """Compatibility error for callers that still import the historical type."""


@dataclass(frozen=True)
class B24ConfidenceProjectionRead:
    """B2.4-persisted classification plus exact snapshot/lifecycle authority."""

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
    evidence_snapshot_at: datetime | None
    source_read_started_at: datetime | None
    source_read_completed_at: datetime | None
    deterministic_revenue_minor: int | None
    deterministic_row_count: int | None
    match_verdict_count: int | None
    currency_count: int | None
    confidence_classified_at: datetime | None
    confidence_evidence_snapshot_hash: str | None
    snapshot_freshness: SnapshotFreshness
    has_snapshot_lineage: bool
    has_later_dirty_evidence: bool
    has_newer_fit: bool
    decision: ConfidencePolicyDecision

    #: The inference regime that produced this confidence. Read from the fit,
    #: never recomputed -- Trust may not reach into Bayesian modules, and the
    #: process that knew these values exited long ago.
    #:
    #: Defaulted to None because rows written before C10 genuinely have no
    #: recorded regime. That is the honest representation of a real gap; the
    #: places where a regime is mandatory enforce it directly -- the database
    #: refuses a usable confidence bucket without a policy bundle, and the P13
    #: closure proof refuses an available envelope whose provenance is absent.
    inference_profile_version: str | None = None
    runtime_policy_version: str | None = None
    sampling_policy_version: str | None = None
    diagnostic_policy_version: str | None = None
    policy_bundle_hash: str | None = None
    authorized_chains: int | None = None
    authorized_posterior_draws_total: int | None = None
    observed_chains: int | None = None
    observed_posterior_draws_total: int | None = None

    @property
    def source_snapshot_mismatch(self) -> bool:
        """Preserve the historical adapter property with fail-closed semantics."""

        return self.snapshot_freshness != "current"


_AUTHORITY = subject_authority_definition("confidence_projection")
CONFIDENCE_PROJECTION_PHYSICAL_READ_TABLES = _AUTHORITY.physical_read_tables

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
            fit.created_at,
            fit.completed_at,
            fit.updated_at,
            fit.diagnostic_status,
            fit.diagnostic_failure_reason,
            fit.credible_interval_status,
            fit.confidence_bucket,
            fit.confidence_bucket_reason,
            fit.confidence_policy_version,
            fit.confidence_semantics_version,
            fit.confidence_deterministic_revenue_minor,
            fit.confidence_deterministic_row_count,
            fit.confidence_match_verdict_count,
            fit.confidence_currency_count,
            fit.confidence_classified_at,
            fit.confidence_evidence_snapshot_hash,
            fit.source_read_started_at,
            fit.source_read_completed_at,
            fit.artifact_ref AS fit_artifact_ref,
            fit.artifact_hash AS fit_artifact_hash,
            fit.inference_profile_version,
            fit.runtime_policy_version,
            fit.sampling_policy_version,
            fit.diagnostic_policy_version,
            fit.policy_bundle_hash,
            fit.authorized_chains,
            fit.authorized_posterior_draws_total,
            fit.n_chains AS observed_chains,
            fit.n_samples_actual AS observed_posterior_draws_total
        FROM public.bayesian_model_fits fit
        WHERE fit.tenant_id = :tenant_id
          AND fit.id = :fit_id
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
          AND artifact.artifact_ref = requested_fit.fit_artifact_ref
          AND artifact.artifact_hash = requested_fit.fit_artifact_hash
        ORDER BY
            artifact.tenant_id,
            artifact.fit_id,
            CASE artifact.artifact_type
                WHEN 'posterior_summary' THEN 0
                WHEN 'diagnostics' THEN 1
                ELSE 2
            END,
            artifact.created_at DESC,
            artifact.id DESC
    ),
    freshness_authority AS (
        SELECT
            requested_fit.fit_id,
            EXISTS (
                SELECT 1
                FROM public.b24_dirty_events dirty
                WHERE dirty.tenant_id = requested_fit.tenant_id
                  AND dirty.model_type = requested_fit.model_type
                  AND dirty.model_version = requested_fit.model_version
                  AND dirty.source_window_start = requested_fit.source_window_start
                  AND dirty.source_window_end = requested_fit.source_window_end
                  AND dirty.source_snapshot_hash = requested_fit.source_snapshot_hash
            ) AS has_snapshot_lineage,
            -- C8: staleness is window OVERLAP, not window equality.
            -- A dirty event records the SCOPE of a source change; a fit records
            -- the window it read. Requiring the two to be equal meant a change
            -- inside a 30-day fit could not stale it, and a writer cannot know
            -- the fit windows it affects without unbounded write-time fan-out.
            -- Overlap is evaluated here, correlated to one requested fit, so the
            -- cost stays bounded by that fit's window and is index-supported.
            -- model_version is deliberately absent: a change to the underlying
            -- financial truth stales an affected fit regardless of which
            -- pipeline version produced it.
            EXISTS (
                SELECT 1
                FROM public.b24_dirty_events dirty
                WHERE dirty.tenant_id = requested_fit.tenant_id
                  AND dirty.model_type = requested_fit.model_type
                  AND public.b24_source_windows_overlap(
                      dirty.source_window_start,
                      dirty.source_window_end,
                      requested_fit.source_window_start,
                      requested_fit.source_window_end
                  )
                  AND dirty.observed_at > COALESCE(
                      requested_fit.source_read_started_at,
                      requested_fit.created_at
                  )
                  AND dirty.source_snapshot_hash IS DISTINCT FROM requested_fit.source_snapshot_hash
            ) AS has_later_dirty_evidence,
            EXISTS (
                SELECT 1
                FROM public.bayesian_model_fits newer_fit
                WHERE newer_fit.tenant_id = requested_fit.tenant_id
                  AND newer_fit.model_type = requested_fit.model_type
                  AND newer_fit.model_version = requested_fit.model_version
                  AND newer_fit.source_window_start = requested_fit.source_window_start
                  AND newer_fit.source_window_end = requested_fit.source_window_end
                  AND newer_fit.source_snapshot_hash <> requested_fit.source_snapshot_hash
                  AND newer_fit.created_at > requested_fit.created_at
            ) AS has_newer_fit
        FROM requested_fit
    )
    SELECT
        requested_fit.*,
        artifact_summary.artifact_ref,
        artifact_summary.artifact_hash,
        artifact_summary.artifact_lifecycle_status,
        freshness_authority.has_snapshot_lineage,
        freshness_authority.has_later_dirty_evidence,
        freshness_authority.has_newer_fit
    FROM requested_fit
    JOIN freshness_authority
      ON freshness_authority.fit_id = requested_fit.fit_id
    LEFT OUTER JOIN artifact_summary
      ON artifact_summary.tenant_id = requested_fit.tenant_id
     AND artifact_summary.fit_id = requested_fit.fit_id
    """
)


def _unavailable(reason: ConfidenceBucketReason) -> ConfidencePolicyDecision:
    return ConfidencePolicyDecision(
        confidence_available=False,
        confidence_bucket=ConfidenceBucket.UNAVAILABLE,
        confidence_bucket_reason=reason,
        confidence_policy_version=CONFIDENCE_POLICY_VERSION,
        confidence_semantics_version=CONFIDENCE_SEMANTICS_VERSION,
    )


def _snapshot_freshness(mapping: dict[str, object]) -> SnapshotFreshness:
    if (
        not bool(mapping.get("has_snapshot_lineage"))
        or not isinstance(mapping.get("source_read_started_at"), datetime)
        or not isinstance(mapping.get("source_read_completed_at"), datetime)
    ):
        return "unknown"
    if bool(mapping.get("has_later_dirty_evidence")) or bool(
        mapping.get("has_newer_fit")
    ):
        return "stale"
    return "current"


def _policy_provenance_complete(mapping: dict[str, object]) -> bool:
    """Return whether usable confidence names and matches its producing regime."""

    versions = (
        mapping.get("inference_profile_version"),
        mapping.get("runtime_policy_version"),
        mapping.get("sampling_policy_version"),
        mapping.get("diagnostic_policy_version"),
    )
    if any(not isinstance(value, str) or not value.strip() for value in versions):
        return False
    bundle_hash = mapping.get("policy_bundle_hash")
    if (
        not isinstance(bundle_hash, str)
        or len(bundle_hash) != 64
        or any(character not in "0123456789abcdef" for character in bundle_hash)
    ):
        return False
    topology = (
        mapping.get("authorized_chains"),
        mapping.get("authorized_posterior_draws_total"),
        mapping.get("observed_chains"),
        mapping.get("observed_posterior_draws_total"),
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in topology):
        return False
    authorized_chains, authorized_draws, observed_chains, observed_draws = cast(
        tuple[int, int, int, int], topology
    )
    return (
        authorized_chains > 0
        and authorized_draws > 0
        and observed_chains == authorized_chains
        and observed_draws == authorized_draws
    )


def _projection_decision(
    mapping: dict[str, object], *, freshness: SnapshotFreshness
) -> ConfidencePolicyDecision:
    if freshness == "unknown":
        return _unavailable(ConfidenceBucketReason.SOURCE_AUTHORITY_UNKNOWN)
    if freshness == "stale":
        return _unavailable(ConfidenceBucketReason.SOURCE_SNAPSHOT_CHANGED)
    if str(mapping.get("model_type") or "") not in SUPPORTED_CONFIDENCE_MODEL_TYPES:
        return _unavailable(ConfidenceBucketReason.UNSUPPORTED_MODEL_TYPE)
    persisted = persisted_confidence_decision(
        confidence_bucket=(
            str(mapping["confidence_bucket"])
            if mapping.get("confidence_bucket") is not None
            else None
        ),
        confidence_bucket_reason=(
            str(mapping["confidence_bucket_reason"])
            if mapping.get("confidence_bucket_reason") is not None
            else None
        ),
        confidence_policy_version=(
            str(mapping["confidence_policy_version"])
            if mapping.get("confidence_policy_version") is not None
            else None
        ),
        confidence_semantics_version=(
            str(mapping["confidence_semantics_version"])
            if mapping.get("confidence_semantics_version") is not None
            else None
        ),
        deterministic_revenue_minor=mapping.get(
            "confidence_deterministic_revenue_minor"
        ),
        deterministic_row_count=mapping.get("confidence_deterministic_row_count"),
        match_verdict_count=mapping.get("confidence_match_verdict_count"),
        currency_count=mapping.get("confidence_currency_count"),
        confidence_classified_at=mapping.get("confidence_classified_at"),
        confidence_evidence_snapshot_hash=(
            str(mapping["confidence_evidence_snapshot_hash"])
            if mapping.get("confidence_evidence_snapshot_hash") is not None
            else None
        ),
        source_snapshot_hash=(
            str(mapping["source_snapshot_hash"])
            if mapping.get("source_snapshot_hash") is not None
            else None
        ),
        source_read_started_at=mapping.get("source_read_started_at"),
        source_read_completed_at=mapping.get("source_read_completed_at"),
        fit_status=(
            str(mapping["fit_status"])
            if mapping.get("fit_status") is not None
            else None
        ),
        data_completeness_status=(
            str(mapping["data_completeness_status"])
            if mapping.get("data_completeness_status") is not None
            else None
        ),
        fallback_applied=(
            bool(mapping["fallback_applied"])
            if isinstance(mapping.get("fallback_applied"), bool)
            else None
        ),
        diagnostic_status=(
            str(mapping["diagnostic_status"])
            if mapping.get("diagnostic_status") is not None
            else None
        ),
        credible_interval_status=(
            str(mapping["credible_interval_status"])
            if mapping.get("credible_interval_status") is not None
            else None
        ),
    )
    if not persisted.confidence_available:
        return persisted
    # The database constraint governs every new write but is intentionally
    # NOT VALID for historical rows: inventing provenance for old confidence
    # would be worse than admitting it was never recorded. This consumer guard
    # makes those legacy rows unusable and independently checks observed versus
    # authorized topology before Trust can sign an available claim.
    if not _policy_provenance_complete(mapping):
        return _unavailable(ConfidenceBucketReason.PERSISTED_CLASSIFICATION_INVALID)
    lifecycle = mapping.get("artifact_lifecycle_status")
    if lifecycle == "pruned":
        return _unavailable(ConfidenceBucketReason.ARTIFACT_PRUNED)
    if (
        lifecycle != "active"
        or not mapping.get("artifact_ref")
        or not mapping.get("artifact_hash")
    ):
        return _unavailable(ConfidenceBucketReason.ARTIFACT_UNAVAILABLE)
    return persisted


async def read_b24_confidence_projection_for_fit(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    fit_id: UUID,
) -> B24ConfidenceProjectionRead | None:
    """Project one exact fit without live-source aggregation or reclassification."""

    assert_executable_read_authority(
        str(_EXACT_FIT_PROJECTION_SQL),
        expected_tables=CONFIDENCE_PROJECTION_PHYSICAL_READ_TABLES,
    )
    result = await session.execute(
        _EXACT_FIT_PROJECTION_SQL,
        {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
    )
    row = result.mappings().first()
    if row is None:
        return None
    mapping = dict(row)
    freshness = _snapshot_freshness(mapping)
    decision = _projection_decision(mapping, freshness=freshness)
    observed_at = mapping.get("completed_at") or mapping["updated_at"]

    def _nullable_int(name: str) -> int | None:
        value = mapping.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            return None
        return int(value)

    def _nullable_str(column: str) -> str | None:
        value = mapping.get(column)
        return None if value is None else str(value)

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
        inference_profile_version=_nullable_str("inference_profile_version"),
        runtime_policy_version=_nullable_str("runtime_policy_version"),
        sampling_policy_version=_nullable_str("sampling_policy_version"),
        diagnostic_policy_version=_nullable_str("diagnostic_policy_version"),
        policy_bundle_hash=_nullable_str("policy_bundle_hash"),
        authorized_chains=_nullable_int("authorized_chains"),
        authorized_posterior_draws_total=_nullable_int(
            "authorized_posterior_draws_total"
        ),
        observed_chains=_nullable_int("observed_chains"),
        observed_posterior_draws_total=_nullable_int("observed_posterior_draws_total"),
        observed_at=observed_at,
        evidence_snapshot_at=mapping.get("source_read_started_at"),
        source_read_started_at=mapping.get("source_read_started_at"),
        source_read_completed_at=mapping.get("source_read_completed_at"),
        deterministic_revenue_minor=_nullable_int(
            "confidence_deterministic_revenue_minor"
        ),
        deterministic_row_count=_nullable_int("confidence_deterministic_row_count"),
        match_verdict_count=_nullable_int("confidence_match_verdict_count"),
        currency_count=_nullable_int("confidence_currency_count"),
        confidence_classified_at=mapping.get("confidence_classified_at"),
        confidence_evidence_snapshot_hash=(
            str(mapping["confidence_evidence_snapshot_hash"])
            if mapping.get("confidence_evidence_snapshot_hash") is not None
            else None
        ),
        snapshot_freshness=freshness,
        has_snapshot_lineage=bool(mapping.get("has_snapshot_lineage")),
        has_later_dirty_evidence=bool(mapping.get("has_later_dirty_evidence")),
        has_newer_fit=bool(mapping.get("has_newer_fit")),
        decision=decision,
    )
