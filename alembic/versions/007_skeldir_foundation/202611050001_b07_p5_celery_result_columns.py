"""B0.7-P5 Celery 5.6 database result metadata columns.

Revision ID: 202611050001
Revises: 202610280001
Create Date: 2026-11-05
"""

from __future__ import annotations

from alembic import op


revision = "202611050001"
down_revision = "202610280001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.celery_taskmeta"
        " ADD COLUMN IF NOT EXISTS children BYTEA,"
        " ADD COLUMN IF NOT EXISTS queue VARCHAR(155),"
        " ADD COLUMN IF NOT EXISTS stamps BYTEA"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.celery_taskmeta"
        " DROP COLUMN IF EXISTS stamps,"
        " DROP COLUMN IF EXISTS queue,"
        " DROP COLUMN IF EXISTS children"
    )
