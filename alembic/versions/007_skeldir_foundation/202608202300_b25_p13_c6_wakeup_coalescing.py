"""B2.5-P13 C6 coalesce planner wakeups off the ingestion hot path.

Revision ID: 202608202300
Revises: 202608201200
Create Date: 2026-08-20 23:00:00.000000

Pending wakeups already represent all unplanned dirty events for a tenant.  A
revision change is only required when new work arrives while a planner owns a
lease; in that case the lease is invalidated and the row becomes pending again.
This preserves crash/replay liveness without serializing every ingestion
transaction on one tenant-scoped wakeup row.
"""

from __future__ import annotations

from alembic import op


revision = "202608202300"
down_revision = "202608201200"
branch_labels = None
depends_on = None


_COALESCED_SIGNAL_SQL = """
CREATE FUNCTION public.b24_signal_fit_planner_wakeup_coalesced()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    IF NEW.status IN ('pending', 'authority_retry_ready')
       AND (
            TG_OP = 'INSERT'
            OR OLD.status IS DISTINCT FROM NEW.status
       ) THEN
        INSERT INTO public.b24_fit_planner_wakeups (
            tenant_id, observed_at
        ) VALUES (NEW.tenant_id, NEW.observed_at)
        ON CONFLICT (tenant_id) DO NOTHING;

        IF NOT FOUND THEN
            UPDATE public.b24_fit_planner_wakeups
            SET wakeup_revision = wakeup_revision + 1,
                status = 'pending',
                lease_owner = NULL,
                lease_expires_at = NULL,
                observed_at = LEAST(observed_at, NEW.observed_at),
                updated_at = now()
            WHERE tenant_id = NEW.tenant_id
              AND status = 'leased';
        END IF;
    END IF;
    RETURN NEW;
END
$$;
"""


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE 'GRANT CREATE ON SCHEMA public TO app_worker';
            END IF;
        END
        $$;
        """
    )
    op.execute(_COALESCED_SIGNAL_SQL)
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE 'ALTER FUNCTION '
                        'public.b24_signal_fit_planner_wakeup_coalesced() '
                        'OWNER TO app_worker';
                EXECUTE 'REVOKE CREATE ON SCHEMA public FROM app_worker';
            END IF;
        END
        $$;
        DROP TRIGGER IF EXISTS trg_b24_signal_fit_planner_wakeup
            ON public.b24_dirty_events;
        CREATE TRIGGER trg_b24_signal_fit_planner_wakeup
        AFTER INSERT OR UPDATE OF status ON public.b24_dirty_events
        FOR EACH ROW EXECUTE FUNCTION
            public.b24_signal_fit_planner_wakeup_coalesced();
        REVOKE ALL ON FUNCTION public.b24_signal_fit_planner_wakeup_coalesced()
            FROM PUBLIC, app_user, app_rw, app_ro;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b24_signal_fit_planner_wakeup
            ON public.b24_dirty_events;
        CREATE TRIGGER trg_b24_signal_fit_planner_wakeup
        AFTER INSERT OR UPDATE OF status ON public.b24_dirty_events
        FOR EACH ROW EXECUTE FUNCTION public.b24_signal_fit_planner_wakeup();
        DROP FUNCTION public.b24_signal_fit_planner_wakeup_coalesced();
        """
    )
