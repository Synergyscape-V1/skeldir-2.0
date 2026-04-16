"""B2.1-P3 add persisted recompute projection identity to allocations.

Revision ID: 202604160930
Revises: 202604130815
Create Date: 2026-04-16 09:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "202604160930"
down_revision: Union[str, None] = "202604130815"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "attribution_allocations",
        sa.Column(
            "recompute_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "attribution_allocations_recompute_job_id_fkey",
        "attribution_allocations",
        "attribution_recompute_jobs",
        ["recompute_job_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "idx_allocations_tenant_projection_channel",
        "attribution_allocations",
        ["tenant_id", "recompute_job_id", "model_type", "channel_code"],
    )


def downgrade() -> None:
    op.drop_index(  # CI:DESTRUCTIVE_OK - rollback path for B2.1-P3 projection identity migration.
        "idx_allocations_tenant_projection_channel",
        table_name="attribution_allocations",
    )
    op.drop_constraint(  # CI:DESTRUCTIVE_OK - rollback path for B2.1-P3 projection identity migration.
        "attribution_allocations_recompute_job_id_fkey",
        "attribution_allocations",
        type_="foreignkey",
    )
    op.drop_column(  # CI:DESTRUCTIVE_OK - rollback path for B2.1-P3 projection identity migration.
        "attribution_allocations",
        "recompute_job_id",
    )
