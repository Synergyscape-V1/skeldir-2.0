"""B1.3-P3: durable platform credential lifecycle metadata extension.

Revision ID: 202603101530
Revises: 202603101000
Create Date: 2026-03-10 15:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603101530"
down_revision: Union[str, None] = "202603101000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.platform_credentials
            ADD COLUMN IF NOT EXISTS next_refresh_due_at timestamptz,
            ADD COLUMN IF NOT EXISTS lifecycle_status text NOT NULL DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS refresh_failure_count integer NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS last_failure_class text,
            ADD COLUMN IF NOT EXISTS last_failure_at timestamptz,
            ADD COLUMN IF NOT EXISTS last_refresh_at timestamptz,
            ADD COLUMN IF NOT EXISTS revoked_at timestamptz
        """
    )

    op.execute(
        """
        UPDATE public.platform_credentials
        SET next_refresh_due_at = COALESCE(next_refresh_due_at, expires_at)
        WHERE next_refresh_due_at IS NULL
          AND expires_at IS NOT NULL
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN public.platform_credentials.next_refresh_due_at IS
            'Queryable scheduler watermark for next provider refresh attempt.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.platform_credentials.lifecycle_status IS
            'Durable provider credential lifecycle state: active, degraded, or revoked.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.platform_credentials.refresh_failure_count IS
            'Count of consecutive refresh failures for this credential.'
        """
    )

    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_lifecycle_status_valid")  # CI:DESTRUCTIVE_OK - idempotent constraint replacement in B1.3-P3
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_refresh_failure_count_nonnegative")  # CI:DESTRUCTIVE_OK - idempotent constraint replacement in B1.3-P3
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_revoked_status_consistency")  # CI:DESTRUCTIVE_OK - idempotent constraint replacement in B1.3-P3
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_revoked_refresh_due_null")  # CI:DESTRUCTIVE_OK - idempotent constraint replacement in B1.3-P3

    op.execute(
        """
        ALTER TABLE public.platform_credentials
            ADD CONSTRAINT ck_platform_credentials_lifecycle_status_valid
                CHECK (lifecycle_status IN ('active', 'degraded', 'revoked')),
            ADD CONSTRAINT ck_platform_credentials_refresh_failure_count_nonnegative
                CHECK (refresh_failure_count >= 0),
            ADD CONSTRAINT ck_platform_credentials_revoked_status_consistency
                CHECK ((revoked_at IS NULL) OR (lifecycle_status = 'revoked')),
            ADD CONSTRAINT ck_platform_credentials_revoked_refresh_due_null
                CHECK ((lifecycle_status <> 'revoked') OR (next_refresh_due_at IS NULL))
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_platform_credentials_refresh_due
            ON public.platform_credentials (tenant_id, lifecycle_status, next_refresh_due_at ASC)
            WHERE next_refresh_due_at IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_platform_credentials_tenant_lifecycle_updated
            ON public.platform_credentials (tenant_id, lifecycle_status, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_platform_credentials_tenant_revoked_at
            ON public.platform_credentials (tenant_id, revoked_at DESC)
            WHERE revoked_at IS NOT NULL
        """
    )

    # Reassert tenant isolation boundary for modified durable table.
    op.execute("ALTER TABLE public.platform_credentials ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE public.platform_credentials FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON public.platform_credentials")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON public.platform_credentials
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.idx_platform_credentials_tenant_revoked_at")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle index
    op.execute("DROP INDEX IF EXISTS public.idx_platform_credentials_tenant_lifecycle_updated")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle index
    op.execute("DROP INDEX IF EXISTS public.idx_platform_credentials_refresh_due")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 scheduler index

    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_revoked_refresh_due_null")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle constraint
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_revoked_status_consistency")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle constraint
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_refresh_failure_count_nonnegative")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle constraint
    op.execute("ALTER TABLE public.platform_credentials DROP CONSTRAINT IF EXISTS ck_platform_credentials_lifecycle_status_valid")  # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 lifecycle constraint

    op.execute(
        """
        ALTER TABLE public.platform_credentials
            DROP COLUMN IF EXISTS revoked_at, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS last_refresh_at, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS last_failure_at, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS last_failure_class, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS refresh_failure_count, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS lifecycle_status, -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
            DROP COLUMN IF EXISTS next_refresh_due_at -- # CI:DESTRUCTIVE_OK - rollback for B1.3-P3 durable lifecycle columns
        """
    )
