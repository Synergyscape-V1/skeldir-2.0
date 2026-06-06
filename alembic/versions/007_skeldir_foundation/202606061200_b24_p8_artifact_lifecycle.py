"""B2.4-P8 artifact persistence, lifecycle, and storage governance.

Revision ID: 202606061200
Revises: 202606041200
Create Date: 2026-06-06 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606061200"
down_revision: Union[str, None] = "202606041200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    op.execute(
        "ALTER TABLE public.bayesian_artifacts ADD COLUMN IF NOT EXISTS payload_json jsonb"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts ADD COLUMN IF NOT EXISTS payload_bytes bytea"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "ADD COLUMN IF NOT EXISTS payload_byte_count bigint DEFAULT 0 NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "ADD COLUMN IF NOT EXISTS lifecycle_status character varying(32) DEFAULT 'active' NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "ADD COLUMN IF NOT EXISTS policy_version character varying(64) DEFAULT 'b24-p8-artifact-policy-v1' NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts ADD COLUMN IF NOT EXISTS pruned_reason character varying(64)"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "ADD COLUMN IF NOT EXISTS pruned_metadata jsonb DEFAULT '{}'::jsonb NOT NULL"
    )
    op.execute(
        "ALTER TABLE public.bayesian_artifacts "
        "ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone DEFAULT now() NOT NULL"
    )

    op.execute(
        """
        UPDATE public.bayesian_artifacts
        SET payload_byte_count = CASE
                WHEN payload_bytes IS NULL THEN 0
                WHEN octet_length(payload_bytes) <> artifact_size_bytes THEN 0
                WHEN artifact_size_bytes > 65536 THEN 0
                WHEN storage_backend <> 'postgres' THEN 0
                WHEN artifact_type NOT IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN 0
                WHEN artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$' THEN 0
                ELSE LEAST(artifact_size_bytes, 65536)
            END,
            payload_bytes = CASE
                WHEN payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes THEN NULL
                WHEN artifact_size_bytes > 65536 THEN NULL
                WHEN artifact_size_bytes = 0
                    AND pruned_at IS NULL
                    AND storage_backend = 'postgres'
                    AND artifact_type IN (
                        'diagnostics',
                        'summary',
                        'source_manifest',
                        'fit_metadata',
                        'input_manifest',
                        'model_spec',
                        'posterior_summary'
                    )
                    AND artifact_ref ~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'
                    THEN ''::bytea
                ELSE payload_bytes
            END,
            lifecycle_status = CASE
                WHEN payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes THEN 'pruned'
                WHEN artifact_size_bytes > 65536 THEN 'pruned'
                WHEN storage_backend <> 'postgres' THEN 'pruned'
                WHEN artifact_type NOT IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN 'pruned'
                WHEN artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$' THEN 'pruned'
                WHEN payload_bytes IS NULL AND artifact_size_bytes > 0 THEN 'pruned'
                WHEN pruned_at IS NULL THEN 'active'
                ELSE 'pruned'
            END,
            expires_at = CASE
                WHEN payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes THEN COALESCE(expires_at, now())
                WHEN artifact_size_bytes > 65536 THEN COALESCE(expires_at, now())
                WHEN storage_backend <> 'postgres' THEN COALESCE(expires_at, now())
                WHEN artifact_type NOT IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN COALESCE(expires_at, now())
                WHEN artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$' THEN COALESCE(expires_at, now())
                WHEN payload_bytes IS NULL AND artifact_size_bytes > 0 THEN COALESCE(expires_at, now())
                ELSE expires_at
            END,
            pruned_at = CASE
                WHEN payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes THEN COALESCE(pruned_at, now())
                WHEN artifact_size_bytes > 65536 THEN COALESCE(pruned_at, now())
                WHEN storage_backend <> 'postgres' THEN COALESCE(pruned_at, now())
                WHEN artifact_type NOT IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN COALESCE(pruned_at, now())
                WHEN artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$' THEN COALESCE(pruned_at, now())
                WHEN payload_bytes IS NULL AND artifact_size_bytes > 0 THEN COALESCE(pruned_at, now())
                ELSE pruned_at
            END,
            pruned_reason = CASE
                WHEN payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes THEN COALESCE(pruned_reason, 'manual_governance')
                WHEN artifact_size_bytes > 65536 THEN COALESCE(pruned_reason, 'manual_governance')
                WHEN storage_backend <> 'postgres' THEN COALESCE(pruned_reason, 'manual_governance')
                WHEN artifact_type NOT IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN COALESCE(pruned_reason, 'manual_governance')
                WHEN artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$' THEN COALESCE(pruned_reason, 'manual_governance')
                WHEN payload_bytes IS NULL AND artifact_size_bytes > 0 THEN COALESCE(pruned_reason, 'manual_governance')
                ELSE pruned_reason
            END,
            pruned_metadata = CASE
                WHEN (payload_bytes IS NOT NULL AND octet_length(payload_bytes) <> artifact_size_bytes)
                    OR artifact_size_bytes > 65536
                    OR storage_backend <> 'postgres'
                    OR artifact_type NOT IN (
                        'diagnostics',
                        'summary',
                        'source_manifest',
                        'fit_metadata',
                        'input_manifest',
                        'model_spec',
                        'posterior_summary'
                    )
                    OR artifact_ref !~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'
                    OR (payload_bytes IS NULL AND artifact_size_bytes > 0)
                    THEN jsonb_build_object(
                    'artifact_ref', artifact_ref,
                    'artifact_hash', artifact_hash,
                    'artifact_type', artifact_type,
                    'storage_backend', storage_backend,
                    'artifact_size_bytes', artifact_size_bytes,
                    'policy_version', 'b24-p8-artifact-policy-v1',
                    'legacy_payload_absent', true
                )
                ELSE pruned_metadata
            END,
            storage_backend = 'postgres',
            artifact_type = CASE
                WHEN artifact_type IN (
                    'diagnostics',
                    'summary',
                    'source_manifest',
                    'fit_metadata',
                    'input_manifest',
                    'model_spec',
                    'posterior_summary'
                ) THEN artifact_type
                ELSE 'summary'
            END,
            artifact_uri_internal = artifact_ref,
            policy_version = 'b24-p8-artifact-policy-v1',
            updated_at = COALESCE(created_at, now())
        WHERE policy_version IS NULL
           OR payload_byte_count IS NULL
           OR lifecycle_status IS NULL
           OR payload_bytes IS NULL
        """
    )

    for constraint_name in (
        "ck_bayesian_artifacts_artifact_type",
        "ck_bayesian_artifacts_storage_backend",
        "ck_bayesian_artifacts_uri_not_blank",
        "ck_bayesian_artifacts_compression",
        "ck_bayesian_artifacts_size_non_negative",
        "ck_bayesian_artifacts_pruned_requires_expiry",
    ):
        op.execute(
            f"ALTER TABLE public.bayesian_artifacts DROP CONSTRAINT IF EXISTS {constraint_name}"
        )

    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_artifact_type
        CHECK (
            artifact_type IN (
                'diagnostics',
                'summary',
                'source_manifest',
                'fit_metadata',
                'input_manifest',
                'model_spec',
                'posterior_summary'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_storage_backend
        CHECK (storage_backend = 'postgres')
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_internal_uri
        CHECK (
            lifecycle_status = 'pruned'
            OR (
                artifact_uri_internal = artifact_ref
                AND artifact_uri_internal ~ '^b24://artifact/[a-f0-9-]{36}/[a-z0-9_]{3,32}/[a-f0-9]{12}$'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_size_non_negative
        CHECK (artifact_size_bytes >= 0)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_size_p8_cap
        CHECK (lifecycle_status = 'pruned' OR artifact_size_bytes <= 65536)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_payload_byte_count_p8_cap
        CHECK (payload_byte_count >= 0 AND payload_byte_count <= 65536)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_payload_bytes_p8_cap
        CHECK (payload_bytes IS NULL OR octet_length(payload_bytes) <= 65536)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_payload_byte_count_matches
        CHECK (payload_bytes IS NULL OR octet_length(payload_bytes) = payload_byte_count)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_compression
        CHECK (compression IS NULL OR compression IN ('none', 'gzip'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry
        CHECK (pruned_at IS NULL OR expires_at IS NOT NULL)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_status
        CHECK (lifecycle_status IN ('active', 'pruned'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_lifecycle_payload_state
        CHECK (
            (
                lifecycle_status = 'active'
                AND payload_bytes IS NOT NULL
                AND payload_byte_count = artifact_size_bytes
                AND pruned_at IS NULL
            )
            OR (
                lifecycle_status = 'pruned'
                AND payload_bytes IS NULL
                AND payload_byte_count = 0
                AND pruned_at IS NOT NULL
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_policy_version_not_blank
        CHECK (char_length(trim(policy_version)) > 0)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_pruned_reason
        CHECK (
            pruned_reason IS NULL
            OR pruned_reason IN ('retention_expired', 'manual_governance')
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.bayesian_artifact_storage_quotas (
            tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
            policy_version character varying(64) NOT NULL,
            quota_bytes bigint DEFAULT 1048576 NOT NULL,
            active_bytes bigint DEFAULT 0 NOT NULL,
            pruned_bytes bigint DEFAULT 0 NOT NULL,
            active_artifact_count integer DEFAULT 0 NOT NULL,
            pruned_artifact_count integer DEFAULT 0 NOT NULL,
            rejected_count integer DEFAULT 0 NOT NULL,
            last_rejection_reason character varying(64),
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT ck_bayesian_artifact_storage_quotas_bytes_non_negative
                CHECK (quota_bytes >= 0 AND active_bytes >= 0 AND pruned_bytes >= 0),
            CONSTRAINT ck_bayesian_artifact_storage_quotas_counts_non_negative
                CHECK (
                    active_artifact_count >= 0
                    AND pruned_artifact_count >= 0
                    AND rejected_count >= 0
                ),
            CONSTRAINT ck_bayesian_artifact_storage_quotas_active_within_quota
                CHECK (active_bytes <= quota_bytes),
            CONSTRAINT ck_bayesian_artifact_storage_quotas_policy_version_not_blank
                CHECK (char_length(trim(policy_version)) > 0),
            CONSTRAINT ck_bayesian_artifact_storage_quotas_rejection_reason
                CHECK (
                    last_rejection_reason IS NULL
                    OR last_rejection_reason IN (
                        'tenant_quota_exceeded',
                        'fit_wal_budget_exceeded',
                        'policy_rejected'
                    )
                )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifact_storage_quotas
        ENABLE ROW LEVEL SECURITY
        """
    )
    op.execute(
        """
        ALTER TABLE ONLY public.bayesian_artifact_storage_quotas
        FORCE ROW LEVEL SECURITY
        """
    )
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_policy_bayesian_artifact_storage_quotas
        ON public.bayesian_artifact_storage_quotas
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_bayesian_artifact_storage_quotas
        ON public.bayesian_artifact_storage_quotas
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    for role in ("app_user", "app_rw"):
        _grant_if_role_exists(
            role,
            f"GRANT SELECT, INSERT, UPDATE ON TABLE public.bayesian_artifact_storage_quotas TO {role}",
        )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.bayesian_artifact_storage_quotas TO app_ro",
    )


def downgrade() -> None:
    for role in ("app_ro", "app_rw", "app_user"):
        _revoke_if_role_exists(
            role,
            f"REVOKE ALL ON TABLE public.bayesian_artifact_storage_quotas FROM {role}",
        )
    op.execute("DROP TABLE IF EXISTS public.bayesian_artifact_storage_quotas")
    for constraint_name in (
        "ck_bayesian_artifacts_pruned_reason",
        "ck_bayesian_artifacts_policy_version_not_blank",
        "ck_bayesian_artifacts_lifecycle_payload_state",
        "ck_bayesian_artifacts_lifecycle_status",
        "ck_bayesian_artifacts_payload_byte_count_matches",
        "ck_bayesian_artifacts_payload_bytes_p8_cap",
        "ck_bayesian_artifacts_payload_byte_count_p8_cap",
        "ck_bayesian_artifacts_size_p8_cap",
        "ck_bayesian_artifacts_internal_uri",
        "ck_bayesian_artifacts_storage_backend",
        "ck_bayesian_artifacts_artifact_type",
        "ck_bayesian_artifacts_compression",
        "ck_bayesian_artifacts_size_non_negative",
        "ck_bayesian_artifacts_pruned_requires_expiry",
    ):
        op.execute(
            f"ALTER TABLE public.bayesian_artifacts DROP CONSTRAINT IF EXISTS {constraint_name}"
        )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_artifact_type
        CHECK (artifact_type IN ('posterior_trace', 'diagnostics', 'summary', 'source_manifest', 'fit_metadata'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_storage_backend
        CHECK (storage_backend IN ('postgres', 'object_storage', 'local_fs'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_uri_not_blank
        CHECK (char_length(trim(artifact_uri_internal)) > 0)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_size_non_negative
        CHECK (artifact_size_bytes >= 0)
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_compression
        CHECK (compression IS NULL OR compression IN ('none', 'gzip', 'zstd'))
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_artifacts
        ADD CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry
        CHECK (pruned_at IS NULL OR expires_at IS NOT NULL)
        """
    )
    for column in (
        "updated_at",
        "pruned_metadata",
        "pruned_reason",
        "policy_version",
        "lifecycle_status",
        "payload_byte_count",
        "payload_bytes",
        "payload_json",
    ):
        op.execute(
            f"ALTER TABLE public.bayesian_artifacts DROP COLUMN IF EXISTS {column}"
        )
