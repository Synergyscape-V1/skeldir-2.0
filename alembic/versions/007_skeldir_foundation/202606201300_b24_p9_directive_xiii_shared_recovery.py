"""B2.4-P9 Directive XIII shared eligible-worker recovery.

Revision ID: 202606201300
Revises: 202606181200
Create Date: 2026-06-20 13:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202606201300"
down_revision = "202606181200"
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


_CLAIM_FUNCTION_SHARED_RECOVERY = """
CREATE OR REPLACE FUNCTION public.b24_claim_fit_dispatch(
    p_dispatch_id uuid,
    p_fit_id uuid,
    p_task_name text,
    p_attempt_id uuid,
    p_payload_hash text,
    p_worker_generation text,
    p_worker_pid integer,
    p_worker_process_token text,
    p_recovery_generation integer DEFAULT 0,
    p_lease_seconds integer DEFAULT 330
)
RETURNS TABLE (
    outcome text,
    tenant_id uuid,
    fit_id uuid,
    dispatch_id uuid,
    attempt_id uuid,
    claim_epoch integer,
    lease_capability text,
    lease_expires_at timestamp with time zone
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_row public.b24_fit_dispatch_outbox%ROWTYPE;
    v_lease text;
    v_lease_digest text;
    v_next_epoch integer;
    v_lease_seconds integer := LEAST(GREATEST(COALESCE(p_lease_seconds, 330), 30), 900);
    v_outcome text;
    v_shared_recovery_eligible boolean;
BEGIN
    PERFORM set_config('app.b24_worker_authority_access', 'on', true);
    PERFORM set_config('app.b24_dispatch_claim_access', 'on', true);

    IF NOT EXISTS (
        SELECT 1
        FROM public.b24_worker_process_authority auth
        WHERE auth.generation_id = p_worker_generation
          AND auth.pid = p_worker_pid
          AND auth.process_token_digest = public.b24_sha256_text(p_worker_process_token)
          AND auth.status = 'active'
          AND auth.revoked_at IS NULL
          AND auth.expires_at > now()
    ) THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    SELECT *
    INTO v_row
    FROM public.b24_fit_dispatch_outbox outbox
    WHERE outbox.id = p_dispatch_id
      AND outbox.fit_id = p_fit_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    v_shared_recovery_eligible := (
        COALESCE(v_row.recovery_generation, 0) > 0
        AND COALESCE(p_recovery_generation, 0) = COALESCE(v_row.recovery_generation, 0)
        AND v_row.assigned_worker_generation IS NULL
        AND v_row.assignment_reason = 'recovery_shared_eligible'
    );

    IF v_row.fit_id <> p_fit_id
       OR v_row.task_name <> p_task_name
       OR v_row.attempt_id <> p_attempt_id
       OR v_row.payload_hash <> p_payload_hash
       OR COALESCE(v_row.recovery_generation, 0) <> COALESCE(p_recovery_generation, 0)
       OR NOT COALESCE(
            v_row.assigned_worker_generation = p_worker_generation
            OR v_shared_recovery_eligible,
            false
       )
       OR v_row.assignment_expires_at IS NULL
       OR v_row.assignment_expires_at <= now() THEN
        RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, NULL::uuid,
            NULL::uuid, NULL::integer, NULL::text, NULL::timestamptz;
        RETURN;
    END IF;

    IF v_row.status = 'completed' THEN
        RETURN QUERY SELECT 'ALREADY_COMPLETED', v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    ELSIF v_row.status = 'cancelled' THEN
        v_outcome := 'CANCELLED';
    ELSIF v_row.status = 'expired' THEN
        v_outcome := 'EXPIRED';
    ELSIF v_row.status = 'superseded' THEN
        v_outcome := 'SUPERSEDED';
    ELSIF v_row.status IN ('failed_terminal', 'dead_lettered', 'quarantined') THEN
        v_outcome := 'TERMINAL_FAILURE';
    ELSIF v_row.lease_expires_at IS NOT NULL
          AND v_row.lease_expires_at > now()
          AND v_row.status IN ('leased', 'running') THEN
        RETURN QUERY SELECT 'ACTIVE_LEASE', v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    ELSE
        v_outcome := CASE WHEN v_row.claim_count = 0 THEN 'ACQUIRED' ELSE 'RECLAIMED' END;
    END IF;

    IF v_outcome <> 'ACQUIRED' AND v_outcome <> 'RECLAIMED' THEN
        RETURN QUERY SELECT v_outcome, v_row.tenant_id, v_row.fit_id,
            v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
            v_row.lease_expires_at;
        RETURN;
    END IF;

    v_lease := encode(gen_random_bytes(32), 'hex');
    v_lease_digest := public.b24_sha256_text(v_lease);
    v_next_epoch := v_row.claim_epoch + 1;

    UPDATE public.b24_fit_dispatch_outbox outbox
    SET status = 'leased',
        claim_epoch = v_next_epoch,
        lease_capability_digest = v_lease_digest,
        lease_owner = p_worker_generation,
        lease_acquired_at = now(),
        lease_expires_at = now() + (v_lease_seconds * interval '1 second'),
        last_heartbeat_at = now(),
        claim_count = claim_count + 1,
        redelivery_count = redelivery_count + CASE WHEN v_row.claim_count > 0 THEN 1 ELSE 0 END,
        next_recovery_at = now() + (v_lease_seconds * interval '1 second'),
        claim_capability = NULL,
        claim_capability_digest = NULL,
        claim_capability_expires_at = NULL,
        updated_at = now()
    WHERE outbox.tenant_id = v_row.tenant_id
      AND outbox.id = v_row.id;

    PERFORM set_config('app.current_tenant_id', v_row.tenant_id::text, true);
    PERFORM set_config('app.b24_dispatch_id', v_row.id::text, true);
    PERFORM set_config('app.b24_attempt_id', v_row.attempt_id::text, true);
    PERFORM set_config('app.b24_claim_epoch', v_next_epoch::text, true);
    PERFORM set_config('app.b24_lease_capability', v_lease, true);

    RETURN QUERY SELECT v_outcome, v_row.tenant_id, v_row.fit_id, v_row.id,
        v_row.attempt_id, v_next_epoch, v_lease,
        now() + (v_lease_seconds * interval '1 second');
END
$$;
"""


_CLAIM_FUNCTION_SPECIFIC_ASSIGNMENT = _CLAIM_FUNCTION_SHARED_RECOVERY.replace(
    """
    v_shared_recovery_eligible := (
        COALESCE(v_row.recovery_generation, 0) > 0
        AND COALESCE(p_recovery_generation, 0) = COALESCE(v_row.recovery_generation, 0)
        AND v_row.assigned_worker_generation IS NULL
        AND v_row.assignment_reason = 'recovery_shared_eligible'
    );

    IF v_row.fit_id <> p_fit_id
       OR v_row.task_name <> p_task_name
       OR v_row.attempt_id <> p_attempt_id
       OR v_row.payload_hash <> p_payload_hash
       OR COALESCE(v_row.recovery_generation, 0) <> COALESCE(p_recovery_generation, 0)
       OR NOT COALESCE(
            v_row.assigned_worker_generation = p_worker_generation
            OR v_shared_recovery_eligible,
            false
       )
       OR v_row.assignment_expires_at IS NULL
       OR v_row.assignment_expires_at <= now() THEN
""",
    """
    v_shared_recovery_eligible := false;

    IF v_row.fit_id <> p_fit_id
       OR v_row.task_name <> p_task_name
       OR v_row.attempt_id <> p_attempt_id
       OR v_row.payload_hash <> p_payload_hash
       OR COALESCE(v_row.recovery_generation, 0) <> COALESCE(p_recovery_generation, 0)
       OR v_row.assigned_worker_generation IS DISTINCT FROM p_worker_generation
       OR v_row.assignment_expires_at IS NULL
       OR v_row.assignment_expires_at <= now() THEN
""",
)


def upgrade() -> None:
    op.execute(_CLAIM_FUNCTION_SHARED_RECOVERY)
    for role in ("app_worker", "app_user"):
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, integer, text, integer, integer) TO {role}",
        )


def downgrade() -> None:
    op.execute(_CLAIM_FUNCTION_SPECIFIC_ASSIGNMENT)
    op.execute(
        """
        UPDATE public.b24_fit_dispatch_outbox
        SET assignment_reason = 'recovery_republish'
        WHERE recovery_generation > 0
          AND assignment_reason = 'recovery_shared_eligible';
        """
    )
