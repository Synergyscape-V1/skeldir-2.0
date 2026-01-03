"""Anchor post-merge revision for unambiguous downgrade.

Revision ID: 202601031930
Revises: de648b76dd68
Create Date: 2026-01-03 19:30:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "202601031930"
down_revision: Union[str, None] = "de648b76dd68"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op anchor revision to make downgrade steps unambiguous."""


def downgrade() -> None:
    """No-op anchor revision to make downgrade steps unambiguous."""

