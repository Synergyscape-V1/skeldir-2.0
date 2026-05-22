"""Add B2.4-P3 dirty planning, active lease, and dispatch outbox.

Revision ID: 202605221430
Revises: 202605221200
Create Date: 2026-05-22 14:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605221430"
down_revision: Union[str, None] = "202605221200"
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


def _enable_tenant_rls(table: str, policy: str) -> None:
    op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""
        CREATE POLICY {policy}
            ON public.{table}
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE public.b24_dirty_events (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            dirty_reason character varying(64) NOT NULL,
            source_family character varying(64) NOT NULL,
            event_hash character varying(64),
            source_event_id character varying(128),
            status character varying(32) DEFAULT 'pending' NOT NULL,
            planner_owner character varying(128),
            leased_at timestamp with time zone,
            lease_expires_at timestamp with time zone,
            coalesced_at timestamp with time zone,
            claimed_at timestamp with time zone,
            suppressed_at timestamp with time zone,
            fallback_at timestamp with time zone,
            superseded_at timestamp with time zone,
            dispatched_at timestamp with time zone,
            pruned_at timestamp with time zone,
            observed_at timestamp with time zone DEFAULT now() NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_dirty_events_pkey PRIMARY KEY (tenant_id, id),
            CONSTRAINT ck_b24_dirty_events_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_dirty_events_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_dirty_events_source_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_dirty_events_event_hash_sha256
                CHECK (event_hash IS NULL OR event_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_dirty_events_status
                CHECK (status IN (
                    'pending',
                    'leased',
                    'coalesced',
                    'claimed',
                    'suppressed',
                    'fallback_only',
                    'superseded',
                    'dispatched',
                    'pruned'
                )),
            CONSTRAINT ck_b24_dirty_events_reason_not_blank
                CHECK (char_length(trim(dirty_reason)) > 0),
            CONSTRAINT ck_b24_dirty_events_source_family_not_blank
                CHECK (char_length(trim(source_family)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_dirty_events_tenant_status_observed
            ON public.b24_dirty_events (tenant_id, status, observed_at ASC, id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_dirty_events_tenant_model_window_pending
            ON public.b24_dirty_events (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end,
                observed_at ASC,
                id ASC
            )
            WHERE status IN ('pending', 'leased')
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_dirty_events_tenant_event_hash
            ON public.b24_dirty_events (tenant_id, event_hash)
            WHERE event_hash IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE public.b24_active_execution_leases (
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            model_type character varying(64) NOT NULL,
            model_version character varying(64) NOT NULL,
            source_window_start timestamp with time zone NOT NULL,
            source_window_end timestamp with time zone NOT NULL,
            fit_id uuid,
            active_source_snapshot_hash character varying(64),
            latest_desired_source_snapshot_hash character varying(64),
            status character varying(32) DEFAULT 'claiming' NOT NULL,
            needs_refit_after_current boolean DEFAULT false NOT NULL,
            lease_owner character varying(128),
            lease_acquired_at timestamp with time zone DEFAULT now() NOT NULL,
            leased_until timestamp with time zone NOT NULL,
            heartbeat_at timestamp with time zone,
            stale_recovered_at timestamp with time zone,
            terminal_at timestamp with time zone,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b24_active_execution_leases_pkey PRIMARY KEY (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end
            ),
            CONSTRAINT fk_b24_active_execution_fit
                FOREIGN KEY (tenant_id, fit_id)
                REFERENCES public.bayesian_model_fits(tenant_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT ck_b24_active_execution_model_type_format
                CHECK (model_type ~ '^[a-z][a-z0-9_]{1,63}$'),
            CONSTRAINT ck_b24_active_execution_model_version_not_blank
                CHECK (char_length(trim(model_version)) > 0),
            CONSTRAINT ck_b24_active_execution_source_window_order
                CHECK (source_window_end > source_window_start),
            CONSTRAINT ck_b24_active_execution_active_hash_sha256
                CHECK (active_source_snapshot_hash IS NULL OR active_source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_active_execution_desired_hash_sha256
                CHECK (latest_desired_source_snapshot_hash IS NULL OR latest_desired_source_snapshot_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_active_execution_status
                CHECK (status IN (
                    'claiming',
                    'dispatch_pending',
                    'dispatched',
                    'running',
                    'cancel_requested',
                    'succeeded',
                    'failed',
                    'fallback_only',
                    'cancelled',
                    'stale_recovered'
                )),
            CONSTRAINT ck_b24_active_execution_active_fit_required
                CHECK (
                    status = 'claiming'
                    OR fit_id IS NOT NULL
                )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_active_execution_tenant_status_lease
            ON public.b24_active_execution_leases (tenant_id, status, leased_until ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_active_execution_tenant_fit
            ON public.b24_active_execution_leases (tenant_id, fit_id)
            WHERE fit_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_active_execution_superseded
            ON public.b24_active_execution_leases (
                tenant_id,
                model_type,
                model_version,
                source_window_start,
                source_window_end
            )
            WHERE needs_refit_after_current = true
        """
    )

    op.execute(
        """
        CREATE TABLE public.b24_fit_dispatch_outbox (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            fit_id uuid NOT NULL,
            dispatch_key character varying(128) NOT NULL,
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
            CONSTRAINT b24_fit_dispatch_outbox_pkey PRIMARY KEY (tenant_id, id),
            CONSTRAINT fk_b24_fit_dispatch_outbox_fit
                FOREIGN KEY (tenant_id, fit_id)
                REFERENCES public.bayesian_model_fits(tenant_id, id)
                ON DELETE RESTRICT,
            CONSTRAINT uq_b24_fit_dispatch_outbox_dispatch_key
                UNIQUE (tenant_id, dispatch_key),
            CONSTRAINT uq_b24_fit_dispatch_outbox_fit
                UNIQUE (tenant_id, fit_id),
            CONSTRAINT ck_b24_fit_dispatch_outbox_status
                CHECK (status IN (
                    'pending',
                    'dispatching',
                    'dispatched',
                    'failed_retryable',
                    'dead_lettered',
                    'stale_recovered'
                )),
            CONSTRAINT ck_b24_fit_dispatch_outbox_attempt_count
                CHECK (attempt_count >= 0),
            CONSTRAINT ck_b24_fit_dispatch_outbox_max_attempts
                CHECK (max_attempts > 0),
            CONSTRAINT ck_b24_fit_dispatch_outbox_dispatch_key_not_blank
                CHECK (char_length(trim(dispatch_key)) > 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_fit_dispatch_outbox_due
            ON public.b24_fit_dispatch_outbox (tenant_id, status, next_attempt_at ASC, id ASC)
            WHERE status IN ('pending', 'failed_retryable', 'stale_recovered')
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b24_fit_dispatch_outbox_dispatching
            ON public.b24_fit_dispatch_outbox (tenant_id, dispatching_started_at ASC)
            WHERE status = 'dispatching'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p3_attribution_events_source_stream_fallback
            ON public.attribution_events (tenant_id, occurred_at ASC, id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p3_attribution_allocations_source_stream_fallback
            ON public.attribution_allocations (tenant_id, created_at ASC, id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p3_match_verdicts_source_stream_fallback
            ON public.b23_match_verdicts (tenant_id, last_transition_at ASC, id ASC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_p3_revenue_events_source_stream_fallback
            ON public.b23_revenue_events (tenant_id, event_occurred_at ASC, id ASC)
        """
    )

    for table, policy in (
        ("b24_dirty_events", "tenant_isolation_policy_b24_dirty_events"),
        ("b24_active_execution_leases", "tenant_isolation_policy_b24_active_execution_leases"),
        ("b24_fit_dispatch_outbox", "tenant_isolation_policy_b24_fit_dispatch_outbox"),
    ):
        _enable_tenant_rls(table, policy)
        _grant_if_role_exists("app_user", f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO app_user")
        _grant_if_role_exists("app_worker", f"GRANT SELECT, INSERT, UPDATE ON public.{table} TO app_worker")
        _revoke_if_role_exists("app_readonly", f"REVOKE INSERT, UPDATE, DELETE ON public.{table} FROM app_readonly")


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p3_revenue_events_source_stream_fallback"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 fallback source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p3_match_verdicts_source_stream_fallback"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 fallback source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p3_attribution_allocations_source_stream_fallback"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 fallback source stream index.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_p3_attribution_events_source_stream_fallback"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 fallback source stream index.
    op.execute("DROP TABLE IF EXISTS public.b24_fit_dispatch_outbox")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 outbox.
    op.execute("DROP TABLE IF EXISTS public.b24_active_execution_leases")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 active lease.
    op.execute("DROP TABLE IF EXISTS public.b24_dirty_events")  # CI:DESTRUCTIVE_OK - reversible rollback for additive B2.4-P3 dirty events.
