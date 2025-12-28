"""R4: Create worker_side_effects table for crash/idempotency proofs.

This table is used by the R4 harness to prove:
- crash-after-write/pre-ack redelivery does not double-apply side effects
- sentinel tasks continue to execute after runaway timeouts

Data class: Non-PII. Tenant-scoped with RLS enforced via app.current_tenant_id.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512280100"
down_revision: Union[str, None] = "202512271910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS worker_side_effects (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            task_id text NOT NULL,
            correlation_id uuid,
            effect_key text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_worker_side_effects_tenant_task_id
        ON worker_side_effects (tenant_id, task_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_worker_side_effects_tenant_created_at
        ON worker_side_effects (tenant_id, created_at DESC);
        """
    )

    op.execute(
        """
        COMMENT ON TABLE worker_side_effects IS
        'Tenant-scoped worker side effects. Purpose: Idempotency/crash-safety proofs for background tasks. Data class: Non-PII. RLS enforced.';
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN worker_side_effects.task_id IS
        'Celery task_id used as idempotency key for crash-safe re-delivery.';
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.worker_side_effects TO app_user;
            END IF;
        END
        $$;
        """
    )

    op.execute("ALTER TABLE worker_side_effects ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE worker_side_effects FORCE ROW LEVEL SECURITY;")
    op.execute(
        """
        DROP POLICY IF EXISTS tenant_isolation_policy ON worker_side_effects;
        CREATE POLICY tenant_isolation_policy ON worker_side_effects
        FOR ALL
        TO app_user
        USING (tenant_id = current_setting('app.current_tenant_id', true)::UUID)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::UUID);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON worker_side_effects;")
    op.execute("DROP TABLE IF EXISTS worker_side_effects CASCADE;")

