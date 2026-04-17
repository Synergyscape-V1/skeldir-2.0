"""B2.1-P3 align allocation uniqueness with projection identity.

Revision ID: 202604171200
Revises: 202604160930
Create Date: 2026-04-17 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604171200"
down_revision: Union[str, None] = "202604160930"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy uniqueness only for rows without projection identity.
    op.execute(
        "DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_model_channel"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel
        ON attribution_allocations (tenant_id, event_id, model_version, channel_code)
        WHERE model_version IS NOT NULL AND recompute_job_id IS NULL
        """
    )

    # Projection-aware uniqueness for persisted deterministic projections.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_attribution_allocations_tenant_event_projection_channel
        ON attribution_allocations (tenant_id, event_id, recompute_job_id, channel_code)
        WHERE recompute_job_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_projection_channel"
    )
    op.execute(
        "DROP INDEX IF EXISTS idx_attribution_allocations_tenant_event_model_channel"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX idx_attribution_allocations_tenant_event_model_channel
        ON attribution_allocations (tenant_id, event_id, model_version, channel_code)
        WHERE model_version IS NOT NULL
        """
    )
