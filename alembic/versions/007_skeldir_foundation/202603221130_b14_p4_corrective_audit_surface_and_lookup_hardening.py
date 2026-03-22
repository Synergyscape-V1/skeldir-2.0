"""B1.4-P4 corrective closeout: audit-surface split + lookup hardening.

Revision ID: 202603221130
Revises: 202603212015
Create Date: 2026-03-22 11:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603221130"
down_revision: Union[str, None] = "202603212015"
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
        CREATE TABLE public.compliance_audit_ledger (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            occurred_at timestamptz NOT NULL,
            audit_event_type varchar(64) NOT NULL,
            correlation_id uuid,
            idempotency_key varchar(255) NOT NULL,
            selector jsonb NOT NULL DEFAULT '{}'::jsonb,
            selector_hash char(64) NOT NULL,
            effects jsonb NOT NULL DEFAULT '{}'::jsonb,
            evidence_hash char(64) NOT NULL,
            actor varchar(64) NOT NULL DEFAULT 'privacy_worker',
            CONSTRAINT uq_compliance_audit_ledger_tenant_idempotency_key
                UNIQUE (tenant_id, idempotency_key)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.compliance_audit_ledger IS
            'Append-only audit artifacts proving deterministic privacy erasure without mutating attribution_events.'
        """
    )
    op.execute(
        """
        CREATE INDEX idx_compliance_audit_ledger_tenant_created
            ON public.compliance_audit_ledger (tenant_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_compliance_audit_ledger_tenant_correlation
            ON public.compliance_audit_ledger (tenant_id, correlation_id)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_compliance_audit_ledger_append_only()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION
                'compliance_audit_ledger is append-only; UPDATE and DELETE are forbidden';
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_compliance_audit_ledger_append_only
            BEFORE UPDATE OR DELETE ON public.compliance_audit_ledger
            FOR EACH ROW
            EXECUTE FUNCTION public.fn_compliance_audit_ledger_append_only()
        """
    )

    op.execute("ALTER TABLE public.compliance_audit_ledger ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.compliance_audit_ledger FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_policy_compliance_audit_ledger
            ON public.compliance_audit_ledger
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_compliance_audit_ledger
            ON public.compliance_audit_ledger
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    op.execute(
        """
        ALTER TABLE public.raw_event_payloads
            ADD COLUMN IF NOT EXISTS lookup_hash varchar(64)
        """
    )
    op.execute(
        """
        UPDATE public.raw_event_payloads rep
        SET lookup_hash = encode(digest(e.idempotency_key, 'sha256'), 'hex')
        FROM public.attribution_events e
        WHERE rep.event_id = e.id
          AND rep.tenant_id = e.tenant_id
        """
    )
    op.execute(
        """
        UPDATE public.raw_event_payloads
        SET lookup_hash = encode(digest('', 'sha256'), 'hex')
        WHERE lookup_hash IS NULL OR lookup_hash = ''
        """
    )
    op.execute(
        """
        ALTER TABLE public.raw_event_payloads
            ALTER COLUMN lookup_hash SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.raw_event_payloads
            ADD CONSTRAINT ck_raw_event_payloads_lookup_hash_sha256
            CHECK (char_length(lookup_hash) = 64)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_event_payloads_tenant_lookup_hash
            ON public.raw_event_payloads (tenant_id, lookup_hash)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_raw_event_payloads_payload_json_gin
            ON public.raw_event_payloads
            USING gin (payload_json jsonb_path_ops)
        """
    )

    op.execute(
        """
        ALTER TABLE public.dead_events
            ADD COLUMN IF NOT EXISTS idempotency_key varchar(255)
        """
    )
    op.execute(
        """
        UPDATE public.dead_events
        SET idempotency_key = NULLIF(raw_payload->>'idempotency_key', '')
        WHERE idempotency_key IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dead_events_tenant_idempotency_key
            ON public.dead_events (tenant_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
        """
    )

    op.execute(
        """
        ALTER TABLE public.dead_events_quarantine
            ADD COLUMN IF NOT EXISTS idempotency_key varchar(255)
        """
    )
    op.execute(
        """
        UPDATE public.dead_events_quarantine
        SET idempotency_key = NULLIF(raw_payload->>'idempotency_key', '')
        WHERE idempotency_key IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dead_events_quarantine_tenant_idempotency_key
            ON public.dead_events_quarantine (tenant_id, idempotency_key)
            WHERE idempotency_key IS NOT NULL
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT ON TABLE public.compliance_audit_ledger TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT ON TABLE public.compliance_audit_ledger TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.compliance_audit_ledger TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.compliance_audit_ledger FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.compliance_audit_ledger FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.compliance_audit_ledger FROM app_user",
    )

    op.execute(
        """
        DROP INDEX IF EXISTS public.idx_dead_events_quarantine_tenant_idempotency_key
        """
    )
    op.execute(
        """
        ALTER TABLE public.dead_events_quarantine
            DROP COLUMN IF EXISTS idempotency_key -- CI:DESTRUCTIVE_OK - rollback path only for B1.4-P4 corrective migration
        """
    )

    op.execute("DROP INDEX IF EXISTS public.idx_dead_events_tenant_idempotency_key")
    op.execute(
        "ALTER TABLE public.dead_events DROP COLUMN IF EXISTS idempotency_key"  # CI:DESTRUCTIVE_OK - rollback path only for B1.4-P4 corrective migration
    )

    op.execute("DROP INDEX IF EXISTS public.idx_raw_event_payloads_payload_json_gin")
    op.execute("DROP INDEX IF EXISTS public.idx_raw_event_payloads_tenant_lookup_hash")
    op.execute(
        """
        ALTER TABLE public.raw_event_payloads
            DROP CONSTRAINT IF EXISTS ck_raw_event_payloads_lookup_hash_sha256
        """
    )
    op.execute(
        """
        ALTER TABLE public.raw_event_payloads
            DROP COLUMN IF EXISTS lookup_hash -- CI:DESTRUCTIVE_OK - rollback path only for B1.4-P4 corrective migration
        """
    )

    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_policy_compliance_audit_ledger
            ON public.compliance_audit_ledger
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_compliance_audit_ledger_append_only
            ON public.compliance_audit_ledger
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.fn_compliance_audit_ledger_append_only")
    op.execute("DROP INDEX IF EXISTS public.idx_compliance_audit_ledger_tenant_correlation")
    op.execute("DROP INDEX IF EXISTS public.idx_compliance_audit_ledger_tenant_created")
    op.execute(
        "DROP TABLE IF EXISTS public.compliance_audit_ledger"  # CI:DESTRUCTIVE_OK - rollback path only for B1.4-P4 corrective migration
    )
