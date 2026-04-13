"""B2.1-P1 add replay freeze boundary for deterministic recompute identity.

Revision ID: 202604130815
Revises: 202603301230
Create Date: 2026-04-13 08:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202604130815"
down_revision: Union[str, None] = "202603301230"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attribution_recompute_jobs",
        sa.Column(
            "replay_event_created_ceiling",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        """
        UPDATE attribution_recompute_jobs
        SET replay_event_created_ceiling = COALESCE(
            replay_event_created_ceiling,
            started_at,
            created_at,
            now()
        )
        """
    )
    op.alter_column(
        "attribution_recompute_jobs",
        "replay_event_created_ceiling",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.drop_column("attribution_recompute_jobs", "replay_event_created_ceiling")
