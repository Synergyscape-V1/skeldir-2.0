"""SQLAlchemy models for B2.4-P1 Bayesian authority tables."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


# P1 validator token: "partitioning": {"strategy": "hash", "key": ["tenant_id"], "partitions": 16}
class BayesianModelFit(Base, TenantMixin):
    """Tenant-scoped B2.4 model fit authority row."""

    __tablename__ = "bayesian_model_fits"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    eligibility_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    data_completeness_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="unknown",
        server_default="unknown",
    )
    fallback_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    fallback_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sampling_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_eligibility_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_fit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_runtime_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60, server_default="60"
    )
    max_samples: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_cores: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    n_chains: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_samples_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    r_hat_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    ess_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    divergence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hdi_lower: Mapped[float | None] = mapped_column(Float, nullable=True)
    hdi_upper: Mapped[float | None] = mapped_column(Float, nullable=True)
    interval_shape: Mapped[list[int]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    interval_element_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_summary_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credible_interval_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_available",
        server_default="not_available",
    )
    diagnostic_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_computed",
        server_default="not_computed",
    )
    diagnostic_failure_reason: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    diagnostic_policy_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    diagnostic_target_filter_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    interval_policy_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    diagnostics_computed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confidence_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_bucket_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    confidence_policy_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    artifact_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    artifact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "id",
            name="bayesian_model_fits_pkey",
        ),
        UniqueConstraint(
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
            name="uq_bayesian_model_fits_tenant_model_window_snapshot",
        ),
        CheckConstraint(
            "model_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_bayesian_model_fits_model_type_format",
        ),
        CheckConstraint(
            "char_length(trim(model_version)) > 0",
            name="ck_bayesian_model_fits_model_version_not_blank",
        ),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_bayesian_model_fits_source_window_order",
        ),
        CheckConstraint(
            "source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_bayesian_model_fits_source_snapshot_hash_sha256",
        ),
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'persist_pending', 'sampled_unvalidated', 'diagnostics_pending', 'succeeded', 'failed', 'timeout', 'worker_lost', 'fallback_only', 'cancelled')",
            name="ck_bayesian_model_fits_status",
        ),
        CheckConstraint(
            "eligibility_status IN ('unknown', 'eligible', 'ineligible', 'fallback_only')",
            name="ck_bayesian_model_fits_eligibility_status",
        ),
        CheckConstraint(
            "data_completeness_status IN ('unknown', 'complete', 'partial', 'insufficient', 'stale')",
            name="ck_bayesian_model_fits_data_completeness_status",
        ),
        CheckConstraint(
            "fallback_reason IS NULL OR fallback_reason IN ("
            "'source_window_empty', 'insufficient_data', 'insufficient_privacy_cohort', "
            "'input_too_large', 'feature_width_exceeded', 'source_window_too_large', "
            "'memory_bound_exceeded', 'graph_complexity_exceeded', "
            "'parameter_count_exceeded', 'hierarchy_width_exceeded', "
            "'compilation_memory_bound_exceeded', "
            "'cardinality_authority_missing', 'cardinality_authority_stale', "
            "'cardinality_authority_mismatch', "
            "'cardinality_authority_timeout', "
            "'cardinality_authority_build_failed', "
            "'source_profile_unavailable', "
            "'source_snapshot_mismatch', 'transport_rejected', "
            "'result_too_large', 'sampler_health_failed', "
            "'model_memory_exceeded', 'graph_compile_memory_exceeded', "
            "'policy_rejected', "
            "'timeout', 'worker_failure', 'no_convergence', "
            "'resource_bound_exceeded', 'source_unavailable', 'duplicate_fit_suppressed', "
            "'artifact_unavailable', 'storage_quota_exceeded')",
            name="ck_bayesian_model_fits_fallback_reason",
        ),
        CheckConstraint(
            "(fallback_applied = false AND fallback_reason IS NULL) "
            "OR (fallback_applied = true AND fallback_reason IS NOT NULL)",
            name="ck_bayesian_model_fits_fallback_reason_required",
        ),
        CheckConstraint(
            "runtime_seconds IS NULL OR runtime_seconds >= 0",
            name="ck_bayesian_model_fits_runtime_seconds_non_negative",
        ),
        CheckConstraint(
            "max_runtime_seconds >= 0",
            name="ck_bayesian_model_fits_max_runtime_seconds_non_negative",
        ),
        CheckConstraint(
            "max_samples >= 0", name="ck_bayesian_model_fits_max_samples_non_negative"
        ),
        CheckConstraint(
            "max_cores >= 0", name="ck_bayesian_model_fits_max_cores_non_negative"
        ),
        CheckConstraint(
            "n_chains IS NULL OR n_chains >= 0",
            name="ck_bayesian_model_fits_n_chains_non_negative",
        ),
        CheckConstraint(
            "n_samples_actual IS NULL OR n_samples_actual >= 0",
            name="ck_bayesian_model_fits_n_samples_actual_non_negative",
        ),
        CheckConstraint(
            "r_hat_max IS NULL OR r_hat_max > 0",
            name="ck_bayesian_model_fits_r_hat_max_positive",
        ),
        CheckConstraint(
            "ess_min IS NULL OR ess_min >= 0",
            name="ck_bayesian_model_fits_ess_min_non_negative",
        ),
        CheckConstraint(
            "divergence_count IS NULL OR divergence_count >= 0",
            name="ck_bayesian_model_fits_divergence_count_non_negative",
        ),
        CheckConstraint(
            "(hdi_lower IS NULL AND hdi_upper IS NULL) OR (hdi_lower IS NOT NULL AND hdi_upper IS NOT NULL AND hdi_lower <= hdi_upper)",
            name="ck_bayesian_model_fits_hdi_bounds_pair_order",
        ),
        CheckConstraint(
            "interval_element_count IS NULL OR interval_element_count >= 0",
            name="ck_bayesian_model_fits_interval_element_count_non_negative",
        ),
        CheckConstraint(
            "interval_summary_bytes IS NULL OR interval_summary_bytes >= 0",
            name="ck_bayesian_model_fits_interval_summary_bytes_non_negative",
        ),
        CheckConstraint(
            "credible_interval_status IN ('not_available', 'available', 'suppressed', 'invalid', 'pending')",
            name="ck_bayesian_model_fits_credible_interval_status",
        ),
        CheckConstraint(
            "diagnostic_status IN ('not_computed', 'passed', 'failed', 'error', 'unavailable')",
            name="ck_bayesian_model_fits_diagnostic_status",
        ),
        CheckConstraint(
            "diagnostic_failure_reason IS NULL OR diagnostic_failure_reason IN ("
            "'bad_rhat', 'low_ess', 'divergence', 'nonfinite_diagnostic', "
            "'invalid_diagnostic_summary', 'diagnostic_scope_too_large', "
            "'interval_dimension_exceeded', 'interval_payload_too_large', "
            "'diagnostics_failed', 'diagnostics_memory_exceeded', "
            "'diagnostics_timeout', 'skipped_non_sampled')",
            name="ck_bayesian_model_fits_diagnostic_failure_reason",
        ),
        CheckConstraint(
            "(diagnostic_status = 'passed' AND diagnostic_failure_reason IS NULL) "
            "OR (diagnostic_status <> 'passed')",
            name="ck_bayesian_model_fits_passed_has_no_diagnostic_failure",
        ),
        CheckConstraint(
            "credible_interval_status <> 'available' OR ("
            "diagnostic_status = 'passed' "
            "AND fallback_applied = false "
            "AND r_hat_max IS NOT NULL AND r_hat_max <= 1.01 "
            "AND ess_min IS NOT NULL AND ess_min >= 400 "
            "AND divergence_count = 0 "
            "AND hdi_lower IS NOT NULL AND hdi_upper IS NOT NULL "
            "AND interval_element_count IS NOT NULL AND interval_element_count > 0 "
            "AND diagnostic_policy_version IS NOT NULL "
            "AND diagnostic_target_filter_version IS NOT NULL "
            "AND interval_policy_version IS NOT NULL)",
            name="ck_bayesian_model_fits_available_interval_requires_passed_diagnostics",
        ),
        CheckConstraint(
            "confidence_bucket IS NULL OR confidence_bucket IN ('unavailable', 'low', 'medium', 'high', 'fallback', 'needs_review')",
            name="ck_bayesian_model_fits_confidence_bucket",
        ),
        CheckConstraint(
            "artifact_ref IS NULL OR artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'",
            name="ck_bayesian_model_fits_artifact_ref_format",
        ),
        CheckConstraint(
            "artifact_hash IS NULL OR artifact_hash ~ '^[a-f0-9]{64}$'",
            name="ck_bayesian_model_fits_artifact_hash_sha256",
        ),
        CheckConstraint(
            "(artifact_ref IS NULL AND artifact_hash IS NULL) OR (artifact_ref IS NOT NULL AND artifact_hash IS NOT NULL)",
            name="ck_bayesian_model_fits_artifact_ref_hash_pair",
        ),
        Index("idx_bayesian_model_fits_tenant_id", "tenant_id"),
        Index(
            "idx_bayesian_model_fits_tenant_model_window",
            "tenant_id",
            "model_type",
            "source_window_start",
            "source_window_end",
        ),
        Index(
            "idx_bayesian_model_fits_tenant_source_snapshot_hash",
            "tenant_id",
            "source_snapshot_hash",
        ),
        Index("idx_bayesian_model_fits_tenant_status", "tenant_id", "status"),
        Index(
            "idx_bayesian_model_fits_tenant_model_eligibility",
            "tenant_id",
            "model_type",
            "eligibility_status",
            text("last_eligibility_check_at DESC"),
        ),
        Index(
            "idx_bayesian_model_fits_tenant_model_fallback",
            "tenant_id",
            "model_type",
            "fallback_reason",
            text("last_eligibility_check_at DESC"),
            postgresql_where=text("fallback_applied = true"),
        ),
        Index(
            "idx_bayesian_model_fits_tenant_model_window_latest",
            "tenant_id",
            "model_type",
            "source_window_start",
            "source_window_end",
            text("created_at DESC"),
        ),
        {
            "info": {
                "storage_parameters": {"fit_partition_fillfactor": 90},
                "partitioning": {
                    "strategy": "hash",
                    "key": ["tenant_id"],
                    "partitions": 16,
                },
            }
        },
    )


class BayesianArtifact(Base):
    """Tenant-scoped B2.4 artifact authority row."""

    __tablename__ = "bayesian_artifacts"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    fit_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        nullable=False,
    )
    artifact_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(32), nullable=False)
    artifact_uri_internal: Mapped[str] = mapped_column(String(1024), nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_json: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)
    payload_bytes: Mapped[bytes | None] = mapped_column(
        LargeBinary,
        nullable=True,
        deferred=True,
        deferred_raiseload=True,
    )
    payload_byte_count: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    compression: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retention_class: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active", server_default="active"
    )
    policy_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="b24-p8-artifact-policy-v1",
        server_default="b24-p8-artifact-policy-v1",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pruned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pruned_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pruned_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "id",
            name="bayesian_artifacts_pkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "fit_id"],
            ["bayesian_model_fits.tenant_id", "bayesian_model_fits.id"],
            name="fk_bayesian_artifacts_tenant_fit",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id",
            "artifact_ref",
            name="uq_bayesian_artifacts_tenant_artifact_ref",
        ),
        CheckConstraint(
            "artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'",
            name="ck_bayesian_artifacts_artifact_ref_format",
        ),
        CheckConstraint(
            "artifact_hash ~ '^[a-f0-9]{64}$'",
            name="ck_bayesian_artifacts_artifact_hash_sha256",
        ),
        CheckConstraint(
            "artifact_type IN ('diagnostics', 'summary', 'source_manifest', 'fit_metadata', 'input_manifest', 'model_spec', 'posterior_summary')",
            name="ck_bayesian_artifacts_artifact_type",
        ),
        CheckConstraint(
            "storage_backend = 'postgres'",
            name="ck_bayesian_artifacts_storage_backend",
        ),
        CheckConstraint(
            "lifecycle_status IN ('pruned', 'rejected') OR (artifact_uri_internal = artifact_ref AND artifact_uri_internal ~ '^b24://artifact/[a-f0-9-]{36}/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$')",
            name="ck_bayesian_artifacts_internal_uri",
        ),
        CheckConstraint(
            "artifact_size_bytes >= 0", name="ck_bayesian_artifacts_size_non_negative"
        ),
        CheckConstraint(
            "lifecycle_status = 'pruned' OR artifact_size_bytes <= 65536",
            name="ck_bayesian_artifacts_size_p8_cap",
        ),
        CheckConstraint(
            "payload_byte_count >= 0 AND payload_byte_count <= 65536",
            name="ck_bayesian_artifacts_payload_byte_count_p8_cap",
        ),
        CheckConstraint(
            "payload_bytes IS NULL OR octet_length(payload_bytes) <= 65536",
            name="ck_bayesian_artifacts_payload_bytes_p8_cap",
        ),
        CheckConstraint(
            "payload_bytes IS NULL OR octet_length(payload_bytes) = payload_byte_count",
            name="ck_bayesian_artifacts_payload_byte_count_matches",
        ),
        CheckConstraint(
            "compression IS NULL OR compression IN ('none', 'gzip')",
            name="ck_bayesian_artifacts_compression",
        ),
        CheckConstraint(
            "retention_class IN ('ephemeral', 'standard', 'audit')",
            name="ck_bayesian_artifacts_retention_class",
        ),
        CheckConstraint(
            "pruned_at IS NULL OR expires_at IS NOT NULL",
            name="ck_bayesian_artifacts_pruned_requires_expiry",
        ),
        CheckConstraint(
            "lifecycle_status IN ('active', 'pruned', 'rejected')",
            name="ck_bayesian_artifacts_lifecycle_status",
        ),
        CheckConstraint(
            "(lifecycle_status = 'active' AND payload_bytes IS NOT NULL AND payload_byte_count = artifact_size_bytes AND pruned_at IS NULL) "
            "OR (lifecycle_status = 'pruned' AND payload_bytes IS NULL AND payload_byte_count = 0 AND pruned_at IS NOT NULL) "
            "OR (lifecycle_status = 'rejected' AND payload_bytes IS NULL AND payload_byte_count = 0 AND pruned_at IS NULL)",
            name="ck_bayesian_artifacts_lifecycle_payload_state",
        ),
        CheckConstraint(
            "char_length(trim(policy_version)) > 0",
            name="ck_bayesian_artifacts_policy_version_not_blank",
        ),
        CheckConstraint(
            "pruned_reason IS NULL OR pruned_reason IN ('retention_expired', 'manual_governance')",
            name="ck_bayesian_artifacts_pruned_reason",
        ),
        Index("idx_bayesian_artifacts_tenant_id", "tenant_id"),
        Index("idx_bayesian_artifacts_tenant_fit", "tenant_id", "fit_id"),
        Index(
            "idx_bayesian_artifacts_tenant_artifact_ref", "tenant_id", "artifact_ref"
        ),
        Index(
            "idx_bayesian_artifacts_tenant_artifact_hash", "tenant_id", "artifact_hash"
        ),
        {
            "info": {
                "partitioning": {
                    "strategy": "hash",
                    "key": ["tenant_id"],
                    "partitions": 16,
                }
            }
        },
    )


class BayesianArtifactStorageQuota(Base):
    """Tenant-scoped P8 artifact storage telemetry and quota row."""

    __tablename__ = "bayesian_artifact_storage_quotas"

    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    quota_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=1048576, server_default="1048576"
    )
    max_artifact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1000, server_default="1000"
    )
    active_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    pruned_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    active_artifact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    pruned_artifact_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    rejected_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_rejection_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "quota_bytes >= 0 AND active_bytes >= 0 AND pruned_bytes >= 0",
            name="ck_bayesian_artifact_storage_quotas_bytes_non_negative",
        ),
        CheckConstraint(
            "active_artifact_count >= 0 AND pruned_artifact_count >= 0 AND rejected_count >= 0",
            name="ck_bayesian_artifact_storage_quotas_counts_non_negative",
        ),
        CheckConstraint(
            "max_artifact_count > 0",
            name="ck_bayesian_artifact_storage_quotas_max_count_positive",
        ),
        CheckConstraint(
            "active_bytes <= quota_bytes",
            name="ck_bayesian_artifact_storage_quotas_active_within_quota",
        ),
        CheckConstraint(
            "active_artifact_count <= max_artifact_count",
            name="ck_bayesian_artifact_storage_quotas_active_count_within_quota",
        ),
        CheckConstraint(
            "char_length(trim(policy_version)) > 0",
            name="ck_bayesian_artifact_storage_quotas_policy_version_not_blank",
        ),
        CheckConstraint(
            "last_rejection_reason IS NULL OR last_rejection_reason IN ('tenant_quota_exceeded', 'fit_wal_budget_exceeded', 'policy_rejected')",
            name="ck_bayesian_artifact_storage_quotas_rejection_reason",
        ),
    )


class B24DirtyEvent(Base, TenantMixin):
    """Append-only B2.4-P3 dirty event emitted by deterministic hot paths."""

    __tablename__ = "b24_dirty_events"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), default=uuid4, server_default=func.gen_random_uuid()
    )
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    dirty_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    source_family: Mapped[str] = mapped_column(String(64), nullable=False)
    event_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    planner_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    leased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coalesced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suppressed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fallback_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pruned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority_retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    authority_retry_after_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority_wait_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority_reactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    authority_terminal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id", name="b24_dirty_events_pkey"),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_b24_dirty_events_source_window_order",
        ),
        CheckConstraint(
            "event_hash IS NULL OR event_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_dirty_events_event_hash_sha256",
        ),
        CheckConstraint(
            "source_snapshot_hash IS NULL OR source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_dirty_events_source_snapshot_hash_sha256",
        ),
        CheckConstraint(
            "authority_retry_count >= 0",
            name="ck_b24_dirty_events_authority_retry_count_nonnegative",
        ),
        Index(
            "idx_b24_dirty_events_tenant_status_observed",
            "tenant_id",
            "status",
            "observed_at",
            "id",
        ),
        Index(
            "idx_b24_dirty_events_tenant_model_window_pending",
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "observed_at",
            "id",
            postgresql_where=text("status IN ('pending', 'leased')"),
        ),
        Index(
            "idx_b24_dirty_events_authority_retry_ready",
            "tenant_id",
            "status",
            "authority_retry_after_at",
            "observed_at",
            "id",
            postgresql_where=text(
                "status IN ('authority_waiting', 'authority_retry_ready')"
            ),
        ),
    )


class B24ActiveExecutionLease(Base, TenantMixin):
    """Hash-independent active execution lease for one tenant/model/window."""

    __tablename__ = "b24_active_execution_leases"

    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fit_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    active_source_snapshot_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    latest_desired_source_snapshot_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="claiming", server_default="claiming"
    )
    needs_refit_after_current: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    leased_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stale_recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            name="b24_active_execution_leases_pkey",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "fit_id"],
            ["bayesian_model_fits.tenant_id", "bayesian_model_fits.id"],
            name="fk_b24_active_execution_fit",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_b24_active_execution_source_window_order",
        ),
        CheckConstraint(
            "active_source_snapshot_hash IS NULL OR active_source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_active_execution_active_hash_sha256",
        ),
        CheckConstraint(
            "latest_desired_source_snapshot_hash IS NULL OR latest_desired_source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_active_execution_desired_hash_sha256",
        ),
        CheckConstraint(
            "status IN ('profiling', 'profile_passed', 'profile_rejected', 'profile_superseded', 'profile_timeout', 'profile_failed', 'claiming', 'dispatch_pending', 'dispatched', 'running', 'cancel_requested', 'succeeded', 'failed', 'fallback_only', 'cancelled', 'stale_recovered')",
            name="ck_b24_active_execution_status",
        ),
        CheckConstraint(
            "status IN ('claiming', 'profiling', 'profile_passed', 'profile_rejected', 'profile_superseded', 'profile_timeout', 'profile_failed') OR fit_id IS NOT NULL",
            name="ck_b24_active_execution_active_fit_required",
        ),
        Index(
            "idx_b24_active_execution_tenant_status_lease",
            "tenant_id",
            "status",
            "leased_until",
        ),
        Index(
            "idx_b24_active_execution_canonical_profiling",
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "status",
            "leased_until",
            postgresql_where=text("status = 'profiling'"),
        ),
        Index(
            "idx_b24_active_execution_tenant_fit",
            "tenant_id",
            "fit_id",
            postgresql_where=text("fit_id IS NOT NULL"),
        ),
    )


class B24SourceWindowFeatureAuthority(Base, TenantMixin):
    """Snapshot-scoped B2.4-P4 feature cardinality authority."""

    __tablename__ = "b24_source_window_feature_authority"

    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_count: Mapped[int] = mapped_column(Integer, nullable=False)
    currency_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_count: Mapped[int] = mapped_column(Integer, nullable=False)
    campaign_or_feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    freshness_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="fresh", server_default="fresh"
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
            name="b24_source_window_feature_authority_pkey",
        ),
        CheckConstraint(
            "model_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_b24_feature_authority_model_type_format",
        ),
        CheckConstraint(
            "char_length(trim(model_version)) > 0",
            name="ck_b24_feature_authority_model_version_not_blank",
        ),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_b24_feature_authority_source_window_order",
        ),
        CheckConstraint(
            "source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_feature_authority_source_snapshot_hash_sha256",
        ),
        CheckConstraint(
            "channel_count >= 0",
            name="ck_b24_feature_authority_channel_count_nonnegative",
        ),
        CheckConstraint(
            "currency_count >= 0",
            name="ck_b24_feature_authority_currency_count_nonnegative",
        ),
        CheckConstraint(
            "provider_count >= 0",
            name="ck_b24_feature_authority_provider_count_nonnegative",
        ),
        CheckConstraint(
            "campaign_or_feature_count >= 0",
            name="ck_b24_feature_authority_campaign_count_nonnegative",
        ),
        CheckConstraint(
            "freshness_status IN ('fresh', 'stale', 'mismatched')",
            name="ck_b24_feature_authority_freshness_status",
        ),
        CheckConstraint(
            "char_length(trim(policy_version)) > 0",
            name="ck_b24_feature_authority_policy_version_not_blank",
        ),
        Index(
            "idx_b24_feature_authority_tenant_model_window",
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            text("computed_at DESC"),
        ),
    )


class B24FeatureAuthorityBuildRequest(Base, TenantMixin):
    """Snapshot-scoped transient request for feature-authority construction."""

    __tablename__ = "b24_feature_authority_build_requests"

    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="authority_build_requested",
        server_default="authority_build_requested",
    )
    authority_reason: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    retry_after_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminal_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    terminal_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
            name="b24_feature_authority_build_requests_pkey",
        ),
        CheckConstraint(
            "model_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_b24_feature_authority_request_model_type_format",
        ),
        CheckConstraint(
            "char_length(trim(model_version)) > 0",
            name="ck_b24_feature_authority_request_model_version_not_blank",
        ),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_b24_feature_authority_request_window_order",
        ),
        CheckConstraint(
            "source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_feature_authority_request_snapshot_hash_sha256",
        ),
        CheckConstraint(
            "status IN ("
            "'authority_build_requested', 'authority_waiting', "
            "'authority_retry_ready', 'authority_completed', "
            "'authority_timeout', 'authority_build_failed')",
            name="ck_b24_feature_authority_request_status",
        ),
        CheckConstraint(
            "authority_reason IN ("
            "'cardinality_authority_missing', "
            "'cardinality_authority_stale', "
            "'cardinality_authority_mismatch')",
            name="ck_b24_feature_authority_request_reason",
        ),
        CheckConstraint(
            "terminal_reason IS NULL OR terminal_reason IN ("
            "'cardinality_authority_timeout', "
            "'cardinality_authority_build_failed')",
            name="ck_b24_feature_authority_request_terminal_reason",
        ),
        CheckConstraint(
            "retry_count >= 0",
            name="ck_b24_feature_authority_request_retry_count",
        ),
        CheckConstraint(
            "max_retries > 0",
            name="ck_b24_feature_authority_request_max_retries",
        ),
        CheckConstraint(
            "char_length(trim(policy_version)) > 0",
            name="ck_b24_feature_authority_request_policy_version_not_blank",
        ),
        Index(
            "idx_b24_feature_authority_build_requests_due",
            "tenant_id",
            "status",
            "retry_after_at",
            postgresql_where=text(
                "status IN ("
                "'authority_build_requested', "
                "'authority_waiting', "
                "'authority_retry_ready')"
            ),
        ),
    )


class B24FeatureAuthorityBuildOutbox(Base, TenantMixin):
    """Transactional outbox for source-snapshot-scoped feature-authority builds."""

    __tablename__ = "b24_feature_authority_build_outbox"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), default=uuid4, server_default=func.gen_random_uuid()
    )
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dispatch_key: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatching_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stale_recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id", "id", name="b24_feature_authority_build_outbox_pkey"
        ),
        ForeignKeyConstraint(
            [
                "tenant_id",
                "model_type",
                "model_version",
                "source_window_start",
                "source_window_end",
                "source_snapshot_hash",
            ],
            [
                "b24_feature_authority_build_requests.tenant_id",
                "b24_feature_authority_build_requests.model_type",
                "b24_feature_authority_build_requests.model_version",
                "b24_feature_authority_build_requests.source_window_start",
                "b24_feature_authority_build_requests.source_window_end",
                "b24_feature_authority_build_requests.source_snapshot_hash",
            ],
            name="fk_b24_feature_authority_build_outbox_request",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "model_type",
            "model_version",
            "source_window_start",
            "source_window_end",
            "source_snapshot_hash",
            name="uq_b24_feature_authority_build_outbox_candidate",
        ),
        UniqueConstraint(
            "tenant_id",
            "dispatch_key",
            name="uq_b24_feature_authority_build_outbox_dispatch_key",
        ),
        CheckConstraint(
            "model_type ~ '^[a-z][a-z0-9_]{1,63}$'",
            name="ck_b24_feature_authority_build_outbox_model_type_format",
        ),
        CheckConstraint(
            "char_length(trim(model_version)) > 0",
            name="ck_b24_feature_authority_build_outbox_model_version_not_blank",
        ),
        CheckConstraint(
            "source_window_end > source_window_start",
            name="ck_b24_feature_authority_build_outbox_window_order",
        ),
        CheckConstraint(
            "source_snapshot_hash ~ '^[a-f0-9]{64}$'",
            name="ck_b24_feature_authority_build_outbox_hash_sha256",
        ),
        CheckConstraint(
            "status IN ('pending', 'dispatching', 'dispatched', 'failed_retryable', 'dead_lettered', 'stale_recovered')",
            name="ck_b24_feature_authority_build_outbox_status",
        ),
        CheckConstraint(
            "attempt_count >= 0",
            name="ck_b24_feature_authority_build_outbox_attempt_count",
        ),
        CheckConstraint(
            "max_attempts > 0",
            name="ck_b24_feature_authority_build_outbox_max_attempts",
        ),
        Index(
            "idx_b24_feature_authority_build_outbox_due",
            "tenant_id",
            "status",
            "next_attempt_at",
            "id",
            postgresql_where=text(
                "status IN ('pending', 'failed_retryable', 'stale_recovered')"
            ),
        ),
    )


class B24FitDispatchOutbox(Base, TenantMixin):
    """Durable dispatch intent committed atomically with a fit claim."""

    __tablename__ = "b24_fit_dispatch_outbox"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), default=uuid4, server_default=func.gen_random_uuid()
    )
    fit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    dispatch_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatching_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dead_lettered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    stale_recovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_name: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        default="app.tasks.bayesian.execute_fit_intent",
        server_default="app.tasks.bayesian.execute_fit_intent",
    )
    attempt_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, default=uuid4
    )
    payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_capability: Mapped[str | None] = mapped_column(String(128), nullable=True)
    claim_capability_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    claim_capability_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_capability_digest: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    lease_acquired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_epoch: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    claim_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    redelivery_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    recovery_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    superseded_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    terminal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_recovery_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id", name="b24_fit_dispatch_outbox_pkey"),
        ForeignKeyConstraint(
            ["tenant_id", "fit_id"],
            ["bayesian_model_fits.tenant_id", "bayesian_model_fits.id"],
            name="fk_b24_fit_dispatch_outbox_fit",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "tenant_id", "dispatch_key", name="uq_b24_fit_dispatch_outbox_dispatch_key"
        ),
        UniqueConstraint("tenant_id", "fit_id", name="uq_b24_fit_dispatch_outbox_fit"),
        CheckConstraint(
            "attempt_count >= 0", name="ck_b24_fit_dispatch_outbox_attempt_count"
        ),
        CheckConstraint(
            "max_attempts > 0", name="ck_b24_fit_dispatch_outbox_max_attempts"
        ),
        UniqueConstraint(
            "tenant_id", "attempt_id", name="uq_b24_fit_dispatch_outbox_attempt"
        ),
        Index(
            "idx_b24_fit_dispatch_outbox_due",
            "tenant_id",
            "status",
            "next_attempt_at",
            "id",
            postgresql_where=text(
                "status IN ('pending', 'failed_retryable', 'stale_recovered')"
            ),
        ),
        Index(
            "idx_b24_fit_dispatch_outbox_dispatching",
            "tenant_id",
            "dispatching_started_at",
            postgresql_where=text("status = 'dispatching'"),
        ),
    )


class B24FitRecoveryOutbox(Base, TenantMixin):
    """Durable wake-up repair intent for broker loss or stale execution leases."""

    __tablename__ = "b24_fit_recovery_outbox"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), default=uuid4, server_default=func.gen_random_uuid()
    )
    dispatch_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    fit_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    task_name: Mapped[str] = mapped_column(String(256), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    claim_capability: Mapped[str] = mapped_column(String(128), nullable=False)
    recovery_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", server_default="pending"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    publish_attempt_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "id", name="b24_fit_recovery_outbox_pkey"),
        ForeignKeyConstraint(
            ["tenant_id", "dispatch_id"],
            ["b24_fit_dispatch_outbox.tenant_id", "b24_fit_dispatch_outbox.id"],
            name="fk_b24_fit_recovery_outbox_dispatch",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id",
            "dispatch_id",
            "recovery_generation",
            name="uq_b24_fit_recovery_outbox_generation",
        ),
        CheckConstraint(
            "status IN ('pending', 'publishing', 'published', 'failed_retryable', 'quarantined')",
            name="ck_b24_fit_recovery_outbox_status",
        ),
        CheckConstraint(
            "publish_attempt_count >= 0",
            name="ck_b24_fit_recovery_outbox_publish_attempt_count",
        ),
    )
