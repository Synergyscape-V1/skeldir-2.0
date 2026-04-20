"""B2.2-P3 canonical webhook ingress identity envelope substrate.

Revision ID: 202604201200
Revises: 202604171330
Create Date: 2026-04-20 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604201200"
down_revision: Union[str, None] = "202604171330"
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
        CREATE TABLE public.webhook_ingress_identities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            event_id uuid NOT NULL REFERENCES public.attribution_events(id) ON DELETE CASCADE,
            provider varchar(32) NOT NULL,
            provider_native_event_reference varchar(255) NOT NULL,
            provider_native_commerce_reference varchar(255) NOT NULL,
            normalized_commerce_reference_kind varchar(64) NOT NULL,
            normalized_commerce_reference_value varchar(255) NOT NULL,
            verified_amount_minor integer NOT NULL,
            verified_amount_currency char(3) NOT NULL,
            verified_amount_scale integer NOT NULL DEFAULT 2,
            event_timestamp timestamptz NOT NULL,
            idempotency_key varchar(255) NOT NULL,
            verified_commerce_ingress_state varchar(64) NOT NULL,
            verified_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_webhook_ingress_identities_event_id UNIQUE (event_id),
            CONSTRAINT uq_webhook_ingress_identities_tenant_event UNIQUE (tenant_id, event_id),
            CONSTRAINT uq_webhook_ingress_identities_tenant_idempotency UNIQUE (tenant_id, idempotency_key),
            CONSTRAINT ck_webhook_ingress_amount_minor_non_negative CHECK (verified_amount_minor >= 0),
            CONSTRAINT ck_webhook_ingress_amount_scale_non_negative CHECK (verified_amount_scale >= 0)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.webhook_ingress_identities IS
            'B2.2-P3 canonical provider-preserving ingress identity envelope and explicit verified-commerce state substrate.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_webhook_ingress_identities_tenant_provider_created
            ON public.webhook_ingress_identities (tenant_id, provider, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_webhook_ingress_identities_tenant_reference
            ON public.webhook_ingress_identities (
                tenant_id,
                normalized_commerce_reference_kind,
                normalized_commerce_reference_value
            )
        """
    )
    op.execute(
        """
        CREATE INDEX idx_webhook_ingress_identities_tenant_verified_state
            ON public.webhook_ingress_identities (tenant_id, verified_commerce_ingress_state, event_timestamp DESC)
        """
    )

    op.execute("ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.webhook_ingress_identities FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_webhook_ingress_identities ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_webhook_ingress_identities ON public.webhook_ingress_identities
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT ON TABLE public.webhook_ingress_identities TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT ON TABLE public.webhook_ingress_identities TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.webhook_ingress_identities TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.webhook_ingress_identities FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.webhook_ingress_identities FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.webhook_ingress_identities FROM app_user",
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_webhook_ingress_identities ON public.webhook_ingress_identities"
    )
    op.execute("DROP INDEX IF EXISTS public.idx_webhook_ingress_identities_tenant_verified_state")
    op.execute("DROP INDEX IF EXISTS public.idx_webhook_ingress_identities_tenant_reference")
    op.execute("DROP INDEX IF EXISTS public.idx_webhook_ingress_identities_tenant_provider_created")
    op.execute("DROP TABLE IF EXISTS public.webhook_ingress_identities")  # CI:DESTRUCTIVE_OK - rollback for B2.2-P3 webhook ingress identity substrate.
