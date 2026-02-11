"""Revoke direct runtime access to public.tenants.

Revision ID: 202602112130
Revises: 202602102050
Create Date: 2026-02-11 21:30:00

Rationale:
- Runtime webhook ingress must resolve tenant secrets through
  security.resolve_tenant_webhook_secrets(text), not direct table reads.
- 202602102050 introduced direct grants on public.tenants that regress
  least-privilege guarantees verified by B0.5.7-P3 integration checks.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "202602112130"
down_revision: Union[str, None] = "202602102050"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("REVOKE ALL ON TABLE tenants FROM app_user")
    op.execute("REVOKE ALL ON TABLE tenants FROM app_ro")
    op.execute("REVOKE ALL ON TABLE tenants FROM app_rw")


def downgrade() -> None:
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE tenants TO app_rw")
    op.execute("GRANT SELECT ON TABLE tenants TO app_ro")
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE tenants TO app_user")
