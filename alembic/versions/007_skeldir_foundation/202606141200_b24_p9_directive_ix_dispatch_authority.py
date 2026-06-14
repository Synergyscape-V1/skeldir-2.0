"""B2.4-P9 Directive IX dispatch capability and fencing.

Revision ID: 202606141200
Revises: 202606081200
Create Date: 2026-06-14 12:00:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202606141200"
down_revision: Union[str, None] = "202606081200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _grant_if_role_exists(role: str, grant_sql: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE '{grant_sql}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD COLUMN IF NOT EXISTS task_name text,
            ADD COLUMN IF NOT EXISTS attempt_id uuid,
            ADD COLUMN IF NOT EXISTS payload_hash character(64),
            ADD COLUMN IF NOT EXISTS claim_capability text,
            ADD COLUMN IF NOT EXISTS claim_capability_digest character(64),
            ADD COLUMN IF NOT EXISTS claim_capability_expires_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS lease_owner text,
            ADD COLUMN IF NOT EXISTS lease_capability_digest character(64),
            ADD COLUMN IF NOT EXISTS lease_acquired_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS lease_expires_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS last_heartbeat_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS claim_epoch integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS claim_count integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS redelivery_count integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS recovery_generation integer DEFAULT 0 NOT NULL,
            ADD COLUMN IF NOT EXISTS completed_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS cancelled_at timestamp with time zone,
            ADD COLUMN IF NOT EXISTS superseded_by uuid,
            ADD COLUMN IF NOT EXISTS terminal_reason text,
            ADD COLUMN IF NOT EXISTS next_recovery_at timestamp with time zone
        """
    )
    op.execute(
        """
        UPDATE public.b24_fit_dispatch_outbox
        SET task_name = COALESCE(task_name, 'app.tasks.bayesian.execute_fit_intent'),
            attempt_id = COALESCE(attempt_id, id),
            payload_hash = COALESCE(
                payload_hash,
                encode(
                    digest(
                        'app.tasks.bayesian.execute_fit_intent:' || fit_id::text,
                        'sha256'
                    ),
                    'hex'
                )
            ),
            claim_capability = COALESCE(claim_capability, encode(gen_random_bytes(32), 'hex')),
            claim_capability_expires_at = COALESCE(
                claim_capability_expires_at,
                now() + interval '24 hours'
            ),
            next_recovery_at = COALESCE(next_recovery_at, now())
        """
    )
    op.execute(
        """
        UPDATE public.b24_fit_dispatch_outbox
        SET claim_capability_digest = COALESCE(
                claim_capability_digest,
                encode(digest(claim_capability, 'sha256'), 'hex')
            )
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ALTER COLUMN task_name SET NOT NULL,
            ALTER COLUMN attempt_id SET NOT NULL,
            ALTER COLUMN payload_hash SET NOT NULL,
            ALTER COLUMN claim_capability SET NOT NULL,
            ALTER COLUMN claim_capability_digest SET NOT NULL,
            ALTER COLUMN claim_capability_expires_at SET NOT NULL,
            ALTER COLUMN next_recovery_at SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_status
        """
    )  # CI:DESTRUCTIVE_OK - replaces enum with Directive IX lease/recovery states.
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_status
            CHECK (status IN (
                'pending',
                'dispatching',
                'dispatched',
                'leased',
                'running',
                'failed_retryable',
                'completed',
                'failed_terminal',
                'cancelled',
                'expired',
                'superseded',
                'quarantined',
                'dead_lettered',
                'stale_recovered'
            ))
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_payload_hash_sha256
            CHECK (payload_hash ~ '^[a-f0-9]{64}$'),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256
            CHECK (claim_capability_digest ~ '^[a-f0-9]{64}$'),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_lease_capability_digest_sha256
            CHECK (
                lease_capability_digest IS NULL
                OR lease_capability_digest ~ '^[a-f0-9]{64}$'
            ),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_claim_epoch_non_negative
            CHECK (claim_epoch >= 0),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_claim_count_non_negative
            CHECK (claim_count >= 0),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_redelivery_count_non_negative
            CHECK (redelivery_count >= 0),
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_recovery_generation_non_negative
            CHECK (recovery_generation >= 0)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_b24_fit_dispatch_outbox_attempt
            ON public.b24_fit_dispatch_outbox (tenant_id, attempt_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_fit_dispatch_outbox_recoverable
            ON public.b24_fit_dispatch_outbox (status, next_recovery_at ASC, lease_expires_at ASC)
            WHERE status IN ('dispatched', 'leased', 'running', 'failed_retryable', 'stale_recovered')
        """
    )
    op.execute(
        """
        DROP POLICY IF EXISTS dispatch_capability_claim_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_capability_claim_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;

        CREATE POLICY dispatch_capability_claim_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            FOR SELECT
            USING (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true),
                    ''
                )
                AND claim_capability_expires_at > now()
            );

        CREATE POLICY dispatch_capability_claim_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            FOR UPDATE
            USING (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true),
                    ''
                )
                AND claim_capability_expires_at > now()
            )
            WITH CHECK (
                claim_capability_digest = NULLIF(
                    current_setting('app.b24_claim_capability_digest', true),
                    ''
                )
                AND claim_capability_expires_at > now()
            );

        CREATE POLICY dispatch_recovery_reconciler_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            FOR SELECT
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on');

        CREATE POLICY dispatch_recovery_reconciler_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox
            FOR UPDATE
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on')
            WITH CHECK (current_setting('app.b24_recovery_reconciler', true) = 'on');
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b24_fit_recovery_outbox (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            dispatch_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            fit_id uuid NOT NULL,
            attempt_id uuid NOT NULL,
            task_name text NOT NULL,
            payload_hash character(64) NOT NULL,
            claim_capability text NOT NULL,
            recovery_generation integer NOT NULL,
            status character varying(32) DEFAULT 'pending' NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            published_at timestamp with time zone,
            publish_attempt_count integer DEFAULT 0 NOT NULL,
            last_error text,
            CONSTRAINT b24_fit_recovery_outbox_pkey PRIMARY KEY (tenant_id, id),
            CONSTRAINT fk_b24_fit_recovery_outbox_dispatch
                FOREIGN KEY (tenant_id, dispatch_id)
                REFERENCES public.b24_fit_dispatch_outbox(tenant_id, id)
                ON DELETE CASCADE,
            CONSTRAINT uq_b24_fit_recovery_outbox_generation
                UNIQUE (tenant_id, dispatch_id, recovery_generation),
            CONSTRAINT ck_b24_fit_recovery_outbox_status
                CHECK (status IN ('pending', 'publishing', 'published', 'failed_retryable', 'quarantined')),
            CONSTRAINT ck_b24_fit_recovery_outbox_payload_hash_sha256
                CHECK (payload_hash ~ '^[a-f0-9]{64}$'),
            CONSTRAINT ck_b24_fit_recovery_outbox_publish_attempt_count
                CHECK (publish_attempt_count >= 0)
        )
        """
    )
    op.execute(
        """
        ALTER TABLE public.b24_fit_recovery_outbox ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.b24_fit_recovery_outbox FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS tenant_isolation_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox;
        CREATE POLICY tenant_isolation_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox
            USING (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true),
                    ''
                )::uuid
            )
            WITH CHECK (
                tenant_id = NULLIF(
                    current_setting('app.current_tenant_id', true),
                    ''
                )::uuid
            );
        DROP POLICY IF EXISTS recovery_reconciler_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox;
        CREATE POLICY recovery_reconciler_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox
            USING (current_setting('app.b24_recovery_reconciler', true) = 'on')
            WITH CHECK (current_setting('app.b24_recovery_reconciler', true) = 'on');
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_fit_recovery_outbox_due
            ON public.b24_fit_recovery_outbox (status, created_at ASC, id ASC)
            WHERE status IN ('pending', 'failed_retryable')
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_sha256_text(value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT encode(digest(value, 'sha256'), 'hex')
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_claim_fit_dispatch(
            p_dispatch_id uuid,
            p_fit_id uuid,
            p_task_name text,
            p_attempt_id uuid,
            p_payload_hash text,
            p_claim_capability text,
            p_worker_generation text,
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
            v_digest text := public.b24_sha256_text(p_claim_capability);
            v_lease text;
            v_lease_digest text;
            v_next_epoch integer;
            v_lease_seconds integer := LEAST(GREATEST(COALESCE(p_lease_seconds, 330), 30), 900);
            v_outcome text;
        BEGIN
            PERFORM set_config('app.b24_claim_capability_digest', v_digest, true);

            SELECT *
            INTO v_row
            FROM public.b24_fit_dispatch_outbox outbox
            WHERE outbox.id = p_dispatch_id
            FOR UPDATE;

            IF NOT FOUND THEN
                RETURN QUERY SELECT 'UNAUTHORIZED', NULL::uuid, NULL::uuid, p_dispatch_id,
                    p_attempt_id, NULL::integer, NULL::text, NULL::timestamptz;
                RETURN;
            END IF;

            IF v_row.claim_capability_digest <> v_digest
               OR v_row.fit_id <> p_fit_id
               OR v_row.task_name <> p_task_name
               OR v_row.attempt_id <> p_attempt_id
               OR v_row.payload_hash <> p_payload_hash
               OR v_row.claim_capability_expires_at <= now() THEN
                RETURN QUERY SELECT 'UNAUTHORIZED', v_row.tenant_id, v_row.fit_id,
                    v_row.id, v_row.attempt_id, v_row.claim_epoch, NULL::text,
                    v_row.lease_expires_at;
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
                updated_at = now()
            WHERE outbox.tenant_id = v_row.tenant_id
              AND outbox.id = v_row.id;

            PERFORM set_config('app.current_tenant_id', v_row.tenant_id::text, true);
            PERFORM set_config('app.b24_dispatch_id', v_row.id::text, true);
            PERFORM set_config('app.b24_attempt_id', v_row.attempt_id::text, true);
            PERFORM set_config('app.b24_claim_epoch', v_next_epoch::text, true);
            PERFORM set_config('app.b24_lease_capability', v_lease, true);
            PERFORM set_config('app.b24_dispatch_fence_required', 'on', true);

            RETURN QUERY SELECT v_outcome, v_row.tenant_id, v_row.fit_id, v_row.id,
                v_row.attempt_id, v_next_epoch, v_lease,
                now() + (v_lease_seconds * interval '1 second');
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_current_dispatch_fence_valid(
            p_tenant_id uuid,
            p_fit_id uuid
        )
        RETURNS boolean
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1
                FROM public.b24_fit_dispatch_outbox outbox
                WHERE outbox.tenant_id = p_tenant_id
                  AND outbox.fit_id = p_fit_id
                  AND outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
                  AND outbox.attempt_id = NULLIF(current_setting('app.b24_attempt_id', true), '')::uuid
                  AND outbox.claim_epoch = NULLIF(current_setting('app.b24_claim_epoch', true), '')::integer
                  AND outbox.lease_capability_digest = public.b24_sha256_text(
                        current_setting('app.b24_lease_capability', true)
                      )
                  AND outbox.lease_expires_at > now()
                  AND outbox.status IN ('leased', 'running')
            )
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

            IF current_setting('app.b24_dispatch_fence_required', true) IS DISTINCT FROM 'on' THEN
                RETURN NEW;
            END IF;

            IF TG_ARGV[0] = 'fit' THEN
                v_tenant_id := NEW.tenant_id;
                v_fit_id := NEW.id;
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
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_fits ON public.bayesian_model_fits;
        CREATE TRIGGER trg_b24_dispatch_fence_fits
            BEFORE INSERT OR UPDATE ON public.bayesian_model_fits
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('fit');
        DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_artifacts ON public.bayesian_artifacts;
        CREATE TRIGGER trg_b24_dispatch_fence_artifacts
            BEFORE INSERT OR UPDATE ON public.bayesian_artifacts
            FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dispatch_fence('artifact');
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_mark_fit_dispatch_running()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'running',
                last_heartbeat_at = now(),
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_running_fence_rejected';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_complete_fit_dispatch()
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'completed',
                completed_at = now(),
                terminal_reason = NULL,
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_complete_fence_rejected';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_fail_fit_dispatch_terminal(p_reason text)
        RETURNS void
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            UPDATE public.b24_fit_dispatch_outbox outbox
            SET status = 'failed_terminal',
                terminal_reason = LEFT(COALESCE(p_reason, 'worker_failure'), 512),
                completed_at = now(),
                updated_at = now()
            WHERE outbox.id = NULLIF(current_setting('app.b24_dispatch_id', true), '')::uuid
              AND public.b24_current_dispatch_fence_valid(outbox.tenant_id, outbox.fit_id);
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b24_dispatch_failure_fence_rejected';
            END IF;
        END
        $$;
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
            v_claim text;
            v_generation integer;
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
                v_claim := encode(gen_random_bytes(32), 'hex');
                v_generation := v_row.recovery_generation + 1;
                UPDATE public.b24_fit_dispatch_outbox outbox
                SET status = 'stale_recovered',
                    claim_capability = v_claim,
                    claim_capability_digest = public.b24_sha256_text(v_claim),
                    claim_capability_expires_at = now() + interval '24 hours',
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
                    v_row.attempt_id,
                    v_row.task_name,
                    v_row.payload_hash,
                    v_claim,
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
            f"GRANT EXECUTE ON FUNCTION public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, text, integer) TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_mark_fit_dispatch_running() TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_complete_fit_dispatch() TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_fail_fit_dispatch_terminal(text) TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT EXECUTE ON FUNCTION public.b24_create_fit_recovery_wakeups(integer) TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT SELECT, UPDATE ON public.b24_fit_dispatch_outbox TO {role}",
        )
        _grant_if_role_exists(
            role,
            f"GRANT SELECT, INSERT, UPDATE ON public.b24_fit_recovery_outbox TO {role}",
        )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_create_fit_recovery_wakeups(integer)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX recovery function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_fail_fit_dispatch_terminal(text)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX terminal function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_complete_fit_dispatch()"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX terminal function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_mark_fit_dispatch_running()"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX running function.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_artifacts ON public.bayesian_artifacts"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX fencing trigger.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b24_dispatch_fence_fits ON public.bayesian_model_fits"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX fencing trigger.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_enforce_dispatch_fence()"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX fencing function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_current_dispatch_fence_valid(uuid, uuid)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX fencing function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_claim_fit_dispatch(uuid, uuid, text, uuid, text, text, text, integer)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX claim function.
    op.execute(
        "DROP FUNCTION IF EXISTS public.b24_sha256_text(text)"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX helper.
    op.execute(
        """
        DROP POLICY IF EXISTS recovery_reconciler_policy_b24_fit_recovery_outbox
            ON public.b24_fit_recovery_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_recovery_reconciler_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_capability_claim_update_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        DROP POLICY IF EXISTS dispatch_capability_claim_select_b24_fit_dispatch_outbox
            ON public.b24_fit_dispatch_outbox;
        """
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX RLS apertures.
    op.execute(
        "DROP TABLE IF EXISTS public.b24_fit_recovery_outbox"  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive IX recovery outbox.
    )  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive IX recovery outbox.
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b24_fit_dispatch_outbox_recoverable"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX index.
    op.execute(
        "DROP INDEX IF EXISTS public.uq_b24_fit_dispatch_outbox_attempt"
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX index.
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_recovery_generation_non_negative,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_redelivery_count_non_negative,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_claim_count_non_negative,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_claim_epoch_non_negative,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_lease_capability_digest_sha256,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_payload_hash_sha256,
            DROP CONSTRAINT IF EXISTS ck_b24_fit_dispatch_outbox_status
        """
    )  # CI:DESTRUCTIVE_OK - reversible rollback for Directive IX constraints.
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_status
            CHECK (status IN (
                'pending',
                'dispatching',
                'dispatched',
                'failed_retryable',
                'dead_lettered',
                'stale_recovered'
            ))
        """
    )
    for column in (
        "task_name",
        "attempt_id",
        "payload_hash",
        "claim_capability",
        "claim_capability_digest",
        "claim_capability_expires_at",
        "lease_owner",
        "lease_capability_digest",
        "lease_acquired_at",
        "lease_expires_at",
        "last_heartbeat_at",
        "claim_epoch",
        "claim_count",
        "redelivery_count",
        "recovery_generation",
        "completed_at",
        "cancelled_at",
        "superseded_by",
        "terminal_reason",
        "next_recovery_at",
    ):
        op.execute(
            f"ALTER TABLE public.b24_fit_dispatch_outbox DROP COLUMN IF EXISTS {column}"  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive IX columns.
        )  # CI:DESTRUCTIVE_OK - reversible rollback for additive Directive IX columns.
