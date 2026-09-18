"""B2.6-P2 Corrective IV: deployment-plane equivalence authority physics.

Revision ID: 202609180001
Revises: 202609170001

Corrective-IV closes the DEPLOYMENT-PLANE NON-EQUIVALENCE class: the
intended architecture, the deployed architecture, and the CI-proven
architecture must be the same physical system for every load-bearing P2
execution property.

Database-physics changes (this migration):

- Class D (single execution identity): outbox.dispatch_task_id and
  directory.task_id become FOREIGN KEYs to dispatches.task_id, and both
  tables gain composite (tenant_id, webhook_ingress_identity_id) FKs to
  webhook_ingress_identities(tenant_id, id). Split-brain triples
  (dispatch=A, outbox=B, directory=C), orphan directory rows, orphan
  outbox rows, and cross-tenant outbox/directory bindings become
  physically unencodable. The sweeper JOIN can no longer silently drop a
  persisted orphan because no orphan can persist.
- Class C (published != conducted): delivery_state / outbox.state gain
  conducted. Lawful transitions only:
  pending_publish -> published -> conducted. conducted is terminal
  (immutable). Broker acceptance can no longer be mistaken for
  deterministic B2.3 -> P2 conduction: only the worker that actually
  conducted the work may mark conducted, only after B2.3 + P2 success.
  Terminal task failure stays observable as published + worker_failed_jobs
  DLQ FAILURE + result-backend FAILURE (explicit actionable state joinable
  by task identity); redelivery after failure remains possible, so
  published is never prematurely terminal.
- publish_attempts monotonicity: regression (NEW < OLD) is refused by
  trigger on both dispatch and outbox (a CHECK cannot observe OLD).
- Legacy NULL-window closure: Corrective-III left pre-existing rows with
  NULL window_start/window_end re-derivable (and therefore rewritable to
  arbitrary windows). This migration backfills every NULL window from
  the durable ingress event_timestamp (UTC day quantization in SQL),
  then replaces the immutability trigger with a strict variant that
  refuses ANY window change, including NULL -> value.
- Least-privilege worker writes: the deployed B2.3 worker runs as
  app_worker. It needs column-scoped UPDATE to advance delivery state
  (delivery columns only -- identity columns remain trigger-immutable
  for every principal including migration_owner) and SELECT on tenants
  (transition tenant-list reads). No new INSERT/DELETE anywhere; the
  consumer still cannot mint dispatch/outbox/directory authority.

No P3/P4/P5/P8 durable reconciliation state is introduced. conducted is
an operational delivery state only; it is never read as financial truth
(phase-boundary census enforced by validator).
"""

from __future__ import annotations

from alembic import op

revision = "202609180001"
down_revision = "202609170001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Backfill legacy NULL windows BEFORE the strict trigger exists.
    # UTC day quantization in SQL (half-open [day, day+1)). Explicit AT
    # TIME ZONE 'UTC' both ways: date_trunc on timestamptz otherwise uses
    # the session TimeZone and would quantize to the wrong day boundary.
    #
    # RLS note: dispatch AND ingress both carry FORCE ROW LEVEL SECURITY
    # and the migrating principal holds no tenant GUC, so a bare UPDATE
    # would match zero rows SILENTLY (verified live: migration_owner sees 0
    # rows without GUC, and the ingress JOIN side stays hidden even after
    # disabling dispatch alone). The backfill therefore runs with
    # enforcement transiently disabled on both tables and restores
    # ENABLE + FORCE immediately after; policies are untouched and the
    # final enforcement state is byte-identical (proven by the bootstrap
    # equivalence RLS probes).
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        UPDATE public.b23_match_task_dispatches AS d
        SET window_start = (date_trunc('day', i.event_timestamp AT TIME ZONE 'UTC')) AT TIME ZONE 'UTC',
            window_end = (date_trunc('day', i.event_timestamp AT TIME ZONE 'UTC')) AT TIME ZONE 'UTC' + interval '1 day'
        FROM public.webhook_ingress_identities AS i
        WHERE d.webhook_ingress_identity_id = i.id
          AND d.tenant_id = i.tenant_id
          AND (d.window_start IS NULL OR d.window_end IS NULL)
        """
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.webhook_ingress_identities FORCE ROW LEVEL SECURITY"
    )

    # 2. Expand the delivery-state vocabulary on dispatch + outbox.
    op.execute(
        """
        ALTER TABLE public.b23_match_task_dispatches
            DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_delivery_state
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
                    CHECK (delivery_state IN (
                        'pending_publish', 'published', 'conducted'
                    ));
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_outbox
            DROP CONSTRAINT IF EXISTS ck_b26_p2_outbox_state
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b26_p2_outbox_state'
            ) THEN
                ALTER TABLE public.b26_p2_execution_outbox
                    ADD CONSTRAINT ck_b26_p2_outbox_state
                    CHECK (state IN (
                        'pending_publish', 'published', 'conducted'
                    ));
            END IF;
        END $$;
        """
    )

    # 3. Single execution identity: bind outbox + directory to dispatch.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_b26_p2_outbox_dispatch_task_identity'
            ) THEN
                ALTER TABLE public.b26_p2_execution_outbox
                    ADD CONSTRAINT fk_b26_p2_outbox_dispatch_task_identity
                    FOREIGN KEY (dispatch_task_id)
                    REFERENCES public.b23_match_task_dispatches (task_id)
                    ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_b26_p2_outbox_tenant_ingress_composite'
            ) THEN
                ALTER TABLE public.b26_p2_execution_outbox
                    ADD CONSTRAINT fk_b26_p2_outbox_tenant_ingress_composite
                    FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                    REFERENCES public.webhook_ingress_identities (tenant_id, id)
                    ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_b26_p2_directory_dispatch_task_identity'
            ) THEN
                ALTER TABLE public.b26_p2_task_authority_directory
                    ADD CONSTRAINT fk_b26_p2_directory_dispatch_task_identity
                    FOREIGN KEY (task_id)
                    REFERENCES public.b23_match_task_dispatches (task_id)
                    ON DELETE CASCADE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_b26_p2_directory_tenant_ingress_composite'
            ) THEN
                ALTER TABLE public.b26_p2_task_authority_directory
                    ADD CONSTRAINT fk_b26_p2_directory_tenant_ingress_composite
                    FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                    REFERENCES public.webhook_ingress_identities (tenant_id, id)
                    ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )

    # 4. Strict dispatch transition trigger: forward-only delivery law,
    # monotonic attempts, strict window immutability (NULL hole closed).
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
            -- Corrective IV: strict window immutability. The Corrective-III
            -- NULL-OLD exception is closed (legacy rows backfilled above);
            -- any window rewrite, including NULL -> value, refuses.
            IF OLD.window_start IS DISTINCT FROM NEW.window_start THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            -- Corrective IV: attempts monotonicity (regression refuses).
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_dispatch_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            -- Corrective IV: forward-only delivery law.
            -- pending_publish -> published -> conducted; conducted is
            -- terminal (immutable). Terminal task failure is observed via
            -- worker_failed_jobs DLQ + result backend, never by moving the
            -- delivery state backwards or sideways.
            IF OLD.delivery_state IS DISTINCT FROM NEW.delivery_state THEN
                IF OLD.delivery_state = 'pending_publish'
                   AND NEW.delivery_state = 'published' THEN
                    NULL;
                ELSIF OLD.delivery_state = 'published'
                   AND NEW.delivery_state = 'conducted' THEN
                    NULL;
                ELSE
                    RAISE EXCEPTION 'b26_p2_dispatch_delivery_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """
    )

    # 5. Outbox transition trigger: same delivery law + monotonicity +
    # issuance-identity immutability for the relay/producer surface.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_outbox_transitions()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF OLD.dispatch_task_id IS DISTINCT FROM NEW.dispatch_task_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_task_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_tenant_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RAISE EXCEPTION 'b26_p2_outbox_ingress_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_outbox_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.state IS DISTINCT FROM NEW.state THEN
                IF OLD.state = 'pending_publish'
                   AND NEW.state = 'published' THEN
                    NULL;
                ELSIF OLD.state = 'published'
                   AND NEW.state = 'conducted' THEN
                    NULL;
                ELSE
                    RAISE EXCEPTION 'b26_p2_outbox_illegal_transition'
                        USING ERRCODE = '42501';
                END IF;
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
                WHERE tgname = 'trg_b26_p2_outbox_transitions'
            ) THEN
                CREATE TRIGGER trg_b26_p2_outbox_transitions
                BEFORE UPDATE ON public.b26_p2_execution_outbox
                FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_outbox_transitions();
            END IF;
        END $$;
        """
    )

    # 6. Least-privilege worker writes: app_worker may advance DELIVERY
    # columns only (column-scoped UPDATE). Identity columns stay
    # trigger-immutable for every principal. Existence-guarded for
    # bare-database lanes without provisioned roles.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                EXECUTE 'GRANT UPDATE (delivery_state, publish_attempts,'
                    ' last_publish_error, updated_at)'
                    ' ON TABLE public.b23_match_task_dispatches TO app_worker';
                EXECUTE 'GRANT UPDATE (state, publish_attempts,'
                    ' last_publish_error, next_retry_at, updated_at)'
                    ' ON TABLE public.b26_p2_execution_outbox TO app_worker';
                EXECUTE 'GRANT SELECT ON TABLE public.tenants TO app_worker';
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
                REVOKE UPDATE ON TABLE public.b26_p2_execution_outbox FROM app_worker;
                REVOKE UPDATE ON TABLE public.b23_match_task_dispatches FROM app_worker;
                REVOKE SELECT ON TABLE public.tenants FROM app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV worker delivery grants.
    )
    op.execute("DROP TRIGGER IF EXISTS trg_b26_p2_outbox_transitions ON public.b26_p2_execution_outbox")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV outbox law.
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_enforce_outbox_transitions()")  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV outbox law.
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_tenant_ingress_composite"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV coherence.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_dispatch_task_identity"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV coherence.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_tenant_ingress_composite"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV coherence.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_dispatch_task_identity"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV coherence.
    )
    # Restore the two-state vocabulary: conducted rows step back to
    # published first so the narrowed CHECK admits every existing row.
    op.execute(
        """
        UPDATE public.b23_match_task_dispatches
        SET delivery_state = 'published'
        WHERE delivery_state = 'conducted'
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    op.execute(
        """
        UPDATE public.b26_p2_execution_outbox
        SET state = 'published'
        WHERE state = 'conducted'
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_task_dispatches
            DROP CONSTRAINT IF EXISTS ck_b23_match_task_dispatches_delivery_state
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_task_dispatches
            ADD CONSTRAINT ck_b23_match_task_dispatches_delivery_state
            CHECK (delivery_state IN ('pending_publish', 'published'))
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_outbox
            DROP CONSTRAINT IF EXISTS ck_b26_p2_outbox_state
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_outbox
            ADD CONSTRAINT ck_b26_p2_outbox_state
            CHECK (state IN ('pending_publish', 'published'))
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV delivery vocabulary.
    )
    # Restore the Corrective-III dispatch trigger (NULL-window exception +
    # two-state transition law). Full removal stays owned by the
    # Corrective-III downgrade.
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
            IF OLD.delivery_state = 'published' AND NEW.delivery_state = 'pending_publish' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_delivery_no_backward'
                    USING ERRCODE = '42501';
            END IF;
            NEW.updated_at = now();
            RETURN NEW;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective IV trigger law.
    )
