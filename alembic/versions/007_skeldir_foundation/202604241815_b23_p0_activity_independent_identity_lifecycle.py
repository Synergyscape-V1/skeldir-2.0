"""B2.3-P0 activity-independent lifecycle bounds for durable commerce identities.

Revision ID: 202604241815
Revises: 202604241015
Create Date: 2026-04-24 18:15:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604241815"
down_revision: Union[str, None] = "202604241015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CRON_JOB_NAME = "b23_p0_prune_attribution_commerce_identities_hourly"
_CRON_SCHEDULE = "0 * * * *"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_cron")

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger()
        RETURNS trigger
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path = public
            AS $$
            BEGIN
                PERFORM public.fn_b23_p0_prune_attribution_commerce_identities(1000);
                RETURN NULL;
            END;
            $$;
        """
    )

    op.execute(
        f"""
        DO $$
        DECLARE
            existing_job_id bigint;
            scheduled_job_id bigint;
        BEGIN
            IF to_regnamespace('cron') IS NULL THEN
                RAISE EXCEPTION 'missing_required_schema:cron';
            END IF;

            SELECT jobid
            INTO existing_job_id
            FROM cron.job
            WHERE jobname = '{_CRON_JOB_NAME}'
            LIMIT 1;

            IF existing_job_id IS NOT NULL THEN
                PERFORM cron.unschedule(existing_job_id);
            END IF;

            SELECT cron.schedule(
                '{_CRON_JOB_NAME}',
                '{_CRON_SCHEDULE}',
                $cron$SELECT public.fn_b23_p0_prune_attribution_commerce_identities(1000);$cron$
            ) INTO scheduled_job_id;

            IF scheduled_job_id IS NULL THEN
                RAISE EXCEPTION 'failed_to_schedule_job:{_CRON_JOB_NAME}';
            END IF;
        END
        $$;
        """
    )

    op.execute("SELECT public.fn_b23_p0_prune_attribution_commerce_identities(500000)")


def downgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
            existing_job_id bigint;
        BEGIN
            IF to_regnamespace('cron') IS NULL THEN
                RETURN;
            END IF;

            SELECT jobid
            INTO existing_job_id
            FROM cron.job
            WHERE jobname = '{_CRON_JOB_NAME}'
            LIMIT 1;

            IF existing_job_id IS NOT NULL THEN
                PERFORM cron.unschedule(existing_job_id);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_b23_p0_prune_attribution_commerce_identities_trigger()
        RETURNS trigger
            LANGUAGE plpgsql
            SET search_path = public
            AS $$
            BEGIN
                PERFORM public.fn_b23_p0_prune_attribution_commerce_identities(1000);
                RETURN NULL;
            END;
            $$;
        """
    )
