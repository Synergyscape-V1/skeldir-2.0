"""B0.6 Phase 3: Postgres realtime revenue cache + stampede prevention substrate.

Revision ID: 202601281230
Revises: 202601281200
Create Date: 2026-01-28 12:30:00
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202601281230"
down_revision: Union[str, None] = "202601281200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE revenue_cache_entries (
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            cache_key text NOT NULL,
            payload jsonb NOT NULL,
            data_as_of timestamptz NOT NULL,
            expires_at timestamptz NOT NULL,
            error_cooldown_until timestamptz,
            last_error_at timestamptz,
            last_error_message text,
            etag text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, cache_key)
        )
        """
    )

    op.execute(
        """
        COMMENT ON TABLE revenue_cache_entries IS
            'Tenant-scoped realtime revenue cache. Purpose: prevent platform stampede with Postgres-only coordination. Data class: non-PII. Ownership: Attribution service. RLS enabled for tenant isolation.'
        """
    )

    op.execute(
        """
        CREATE INDEX idx_revenue_cache_entries_expires_at
            ON revenue_cache_entries (expires_at)
        """
    )

    op.execute(
        """
        CREATE INDEX idx_revenue_cache_entries_error_cooldown
            ON revenue_cache_entries (error_cooldown_until)
        """
    )

    op.execute("ALTER TABLE revenue_cache_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revenue_cache_entries FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_policy ON revenue_cache_entries;
        CREATE POLICY tenant_isolation_policy ON revenue_cache_entries
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON revenue_cache_entries IS
            'RLS policy enforcing tenant isolation. Requires app.current_tenant_id to be set via set_config().'
        """
    )

    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE revenue_cache_entries TO app_rw")
    op.execute("GRANT SELECT ON TABLE revenue_cache_entries TO app_ro")

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE revenue_cache_entries TO app_user;
          END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS revenue_cache_entries CASCADE")  # CI:DESTRUCTIVE_OK - See docs/database/RUNBOOK-MIGRATION-POLICY.md
