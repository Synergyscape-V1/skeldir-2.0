"""B2.6-P2 C19: admit the result transport to P2 FAILURE telemetry.

The Corrective-VI result-integrity fence
(public.b26_p2_enforce_result_integrity) closes FAILURE telemetry for
exactly the P2 execution namespace to non-transport principals: its
contract comment names transports as the legitimate writer, and the VI
battery pins the refusal for the issuer/API principal
(b26_p2_result_failure_forge_refused). The bypass list itself, however,
omitted the one principal that actually performs runtime result stores:
app_celery_transport (the Celery database result backend DSN).

Observed consequence (B2.5-P13 C19 context-robust closure red
39099129201 / job 117591590001; identical precedent 38977098492 /
job 117230191903): a P2 worker task failed lawfully -- the X8/X9
fail-closed receipt refusal
b26_p2_receipt_effect_refused:scope_not_canonical -- and celery tried
to persist that FAILURE as app_celery_transport. The fence then ran
the directory probe as that principal, which holds no SELECT on
b26_p2_task_authority_directory, and the probe raised a raw
permission-denied from inside the BEFORE trigger. The database backend
retried _store_result with backoff for ~8 minutes on --pool=solo
workers, wedging both C19 workers (CRITICAL Unrecoverable error) and
starving the topology proof (zero confirmations at the 480 s
pipeline timeout).

This revision re-issues the fence unchanged except for adding
app_celery_transport to the transport bypass list: result telemetry
(including the corroboration-only FAILURE state) flows for the
transport principal, while every non-transport principal keeps the
directory probe and the refusal. The status gate, the namespace gate,
and the dispatch pre-registration closure are untouched, so non-P2
namespaces and forged P2 FAILURE telemetry from runtime callers behave
exactly as before. Downgrade restores the VI body byte-for-byte
(transport loses the bypass; stores it performs return to the
probe-and-refuse path).
"""

from __future__ import annotations

from alembic import op

revision = "202610180001"
down_revision = "202609300009"


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_result_integrity()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _is_p2_task boolean;
        BEGIN
            IF NEW.status IS DISTINCT FROM 'FAILURE' THEN
                RETURN NEW;
            END IF;
            IF current_user IN (
                'migration_owner', 'postgres',
                'app_worker', 'app_relay', 'app_beat',
                'app_celery_transport'
            ) THEN
                RETURN NEW;
            END IF;
            SELECT EXISTS (
                SELECT 1 FROM public.b26_p2_task_authority_directory AS dir
                 WHERE dir.task_id = NEW.task_id
            ) INTO _is_p2_task;
            IF NOT _is_p2_task THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'b26_p2_result_failure_forge_refused'
                USING ERRCODE = '42501';
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_result_integrity()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _is_p2_task boolean;
        BEGIN
            IF NEW.status IS DISTINCT FROM 'FAILURE' THEN
                RETURN NEW;
            END IF;
            IF current_user IN (
                'migration_owner', 'postgres',
                'app_worker', 'app_relay', 'app_beat'
            ) THEN
                RETURN NEW;
            END IF;
            SELECT EXISTS (
                SELECT 1 FROM public.b26_p2_task_authority_directory AS dir
                 WHERE dir.task_id = NEW.task_id
            ) INTO _is_p2_task;
            IF NOT _is_p2_task THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'b26_p2_result_failure_forge_refused'
                USING ERRCODE = '42501';
        END $$;
        """
    )
