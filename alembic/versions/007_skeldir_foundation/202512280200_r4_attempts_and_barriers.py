"""R4-FIX: Add attempt tracking + crash barrier tables.

R4 acceptance requires mechanical proof in CI logs that:
- retries actually executed (not just configured)
- crash-after-write/pre-ack involves kill → restart → redelivery (same task_id)

These tables provide an auditable DB truth surface for the harness.
Data class: Non-PII. Tenant-scoped with RLS enforced via app.current_tenant_id.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512280200"
down_revision: Union[str, None] = "202512280100"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS r4_task_attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            task_id text NOT NULL,
            scenario text NOT NULL,
            attempt_no integer NOT NULL CHECK (attempt_no >= 1),
            worker_pid integer,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_r4_task_attempts_tenant_task_attempt
        ON r4_task_attempts (tenant_id, task_id, attempt_no);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_r4_task_attempts_tenant_task
        ON r4_task_attempts (tenant_id, task_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_r4_task_attempts_scenario_created_at
        ON r4_task_attempts (scenario, created_at DESC);
        """
    )
    op.execute(
        """
        COMMENT ON TABLE r4_task_attempts IS
        'R4 harness attempt ledger. Purpose: Prove retries/redelivery executed. Data class: Non-PII. Tenant-scoped via RLS.';
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS r4_crash_barriers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            task_id text NOT NULL,
            scenario text NOT NULL,
            attempt_no integer NOT NULL CHECK (attempt_no >= 1),
            worker_pid integer,
            wrote_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_r4_crash_barriers_tenant_task_attempt
        ON r4_crash_barriers (tenant_id, task_id, attempt_no);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_r4_crash_barriers_scenario_wrote_at
        ON r4_crash_barriers (scenario, wrote_at DESC);
        """
    )
    op.execute(
        """
        COMMENT ON TABLE r4_crash_barriers IS
        'R4 crash barrier rows written after DB side-effect commit but before ack. Purpose: Prove crash-after-write/pre-ack physics. Data class: Non-PII. Tenant-scoped via RLS.';
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.r4_task_attempts TO app_user;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.r4_crash_barriers TO app_user;
            END IF;
        END
        $$;
        """
    )

    for table_name in ["r4_task_attempts", "r4_crash_barriers"]:
        op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name};
            CREATE POLICY tenant_isolation_policy ON {table_name}
            FOR ALL
            TO app_user
            USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
            """
        )


def downgrade() -> None:
    for table_name in ["r4_crash_barriers", "r4_task_attempts"]:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table_name};")
    op.execute("DROP TABLE IF EXISTS r4_crash_barriers CASCADE;")
    op.execute("DROP TABLE IF EXISTS r4_task_attempts CASCADE;")

