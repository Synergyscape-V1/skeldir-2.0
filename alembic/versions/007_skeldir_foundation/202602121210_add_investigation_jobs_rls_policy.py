"""Add missing RLS policy for investigation_jobs.

Revision ID: 202602121210
Revises: 202602121130
Create Date: 2026-02-12 12:10:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602121210"
down_revision: Union[str, None] = "202602121130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE investigation_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE investigation_jobs FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON investigation_jobs")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON investigation_jobs
            AS PERMISSIVE
            FOR ALL
            TO app_user, app_rw, app_ro
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON investigation_jobs")

