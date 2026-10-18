"""Finalize LLM write shape with user scoping and breaker tables

Revision ID: 202602051200
Revises: 202601131610
Create Date: 2026-02-05 12:00:00

Migration Description:
Brings LLM persistence to the B0.7-P1 target write shape by:
- Adding user_id/provider/distillation metadata columns to llm_api_calls
- Making was_cached non-null with default
- Adding per-user rollups to llm_monthly_costs (tenant+user+month)
- Creating breaker and hourly shutoff state tables
- Tightening RLS policies for user-scoped tables
"""
from typing import Sequence, Union

from alembic import op

revision: str = "202602051200"
down_revision: Union[str, None] = "202601131610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # --------------------------------------------------------------------
    # llm_api_calls: add user/provider/distillation + metadata refs
    # --------------------------------------------------------------------
    op.execute(
        f"ALTER TABLE llm_api_calls ADD COLUMN user_id UUID NOT NULL DEFAULT '{SYSTEM_USER_ID}'"
    )
    op.execute("ALTER TABLE llm_api_calls ADD COLUMN provider TEXT NOT NULL DEFAULT 'stub'")
    op.execute(
        "ALTER TABLE llm_api_calls ADD COLUMN distillation_eligible BOOLEAN NOT NULL DEFAULT false"
    )
    op.execute("ALTER TABLE llm_api_calls ADD COLUMN request_metadata_ref JSONB")
    op.execute("ALTER TABLE llm_api_calls ADD COLUMN response_metadata_ref JSONB")
    op.execute("ALTER TABLE llm_api_calls ADD COLUMN reasoning_trace_ref JSONB")

    op.execute("ALTER TABLE llm_api_calls ALTER COLUMN was_cached SET DEFAULT false")
    op.execute("UPDATE llm_api_calls SET was_cached = false WHERE was_cached IS NULL")
    op.execute("ALTER TABLE llm_api_calls ALTER COLUMN was_cached SET NOT NULL")

    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_calls_tenant_user_created_at "
        "ON llm_api_calls(tenant_id, user_id, created_at DESC)"
    )

    # --------------------------------------------------------------------
    # llm_monthly_costs: per-user rollups + unique constraint update
    # --------------------------------------------------------------------
    op.execute(
        f"ALTER TABLE llm_monthly_costs ADD COLUMN user_id UUID NOT NULL DEFAULT '{SYSTEM_USER_ID}'"
    )
    op.execute(
        "ALTER TABLE llm_monthly_costs DROP CONSTRAINT IF EXISTS llm_monthly_costs_tenant_id_month_key"  # CI:DESTRUCTIVE_OK - constraint rename path
    )
    op.execute(
        "ALTER TABLE llm_monthly_costs DROP CONSTRAINT IF EXISTS uq_llm_monthly_costs_tenant_month"  # CI:DESTRUCTIVE_OK - constraint rename path
    )
    op.execute(
        "ALTER TABLE llm_monthly_costs "
        "ADD CONSTRAINT uq_llm_monthly_costs_tenant_user_month UNIQUE (tenant_id, user_id, month)"
    )
    op.execute("DROP INDEX IF EXISTS idx_llm_monthly_tenant_month")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_monthly_tenant_user_month "
        "ON llm_monthly_costs(tenant_id, user_id, month DESC)"
    )

    # --------------------------------------------------------------------
    # New breaker state tables
    # --------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE llm_breaker_state (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            breaker_key TEXT NOT NULL,
            state TEXT NOT NULL CHECK (state IN ('closed', 'open', 'half_open')),
            failure_count INTEGER NOT NULL DEFAULT 0 CHECK (failure_count >= 0),
            opened_at TIMESTAMPTZ,
            last_trip_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(tenant_id, user_id, breaker_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_llm_breaker_state_tenant_user_updated "
        "ON llm_breaker_state(tenant_id, user_id, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE llm_hourly_shutoff_state (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            hour_start TIMESTAMPTZ NOT NULL,
            is_shutoff BOOLEAN NOT NULL DEFAULT false,
            reason TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(tenant_id, user_id, hour_start)
        )
        """
    )
    op.execute(
        "CREATE INDEX idx_llm_hourly_shutoff_tenant_user_hour "
        "ON llm_hourly_shutoff_state(tenant_id, user_id, hour_start DESC)"
    )

    # --------------------------------------------------------------------
    # RLS policy upgrades for user-scoped tables
    # --------------------------------------------------------------------
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON llm_api_calls")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON llm_api_calls
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::uuid
                AND user_id = current_setting('app.current_user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.current_tenant_id', true)::uuid
                AND user_id = current_setting('app.current_user_id', true)::uuid
            )
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON llm_api_calls IS
            'RLS policy enforcing tenant + user isolation. Requires app.current_tenant_id and app.current_user_id.'
        """
    )

    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON llm_monthly_costs")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON llm_monthly_costs
            USING (
                tenant_id = current_setting('app.current_tenant_id', true)::uuid
                AND user_id = current_setting('app.current_user_id', true)::uuid
            )
            WITH CHECK (
                tenant_id = current_setting('app.current_tenant_id', true)::uuid
                AND user_id = current_setting('app.current_user_id', true)::uuid
            )
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON llm_monthly_costs IS
            'RLS policy enforcing tenant + user isolation. Requires app.current_tenant_id and app.current_user_id.'
        """
    )

    # Enable/force RLS for new tables + policies
    for table_name in ("llm_breaker_state", "llm_hourly_shutoff_state"):
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_policy ON {table_name}
                USING (
                    tenant_id = current_setting('app.current_tenant_id', true)::uuid
                    AND user_id = current_setting('app.current_user_id', true)::uuid
                )
                WITH CHECK (
                    tenant_id = current_setting('app.current_tenant_id', true)::uuid
                    AND user_id = current_setting('app.current_user_id', true)::uuid
                )
            """
        )
        op.execute(
            f"""
            COMMENT ON POLICY tenant_isolation_policy ON {table_name} IS
                'RLS policy enforcing tenant + user isolation. Requires app.current_tenant_id and app.current_user_id.'
            """
        )


def downgrade() -> None:
    # Drop new tables
    op.execute("DROP TABLE IF EXISTS llm_hourly_shutoff_state CASCADE")  # CI:DESTRUCTIVE_OK
    op.execute("DROP TABLE IF EXISTS llm_breaker_state CASCADE")  # CI:DESTRUCTIVE_OK

    # Restore llm_monthly_costs unique + drop user_id column
    op.execute("DROP INDEX IF EXISTS idx_llm_monthly_tenant_user_month")
    op.execute(
        "ALTER TABLE llm_monthly_costs DROP CONSTRAINT IF EXISTS uq_llm_monthly_costs_tenant_user_month"  # CI:DESTRUCTIVE_OK - downgrade rollback
    )
    op.execute(
        "ALTER TABLE llm_monthly_costs ADD CONSTRAINT llm_monthly_costs_tenant_id_month_key UNIQUE (tenant_id, month)"
    )
    # Restore the pre-202602051200 tenant-only RLS policy before dropping
    # user_id: the upgrade replaced this policy with a user-scoped
    # predicate, and PostgreSQL refuses to drop a column a live policy
    # depends on (detected by the B0.3 schema-closure gate's
    # downgrade-from-migrated path; previously masked because lanes
    # downgraded from empty and the step was a no-op).
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON llm_monthly_costs")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON llm_monthly_costs
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON llm_monthly_costs IS
            'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().'
        """
    )
    # The upgrade dropped this index; recreate it so the downgraded
    # schema matches the pre-202602051200 construction.
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_llm_monthly_tenant_month "
        "ON llm_monthly_costs(tenant_id, month DESC)"
    )
    op.execute("ALTER TABLE llm_monthly_costs DROP COLUMN IF EXISTS user_id")  # CI:DESTRUCTIVE_OK - downgrade rollback

    # Drop added columns from llm_api_calls
    op.execute("DROP INDEX IF EXISTS idx_llm_calls_tenant_user_created_at")
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS reasoning_trace_ref")  # CI:DESTRUCTIVE_OK - downgrade rollback
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS response_metadata_ref")  # CI:DESTRUCTIVE_OK - downgrade rollback
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS request_metadata_ref")  # CI:DESTRUCTIVE_OK - downgrade rollback
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS distillation_eligible")  # CI:DESTRUCTIVE_OK - downgrade rollback
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS provider")  # CI:DESTRUCTIVE_OK - downgrade rollback
    # Same policy-before-column ordering fix as llm_monthly_costs above.
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON llm_api_calls")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON llm_api_calls
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        COMMENT ON POLICY tenant_isolation_policy ON llm_api_calls IS
            'RLS policy enforcing tenant isolation. Purpose: Prevent cross-tenant data access. Requires app.current_tenant_id to be set via set_config().'
        """
    )
    op.execute("ALTER TABLE llm_api_calls DROP COLUMN IF EXISTS user_id")  # CI:DESTRUCTIVE_OK - downgrade rollback

    op.execute("ALTER TABLE llm_api_calls ALTER COLUMN was_cached DROP NOT NULL")
