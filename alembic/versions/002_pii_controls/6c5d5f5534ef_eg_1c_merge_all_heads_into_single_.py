"""EG-1C: Merge all heads into single canonical head

Revision ID: 6c5d5f5534ef
Revises: e9b7435efea6, 202512091100, 202512171700
Create Date: 2025-12-19 19:12:48.687188

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6c5d5f5534ef'
down_revision: Union[str, None] = ('e9b7435efea6', '202512091100', '202512171700')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass








