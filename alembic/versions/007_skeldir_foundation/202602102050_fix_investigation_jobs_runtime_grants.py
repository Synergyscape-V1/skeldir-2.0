"""Grant runtime privileges for investigation_jobs.

Revision ID: 202602102050
Revises: 202602101300
Create Date: 2026-02-10 20:50:00
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602102050"
down_revision: Union[str, None] = "202602101300"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # investigation_jobs is part of centaur state transitions and requires runtime updates.
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE investigation_jobs TO app_rw")
    op.execute("GRANT SELECT ON TABLE investigation_jobs TO app_ro")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE investigation_jobs TO app_user")
    # tenant builders and contract guards seed test tenants under runtime identity.
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE tenants TO app_rw")
    op.execute("GRANT SELECT ON TABLE tenants TO app_ro")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE tenants TO app_user")


def downgrade() -> None:
    op.execute("REVOKE ALL ON TABLE tenants FROM app_user")
    op.execute("REVOKE ALL ON TABLE tenants FROM app_ro")
    op.execute("REVOKE ALL ON TABLE tenants FROM app_rw")
    op.execute("REVOKE ALL ON TABLE investigation_jobs FROM app_user")
    op.execute("REVOKE ALL ON TABLE investigation_jobs FROM app_ro")
    op.execute("REVOKE ALL ON TABLE investigation_jobs FROM app_rw")
