"""Strictly purge deprecated B2.4-P4 hash-scoped profiling leases.

Revision ID: 202605271200
Revises: 202605261200
Create Date: 2026-05-27 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605271200"
down_revision: Union[str, None] = "202605261200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.b24_p4_profiling_leases') IS NULL THEN
            RAISE EXCEPTION 'Expected public.b24_p4_profiling_leases to exist before corrective purge';
          END IF;
        END $$;
        """
    )
    op.execute(
        "DROP TABLE public.b24_p4_profiling_leases"  # CI:DESTRUCTIVE_OK - authoritative B2.4-P4 deprecated split-brain profiling surface purge.
    )


def downgrade() -> None:
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
    op.execute("ALTER TABLE public.b24_p4_profiling_leases ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.b24_p4_profiling_leases FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b24_p4_profiling_leases
            ON public.b24_p4_profiling_leases
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
