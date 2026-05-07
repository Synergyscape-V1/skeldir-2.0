"""B2.3-P6 downstream-readiness attribution FK enforcement.

Revision ID: 202605071200
Revises: 202605061200
Create Date: 2026-05-07 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202605071200"
down_revision: Union[str, None] = "202605061200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD CONSTRAINT ck_b23_match_verdicts_matched_requires_attribution_event
            CHECK (
                status NOT IN ('matched_provisional', 'matched_confirmed', 'adjusted')
                OR attribution_event_id IS NOT NULL
            ) NOT VALID
        """
    )
    op.execute(
        """
        COMMENT ON CONSTRAINT ck_b23_match_verdicts_matched_requires_attribution_event
        ON public.b23_match_verdicts IS
            'B2.3-P6 downstream-readiness guard: matched/post-match verdict states must carry a durable attribution_event_id for B2.4 consumption.'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_matched_requires_attribution_event
        """
    )
