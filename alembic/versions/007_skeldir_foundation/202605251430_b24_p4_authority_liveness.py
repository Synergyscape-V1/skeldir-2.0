"""Add B2.4-P4 transient feature-authority liveness.

Revision ID: 202605251430
Revises: 202605251200
Create Date: 2026-05-25 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605251430"
down_revision: Union[str, None] = "202605251200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


P4_AUTHORITY_LIVENESS_FALLBACK_REASONS = (
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
    "input_too_large",
    "feature_width_exceeded",
    "source_window_too_large",
    "memory_bound_exceeded",
    "graph_complexity_exceeded",
    "parameter_count_exceeded",
    "hierarchy_width_exceeded",
    "compilation_memory_bound_exceeded",
    "cardinality_authority_missing",
    "cardinality_authority_stale",
    "cardinality_authority_mismatch",
    "cardinality_authority_timeout",
    "cardinality_authority_build_failed",
    "source_profile_unavailable",
    "timeout",
    "worker_failure",
    "no_convergence",
    "resource_bound_exceeded",
    "source_unavailable",
    "duplicate_fit_suppressed",
    "artifact_unavailable",
    "storage_quota_exceeded",
)

P4_FEATURE_AUTHORITY_FALLBACK_REASONS = tuple(
    reason
    for reason in P4_AUTHORITY_LIVENESS_FALLBACK_REASONS
    if reason
    not in {
        "cardinality_authority_timeout",
        "cardinality_authority_build_failed",
    }
)


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def _replace_fallback_constraint(values: tuple[str, ...]) -> None:
    op.execute(
        "ALTER TABLE public.bayesian_model_fits "
        "DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_fallback_reason"
    )
    op.execute(
        f"""
        ALTER TABLE public.bayesian_model_fits
        ADD CONSTRAINT ck_bayesian_model_fits_fallback_reason
        CHECK (
            fallback_reason IS NULL
            OR fallback_reason IN ({_quoted(values)})
        )
        """
    )


def _replace_dirty_status_constraint(values: tuple[str, ...]) -> None:
    op.execute(
        "ALTER TABLE public.b24_dirty_events "
        "DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_status"
    )
    op.execute(
        f"""
        ALTER TABLE public.b24_dirty_events
        ADD CONSTRAINT ck_b24_dirty_events_status
        CHECK (status IN ({_quoted(values)}))
        """
    )


def _grant_if_role_exists(role: str, grant_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{grant_sql}';
            END IF;
        END
        $$;
        """
    )


def _revoke_if_role_exists(role: str, revoke_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{revoke_sql}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    _replace_fallback_constraint(P4_AUTHORITY_LIVENESS_FALLBACK_REASONS)
    _replace_dirty_status_constraint(
        (
            "pending",
            "leased",
            "coalesced",
            "claimed",
            "suppressed",
            "fallback_only",
            "superseded",
            "dispatched",
            "authority_waiting",
            "authority_retry_ready",
            "authority_timeout",
            "authority_build_failed",
            "pruned",
        )
    )
    op.execute(
        """
        ALTER TABLE public.b24_dirty_events
            ADD COLUMN IF NOT EXISTS source_snapshot_hash character varying(64),
            ADD COLUMN IF NOT EXISTS authority_retry_count integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS authority_retry_after_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS authority_wait_started_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS authority_reactivated_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS authority_terminal_at timestamp with time zone
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_dirty_events
        DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_source_snapshot_hash_sha256
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_dirty_events
        ADD CONSTRAINT ck_b24_dirty_events_source_snapshot_hash_sha256
        CHECK (source_snapshot_hash IS NULL OR source_snapshot_hash ~ '^[a-f0-9]{64}$')
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_dirty_events
        DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_authority_retry_count_nonnegative
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_dirty_events
        ADD CONSTRAINT ck_b24_dirty_events_authority_retry_count_nonnegative
        CHECK (authority_retry_count >= 0)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_dirty_events_authority_retry_ready
            ON public.b24_dirty_events (
                tenant_id,
                status,
                authority_retry_after_at ASC,
                observed_at ASC,
                id ASC
            )
            WHERE status IN ('authority_waiting', 'authority_retry_ready')
        """
    )
    op.execute(
        """
        CREATE TABLE public.b24_feature_authority_build_requests (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            source_snapshot_hash character varying(64) NOT NULL,
            status character varying(32) DEFAULT 'authority_build_requested' NOT NULL,
            authority_reason character varying(64) NOT NULL,
            detail text,
            retry_count integer DEFAULT 0 NOT NULL,
            max_retries integer DEFAULT 5 NOT NULL,
            retry_after_at timestamp with time zone,
            requested_at timestamp with time zone DEFAULT now() NOT NULL,
            completed_at timestamp with time zone,
            terminal_reason character varying(64),
            terminal_at timestamp with time zone,
            policy_version character varying(64) NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_feature_authority_build_requests_pkey PRIMARY KEY (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ),
            CONSTRAINT ck_b24_feature_authority_request_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_feature_authority_request_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_feature_authority_request_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_feature_authority_request_snapshot_hash_sha256
                CHECK (source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_feature_authority_request_status
                CHECK (status IN (
                    'authority_build_requested',
                    'authority_waiting',
                    'authority_retry_ready',
                    'authority_completed',
                    'authority_timeout',
                    'authority_build_failed'
                )),
            CONSTRAINT ck_b24_feature_authority_request_reason
                CHECK (authority_reason IN (
                    'cardinality_authority_missing',
                    'cardinality_authority_stale',
                    'cardinality_authority_mismatch'
                )),
            CONSTRAINT ck_b24_feature_authority_request_terminal_reason
                CHECK (
                    terminal_reason IS NULL
                    OR terminal_reason IN (
                        'cardinality_authority_timeout',
                        'cardinality_authority_build_failed'
                    )
                ),
            CONSTRAINT ck_b24_feature_authority_request_retry_count
                CHECK (retry_count >= 0),
            CONSTRAINT ck_b24_feature_authority_request_max_retries
                CHECK (max_retries > 0),
            CONSTRAINT ck_b24_feature_authority_request_policy_version_not_blank
                CHECK (char_length(trim(policy_version)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_feature_authority_build_requests_due
            ON public.b24_feature_authority_build_requests (
                tenant_id,
                status,
                retry_after_at ASC
            )
            WHERE status IN (
                'authority_build_requested',
                'authority_waiting',
                'authority_retry_ready'
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_feature_authority_build_requests
            ENABLE ROW LEVEL SECURITY
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_feature_authority_build_requests
            FORCE ROW LEVEL SECURITY
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b24_feature_authority_build_requests
            ON public.b24_feature_authority_build_requests
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_feature_authority_build_requests TO app_user",
    )
    _grant_if_role_exists(
        "app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_feature_authority_build_requests TO app_worker",
    )
    _revoke_if_role_exists(
        "app_readonly",
        "REVOKE INSERT, UPDATE, DELETE ON public.b24_feature_authority_build_requests FROM app_readonly",
    )


def downgrade() -> None:
    # fmt: off
    op.execute("DROP TABLE IF EXISTS public.b24_feature_authority_build_requests")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 authority liveness requests.
    op.execute("DROP INDEX IF EXISTS public.idx_b24_dirty_events_authority_retry_ready")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 authority liveness index.
    op.execute("ALTER TABLE public.b24_dirty_events DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_authority_retry_count_nonnegative")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness constraint.
    op.execute("ALTER TABLE public.b24_dirty_events DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_source_snapshot_hash_sha256")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness constraint.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS authority_terminal_at")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS authority_reactivated_at")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS authority_wait_started_at")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS authority_retry_after_at")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS authority_retry_count")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    op.execute("ALTER TABLE public.b24_dirty_events DROP COLUMN IF EXISTS source_snapshot_hash")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 dirty-event liveness column.
    # fmt: on
    _replace_dirty_status_constraint(
        (
            "pending",
            "leased",
            "coalesced",
            "claimed",
            "suppressed",
            "fallback_only",
            "superseded",
            "dispatched",
            "pruned",
        )
    )
    _replace_fallback_constraint(P4_FEATURE_AUTHORITY_FALLBACK_REASONS)
