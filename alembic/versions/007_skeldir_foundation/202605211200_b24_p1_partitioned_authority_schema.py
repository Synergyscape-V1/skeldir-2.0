"""B2.4-P1 partitioned Bayesian authority schema closure.

Revision ID: 202605211200
Revises: 202605201430
Create Date: 2026-05-21 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605211200"
down_revision: Union[str, None] = "202605201430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PARTITION_COUNT = 16

FIT_COLUMNS = """
    id,
    tenant_id,
    model_type,
    model_version,
    source_window_start,
    source_window_end,
    source_snapshot_hash,
    status,
    eligibility_status,
    data_completeness_status,
    fallback_applied,
    fallback_reason,
    sampling_started_at,
    last_eligibility_check_at,
    last_fit_at,
    completed_at,
    runtime_seconds,
    max_runtime_seconds,
    max_samples,
    max_cores,
    n_chains,
    n_samples_actual,
    r_hat_max,
    ess_min,
    divergence_count,
    credible_interval_status,
    confidence_bucket,
    confidence_bucket_reason,
    confidence_policy_version,
    artifact_ref,
    artifact_hash,
    created_at,
    updated_at
"""

ARTIFACT_COLUMNS = """
    id,
    tenant_id,
    fit_id,
    artifact_ref,
    artifact_hash,
    artifact_type,
    storage_backend,
    artifact_uri_internal,
    artifact_size_bytes,
    compression,
    retention_class,
    expires_at,
    pruned_at,
    created_at
"""


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


def _drop_index(name: str) -> None:
    op.execute(
        f"DROP INDEX IF EXISTS public.{name}"  # CI:DESTRUCTIVE_OK - migration converts empty P1 authority heaps into partitioned table families.
    )


def _drop_constraint(table: str, name: str) -> None:
    op.execute(
        f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {name}"  # CI:DESTRUCTIVE_OK - constraints are recreated on the partitioned authority parent.
    )


def _create_model_fits_table(*, partitioned: bool) -> None:
    table_suffix = "\n        PARTITION BY HASH (tenant_id)" if partitioned else "\n        WITH (fillfactor = 90)"
    primary_key = (
        "CONSTRAINT bayesian_model_fits_pkey PRIMARY KEY (tenant_id, id)"
        if partitioned
        else "CONSTRAINT bayesian_model_fits_pkey PRIMARY KEY (id)"
    )
    tenant_fit_identity = (
        ""
        if partitioned
        else """,
            CONSTRAINT uq_bayesian_model_fits_tenant_id_id
                UNIQUE (tenant_id, id)"""
    )
    op.execute(
        f"""
        CREATE TABLE public.bayesian_model_fits (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            source_snapshot_hash character varying(64) NOT NULL,
            status character varying(32) DEFAULT 'pending' NOT NULL,
            eligibility_status character varying(32) DEFAULT 'unknown' NOT NULL,
            data_completeness_status character varying(32) DEFAULT 'unknown' NOT NULL,
            fallback_applied boolean DEFAULT false NOT NULL,
            fallback_reason character varying(64),
            sampling_started_at timestamp with time zone,
            last_eligibility_check_at timestamp with time zone,
            last_fit_at timestamp with time zone,
            completed_at timestamp with time zone,
            runtime_seconds integer,
            max_runtime_seconds integer DEFAULT 60 NOT NULL,
            max_samples integer DEFAULT 0 NOT NULL,
            max_cores integer DEFAULT 1 NOT NULL,
            n_chains integer,
            n_samples_actual integer,
            r_hat_max double precision,
            ess_min double precision,
            divergence_count integer,
            credible_interval_status character varying(32) DEFAULT 'not_available' NOT NULL,
            confidence_bucket character varying(32),
            confidence_bucket_reason character varying(255),
            confidence_policy_version character varying(64),
            artifact_ref character varying(255),
            artifact_hash character varying(64),
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            {primary_key}{tenant_fit_identity},
            CONSTRAINT uq_bayesian_model_fits_tenant_model_window_snapshot
                UNIQUE (
                    tenant_id,
                    model_type,
                    model_version,
                    source_window_start,
                    source_window_end,
                    source_snapshot_hash
                ),
            CONSTRAINT ck_bayesian_model_fits_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{{1,63}}$'),
            CONSTRAINT ck_bayesian_model_fits_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_bayesian_model_fits_source_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_bayesian_model_fits_source_snapshot_hash_sha256
                CHECK (source_snapshot_hash ~ '^[a-f0-9]{{64}}$'),
            CONSTRAINT ck_bayesian_model_fits_status
                CHECK (status IN ('pending', 'queued', 'running', 'succeeded', 'failed', 'fallback_only', 'cancelled')),
            CONSTRAINT ck_bayesian_model_fits_eligibility_status
                CHECK (eligibility_status IN ('unknown', 'eligible', 'ineligible', 'fallback_only')),
            CONSTRAINT ck_bayesian_model_fits_data_completeness_status
                CHECK (data_completeness_status IN ('unknown', 'complete', 'partial', 'insufficient', 'stale')),
            CONSTRAINT ck_bayesian_model_fits_fallback_reason
                CHECK (
                    fallback_reason IS NULL
                    OR fallback_reason IN (
                        'insufficient_data',
                        'timeout',
                        'worker_failure',
                        'no_convergence',
                        'resource_bound_exceeded',
                        'source_unavailable',
                        'duplicate_fit_suppressed',
                        'artifact_unavailable',
                        'storage_quota_exceeded'
                    )
                ),
            CONSTRAINT ck_bayesian_model_fits_fallback_reason_required
                CHECK (
                    (fallback_applied = false AND fallback_reason IS NULL)
                    OR (fallback_applied = true AND fallback_reason IS NOT NULL)
                ),
            CONSTRAINT ck_bayesian_model_fits_runtime_seconds_non_negative
                CHECK (runtime_seconds IS NULL OR runtime_seconds >= 0),
            CONSTRAINT ck_bayesian_model_fits_max_runtime_seconds_non_negative
                CHECK (max_runtime_seconds >= 0),
            CONSTRAINT ck_bayesian_model_fits_max_samples_non_negative
                CHECK (max_samples >= 0),
            CONSTRAINT ck_bayesian_model_fits_max_cores_non_negative
                CHECK (max_cores >= 0),
            CONSTRAINT ck_bayesian_model_fits_n_chains_non_negative
                CHECK (n_chains IS NULL OR n_chains >= 0),
            CONSTRAINT ck_bayesian_model_fits_n_samples_actual_non_negative
                CHECK (n_samples_actual IS NULL OR n_samples_actual >= 0),
            CONSTRAINT ck_bayesian_model_fits_r_hat_max_positive
                CHECK (r_hat_max IS NULL OR r_hat_max > 0),
            CONSTRAINT ck_bayesian_model_fits_ess_min_non_negative
                CHECK (ess_min IS NULL OR ess_min >= 0),
            CONSTRAINT ck_bayesian_model_fits_divergence_count_non_negative
                CHECK (divergence_count IS NULL OR divergence_count >= 0),
            CONSTRAINT ck_bayesian_model_fits_credible_interval_status
                CHECK (credible_interval_status IN ('not_available', 'available', 'suppressed', 'invalid', 'pending')),
            CONSTRAINT ck_bayesian_model_fits_confidence_bucket
                CHECK (
                    confidence_bucket IS NULL
                    OR confidence_bucket IN ('unavailable', 'low', 'medium', 'high', 'fallback', 'needs_review')
                ),
            CONSTRAINT ck_bayesian_model_fits_artifact_ref_format
                CHECK (artifact_ref IS NULL OR artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{{1,240}}$'),
            CONSTRAINT ck_bayesian_model_fits_artifact_hash_sha256
                CHECK (artifact_hash IS NULL OR artifact_hash ~ '^[a-f0-9]{{64}}$'),
            CONSTRAINT ck_bayesian_model_fits_artifact_ref_hash_pair
                CHECK (
                    (artifact_ref IS NULL AND artifact_hash IS NULL)
                    OR (artifact_ref IS NOT NULL AND artifact_hash IS NOT NULL)
                )
        ){table_suffix}
        """
    )


def _create_artifacts_table(*, partitioned: bool) -> None:
    table_suffix = "\n        PARTITION BY HASH (tenant_id)" if partitioned else ""
    primary_key = (
        "CONSTRAINT bayesian_artifacts_pkey PRIMARY KEY (tenant_id, id)"
        if partitioned
        else "CONSTRAINT bayesian_artifacts_pkey PRIMARY KEY (id)"
    )
    op.execute(
        f"""
        CREATE TABLE public.bayesian_artifacts (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            fit_id uuid NOT NULL,
            artifact_ref character varying(255) NOT NULL,
            artifact_hash character varying(64) NOT NULL,
            artifact_type character varying(32) NOT NULL,
            storage_backend character varying(32) NOT NULL,
            artifact_uri_internal character varying(1024) NOT NULL,
            artifact_size_bytes bigint NOT NULL,
            compression character varying(32),
            retention_class character varying(32) NOT NULL,
            expires_at timestamp with time zone,
            pruned_at timestamp with time zone,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            {primary_key},
            CONSTRAINT fk_bayesian_artifacts_tenant_fit
                FOREIGN KEY (tenant_id, fit_id)
                REFERENCES public.bayesian_model_fits (tenant_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT uq_bayesian_artifacts_tenant_artifact_ref UNIQUE (tenant_id, artifact_ref),
            CONSTRAINT ck_bayesian_artifacts_artifact_ref_format
                CHECK (artifact_ref ~ '^b24://[a-z0-9][a-z0-9._/-]{{1,240}}$'),
            CONSTRAINT ck_bayesian_artifacts_artifact_hash_sha256
                CHECK (artifact_hash ~ '^[a-f0-9]{{64}}$'),
            CONSTRAINT ck_bayesian_artifacts_artifact_type
                CHECK (artifact_type IN ('posterior_trace', 'diagnostics', 'summary', 'source_manifest', 'fit_metadata')),
            CONSTRAINT ck_bayesian_artifacts_storage_backend
                CHECK (storage_backend IN ('postgres', 'object_storage', 'local_fs')),
            CONSTRAINT ck_bayesian_artifacts_uri_not_blank
                CHECK (char_length(trim(artifact_uri_internal)) > 0),
            CONSTRAINT ck_bayesian_artifacts_size_non_negative
                CHECK (artifact_size_bytes >= 0),
            CONSTRAINT ck_bayesian_artifacts_compression
                CHECK (compression IS NULL OR compression IN ('none', 'gzip', 'zstd')),
            CONSTRAINT ck_bayesian_artifacts_retention_class
                CHECK (retention_class IN ('ephemeral', 'standard', 'audit')),
            CONSTRAINT ck_bayesian_artifacts_pruned_requires_expiry
                CHECK (pruned_at IS NULL OR expires_at IS NOT NULL)
        ){table_suffix}
        """
    )


def _create_partitions(table_name: str, *, fillfactor: int | None = None) -> None:
    for remainder in range(PARTITION_COUNT):
        partition_name = f"{table_name}_p{remainder:02d}"
        op.execute(
            f"""
            CREATE TABLE public.{partition_name}
            PARTITION OF public.{table_name}
            FOR VALUES WITH (MODULUS {PARTITION_COUNT}, REMAINDER {remainder})
            """
        )
        if fillfactor is not None:
            op.execute(f"ALTER TABLE public.{partition_name} SET (fillfactor = {fillfactor})")
        op.execute(f"ALTER TABLE public.{partition_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE ONLY public.{partition_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy_{partition_name}
            ON public.{partition_name}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )


def _create_indexes() -> None:
    for ddl in (
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_id
            ON public.bayesian_model_fits (tenant_id)
        """,
        """
        CREATE INDEX idx_bayesian_artifacts_tenant_id
            ON public.bayesian_artifacts (tenant_id)
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_model_window
            ON public.bayesian_model_fits (
                tenant_id,
                model_type,
                source_window_start,
                source_window_end
            )
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_source_snapshot_hash
            ON public.bayesian_model_fits (tenant_id, source_snapshot_hash)
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_status
            ON public.bayesian_model_fits (tenant_id, status)
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_model_eligibility
            ON public.bayesian_model_fits (
                tenant_id,
                model_type,
                eligibility_status,
                last_eligibility_check_at DESC
            )
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_model_fallback
            ON public.bayesian_model_fits (
                tenant_id,
                model_type,
                fallback_reason,
                last_eligibility_check_at DESC
            )
            WHERE fallback_applied = true
        """,
        """
        CREATE INDEX idx_bayesian_model_fits_tenant_model_window_latest
            ON public.bayesian_model_fits (
                tenant_id,
                model_type,
                source_window_start,
                source_window_end,
                created_at DESC
            )
        """,
        """
        CREATE INDEX idx_bayesian_artifacts_tenant_fit
            ON public.bayesian_artifacts (tenant_id, fit_id)
        """,
        """
        CREATE INDEX idx_bayesian_artifacts_tenant_artifact_ref
            ON public.bayesian_artifacts (tenant_id, artifact_ref)
        """,
        """
        CREATE INDEX idx_bayesian_artifacts_tenant_artifact_hash
            ON public.bayesian_artifacts (tenant_id, artifact_hash)
        """,
    ):
        op.execute(ddl)


def _enable_parent_rls() -> None:
    for table_name in ("bayesian_model_fits", "bayesian_artifacts"):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_bayesian_model_fits
        ON public.bayesian_model_fits
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_bayesian_artifacts
        ON public.bayesian_artifacts
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def _grant_access() -> None:
    for role in ("app_user", "app_rw"):
        _grant_if_role_exists(
            role,
            f"GRANT SELECT, INSERT, UPDATE ON TABLE public.bayesian_model_fits TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT SELECT, INSERT, UPDATE ON TABLE public.bayesian_artifacts TO {role}",
        )
    _grant_if_role_exists("app_ro", "GRANT SELECT ON TABLE public.bayesian_model_fits TO app_ro")
    _grant_if_role_exists("app_ro", "GRANT SELECT ON TABLE public.bayesian_artifacts TO app_ro")


def _revoke_access() -> None:
    for table_name in ("bayesian_artifacts", "bayesian_model_fits"):
        for role in ("app_ro", "app_rw", "app_user"):
            _revoke_if_role_exists(role, f"REVOKE ALL ON TABLE public.{table_name} FROM {role}")


def _drop_current_authority_indexes() -> None:
    for name in (
        "idx_bayesian_artifacts_tenant_artifact_hash",
        "idx_bayesian_artifacts_tenant_artifact_ref",
        "idx_bayesian_artifacts_tenant_fit",
        "idx_bayesian_artifacts_tenant_id",
        "idx_bayesian_model_fits_tenant_model_window_latest",
        "idx_bayesian_model_fits_tenant_model_fallback",
        "idx_bayesian_model_fits_tenant_model_eligibility",
        "idx_bayesian_model_fits_tenant_status",
        "idx_bayesian_model_fits_tenant_source_snapshot_hash",
        "idx_bayesian_model_fits_tenant_model_window",
        "idx_bayesian_model_fits_tenant_id",
    ):
        _drop_index(name)


def _drop_current_authority_constraints() -> None:
    for name in (
        "fk_bayesian_artifacts_tenant_fit",
        "bayesian_artifacts_fit_id_fkey",
        "uq_bayesian_artifacts_tenant_artifact_ref",
        "bayesian_artifacts_tenant_id_fkey",
        "bayesian_artifacts_pkey",
    ):
        _drop_constraint("bayesian_artifacts", name)
    for name in (
        "uq_bayesian_model_fits_tenant_model_window_snapshot",
        "uq_bayesian_model_fits_tenant_id_id",
        "uq_bayesian_model_fits_tenant_source_snapshot_model",
        "bayesian_model_fits_tenant_id_fkey",
        "bayesian_model_fits_pkey",
    ):
        _drop_constraint("bayesian_model_fits", name)


def _rename_current_tables_to_legacy(suffix: str) -> None:
    _drop_current_authority_constraints()
    _drop_current_authority_indexes()
    op.execute(f"ALTER TABLE public.bayesian_artifacts RENAME TO bayesian_artifacts_{suffix}")
    op.execute(f"ALTER TABLE public.bayesian_model_fits RENAME TO bayesian_model_fits_{suffix}")
    op.execute(f"ALTER TABLE public.bayesian_artifacts_{suffix} DISABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.bayesian_model_fits_{suffix} DISABLE ROW LEVEL SECURITY")


def _copy_from_legacy(suffix: str) -> None:
    op.execute(
        f"""
        INSERT INTO public.bayesian_model_fits ({FIT_COLUMNS})
        SELECT {FIT_COLUMNS}
        FROM public.bayesian_model_fits_{suffix}
        """
    )
    op.execute(
        f"""
        INSERT INTO public.bayesian_artifacts ({ARTIFACT_COLUMNS})
        SELECT {ARTIFACT_COLUMNS}
        FROM public.bayesian_artifacts_{suffix}
        """
    )


def _drop_legacy_tables(suffix: str) -> None:
    op.execute(
        f"DROP TABLE IF EXISTS public.bayesian_artifacts_{suffix}"  # CI:DESTRUCTIVE_OK - rows have been copied into the replacement authority table.
    )
    op.execute(
        f"DROP TABLE IF EXISTS public.bayesian_model_fits_{suffix}"  # CI:DESTRUCTIVE_OK - rows have been copied into the replacement authority table.
    )


def _comment_tables(*, partitioned: bool) -> None:
    fit_family = (
        "Final physical table family: HASH partitioned by tenant_id with 16 initial partitions; "
        "child partitions carry fillfactor=90 for lifecycle updates."
        if partitioned
        else "Downgraded heap form from the prior P1 corrective revision; fillfactor=90 retained."
    )
    artifact_family = (
        "Final physical table family: HASH partitioned by tenant_id with 16 initial partitions."
        if partitioned
        else "Downgraded heap form from the prior P1 corrective revision."
    )
    op.execute(
        f"""
        COMMENT ON TABLE public.bayesian_model_fits IS
            'B2.4-P1 tenant-scoped Bayesian fit authority records. {fit_family} Defines persistence only; no statistical runtime, source snapshot computation, diagnostics computation, projection, or public API behavior.'
        """
    )
    op.execute(
        f"""
        COMMENT ON TABLE public.bayesian_artifacts IS
            'B2.4-P1 tenant-scoped Bayesian artifact authority records. {artifact_family} Lifecycle jobs and artifact generation are intentionally out of scope.'
        """
    )


def upgrade() -> None:
    _rename_current_tables_to_legacy("heap_legacy")
    _create_model_fits_table(partitioned=True)
    _create_partitions("bayesian_model_fits", fillfactor=90)
    _create_artifacts_table(partitioned=True)
    _create_partitions("bayesian_artifacts")
    _copy_from_legacy("heap_legacy")
    _create_indexes()
    _enable_parent_rls()
    _comment_tables(partitioned=True)
    _grant_access()
    _drop_legacy_tables("heap_legacy")


def downgrade() -> None:
    _rename_current_tables_to_legacy("partitioned_legacy")
    _create_model_fits_table(partitioned=False)
    _create_artifacts_table(partitioned=False)
    _copy_from_legacy("partitioned_legacy")
    _create_indexes()
    _enable_parent_rls()
    _comment_tables(partitioned=False)
    _grant_access()
    _drop_legacy_tables("partitioned_legacy")
