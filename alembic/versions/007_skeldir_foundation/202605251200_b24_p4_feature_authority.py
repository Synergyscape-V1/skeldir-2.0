"""Add B2.4-P4 snapshot feature authority.

Revision ID: 202605251200
Revises: 202605241430
Create Date: 2026-05-25 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605251200"
down_revision: Union[str, None] = "202605241430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

P4_FEATURE_AUTHORITY_FALLBACK_REASONS = (
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

P4_RESOURCE_FALLBACK_REASONS = tuple(
    reason
    for reason in P4_FEATURE_AUTHORITY_FALLBACK_REASONS
    if reason
    not in {
        "cardinality_authority_missing",
        "cardinality_authority_stale",
        "cardinality_authority_mismatch",
        "source_profile_unavailable",
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
    _replace_fallback_constraint(P4_FEATURE_AUTHORITY_FALLBACK_REASONS)
    op.execute(
        """
        CREATE TABLE public.b24_source_window_feature_authority (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            source_snapshot_hash character varying(64) NOT NULL,
            channel_count integer NOT NULL,
            currency_count integer NOT NULL,
            provider_count integer NOT NULL,
            campaign_or_feature_count integer NOT NULL,
            freshness_status character varying(32) DEFAULT 'fresh' NOT NULL,
            policy_version character varying(64) NOT NULL,
            computed_at timestamp with time zone DEFAULT now() NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_source_window_feature_authority_pkey PRIMARY KEY (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ),
            CONSTRAINT ck_b24_feature_authority_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_feature_authority_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_feature_authority_source_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_feature_authority_source_snapshot_hash_sha256
                CHECK (source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_feature_authority_channel_count_nonnegative
                CHECK (channel_count >= 0),
            CONSTRAINT ck_b24_feature_authority_currency_count_nonnegative
                CHECK (currency_count >= 0),
            CONSTRAINT ck_b24_feature_authority_provider_count_nonnegative
                CHECK (provider_count >= 0),
            CONSTRAINT ck_b24_feature_authority_campaign_count_nonnegative
                CHECK (campaign_or_feature_count >= 0),
            CONSTRAINT ck_b24_feature_authority_freshness_status
                CHECK (freshness_status IN ('fresh', 'stale', 'mismatched')),
            CONSTRAINT ck_b24_feature_authority_policy_version_not_blank
                CHECK (char_length(trim(policy_version)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_feature_authority_tenant_model_window
            ON public.b24_source_window_feature_authority (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                computed_at DESC
            )
        """
    )
    op.execute(
        "ALTER TABLE public.b24_source_window_feature_authority ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b24_source_window_feature_authority FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b24_source_window_feature_authority
            ON public.b24_source_window_feature_authority
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_source_window_feature_authority TO app_user",
    )
    _grant_if_role_exists(
        "app_worker",
        "GRANT SELECT, INSERT, UPDATE ON public.b24_source_window_feature_authority TO app_worker",
    )
    _revoke_if_role_exists(
        "app_readonly",
        "REVOKE INSERT, UPDATE, DELETE ON public.b24_source_window_feature_authority FROM app_readonly",
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.b24_source_window_feature_authority")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 feature authority.
    _replace_fallback_constraint(P4_RESOURCE_FALLBACK_REASONS)
