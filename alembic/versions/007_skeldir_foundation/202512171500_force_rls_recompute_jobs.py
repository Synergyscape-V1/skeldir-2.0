"""Force RLS on attribution_recompute_jobs for tenant isolation (B0.5.3.4)

Revision ID: 202512171500
Revises: 202512151410
Create Date: 2025-12-17 20:00:00

Purpose:
- Enforce RLS policies even for table owners on attribution_recompute_jobs.
- Prevents owner bypass of tenant isolation during worker-scoped recompute.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "202512171500"
down_revision: Union[str, None] = "202512151410"
branch_labels: Union[str, Sequence[str], None] = ("skeldir_foundation",)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Force RLS for attribution_recompute_jobs to avoid owner bypass."""
    op.execute("ALTER TABLE attribution_recompute_jobs FORCE ROW LEVEL SECURITY;")


def downgrade() -> None:
    """Allow disabling forced RLS (reverts to owner bypass behavior)."""
    op.execute("ALTER TABLE attribution_recompute_jobs NO FORCE ROW LEVEL SECURITY;")
