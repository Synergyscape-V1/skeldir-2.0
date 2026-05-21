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
    PrimaryKeyConstraint,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin


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
    source_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", server_default="pending")
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
    sampling_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_eligibility_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_fit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    runtime_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_runtime_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=60, server_default="60")
    max_samples: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_cores: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    n_chains: Mapped[int | None] = mapped_column(Integer, nullable=True)
    n_samples_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    r_hat_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    ess_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    divergence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    credible_interval_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_available",
        server_default="not_available",
    )
    confidence_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confidence_bucket_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence_policy_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
        CheckConstraint("model_type ~ '^[a-z][a-z0-9_]{1,63}$'", name="ck_bayesian_model_fits_model_type_format"),
        CheckConstraint("char_length(trim(model_version)) > 0", name="ck_bayesian_model_fits_model_version_not_blank"),
        CheckConstraint("source_window_end > source_window_start", name="ck_bayesian_model_fits_source_window_order"),
        CheckConstraint("source_snapshot_hash ~ '^[a-f0-9]{64}$'", name="ck_bayesian_model_fits_source_snapshot_hash_sha256"),
        CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'fallback_only', 'cancelled')",
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
        CheckConstraint("runtime_seconds IS NULL OR runtime_seconds >= 0", name="ck_bayesian_model_fits_runtime_seconds_non_negative"),
        CheckConstraint("max_runtime_seconds >= 0", name="ck_bayesian_model_fits_max_runtime_seconds_non_negative"),
        CheckConstraint("max_samples >= 0", name="ck_bayesian_model_fits_max_samples_non_negative"),
        CheckConstraint("max_cores >= 0", name="ck_bayesian_model_fits_max_cores_non_negative"),
        CheckConstraint("n_chains IS NULL OR n_chains >= 0", name="ck_bayesian_model_fits_n_chains_non_negative"),
        CheckConstraint("n_samples_actual IS NULL OR n_samples_actual >= 0", name="ck_bayesian_model_fits_n_samples_actual_non_negative"),
        CheckConstraint("r_hat_max IS NULL OR r_hat_max > 0", name="ck_bayesian_model_fits_r_hat_max_positive"),
        CheckConstraint("ess_min IS NULL OR ess_min >= 0", name="ck_bayesian_model_fits_ess_min_non_negative"),
        CheckConstraint("divergence_count IS NULL OR divergence_count >= 0", name="ck_bayesian_model_fits_divergence_count_non_negative"),
        CheckConstraint(
            "credible_interval_status IN ('not_available', 'available', 'suppressed', 'invalid', 'pending')",
            name="ck_bayesian_model_fits_credible_interval_status",
        ),
        CheckConstraint(
            "confidence_bucket IS NULL OR confidence_bucket IN ('unavailable', 'low', 'medium', 'high', 'fallback', 'needs_review')",
            name="ck_bayesian_model_fits_confidence_bucket",
        ),
        CheckConstraint("artifact_ref IS NULL OR artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'", name="ck_bayesian_model_fits_artifact_ref_format"),
        CheckConstraint("artifact_hash IS NULL OR artifact_hash ~ '^[a-f0-9]{64}$'", name="ck_bayesian_model_fits_artifact_hash_sha256"),
        CheckConstraint(
            "(artifact_ref IS NULL AND artifact_hash IS NULL) OR (artifact_ref IS NOT NULL AND artifact_hash IS NOT NULL)",
            name="ck_bayesian_model_fits_artifact_ref_hash_pair",
        ),
        Index("idx_bayesian_model_fits_tenant_id", "tenant_id"),
        Index("idx_bayesian_model_fits_tenant_model_window", "tenant_id", "model_type", "source_window_start", "source_window_end"),
        Index("idx_bayesian_model_fits_tenant_source_snapshot_hash", "tenant_id", "source_snapshot_hash"),
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
                "partitioning": {"strategy": "hash", "key": ["tenant_id"], "partitions": 16},
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
    compression: Mapped[str | None] = mapped_column(String(32), nullable=True)
    retention_class: Mapped[str] = mapped_column(String(32), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pruned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=func.now(),
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
        UniqueConstraint("tenant_id", "artifact_ref", name="uq_bayesian_artifacts_tenant_artifact_ref"),
        CheckConstraint("artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{1,240}$'", name="ck_bayesian_artifacts_artifact_ref_format"),
        CheckConstraint("artifact_hash ~ '^[a-f0-9]{64}$'", name="ck_bayesian_artifacts_artifact_hash_sha256"),
        CheckConstraint(
            "artifact_type IN ('posterior_trace', 'diagnostics', 'summary', 'source_manifest', 'fit_metadata')",
            name="ck_bayesian_artifacts_artifact_type",
        ),
        CheckConstraint(
            "storage_backend IN ('postgres', 'object_storage', 'local_fs')",
            name="ck_bayesian_artifacts_storage_backend",
        ),
        CheckConstraint("char_length(trim(artifact_uri_internal)) > 0", name="ck_bayesian_artifacts_uri_not_blank"),
        CheckConstraint("artifact_size_bytes >= 0", name="ck_bayesian_artifacts_size_non_negative"),
        CheckConstraint("compression IS NULL OR compression IN ('none', 'gzip', 'zstd')", name="ck_bayesian_artifacts_compression"),
        CheckConstraint("retention_class IN ('ephemeral', 'standard', 'audit')", name="ck_bayesian_artifacts_retention_class"),
        CheckConstraint("pruned_at IS NULL OR expires_at IS NOT NULL", name="ck_bayesian_artifacts_pruned_requires_expiry"),
        Index("idx_bayesian_artifacts_tenant_id", "tenant_id"),
        Index("idx_bayesian_artifacts_tenant_fit", "tenant_id", "fit_id"),
        Index("idx_bayesian_artifacts_tenant_artifact_ref", "tenant_id", "artifact_ref"),
        Index("idx_bayesian_artifacts_tenant_artifact_hash", "tenant_id", "artifact_hash"),
        {"info": {"partitioning": {"strategy": "hash", "key": ["tenant_id"], "partitions": 16}}},
    )
