"""B2.4-P1 evolvable state taxonomies.

The database representation for these values is VARCHAR plus CHECK constraints,
not native PostgreSQL ENUM, so later B2.4 phases can add states through normal
constraint migrations.
"""

from __future__ import annotations

from enum import StrEnum


class FitStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"
    WORKER_LOST = "worker_lost"
    FALLBACK_ONLY = "fallback_only"
    CANCELLED = "cancelled"


class EligibilityStatus(StrEnum):
    UNKNOWN = "unknown"
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    FALLBACK_ONLY = "fallback_only"


class DataCompletenessStatus(StrEnum):
    UNKNOWN = "unknown"
    COMPLETE = "complete"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"
    STALE = "stale"


class FallbackReason(StrEnum):
    SOURCE_WINDOW_EMPTY = "source_window_empty"
    INSUFFICIENT_DATA = "insufficient_data"
    INSUFFICIENT_PRIVACY_COHORT = "insufficient_privacy_cohort"
    INPUT_TOO_LARGE = "input_too_large"
    FEATURE_WIDTH_EXCEEDED = "feature_width_exceeded"
    SOURCE_WINDOW_TOO_LARGE = "source_window_too_large"
    MEMORY_BOUND_EXCEEDED = "memory_bound_exceeded"
    GRAPH_COMPLEXITY_EXCEEDED = "graph_complexity_exceeded"
    PARAMETER_COUNT_EXCEEDED = "parameter_count_exceeded"
    HIERARCHY_WIDTH_EXCEEDED = "hierarchy_width_exceeded"
    COMPILATION_MEMORY_BOUND_EXCEEDED = "compilation_memory_bound_exceeded"
    CARDINALITY_AUTHORITY_MISSING = "cardinality_authority_missing"
    CARDINALITY_AUTHORITY_STALE = "cardinality_authority_stale"
    CARDINALITY_AUTHORITY_MISMATCH = "cardinality_authority_mismatch"
    CARDINALITY_AUTHORITY_TIMEOUT = "cardinality_authority_timeout"
    CARDINALITY_AUTHORITY_BUILD_FAILED = "cardinality_authority_build_failed"
    SOURCE_PROFILE_UNAVAILABLE = "source_profile_unavailable"
    TIMEOUT = "timeout"
    WORKER_FAILURE = "worker_failure"
    NO_CONVERGENCE = "no_convergence"
    RESOURCE_BOUND_EXCEEDED = "resource_bound_exceeded"
    SOURCE_UNAVAILABLE = "source_unavailable"
    DUPLICATE_FIT_SUPPRESSED = "duplicate_fit_suppressed"
    ARTIFACT_UNAVAILABLE = "artifact_unavailable"
    STORAGE_QUOTA_EXCEEDED = "storage_quota_exceeded"


class CredibleIntervalStatus(StrEnum):
    NOT_AVAILABLE = "not_available"
    AVAILABLE = "available"
    SUPPRESSED = "suppressed"
    INVALID = "invalid"
    PENDING = "pending"


class ConfidenceBucket(StrEnum):
    UNAVAILABLE = "unavailable"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    FALLBACK = "fallback"
    NEEDS_REVIEW = "needs_review"


class ArtifactType(StrEnum):
    POSTERIOR_TRACE = "posterior_trace"
    DIAGNOSTICS = "diagnostics"
    SUMMARY = "summary"
    SOURCE_MANIFEST = "source_manifest"
    FIT_METADATA = "fit_metadata"


class StorageBackend(StrEnum):
    POSTGRES = "postgres"
    OBJECT_STORAGE = "object_storage"
    LOCAL_FS = "local_fs"


class Compression(StrEnum):
    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"


class RetentionClass(StrEnum):
    EPHEMERAL = "ephemeral"
    STANDARD = "standard"
    AUDIT = "audit"
