"""B2.3-P1 canonical match-input semantics and schema authority lock.

Revision ID: 202604291200
Revises: 202604241815
Create Date: 2026-04-29 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604291200"
down_revision: Union[str, None] = "202604241815"
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
        """
        CREATE TABLE public.b23_match_verdicts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            attribution_event_id uuid NULL REFERENCES public.attribution_events(id) ON DELETE SET NULL,
            webhook_ingress_identity_id uuid NULL REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL,
            provider varchar(32) NOT NULL,
            canonical_commerce_reference varchar(255) NOT NULL,
            provider_native_event_reference varchar(255) NOT NULL,
            provider_native_commerce_reference varchar(255) NOT NULL,
            status varchar(32) NOT NULL,
            match_quality varchar(16) NOT NULL,
            attributed_amount_minor integer NOT NULL,
            verified_amount_minor integer NOT NULL,
            currency_code char(3) NOT NULL,
            pending_since timestamptz NOT NULL DEFAULT now(),
            provisional_expires_at timestamptz NULL,
            confirmed_at timestamptz NULL,
            adjusted_at timestamptz NULL,
            unmatched_marked_at timestamptz NULL,
            last_transition_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_b23_match_verdicts_tenant_provider_event_ref
                UNIQUE (tenant_id, provider, provider_native_event_reference),
            CONSTRAINT ck_b23_match_verdicts_status
                CHECK (
                    status IN (
                        'pending',
                        'matched_provisional',
                        'matched_confirmed',
                        'adjusted',
                        'unmatched'
                    )
                ),
            CONSTRAINT ck_b23_match_verdicts_match_quality
                CHECK (match_quality IN ('high', 'medium', 'low')),
            CONSTRAINT ck_b23_match_verdicts_attributed_amount_non_negative
                CHECK (attributed_amount_minor >= 0),
            CONSTRAINT ck_b23_match_verdicts_verified_amount_non_negative
                CHECK (verified_amount_minor >= 0),
            CONSTRAINT ck_b23_match_verdicts_provider_not_blank
                CHECK (char_length(provider) > 0),
            CONSTRAINT ck_b23_match_verdicts_canonical_reference_not_blank
                CHECK (char_length(canonical_commerce_reference) > 0),
            CONSTRAINT ck_b23_match_verdicts_provider_event_reference_not_blank
                CHECK (char_length(provider_native_event_reference) > 0),
            CONSTRAINT ck_b23_match_verdicts_provider_commerce_reference_not_blank
                CHECK (char_length(provider_native_commerce_reference) > 0),
            CONSTRAINT ck_b23_match_verdicts_currency_code_len
                CHECK (char_length(trim(currency_code)) = 3)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b23_match_verdicts IS
            'B2.3-P1 authoritative tenant-scoped deterministic match verdict substrate (no raw payload authority, no PII).'
        """
    )
    op.execute(
        """
        CREATE TABLE public.b23_exception_records (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            match_verdict_id uuid NOT NULL REFERENCES public.b23_match_verdicts(id) ON DELETE CASCADE,
            provider varchar(32) NOT NULL,
            canonical_commerce_reference varchar(255) NOT NULL,
            status varchar(16) NOT NULL,
            severity varchar(16) NOT NULL,
            resolution_code varchar(64) NULL,
            resolution_notes text NULL,
            raised_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz NULL,
            dismissed_at timestamptz NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b23_exception_records_status
                CHECK (status IN ('open', 'acknowledged', 'resolved', 'dismissed')),
            CONSTRAINT ck_b23_exception_records_severity
                CHECK (severity IN ('flagged', 'alert')),
            CONSTRAINT ck_b23_exception_records_resolution_code_required
                CHECK (
                    status NOT IN ('resolved', 'dismissed')
                    OR (resolution_code IS NOT NULL AND char_length(trim(resolution_code)) > 0)
                )
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b23_exception_records IS
            'B2.3-P1 first-class exception workflow records for deterministic discrepancy handling.'
        """
    )
    op.execute(
        """
        CREATE TABLE public.b23_revenue_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            match_verdict_id uuid NULL REFERENCES public.b23_match_verdicts(id) ON DELETE SET NULL,
            webhook_ingress_identity_id uuid NULL REFERENCES public.webhook_ingress_identities(id) ON DELETE SET NULL,
            provider varchar(32) NOT NULL,
            provider_native_event_reference varchar(255) NOT NULL,
            provider_native_commerce_reference varchar(255) NOT NULL,
            canonical_commerce_reference varchar(255) NOT NULL,
            event_type varchar(32) NOT NULL,
            amount_minor integer NOT NULL,
            currency_code char(3) NOT NULL,
            event_occurred_at timestamptz NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_b23_revenue_events_tenant_provider_event_ref
                UNIQUE (tenant_id, provider, provider_native_event_reference),
            CONSTRAINT ck_b23_revenue_events_event_type
                CHECK (
                    event_type IN (
                        'payment_capture',
                        'partial_refund',
                        'full_refund',
                        'chargeback_opened',
                        'chargeback_won',
                        'chargeback_lost',
                        'reversal'
                    )
                ),
            CONSTRAINT ck_b23_revenue_events_amount_non_negative
                CHECK (amount_minor >= 0),
            CONSTRAINT ck_b23_revenue_events_provider_not_blank
                CHECK (char_length(provider) > 0),
            CONSTRAINT ck_b23_revenue_events_provider_event_reference_not_blank
                CHECK (char_length(provider_native_event_reference) > 0),
            CONSTRAINT ck_b23_revenue_events_provider_commerce_reference_not_blank
                CHECK (char_length(provider_native_commerce_reference) > 0),
            CONSTRAINT ck_b23_revenue_events_canonical_reference_not_blank
                CHECK (char_length(canonical_commerce_reference) > 0),
            CONSTRAINT ck_b23_revenue_events_currency_code_len
                CHECK (char_length(trim(currency_code)) = 3)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b23_revenue_events IS
            'B2.3-P1 append-only post-capture revenue event ledger primitives with tenant-scoped provider idempotency.'
        """
    )
    op.execute(
        """
        CREATE TABLE public.b23_webhook_ingestion_logs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            provider varchar(32) NOT NULL,
            provider_native_event_reference varchar(255) NULL,
            ingestion_status varchar(16) NOT NULL,
            failure_reason text NULL,
            correlation_id uuid NULL,
            received_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_b23_webhook_ingestion_logs_status
                CHECK (ingestion_status IN ('success', 'failed')),
            CONSTRAINT ck_b23_webhook_ingestion_logs_failure_reason_when_failed
                CHECK (
                    ingestion_status <> 'failed'
                    OR (failure_reason IS NOT NULL AND char_length(trim(failure_reason)) > 0)
                ),
            CONSTRAINT ck_b23_webhook_ingestion_logs_provider_not_blank
                CHECK (char_length(provider) > 0)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b23_webhook_ingestion_logs IS
            'B2.3-P1 SQL-queryable webhook ingestion telemetry substrate; operational only and not first-authority payload storage.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_b23_match_verdicts_tenant_status_transition
            ON public.b23_match_verdicts (tenant_id, status, last_transition_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_match_verdicts_tenant_provider_reference
            ON public.b23_match_verdicts (tenant_id, provider, canonical_commerce_reference)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_match_verdicts_tenant_provider_commerce_native
            ON public.b23_match_verdicts (tenant_id, provider, provider_native_commerce_reference)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_match_verdicts_tenant_state_timestamps
            ON public.b23_match_verdicts (
                tenant_id,
                pending_since,
                provisional_expires_at,
                confirmed_at,
                unmatched_marked_at,
                adjusted_at
            )
        """
    )

    op.execute(
        """
        CREATE INDEX idx_b23_exception_records_tenant_status_severity
            ON public.b23_exception_records (tenant_id, status, severity, raised_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_exception_records_tenant_provider_reference
            ON public.b23_exception_records (tenant_id, provider, canonical_commerce_reference)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_b23_revenue_events_tenant_event_type_recorded
            ON public.b23_revenue_events (tenant_id, event_type, recorded_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_revenue_events_tenant_provider_reference
            ON public.b23_revenue_events (tenant_id, provider, canonical_commerce_reference, event_occurred_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_revenue_events_tenant_provider_commerce_native
            ON public.b23_revenue_events (tenant_id, provider, provider_native_commerce_reference)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_provider_received
            ON public.b23_webhook_ingestion_logs (tenant_id, provider, received_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_b23_webhook_ingestion_logs_tenant_status_received
            ON public.b23_webhook_ingestion_logs (tenant_id, ingestion_status, received_at DESC)
        """
    )

    for table_name in (
        "b23_match_verdicts",
        "b23_exception_records",
        "b23_revenue_events",
        "b23_webhook_ingestion_logs",
    ):
        op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE ONLY public.{table_name} FORCE ROW LEVEL SECURITY")

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_match_verdicts ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b23_match_verdicts ON public.b23_match_verdicts
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_exception_records ON public.b23_exception_records"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b23_exception_records ON public.b23_exception_records
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_revenue_events ON public.b23_revenue_events"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b23_revenue_events ON public.b23_revenue_events
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_webhook_ingestion_logs ON public.b23_webhook_ingestion_logs"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b23_webhook_ingestion_logs ON public.b23_webhook_ingestion_logs
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_verdicts TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.b23_match_verdicts TO app_ro",
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_exception_records TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_exception_records TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.b23_exception_records TO app_ro",
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT ON TABLE public.b23_revenue_events TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT ON TABLE public.b23_revenue_events TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.b23_revenue_events TO app_ro",
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT ON TABLE public.b23_webhook_ingestion_logs TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT ON TABLE public.b23_webhook_ingestion_logs TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.b23_webhook_ingestion_logs TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.b23_webhook_ingestion_logs FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.b23_webhook_ingestion_logs FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.b23_webhook_ingestion_logs FROM app_user",
    )

    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.b23_revenue_events FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.b23_revenue_events FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.b23_revenue_events FROM app_user",
    )

    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.b23_exception_records FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.b23_exception_records FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.b23_exception_records FROM app_user",
    )

    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_user",
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_webhook_ingestion_logs ON public.b23_webhook_ingestion_logs"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_revenue_events ON public.b23_revenue_events"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_exception_records ON public.b23_exception_records"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b23_match_verdicts ON public.b23_match_verdicts"
    )

    op.execute("DROP INDEX IF EXISTS public.idx_b23_webhook_ingestion_logs_tenant_status_received")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_webhook_ingestion_logs_tenant_provider_received")
    op.execute(
        "DROP TABLE IF EXISTS public.b23_webhook_ingestion_logs"
    )  # CI:DESTRUCTIVE_OK - reversible downgrade for B2.3-P1 schema authority lock migration

    op.execute("DROP INDEX IF EXISTS public.idx_b23_revenue_events_tenant_provider_commerce_native")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_revenue_events_tenant_provider_reference")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_revenue_events_tenant_event_type_recorded")
    op.execute(
        "DROP TABLE IF EXISTS public.b23_revenue_events"
    )  # CI:DESTRUCTIVE_OK - reversible downgrade for B2.3-P1 schema authority lock migration

    op.execute("DROP INDEX IF EXISTS public.idx_b23_exception_records_tenant_provider_reference")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_exception_records_tenant_status_severity")
    op.execute(
        "DROP TABLE IF EXISTS public.b23_exception_records"
    )  # CI:DESTRUCTIVE_OK - reversible downgrade for B2.3-P1 schema authority lock migration

    op.execute("DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_state_timestamps")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_provider_commerce_native")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_provider_reference")
    op.execute("DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_status_transition")
    op.execute(
        "DROP TABLE IF EXISTS public.b23_match_verdicts"
    )  # CI:DESTRUCTIVE_OK - reversible downgrade for B2.3-P1 schema authority lock migration
