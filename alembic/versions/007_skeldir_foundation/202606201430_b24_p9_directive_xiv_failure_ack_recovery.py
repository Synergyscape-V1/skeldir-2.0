"""B2.4-P9 Directive XIV failure-ACK recovery.

Revision ID: 202606201430
Revises: 202606201300
Create Date: 2026-06-20 14:30:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202606201430"
down_revision = "202606201300"
branch_labels = None
depends_on = None


def _grant_if_role_exists(role: str, statement: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE {statement!r};
            END IF;
        END $$;
        """
    )


_RECOVERABLE_FAILURE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.b24_fail_fit_dispatch_recoverable(p_reason text)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_row record;
    v_terminal boolean;
    v_status text;
BEGIN
    SELECT *
    INTO v_row
    FROM public.b24_fit_dispatch_outbox outbox
    WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
      AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id)
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'b24_dispatch_recoverable_failure_fence_rejected';
    END IF;

    v_terminal := COALESCE(v_row.claim_count, 0) >= COALESCE(v_row.max_attempts, 1);
    v_status := CASE WHEN v_terminal THEN 'failed_terminal' ELSE 'failed_retryable' END;

    UPDATE public.bayesian_model_fits fit
    SET status = CASE WHEN v_terminal THEN 'failed' ELSE 'queued' END,
        fallback_applied = CASE WHEN v_terminal THEN true ELSE false END,
        fallback_reason = CASE
            WHEN v_terminal THEN COALESCE(NULLIF(p_reason, ''), 'worker_failure')
            ELSE NULL
        END,
        credible_interval_status = CASE
            WHEN v_terminal THEN 'not_available'
            ELSE fit.credible_interval_status
        END,
        diagnostic_status = CASE
            WHEN v_terminal THEN 'unavailable'
            ELSE fit.diagnostic_status
        END,
        diagnostic_failure_reason = CASE
            WHEN v_terminal THEN 'skipped_non_sampled'
            ELSE fit.diagnostic_failure_reason
        END,
        completed_at = CASE WHEN v_terminal THEN now() ELSE NULL END,
        updated_at = now()
    WHERE fit.tenant_id = v_row.tenant_id
      AND fit.id = v_row.fit_id
      AND fit.status IN ('pending', 'queued', 'running', 'persist_pending');

    UPDATE public.b24_fit_dispatch_outbox outbox
    SET status = v_status,
        terminal_reason = LEFT(
            'recoverable_ack:' || COALESCE(NULLIF(p_reason, ''), 'worker_failure'),
            512
        ),
        lease_owner = NULL,
        lease_capability_digest = NULL,
        lease_acquired_at = NULL,
        lease_expires_at = NULL,
        last_heartbeat_at = NULL,
        assigned_worker_generation = NULL,
        assignment_generation = assignment_generation + 1,
        assignment_expires_at = NULL,
        assignment_reason = 'failure_ack_recovery_required',
        next_recovery_at = now(),
        completed_at = CASE WHEN v_terminal THEN now() ELSE NULL END,
        updated_at = now()
    WHERE outbox.tenant_id = v_row.tenant_id
      AND outbox.id = v_row.id;

    RETURN v_status;
END
$$;
"""


def upgrade() -> None:
    op.execute(_RECOVERABLE_FAILURE_FUNCTION)
    for role in ("app_worker", "app_user"):
        _grant_if_role_exists(
            role,
            (
                "GRANT EXECUTE ON FUNCTION "
                "public.b24_fail_fit_dispatch_recoverable(text) TO "
                f"{role}"
            ),
        )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_fail_fit_dispatch_recoverable(text)"
    )  # CI:DESTRUCTIVE_OK - rollback removes Directive XIV recoverable failure API.
