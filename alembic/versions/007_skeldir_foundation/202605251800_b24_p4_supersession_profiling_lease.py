"""Add B2.4-P4 snapshot supersession, build outbox, and profiling lease.

Revision ID: 202605251800
Revises: 202605251430
Create Date: 2026-05-25 18:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605251800"
down_revision: Union[str, None] = "202605251430"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _quoted(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


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
            "authority_retry_superseded",
            "authority_timeout",
            "authority_build_failed",
            "pruned",
        )
    )
    op.execute(
        """
        CREATE TABLE public.b24_feature_authority_build_outbox (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            source_snapshot_hash character varying(64) NOT NULL,
            dispatch_key character varying(160) NOT NULL,
            status character varying(32) DEFAULT 'pending' NOT NULL,
            attempt_count integer DEFAULT 0 NOT NULL,
            max_attempts integer DEFAULT 5 NOT NULL,
            next_attempt_at timestamp with time zone DEFAULT now() NOT NULL,
            last_attempt_at timestamp with time zone,
            dispatching_started_at timestamp with time zone,
            dispatched_at timestamp with time zone,
            dead_lettered_at timestamp with time zone,
            stale_recovered_at timestamp with time zone,
            last_error text,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_feature_authority_build_outbox_pkey PRIMARY KEY (tenant_id, id),
            CONSTRAINT fk_b24_feature_authority_build_outbox_request FOREIGN KEY (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ) REFERENCES public.b24_feature_authority_build_requests (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ) ON DELETE CASCADE,
            CONSTRAINT uq_b24_feature_authority_build_outbox_candidate UNIQUE (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ),
            CONSTRAINT uq_b24_feature_authority_build_outbox_dispatch_key UNIQUE (
                tenant_id,
                dispatch_key
            ),
            CONSTRAINT ck_b24_feature_authority_build_outbox_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_feature_authority_build_outbox_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_feature_authority_build_outbox_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_feature_authority_build_outbox_hash_sha256
                CHECK (source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_feature_authority_build_outbox_status
                CHECK (status IN (
                    'pending',
                    'dispatching',
                    'dispatched',
                    'failed_retryable',
                    'dead_lettered',
                    'stale_recovered'
                )),
            CONSTRAINT ck_b24_feature_authority_build_outbox_attempt_count
                CHECK (attempt_count >= 0),
            CONSTRAINT ck_b24_feature_authority_build_outbox_max_attempts
                CHECK (max_attempts > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_feature_authority_build_outbox_due
            ON public.b24_feature_authority_build_outbox (
                tenant_id,
                status,
                next_attempt_at ASC,
                id ASC
            )
            WHERE status IN ('pending', 'failed_retryable', 'stale_recovered')
        """
    )
    op.execute(
        """
        CREATE TABLE public.b24_p4_profiling_leases (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            source_snapshot_hash character varying(64) NOT NULL,
            profiling_lease_id character varying(64) NOT NULL,
            status character varying(32) DEFAULT 'profiling' NOT NULL,
            lease_owner character varying(128),
            leased_until timestamp with time zone NOT NULL,
            attempt_count integer DEFAULT 0 NOT NULL,
            terminal_reason character varying(128),
            terminal_at timestamp with time zone,
            stale_recovered_at timestamp with time zone,
            policy_version character varying(64) NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_p4_profiling_leases_pkey PRIMARY KEY (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                source_snapshot_hash
            ),
            CONSTRAINT uq_b24_p4_profiling_leases_id UNIQUE (
                tenant_id,
                profiling_lease_id
            ),
            CONSTRAINT ck_b24_p4_profiling_leases_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_p4_profiling_leases_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_p4_profiling_leases_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_p4_profiling_leases_hash_sha256
                CHECK (source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_p4_profiling_leases_id_sha256
                CHECK (profiling_lease_id ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_p4_profiling_leases_status
                CHECK (status IN (
                    'profiling',
                    'profile_rejected',
                    'profile_passed',
                    'profile_superseded',
                    'profile_timeout',
                    'profile_failed'
                )),
            CONSTRAINT ck_b24_p4_profiling_leases_attempt_count
                CHECK (attempt_count >= 0),
            CONSTRAINT ck_b24_p4_profiling_leases_policy_version_not_blank
                CHECK (char_length(trim(policy_version)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_p4_profiling_leases_active
            ON public.b24_p4_profiling_leases (
                tenant_id,
                status,
                leased_until ASC
            )
            WHERE status = 'profiling'
        """
    )
    for table in (
        "b24_feature_authority_build_outbox",
        "b24_p4_profiling_leases",
    ):
        # Policy names: tenant_isolation_policy_b24_feature_authority_build_outbox,
        # tenant_isolation_policy_b24_p4_profiling_leases.
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy_{table}
                ON public.{table}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            """
        )
        _grant_if_role_exists(
            "app_user", f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO app_user"
        )
        _grant_if_role_exists(
            "app_worker",
            f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO app_worker",
        )
        _revoke_if_role_exists(
            "app_readonly",
            f"REVOKE INSERT, UPDATE, DELETE ON public.{table} FROM app_readonly",
        )


def downgrade() -> None:
    # fmt: off
    op.execute("DROP TABLE IF EXISTS public.b24_p4_profiling_leases")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 profiling leases.
    op.execute("DROP TABLE IF EXISTS public.b24_feature_authority_build_outbox")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P4 authority build outbox.
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
            "authority_waiting",
            "authority_retry_ready",
            "authority_timeout",
            "authority_build_failed",
            "pruned",
        )
    )
