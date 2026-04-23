"""B2.3-P0 durable attribution-side commerce identity substrate.

Revision ID: 202604231130
Revises: 202604201200
Create Date: 2026-04-23 11:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604231130"
down_revision: Union[str, None] = "202604201200"
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
        CREATE TABLE public.attribution_commerce_identities (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            attribution_event_id uuid NOT NULL REFERENCES public.attribution_events(id) ON DELETE CASCADE,
            provider varchar(32) NOT NULL,
            canonical_commerce_reference varchar(255) NOT NULL,
            source varchar(64) NOT NULL DEFAULT 'ingestion_runtime',
            first_observed_at timestamptz NOT NULL DEFAULT now(),
            last_observed_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_attr_commerce_identity_tenant_event
                UNIQUE (tenant_id, attribution_event_id),
            CONSTRAINT uq_attr_commerce_identity_tenant_provider_reference
                UNIQUE (tenant_id, provider, canonical_commerce_reference),
            CONSTRAINT ck_attr_commerce_identity_provider_not_blank
                CHECK (char_length(provider) > 0),
            CONSTRAINT ck_attr_commerce_identity_reference_not_blank
                CHECK (char_length(canonical_commerce_reference) > 0),
            CONSTRAINT ck_attr_commerce_identity_observed_time_order
                CHECK (last_observed_at >= first_observed_at)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.attribution_commerce_identities IS
            'B2.3-P0 allowed delayed-arrival topology: durable tenant-scoped non-PII commerce-grain identity substrate used to resolve late verified revenue without session extension or cross-session identity reconstruction.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_attr_commerce_identity_tenant_provider_reference
            ON public.attribution_commerce_identities (tenant_id, provider, canonical_commerce_reference)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_attr_commerce_identity_tenant_last_observed
            ON public.attribution_commerce_identities (tenant_id, last_observed_at DESC)
        """
    )

    op.execute("ALTER TABLE public.attribution_commerce_identities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE ONLY public.attribution_commerce_identities FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_attribution_commerce_identities ON public.attribution_commerce_identities"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_attribution_commerce_identities
            ON public.attribution_commerce_identities
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )

    _grant_if_role_exists(
        "app_user",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.attribution_commerce_identities TO app_user",
    )
    _grant_if_role_exists(
        "app_rw",
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.attribution_commerce_identities TO app_rw",
    )
    _grant_if_role_exists(
        "app_ro",
        "GRANT SELECT ON TABLE public.attribution_commerce_identities TO app_ro",
    )


def downgrade() -> None:
    _revoke_if_role_exists(
        "app_ro",
        "REVOKE ALL ON TABLE public.attribution_commerce_identities FROM app_ro",
    )
    _revoke_if_role_exists(
        "app_rw",
        "REVOKE ALL ON TABLE public.attribution_commerce_identities FROM app_rw",
    )
    _revoke_if_role_exists(
        "app_user",
        "REVOKE ALL ON TABLE public.attribution_commerce_identities FROM app_user",
    )

    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_attribution_commerce_identities ON public.attribution_commerce_identities"
    )
    op.execute("DROP INDEX IF EXISTS public.idx_attr_commerce_identity_tenant_last_observed")
    op.execute("DROP INDEX IF EXISTS public.idx_attr_commerce_identity_tenant_provider_reference")
    op.execute("DROP TABLE IF EXISTS public.attribution_commerce_identities")  # CI:DESTRUCTIVE_OK - rollback for B2.3-P0 delayed-arrival commerce identity substrate.
