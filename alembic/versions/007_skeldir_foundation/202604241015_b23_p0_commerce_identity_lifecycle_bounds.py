"""B2.3-P0 commerce identity lifecycle bounds.

Revision ID: 202604241015
Revises: 202604231130
Create Date: 2026-04-24 10:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604241015"
down_revision: Union[str, None] = "202604231130"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_attr_commerce_identity_last_observed
            ON public.attribution_commerce_identities (last_observed_at ASC)
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities(
            max_delete integer DEFAULT 1000
        ) RETURNS integer
            LANGUAGE plpgsql
            AS $$
            DECLARE
                cutoff timestamptz := now() - interval '90 days';
                deleted_count integer := 0;
            BEGIN
                WITH doomed AS (
                    SELECT id
                    FROM public.attribution_commerce_identities
                    WHERE last_observed_at < cutoff
                    ORDER BY last_observed_at ASC
                    LIMIT GREATEST(max_delete, 1)
                )
                DELETE FROM public.attribution_commerce_identities target
                USING doomed
                WHERE target.id = doomed.id;

                GET DIAGNOSTICS deleted_count = ROW_COUNT;
                RETURN deleted_count;
            END;
            $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger()
        RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM public.fn_b23_p0_prune_attribution_commerce_identities(1000);
                RETURN NULL;
            END;
            $$;
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b23_p0_prune_attribution_commerce_identities
            ON public.attribution_commerce_identities
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_b23_p0_prune_attribution_commerce_identities
            AFTER INSERT OR UPDATE OF last_observed_at ON public.attribution_commerce_identities
            FOR EACH STATEMENT
            EXECUTE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger()
        """
    )

    op.execute("SELECT public.fn_b23_p0_prune_attribution_commerce_identities(500000)")


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b23_p0_prune_attribution_commerce_identities
            ON public.attribution_commerce_identities
        """
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.fn_b23_p0_prune_attribution_commerce_identities_trigger()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.fn_b23_p0_prune_attribution_commerce_identities(integer)"
    )
    op.execute("DROP INDEX IF EXISTS public.idx_attr_commerce_identity_last_observed")
