"""B1.4-P0: event payload authority lock for immutable attribution events.

Revision ID: 202603141700
Revises: 202603101530
Create Date: 2026-03-14 17:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202603141700"
down_revision: Union[str, None] = "202603101530"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_guard_attribution_events_payload_identity()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.raw_payload IS NULL THEN
                RETURN NEW;
            END IF;

            IF (
                jsonb_path_exists(NEW.raw_payload, '$.**.vendor_payload')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.billing_details')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body_sha256')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.raw_body_bytes')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.parse_error')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.device_fingerprint')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.user_agent')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.ip_hash')
                OR jsonb_path_exists(NEW.raw_payload, '$.**.session_id')
            ) THEN
                RAISE EXCEPTION
                    'privacy authority violation: forbidden identity/raw-envelope key in attribution_events.raw_payload';
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    op.execute(
        """
        COMMENT ON FUNCTION public.fn_guard_attribution_events_payload_identity() IS
            'B1.4-P0 payload authority lock. Blocks identity-proxy and raw-envelope keys from immutable attribution_events.raw_payload.';
        """
    )

    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_guard_attribution_events_payload_identity
        ON public.attribution_events;
        """
    )

    op.execute(
        """
        CREATE TRIGGER trg_guard_attribution_events_payload_identity
            BEFORE INSERT ON public.attribution_events
            FOR EACH ROW
            EXECUTE FUNCTION public.fn_guard_attribution_events_payload_identity();
        """
    )

    op.execute(
        """
        COMMENT ON TRIGGER trg_guard_attribution_events_payload_identity ON public.attribution_events IS
            'B1.4-P0 insert-time payload authority lock for immutable attribution events.';
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_guard_attribution_events_payload_identity
        ON public.attribution_events;
        """
    )
    op.execute("DROP FUNCTION IF EXISTS public.fn_guard_attribution_events_payload_identity();")

