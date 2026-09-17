"""B2.6-P2 Corrective III: durable execution intent, authority physics, least privilege.

Revision ID: 202609170001
Revises: 202609072001

Corrective-III closes the false-canonicality class:

- Class A: acceptance and recoverable delivery intent cannot diverge.
  Dispatch rows gain a recoverable delivery state plus persisted window
  authority; a new application-owned outbox table carries the stable
  logical execution identity with observable pending/retry state.
- Class B/C: worker admission precedes B2.3; authority is resolved from
  durable server-owned state without trusting caller GUC; relational
  tenant/source/task/state invariants move to database physics; the
  consumer cannot mint the authority it validates.

No P3/P4/P5/P8 durable reconciliation state is introduced. The outbox
carries transport intent only (task identity + tenant + ingress), never
financial truth.
"""

from __future__ import annotations

from alembic import op

revision = "202609170001"
down_revision = "202609072001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Composite uniqueness needed for tenant<->source relational binding.
    # webhook_ingress_identities(id) is PK; add UNIQUE(tenant_id, id) so the
    # dispatch table can FK both columns atomically. IF NOT EXISTS keeps
    # empty->head and predecessor->candidate replays identical.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_webhook_ingress_identities_tenant_id'
            ) THEN
                ALTER TABLE public.webhook_ingress_identities
                    ADD CONSTRAINT uq_webhook_ingress_identities_tenant_id
                    UNIQUE (tenant_id, id);
            END IF;
        END $$;
        """
    )

    # 2. Recoverable delivery + persisted window authority on dispatch.
    op.execute(
        """
        ALTER TABLE public.b23_match_task_dispatches
            ADD COLUMN IF NOT EXISTS delivery_state character varying(32)
                NOT NULL DEFAULT 'pending_publish',
            ADD COLUMN IF NOT EXISTS publish_attempts integer
                NOT NULL DEFAULT 0,
            ADD COLUMN IF NOT EXISTS last_publish_error text,
            ADD COLUMN IF NOT EXISTS window_start timestamp with time zone,
            ADD COLUMN IF NOT EXISTS window_end timestamp with time zone
        """
    )
    # Backfill legacy rows (Corrective-II) to the recoverable pending state.
    # Legacy rows have no persisted window; they remain NULL (observable) and
    # the worker re-derives the window from durable ingress event time.
    op.execute(
        """
        UPDATE public.b23_match_task_dispatches
        SET delivery_state = 'pending_publish'
        WHERE delivery_state IS NULL OR delivery_state NOT IN ('pending_publish', 'published')
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_task_dispatches_delivery_state'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT ck_b23_match_task_dispatches_delivery_state
                    CHECK (delivery_state IN ('pending_publish', 'published'));
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_task_dispatches_publish_attempts'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT ck_b23_match_task_dispatches_publish_attempts
                    CHECK (publish_attempts >= 0);
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_task_dispatches_window_order'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT ck_b23_match_task_dispatches_window_order
                    CHECK (
                        window_start IS NULL
                        OR window_end IS NULL
                        OR window_start < window_end
                    );
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_task_dispatches_task_name'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT ck_b23_match_task_dispatches_task_name
                    CHECK (
                        task_name = 'app.tasks.revenue_verification.execute_b23_batch_match_engine'
                    );
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_b23_dispatch_tenant_ingress_composite'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT fk_b23_dispatch_tenant_ingress_composite
                    FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                    REFERENCES public.webhook_ingress_identities (tenant_id, id)
                    ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_dispatch_delivery_state
            ON public.b23_match_task_dispatches (delivery_state, dispatched_at)
        """
    )

    # 3. Application-owned durable execution-intent outbox. One row per
    # stable logical execution identity (dispatch task_id). The relay
    # publishes pending rows; the worker consumes only published authority.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_execution_outbox (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            dispatch_task_id character varying(155) NOT NULL,
            webhook_ingress_identity_id uuid NOT NULL
                REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE,
            state character varying(32) DEFAULT 'pending_publish' NOT NULL,
            publish_attempts integer DEFAULT 0 NOT NULL,
            last_publish_error text,
            next_retry_at timestamp with time zone DEFAULT now() NOT NULL,
            payload jsonb DEFAULT '{}'::jsonb NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            updated_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b26_p2_execution_outbox_pkey PRIMARY KEY (id),
            CONSTRAINT uq_b26_p2_execution_outbox_task UNIQUE (dispatch_task_id),
            CONSTRAINT uq_b26_p2_execution_outbox_tenant_ingress
                UNIQUE (tenant_id, webhook_ingress_identity_id),
            CONSTRAINT ck_b26_p2_outbox_state
                CHECK (state IN ('pending_publish', 'published')),
            CONSTRAINT ck_b26_p2_outbox_attempts CHECK (publish_attempts >= 0)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b26_p2_outbox_pending
            ON public.b26_p2_execution_outbox (state, next_retry_at)
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_outbox FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'b26_p2_execution_outbox'
                  AND policyname = 'tenant_isolation_policy_b26_p2_execution_outbox'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_execution_outbox
                ON public.b26_p2_execution_outbox
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b26_p2_execution_outbox IS
            'B2.6-P2 Corrective III durable execution intent: stable logical task identity with recoverable pending/published delivery state. Transport intent only; never financial truth.'
        """
    )

    # 4. Least privilege: the consumer cannot mint the authority it validates.
    # app_rw loses dispatch INSERT/UPDATE (keeps SELECT for reads); the
    # producer (app_user) retains issuance; the worker gets explicit SELECT.
    # app_user/app_rw/app_ro are migration-guaranteed roles (001 202511131121);
    # app_worker exists only after role provisioning, so its grants are
    # existence-guarded: bare-database jobs (schema-authority, unit lanes)
    # migrate without provisioned roles and must not fail here.
    op.execute("REVOKE INSERT, UPDATE ON TABLE public.b23_match_task_dispatches FROM app_rw")
    op.execute("GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_rw")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_user"
    )
    op.execute("GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ro")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_execution_outbox TO app_user"
    )
    op.execute("GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_rw")
    op.execute("GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_ro")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_worker;
            END IF;
        END $$;
        """
    )

    # 5. Issuance immutability: runtime roles cannot rewrite identifiers,
    # tenant/source binding, or window authority after issuance. Only the
    # recoverable delivery columns may advance.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_immutability()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_id IS DISTINCT FROM NEW.task_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_id_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.task_name IS DISTINCT FROM NEW.task_name THEN
                RAISE EXCEPTION 'b26_p2_dispatch_task_name_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.queue IS DISTINCT FROM NEW.queue THEN
                RAISE EXCEPTION 'b26_p2_dispatch_queue_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.routing_key IS DISTINCT FROM NEW.routing_key THEN
                RAISE EXCEPTION 'b26_p2_dispatch_routing_key_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider IS DISTINCT FROM NEW.provider THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_event_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.provider_native_commerce_reference IS DISTINCT FROM NEW.provider_native_commerce_reference THEN
                RAISE EXCEPTION 'b26_p2_dispatch_commerce_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.normalized_commerce_reference_value IS DISTINCT FROM NEW.normalized_commerce_reference_value THEN
                RAISE EXCEPTION 'b26_p2_dispatch_norm_ref_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.correlation_id IS DISTINCT FROM NEW.correlation_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_correlation_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_start IS DISTINCT FROM NEW.window_start
               AND OLD.window_start IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end
               AND OLD.window_end IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            -- Lawful delivery transitions only: pending_publish -> published.
            IF OLD.delivery_state = 'published' AND NEW.delivery_state = 'pending_publish' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_delivery_no_backward'
                    USING ERRCODE = '42501';
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_dispatch_immutability'
            ) THEN
                CREATE TRIGGER trg_b26_p2_dispatch_immutability
                BEFORE UPDATE ON public.b23_match_task_dispatches
                FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_dispatch_immutability();
            END IF;
        END $$;
        """
    )
    # Function ownership follows repo precedent (no OWNER TO): the function is
    # owned by the migrating principal (migration_owner in provisioned
    # environments). Runtime principals hold no DDL on the schema, so
    # owner-only replacement holds regardless of which admin owns it.

    # 6. GUC-independent admission directory: the worker begins from the
    # least forgeable stable handle (broker task identity) and resolves the
    # authoritative tenant without trusting caller-supplied GUC. Task IDs
    # are unguessable UUIDs; the directory carries no RLS (lookup by exact
    # task_id only, no enumeration) and is producer-written / worker-read.
    # Full authority (task_name/queue/status/window) is then validated under
    # the RETURNED tenant GUC via the existing resolver, so the message
    # tenant never selects the visibility root.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_task_authority_directory (
            task_id character varying(155) NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            webhook_ingress_identity_id uuid NOT NULL
                REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE,
            window_start timestamp with time zone NOT NULL,
            window_end timestamp with time zone NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b26_p2_task_authority_directory_pkey PRIMARY KEY (task_id),
            CONSTRAINT ck_b26_p2_directory_window_order CHECK (window_start < window_end)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b26_p2_task_authority_directory IS
            'B2.6-P2 Corrective III GUC-independent admission directory: stable task identity to authoritative tenant binding. No RLS by design (exact task_id lookup only; IDs unguessable). Producer-written, worker-read.'
        """
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_task_authority_directory TO app_rw"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_task_authority_directory TO app_ro"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT ON TABLE public.b26_p2_task_authority_directory TO app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "GRANT SELECT, INSERT ON TABLE public.b26_p2_task_authority_directory TO app_user"
    )
    # Constrained admission resolver: fixed search_path, minimal output.
    # The resolver reads ONLY the GUC-independent directory (no RLS) keyed
    # by the broker task identity. Full dispatch/ingress validation then
    # runs under the RETURNED tenant (never the message tenant). Owned by
    # migration_owner; runtime principals cannot replace it (owner-only DDL).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_resolve_dispatch_authority(p_task_id text)
        RETURNS TABLE (
            tenant_id uuid,
            webhook_ingress_identity_id uuid,
            window_start timestamp with time zone,
            window_end timestamp with time zone
        )
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path TO 'public', 'pg_temp'
        AS $$
            SELECT dir.tenant_id,
                   dir.webhook_ingress_identity_id,
                   dir.window_start,
                   dir.window_end
            FROM public.b26_p2_task_authority_directory AS dir
            WHERE dir.task_id = p_task_id
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) TO app_user")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) TO app_worker;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) FROM app_worker;
            END IF;
        END $$;
        """
    )
    op.execute("REVOKE EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) FROM app_user")
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_resolve_dispatch_authority(text)")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III admission resolver.
    op.execute("REVOKE ALL ON TABLE public.b26_p2_task_authority_directory FROM app_user")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE ALL ON TABLE public.b26_p2_task_authority_directory FROM app_worker;
            END IF;
        END $$;
        """
    )
    op.execute("REVOKE ALL ON TABLE public.b26_p2_task_authority_directory FROM app_rw")
    op.execute("REVOKE ALL ON TABLE public.b26_p2_task_authority_directory FROM app_ro")
    op.execute("DROP TABLE IF EXISTS public.b26_p2_task_authority_directory")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III admission directory.
    op.execute("DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_immutability ON public.b23_match_task_dispatches")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III immutability.
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_enforce_dispatch_immutability()")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III immutability.
    op.execute("GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_rw")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE SELECT ON TABLE public.b23_match_task_dispatches FROM app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b26_p2_execution_outbox ON public.b26_p2_execution_outbox"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III outbox.
    )
    op.execute("DROP TABLE IF EXISTS public.b26_p2_execution_outbox")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III outbox.
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS fk_b23_dispatch_tenant_ingress_composite"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III relational binding.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_task_name"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III task-name physics.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_window_order"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III window physics.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_publish_attempts"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery physics.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_delivery_state"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery physics.
    )
    op.execute("DROP INDEX IF EXISTS public.idx_b23_dispatch_delivery_state")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery index.
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP COLUMN IF EXISTS window_end"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III window authority.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP COLUMN IF EXISTS window_start"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III window authority.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP COLUMN IF EXISTS last_publish_error"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery state.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP COLUMN IF EXISTS publish_attempts"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery state.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP COLUMN IF EXISTS delivery_state"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III delivery state.
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DROP CONSTRAINT IF EXISTS uq_webhook_ingress_identities_tenant_id"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective III composite binding.
    )
