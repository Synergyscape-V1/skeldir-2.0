"""B2.4-P9 Directive X broker-independent dispatch authority.

Revision ID: 202606181200
Revises: 202606141200
Create Date: 2026-06-18 12:00:00.000000
"""

from __future__ import annotations

from alembic import op


revision = "202606181200"
down_revision = "202606141200"
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


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b24_worker_process_authority (
            generation_id text NOT NULL,
            pid integer NOT NULL,
            parent_pid integer NOT NULL,
            topology_fingerprint character(64) NOT NULL,
            process_token_digest character(64) NOT NULL,
            status character varying(32) DEFAULT 'active' NOT NULL,
            registered_at timestamp with time zone DEFAULT now() NOT NULL,
            expires_at timestamp with time zone NOT NULL,
            revoked_at timestamp with time zone,
            CONSTRAINT b24_worker_process_authority_pkey PRIMARY KEY (generation_id, pid),
            CONSTRAINT ck_b24_worker_process_authority_generation
                CHECK (length(generation_id) >= 16),
            CONSTRAINT ck_b24_worker_process_authority_digest
                CHECK (process_token_digest ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_worker_process_authority_topology_fingerprint
                CHECK (topology_fingerprint ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_worker_process_authority_status
                CHECK (status IN ('active', 'revoked', 'expired'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_worker_process_authority_active
            ON public.b24_worker_process_authority (expires_at ASC, registered_at ASC)
            WHERE status = 'active'
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_worker_process_authority ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.b24_worker_process_authority FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS deny_all_b24_worker_process_authority
            ON public.b24_worker_process_authority;
        CREATE POLICY deny_all_b24_worker_process_authority
            ON public.b24_worker_process_authority
            USING (false)
            WITH CHECK (false);
        DROP POLICY IF EXISTS function_access_b24_worker_process_authority
            ON public.b24_worker_process_authority;
        CREATE POLICY function_access_b24_worker_process_authority
            ON public.b24_worker_process_authority
            USING (current_setting('app.b24_worker_authority_access', true) = 'on')
            WITH CHECK (current_setting('app.b24_worker_authority_access', true) = 'on');
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD COLUMN IF NOT EXISTS assigned_worker_generation text,
            ADD COLUMN IF NOT EXISTS assignment_generation integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS assignment_expires_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS assignment_reason text;
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_assignment_generation_non_negative;
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_assignment_generation_non_negative
            CHECK (assignment_generation >= 0);
        UPDATE public.b24_fit_dispatch_outbox
        SET claim_capability = NULL,
            claim_capability_digest = NULL,
            claim_capability_expires_at = NULL
        WHERE claim_capability IS NOT NULL
           OR claim_capability_digest IS NOT NULL
           OR claim_capability_expires_at IS NOT NULL;
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_recovery_outbox
            ALTER COLUMN claim_capability DROP NOT NULL;
        UPDATE public.b24_fit_recovery_outbox
        SET claim_capability = NULL
        WHERE claim_capability IS NOT NULL;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_register_worker_process_authority(
            p_generation_id text,
            p_pid integer,
            p_parent_pid integer,
            p_topology_fingerprint text,
            p_process_token text,
            p_ttl_seconds integer DEFAULT 3600
        )
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_ttl integer := LEAST(GREATEST(COALESCE(p_ttl_seconds, 3600), 30), 86400);
        BEGIN
            IF p_generation_id IS NULL
               OR p_generation_id = ''
               OR p_generation_id = 'unknown-generation'
               OR p_process_token IS NULL
               OR p_process_token = ''
               OR p_topology_fingerprint !~ '^[a-f0-9]{64}$' THEN
                RAISE EXCEPTION 'b24_worker_process_authority_invalid';
            END IF;

            PERFORM set_config('app.b24_worker_authority_access', 'on', true);

            INSERT INTO public.b24_worker_process_authority (
                generation_id,
                pid,
                parent_pid,
                topology_fingerprint,
                process_token_digest,
                status,
                registered_at,
                expires_at,
                revoked_at
            )
            VALUES (
                p_generation_id,
                p_pid,
                p_parent_pid,
                p_topology_fingerprint,
                public.b24_sha256_text(p_process_token),
                'active',
                now(),
                now() + (v_ttl * interval '1 second'),
                NULL
            )
            ON CONFLICT (generation_id, pid)
            DO UPDATE SET
                parent_pid = EXCLUDED.parent_pid,
                topology_fingerprint = EXCLUDED.topology_fingerprint,
                process_token_digest = EXCLUDED.process_token_digest,
                status = 'active',
                registered_at = now(),
                expires_at = EXCLUDED.expires_at,
                revoked_at = NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_next_active_worker_generation()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_generation text;
        BEGIN
            PERFORM set_config('app.b24_worker_authority_access', 'on', true);

            SELECT auth.generation_id
            INTO v_generation
            FROM public.b24_worker_process_authority auth
            WHERE auth.status = 'active'
              AND auth.revoked_at IS NULL
              AND auth.expires_at > now()
            ORDER BY auth.registered_at ASC, auth.generation_id ASC
            LIMIT 1;
            RETURN v_generation;
        END
        $$;
        """
    )
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.b24_claim_fit_dispatch(
            uuid, uuid, text, uuid, text, text, text, integer
        );
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
        BEGIN
            PERFORM set_config('app.b24_worker_authority_access', 'on', true);

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

            IF v_row.fit_id <> p_fit_id
               OR v_row.task_name <> p_task_name
               OR v_row.attempt_id <> p_attempt_id
               OR v_row.payload_hash <> p_payload_hash
               OR COALESCE(v_row.recovery_generation, 0) <> COALESCE(p_recovery_generation, 0)
               OR v_row.assigned_worker_generation IS DISTINCT FROM p_worker_generation
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
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_dispatch_fence()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_tenant_id uuid;
            v_fit_id uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'b24_dispatch_delete_forbidden';
            END IF;

            IF TG_OP = 'UPDATE' THEN
                IF TG_ARGV[0] = 'fit' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id OR NEW.id IS DISTINCT FROM OLD.id THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_fit_authority';
                    END IF;
                ELSIF TG_ARGV[0] = 'artifact' THEN
                    IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
                       OR NEW.fit_id IS DISTINCT FROM OLD.fit_id
                       OR NEW.artifact_ref IS DISTINCT FROM OLD.artifact_ref THEN
                        RAISE EXCEPTION 'b24_dispatch_immutable_artifact_authority';
                    END IF;
                ELSE
                    RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
                END IF;
            END IF;

            IF TG_ARGV[0] = 'fit' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.id;
                IF TG_OP = 'INSERT' AND NEW.status = 'queued' THEN
                    RETURN NEW;
                END IF;
            ELSIF TG_ARGV[0] = 'artifact' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.fit_id;
            ELSE
                RAISE EXCEPTION 'b24_dispatch_unknown_fence_subject';
            END IF;

            IF NOT public.b24_current_dispatch_fence_valid(v_tenant_id, v_fit_id) THEN
                RAISE EXCEPTION 'b24_dispatch_fence_rejected';
            END IF;
            RETURN NEW;
        END
        $$;

        DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_fits ON public.bayesian_model_fits;
        CREATE TRIGGER trg_b24_dispatch_fence_fits
            BEFORE INSERT OR UPDATE OR DELETE ON public.bayesian_model_fits
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('fit');
        DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_artifacts ON public.bayesian_artifacts;
        CREATE TRIGGER trg_b24_dispatch_fence_artifacts
            BEFORE INSERT OR UPDATE OR DELETE ON public.bayesian_artifacts
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('artifact');
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_create_fit_recovery_wakeups(
            p_limit integer DEFAULT 25
        )
        RETURNS integer
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            v_count integer := 0;
            v_row record;
            v_generation integer;
            v_attempt_id uuid;
        BEGIN
            PERFORM set_config('app.b24_recovery_reconciler', 'on', true);

            FOR v_row IN
                SELECT *
                FROM public.b24_fit_dispatch_outbox outbox
                WHERE outbox.status IN ('dispatched', 'leased', 'running', 'failed_retryable', 'stale_recovered')
                  AND outbox.next_recovery_at <= now()
                  AND (
                      outbox.lease_expires_at IS NULL
                      OR outbox.lease_expires_at <= now()
                      OR outbox.status IN ('failed_retryable', 'stale_recovered')
                  )
                ORDER BY outbox.next_recovery_at ASC, outbox.id ASC
                LIMIT LEAST(GREATEST(COALESCE(p_limit, 25), 1), 100)
                FOR UPDATE SKIP LOCKED
            LOOP
                v_generation := v_row.recovery_generation + 1;
                v_attempt_id := gen_random_uuid();
                UPDATE public.b24_fit_dispatch_outbox outbox
                SET status = 'stale_recovered',
                    attempt_id = v_attempt_id,
                    claim_capability = NULL,
                    claim_capability_digest = NULL,
                    claim_capability_expires_at = NULL,
                    lease_capability_digest = NULL,
                    lease_expires_at = NULL,
                    assigned_worker_generation = NULL,
                    assignment_generation = assignment_generation + 1,
                    assignment_expires_at = NULL,
                    assignment_reason = 'stale_recovery',
                    recovery_generation = v_generation,
                    next_recovery_at = now() + interval '5 minutes',
                    updated_at = now()
                WHERE outbox.tenant_id = v_row.tenant_id
                  AND outbox.id = v_row.id;

                INSERT INTO public.b24_fit_recovery_outbox (
                    dispatch_id,
                    tenant_id,
                    fit_id,
                    attempt_id,
                    task_name,
                    payload_hash,
                    claim_capability,
                    recovery_generation
                )
                VALUES (
                    v_row.id,
                    v_row.tenant_id,
                    v_row.fit_id,
                    v_attempt_id,
                    v_row.task_name,
                    v_row.payload_hash,
                    NULL,
                    v_generation
                )
                ON CONFLICT (tenant_id, dispatch_id, recovery_generation) DO NOTHING;
                v_count := v_count + 1;
            END LOOP;
            RETURN v_count;
        END
        $$;
        """
    )
    for role in ("app_worker", "app_user"):
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_register_worker_process_authority(text, integer, integer, text, text, integer) TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_next_active_worker_generation() TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, integer, text, integer, integer) TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"REVOKE DELETE ON public.bayesian_model_fits FROM {role}",
        )
        _grant_if_role_exists(
            role,
            f"REVOKE DELETE ON public.bayesian_artifacts FROM {role}",
        )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_register_worker_process_authority(text, integer, integer, text, text, integer)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive X worker authority registration.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_next_active_worker_generation()"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive X assignment helper.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, integer, text, integer, integer)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive X claim function.
    op.execute(
        "DROP TABLE IF EXISTS public.b24_worker_process_authority"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive X worker registry.
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_assignment_generation_non_negative,
            DROP COLUMN IF EXISTS assignment_reason,
            DROP COLUMN IF EXISTS assignment_expires_at,
            DROP COLUMN IF EXISTS assignment_generation,
            DROP COLUMN IF EXISTS assigned_worker_generation;
        """
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive X assignment columns.
