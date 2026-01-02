"""Merge skeldir_foundation heads

Revision ID: de648b76dd68
Revises: 202512241930, 202512301930
Create Date: 2026-01-02 09:33:06.238582

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de648b76dd68'
down_revision: Union[str, None] = ('202512241930', '202512301930')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass








