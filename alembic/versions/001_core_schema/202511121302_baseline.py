"""Schema Foundation Baseline—Pre-B0.3

Revision ID: baseline
Revises: 
Create Date: 2025-11-12 13:02:00

This is the initial baseline migration for B0.3 governance baseline.
It represents the zero-state schema (empty database) before any domain tables are implemented.

This migration is intentionally empty - it only establishes the migration tracking table.
No DDL is applied in this baseline.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'baseline'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Baseline migration - no-op.
    
    This migration establishes the baseline for future schema changes.
    The alembic_version table will be created automatically by Alembic
    to track migration state.
    
    No DDL is applied in this baseline migration.
    """
    pass


def downgrade() -> None:
    """
    Baseline rollback - no-op.
    
    Rolling back the baseline returns the database to its initial state
    (before any migrations were applied).
    """
    pass




