"""Phase 4 security closure: tenant RLS FORCE enforcement and DLQ quarantine lane.

Revision ID: 202602121130
Revises: 202602102050
Create Date: 2026-02-12 11:30:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602121130"
down_revision: Union[str, None] = "202602102050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drift guard: every tenant-scoped or user-scoped base table must have FORCE RLS.
    # We do not auto-generate policies here to avoid weakening stricter table-specific policies.
    op.execute(
        """
        DO $$
        DECLARE
            rec RECORD;
        BEGIN
            FOR rec IN
                WITH tenant_scoped AS (
                    SELECT c.oid, c.relname AS table_name
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_attribute a ON a.attrelid = c.oid
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'r'
                      AND a.attname = 'tenant_id'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                ),
                user_scoped AS (
                    SELECT c.oid, c.relname AS table_name
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    JOIN pg_attribute a ON a.attrelid = c.oid
                    JOIN pg_constraint con
                      ON con.conrelid = c.oid
                     AND con.contype = 'f'
                    JOIN pg_class refc ON refc.oid = con.confrelid
                    JOIN pg_namespace refn ON refn.oid = refc.relnamespace
                    WHERE n.nspname = 'public'
                      AND c.relkind = 'r'
                      AND a.attname = 'user_id'
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                      AND refn.nspname = 'public'
                      AND refc.relname = 'users'
                )
                SELECT DISTINCT table_name
                FROM (
                    SELECT table_name FROM tenant_scoped
                    UNION ALL
                    SELECT table_name FROM user_scoped
                ) scoped
            LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', rec.table_name);
                EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', rec.table_name);
            END LOOP;
        END $$;
        """
    )

    # Quarantine lane for unresolved tenant context.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dead_events_quarantine (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NULL REFERENCES tenants(id) ON DELETE SET NULL,
            source text NOT NULL,
            raw_payload jsonb NOT NULL,
            error_type text NOT NULL,
            error_code text NULL,
            error_message text NOT NULL,
            error_detail jsonb NOT NULL DEFAULT '{}'::jsonb,
            correlation_id uuid NULL,
            ingested_at timestamptz NOT NULL DEFAULT now(),
            created_by_role text NOT NULL DEFAULT current_user
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dead_events_quarantine_tenant_ingested_at
            ON dead_events_quarantine (tenant_id, ingested_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dead_events_quarantine_null_lane
            ON dead_events_quarantine (ingested_at DESC)
            WHERE tenant_id IS NULL;
        """
    )

    op.execute("ALTER TABLE dead_events_quarantine ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE dead_events_quarantine FORCE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS tenant_lane_select ON dead_events_quarantine")
    op.execute("DROP POLICY IF EXISTS tenant_lane_insert ON dead_events_quarantine")
    op.execute("DROP POLICY IF EXISTS quarantine_lane_insert ON dead_events_quarantine")
    op.execute("DROP POLICY IF EXISTS ops_quarantine_select ON dead_events_quarantine")

    op.execute(
        """
        CREATE POLICY tenant_lane_select ON dead_events_quarantine
            FOR SELECT
            TO app_user, app_rw, app_ro
            USING (
                tenant_id IS NOT NULL
                AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
            );
        """
    )
    op.execute(
        """
        CREATE POLICY tenant_lane_insert ON dead_events_quarantine
            FOR INSERT
            TO app_user, app_rw
            WITH CHECK (
                tenant_id IS NOT NULL
                AND tenant_id = current_setting('app.current_tenant_id', true)::uuid
            );
        """
    )
    op.execute(
        """
        CREATE POLICY quarantine_lane_insert ON dead_events_quarantine
            FOR INSERT
            TO app_user, app_rw
            WITH CHECK (tenant_id IS NULL);
        """
    )
    op.execute(
        """
        CREATE POLICY ops_quarantine_select ON dead_events_quarantine
            FOR SELECT
            TO PUBLIC
            USING (tenant_id IS NULL AND current_user = 'app_ops');
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ops') THEN
                EXECUTE 'GRANT USAGE ON SCHEMA public TO app_ops';
                EXECUTE 'GRANT SELECT ON TABLE dead_events_quarantine TO app_ops';
            END IF;
        END $$;
        """
    )
    op.execute("GRANT SELECT, INSERT ON TABLE dead_events_quarantine TO app_user")
    op.execute("GRANT SELECT, INSERT ON TABLE dead_events_quarantine TO app_rw")
    op.execute("GRANT SELECT ON TABLE dead_events_quarantine TO app_ro")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ops') THEN
                EXECUTE 'REVOKE ALL ON TABLE dead_events_quarantine FROM app_ops';
            END IF;
        END $$;
        """
    )
    op.execute("REVOKE ALL ON TABLE dead_events_quarantine FROM app_ro")
    op.execute("REVOKE ALL ON TABLE dead_events_quarantine FROM app_rw")
    op.execute("REVOKE ALL ON TABLE dead_events_quarantine FROM app_user")
    op.execute("DROP TABLE IF EXISTS dead_events_quarantine")  # CI:DESTRUCTIVE_OK - Quarantine lane rollback for Phase 4
