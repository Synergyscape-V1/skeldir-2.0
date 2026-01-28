"""B0.6 Phase 2: Platform connection and credential substrate.

Revision ID: 202601281200
Revises: 202601221200
Create Date: 2026-01-28 12:00:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202601281200"
down_revision: Union[str, None] = "202601221200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        """
        CREATE TABLE platform_connections (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            platform text NOT NULL,
            platform_account_id text NOT NULL,
            status text NOT NULL DEFAULT 'active'
                CHECK (status IN ('pending', 'active', 'disabled')),
            connection_metadata jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN platform_connections.connection_metadata IS
            'Optional non-PII metadata for platform connection context.'
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_platform_connections_tenant_platform_account
            ON platform_connections (tenant_id, platform, platform_account_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_platform_connections_tenant_platform_updated_at
            ON platform_connections (tenant_id, platform, updated_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE platform_connections IS
            'Tenant-scoped platform account bindings. Purpose: Store platform account identifiers per tenant. Data class: Non-PII. Ownership: Attribution service. RLS enabled for tenant isolation.'
        """
    )

    op.execute(
        """
        CREATE TABLE platform_credentials (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            platform_connection_id uuid NOT NULL REFERENCES platform_connections(id) ON DELETE CASCADE,
            platform text NOT NULL,
            encrypted_access_token bytea NOT NULL,
            encrypted_refresh_token bytea,
            expires_at timestamptz,
            scope text,
            token_type text,
            key_id text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX uq_platform_credentials_tenant_platform_connection
            ON platform_credentials (tenant_id, platform, platform_connection_id)
        """
    )
    op.execute(
        """
        CREATE INDEX idx_platform_credentials_tenant_platform_updated_at
            ON platform_credentials (tenant_id, platform, updated_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON TABLE platform_credentials IS
            'Encrypted platform credentials per tenant connection. Purpose: Store access/refresh tokens encrypted at rest. Data class: Security credential. Ownership: Attribution service. RLS enabled for tenant isolation.'
        """
    )

    for table_name in ("platform_connections", "platform_credentials"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name};
            CREATE POLICY tenant_isolation_policy ON {table_name}
                USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
            """
        )
        op.execute(
            f"""
            COMMENT ON POLICY tenant_isolation_policy ON {table_name} IS
                'RLS policy enforcing tenant isolation. Requires app.current_tenant_id to be set via set_config().'
            """
        )

    # Grants for application roles.
    for table_name in ("platform_connections", "platform_credentials"):
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {table_name} TO app_rw")
        op.execute(f"GRANT SELECT ON TABLE {table_name} TO app_ro")

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE platform_connections TO app_user;
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE platform_credentials TO app_user;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    for table_name in ("platform_credentials", "platform_connections"):
        op.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")  # CI:DESTRUCTIVE_OK - Downgrade rollback
