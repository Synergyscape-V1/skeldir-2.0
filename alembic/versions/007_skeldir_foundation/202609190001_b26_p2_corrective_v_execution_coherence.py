"""B2.6-P2 Corrective V: one physical execution tuple, consequence-bound
conduction, published-unconsumed honesty, least-privilege recovery.

Revision ID: 202609190001
Revises: 202609180001

Corrective-IV closed the deployment-plane class but left three related
trust properties false (auditors T and N, 2026-09-19, NOT COMPLETE):

1. MULTIPLE LOCALLY VALID PROJECTIONS DO NOT CONSTITUTE ONE EXECUTION
   AUTHORITY. The four IV foreign keys are two independent legs
   (task-only -> dispatches, tenant/ingress-only -> ingress), not one
   coherent (task, tenant, ingress) tuple. A child row combining
   task(D1) + tenant/ingress(D2) satisfies every FK and persists.

2. `conducted` IS NOT PHYSICALLY BOUND TO THE CONSEQUENCE IT ASSERTS.
   app_worker can mark any same-tenant published task conducted with a
   generic column UPDATE, with zero B2.3/P2 consequence.

3. `published` WORK CAN REMAIN PERMANENTLY UNCONSUMED WITHOUT A
   GOVERNED PRODUCTION-VISIBLE SIGNAL. No staleness law exists; the
   housekeeping health probe is blind to b23_match_engine.

Database-physics changes (this migration):

- Class A (one execution tuple): dispatches gains
  UNIQUE(task_id, tenant_id, webhook_ingress_identity_id)
  (uq_b23_dispatch_execution_tuple). The two child coherence legs are
  replaced by single-parent composite foreign keys against that exact
  tuple:
    outbox(dispatch_task_id, tenant_id, webhook_ingress_identity_id)
      -> dispatches(task_id, tenant_id, webhook_ingress_identity_id)
    directory(task_id, tenant_id, webhook_ingress_identity_id)
      -> dispatches(task_id, tenant_id, webhook_ingress_identity_id)
  A child can no longer satisfy its FKs against two different parents.
  The direct child->ingress composite FKs are dropped: the tuple path
  through dispatches (which itself FKs ingress) is the single parent.
  ON DELETE CASCADE is preserved: a projection cannot outlive the
  execution it projects (cardinality conservation, not provenance
  destruction of accepted truth -- dispatch rows themselves are never
  deleted by any runtime path).
- Census / repair / durable quarantine: before the tuple law installs,
  every outbox/directory row is classified. A row whose task matches
  exactly one dispatch is deterministically repaired to that dispatch's
  tuple (tenant, ingress, directory window). A row with no dispatch
  parent, or a row occupying another execution's repair target, is moved
  to the durable b26_p2_execution_quarantine table (original identity,
  reason, source relation, timestamp, migration identity) -- never
  silently deleted. Coherent rows are untouched.
- Class B (window coherence): the admission directory gains a
  write-time coherence law (b26_p2_enforce_directory_coherence):
  INSERT/UPDATE must carry exactly the dispatch row's
  (tenant, ingress, window); any divergence -- including a forged
  window on a lawful task -- refuses. UPDATE of any directory identity
  or window field refuses (strict immutability, NULL-safe via
  IS DISTINCT FROM). The writer's own tenant GUC is the visibility
  root (same-tenant dispatch row must be visible, else refuse
  fail-closed), so no BYPASSRLS or FORCE weakening is required.
- Class C (consequence-bound conducted): direct transitions INTO
  `conducted` are closed to every runtime principal. The dispatch and
  outbox transition triggers admit pending_publish -> published ->
  conducted only when performed by the migration owner -- i.e. inside
  the constrained b26_p2_mark_conducted() SECURITY DEFINER gate or by a
  migration. The gate requires, for exactly the named task: dispatch
  and outbox both published (twin projections agree), a conduction
  receipt matching the tuple, B2.3 verdict consequence for the bound
  (tenant, ingress), and caller session_user app_worker (SET ROLE
  cannot forge session_user). Already-conducted is an idempotent
  no-op (crash-boundary convergence). Celery result state is never
  consulted (transport is corroboration, not truth).
- Conduction receipts (b26_p2_conduction_receipts): narrow operational
  provenance per execution (task PK, tuple FK to dispatches, window,
  B2.3 processed count, P2 scope identity). Never financial truth:
  no P3 reason, no P4 snapshot, never read as reconciliation truth
  (phase-boundary census covers this).
- Class D (published-unconsumed honesty): b26_p2_stale_unconducted()
  exposes published twin rows older than a governed threshold
  (default 300s) as an operational signal. It alters no financial
  state; the relay sweep logs it and the conduction health endpoint
  serves it.
- Least privilege: dedicated recovery logins app_relay (SELECT plus
  delivery-column UPDATE on dispatch/outbox, broker DML) and app_beat
  (broker DML only). Neither can INSERT/UPDATE/DELETE execution
  authority, directory, receipts, or quarantine, nor EXECUTE the
  conduction gate or the admission resolver.

No P3/P4/P5/P8 durable reconciliation state is introduced. conducted,
receipts, quarantine rows, and staleness remain operational state.
"""

from __future__ import annotations

from alembic import op

revision = "202609190001"
down_revision = "202609180001"
branch_labels = None
depends_on = None

_MIGRATION_IDENTITY = "202609190001"


def upgrade() -> None:
    # 0. Lock ordering first (Corrective-IV discipline): the two child
    # tables are locked IN SHARE ROW EXCLUSIVE MODE before this
    # transaction holds any other table lock, so the census/repair/
    # quarantine snapshots below cannot interleave with a concurrent
    # child writer. Only the child tables are locked: locking the
    # dispatch parent too deadlocks against a coherent triple writer
    # holding an uncommitted dispatch row (reproduced in IV).
    op.execute(
        "LOCK TABLE public.b26_p2_execution_outbox IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_task_authority_directory IN SHARE ROW EXCLUSIVE MODE"
    )

    # 1. Durable quarantine table: ambiguous execution evidence receives
    # durable disposition (identity, reason, source, timestamp,
    # migration) instead of NOTICE-only deletion. Tenant RLS (like the
    # outbox) so the phase4 coverage probe holds with no exemption;
    # runtime roles hold SELECT only -- only the migration owner moves
    # rows here.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_execution_quarantine (
            id uuid DEFAULT gen_random_uuid() NOT NULL,
            source_relation text NOT NULL,
            task_id character varying(155) NOT NULL,
            tenant_id uuid NULL REFERENCES public.tenants(id) ON DELETE SET NULL,
            webhook_ingress_identity_id uuid NULL,
            window_start timestamp with time zone NULL,
            window_end timestamp with time zone NULL,
            reason text NOT NULL,
            original_payload jsonb DEFAULT '{}'::jsonb NOT NULL,
            migration_identity text NOT NULL,
            quarantined_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b26_p2_execution_quarantine_pkey PRIMARY KEY (id),
            CONSTRAINT ck_b26_p2_quarantine_source
                CHECK (source_relation IN (
                    'b26_p2_execution_outbox',
                    'b26_p2_task_authority_directory'
                )),
            CONSTRAINT ck_b26_p2_quarantine_reason_not_blank
                CHECK (char_length(reason) > 0)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b26_p2_execution_quarantine IS
            'B2.6-P2 Corrective V durable quarantine: incoherent execution projections removed by migration with full provenance. Operational/audit state only; never financial truth.'
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_quarantine FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'b26_p2_execution_quarantine'
                  AND policyname = 'tenant_isolation_policy_b26_p2_execution_quarantine'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_execution_quarantine
                ON public.b26_p2_execution_quarantine
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            END IF;
        END $$;
        """
    )

    # 2. Conduction receipts: narrow operational provenance per
    # execution. The tuple FK binds every receipt to exactly one
    # canonical execution; receipts for forked authority are
    # unencodable. Tenant RLS like the outbox.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_conduction_receipts (
            task_id character varying(155) NOT NULL,
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            webhook_ingress_identity_id uuid NOT NULL
                REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE,
            window_start timestamp with time zone NOT NULL,
            window_end timestamp with time zone NOT NULL,
            b23_processed_count integer NOT NULL DEFAULT 0,
            p2_scope_identity text NOT NULL,
            created_at timestamp with time zone DEFAULT now() NOT NULL,
            CONSTRAINT b26_p2_conduction_receipts_pkey PRIMARY KEY (task_id),
            CONSTRAINT ck_b26_p2_receipt_window_order
                CHECK (window_start < window_end),
            CONSTRAINT ck_b26_p2_receipt_processed_non_negative
                CHECK (b23_processed_count >= 0),
            CONSTRAINT ck_b26_p2_receipt_scope_not_blank
                CHECK (char_length(p2_scope_identity) > 0)
        )
        """
    )
    op.execute(
        """
        COMMENT ON TABLE public.b26_p2_conduction_receipts IS
            'B2.6-P2 Corrective V conduction receipts: task-specific operational provenance (B2.3 count + P2 scope identity) required by the conducted gate. Operational state only; never financial truth.'
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_conduction_receipts FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'b26_p2_conduction_receipts'
                  AND policyname = 'tenant_isolation_policy_b26_p2_conduction_receipts'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_conduction_receipts
                ON public.b26_p2_conduction_receipts
                USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
            END IF;
        END $$;
        """
    )

    # 3. Recovery principals are provisioned by
    # prepare_migration_authority_boundary.py (the migrating principal
    # holds no CREATEROLE, so migrations never create logins -- they
    # only grant, existence-guarded, exactly like the app_worker
    # precedent). Bare-role lanes keep working; provisioned lanes get
    # the least-privilege shape below (step 10).

    # 4. The canonical execution-tuple key. This UNIQUE is what makes
    # the single-parent composite FKs below structurally possible
    # (Postgres requires the referenced columns to be unique).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_b23_dispatch_execution_tuple'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT uq_b23_dispatch_execution_tuple
                    UNIQUE (task_id, tenant_id, webhook_ingress_identity_id);
            END IF;
        END $$;
        """
    )

    # 4b. Issuance-time window coherence (H-V-B04 sibling): a dispatch
    # without a persisted window is not an executable authority (no
    # directory row can bind it, no admission can resolve it). Forbid
    # NULL windows at the boundary instead of merely immunizing their
    # rewrites. The NULL census lives inside the RLS-disabled census
    # block below (a bare count would match zero rows silently under
    # FORCE RLS and pass vacuously).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_dispatch_window_present'
            ) THEN
                ALTER TABLE public.b23_match_task_dispatches
                    ADD CONSTRAINT ck_b23_dispatch_window_present
                    CHECK (window_start IS NOT NULL AND window_end IS NOT NULL);
            END IF;
        END $$;
        """
    )

    # 5. Census / deterministic repair / durable quarantine, converged
    # by bounded retry (IV discipline: quarantine and FK validation run
    # as separate statements under READ COMMITTED; a parent-side delete
    # landing between snapshots must re-converge, not fail opaquely).
    # RLS is transiently disabled on the census tables exactly as in IV
    # (the migrating principal holds no tenant GUC; a bare census would
    # match zero rows SILENTLY) and restored immediately after.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DISABLE ROW LEVEL SECURITY"
    )
    # The Corrective-IV outbox transition trigger freezes tenant/ingress
    # on UPDATE (issuance immutability). Deterministic repair must move
    # drifted children back onto their canonical tuple, so the trigger
    # is parked for the census window only: the step-0 child-table locks
    # already fence every concurrent writer, the trigger is re-enabled
    # before this transaction commits, and the repaired rows satisfy the
    # re-enabled law by construction (they equal their dispatch tuple).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_outbox_transitions'
            ) THEN
                ALTER TABLE public.b26_p2_execution_outbox
                    DISABLE TRIGGER trg_b26_p2_outbox_transitions;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            attempt integer := 0;
            _n_parentless_outbox integer := 0;
            _n_parentless_dir integer := 0;
            _n_repaired_outbox integer := 0;
            _n_repaired_dir integer := 0;
            _n_blocker integer := 0;
            _fk_present integer := 0;
            _remaining integer := 0;
            _q_outbox_total integer := 0;
            _q_dir_total integer := 0;
        BEGIN
            LOOP
                -- 5a. NULL-window census (RLS-disabled): a surviving
                -- NULL window is not executable authority and can
                -- neither be repaired (inventing time) nor quarantined
                -- as a child projection. Fail closed.
                SELECT count(*) INTO _remaining
                FROM public.b23_match_task_dispatches AS d
                WHERE d.window_start IS NULL OR d.window_end IS NULL;
                IF _remaining <> 0 THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_null_window_survives:%',
                        _remaining;
                END IF;
                -- 5a. Parentless rows can never lawfully conduct (the
                -- admission resolver requires a dispatch row and the P2
                -- tail requires dispatch authority): move to durable
                -- quarantine, preserving identity and payload.
                INSERT INTO public.b26_p2_execution_quarantine (
                    source_relation, task_id, tenant_id,
                    webhook_ingress_identity_id, window_start, window_end,
                    reason, original_payload, migration_identity
                )
                SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                       o.webhook_ingress_identity_id, NULL, NULL,
                       'corrective_v:parentless_outbox_no_dispatch_parent',
                       COALESCE(o.payload, '{}'::jsonb), '202609190001'
                FROM public.b26_p2_execution_outbox AS o
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = o.dispatch_task_id
                );
                GET DIAGNOSTICS _n_parentless_outbox = ROW_COUNT;
                DELETE FROM public.b26_p2_execution_outbox AS o
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = o.dispatch_task_id
                );
                INSERT INTO public.b26_p2_execution_quarantine (
                    source_relation, task_id, tenant_id,
                    webhook_ingress_identity_id, window_start, window_end,
                    reason, original_payload, migration_identity
                )
                SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                       dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                       'corrective_v:parentless_directory_no_dispatch_parent',
                       jsonb_build_object(
                           'window_start', dir.window_start::text,
                           'window_end', dir.window_end::text
                       ), '202609190001'
                FROM public.b26_p2_task_authority_directory AS dir
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = dir.task_id
                );
                GET DIAGNOSTICS _n_parentless_dir = ROW_COUNT;
                DELETE FROM public.b26_p2_task_authority_directory AS dir
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = dir.task_id
                );
                _q_outbox_total := _q_outbox_total + _n_parentless_outbox;
                _q_dir_total := _q_dir_total + _n_parentless_dir;

                -- 5b. Blocker rows: a child occupying another execution's
                -- repair target (same tenant/ingress, different task)
                -- cannot be repaired in place and has no authoritative
                -- parent for its current tuple: quarantine durably.
                INSERT INTO public.b26_p2_execution_quarantine (
                    source_relation, task_id, tenant_id,
                    webhook_ingress_identity_id, window_start, window_end,
                    reason, original_payload, migration_identity
                )
                SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                       o.webhook_ingress_identity_id, NULL, NULL,
                       'corrective_v:cross_product_blocker_occupies_foreign_repair_target',
                       COALESCE(o.payload, '{}'::jsonb), '202609190001'
                FROM public.b26_p2_execution_outbox AS o
                WHERE EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.tenant_id = o.tenant_id
                      AND d.webhook_ingress_identity_id = o.webhook_ingress_identity_id
                      AND d.task_id IS DISTINCT FROM o.dispatch_task_id
                );
                GET DIAGNOSTICS _n_blocker = ROW_COUNT;
                _q_outbox_total := _q_outbox_total + _n_blocker;
                DELETE FROM public.b26_p2_execution_outbox AS o
                WHERE EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.tenant_id = o.tenant_id
                      AND d.webhook_ingress_identity_id = o.webhook_ingress_identity_id
                      AND d.task_id IS DISTINCT FROM o.dispatch_task_id
                );
                INSERT INTO public.b26_p2_execution_quarantine (
                    source_relation, task_id, tenant_id,
                    webhook_ingress_identity_id, window_start, window_end,
                    reason, original_payload, migration_identity
                )
                SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                       dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                       'corrective_v:cross_product_blocker_occupies_foreign_repair_target',
                       jsonb_build_object(
                           'window_start', dir.window_start::text,
                           'window_end', dir.window_end::text
                       ), '202609190001'
                FROM public.b26_p2_task_authority_directory AS dir
                WHERE EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.tenant_id = dir.tenant_id
                      AND d.webhook_ingress_identity_id = dir.webhook_ingress_identity_id
                      AND d.task_id IS DISTINCT FROM dir.task_id
                );
                GET DIAGNOSTICS _n_blocker = ROW_COUNT;
                _q_dir_total := _q_dir_total + _n_blocker;
                DELETE FROM public.b26_p2_task_authority_directory AS dir
                WHERE EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.tenant_id = dir.tenant_id
                      AND d.webhook_ingress_identity_id = dir.webhook_ingress_identity_id
                      AND d.task_id IS DISTINCT FROM dir.task_id
                );

                -- 5c. Deterministic repair: exactly one authoritative
                -- parent is inferable from the task identity, so the
                -- child's tuple (and directory window) is set to the
                -- canonical dispatch values. Coherent rows match
                -- already and are untouched.
                UPDATE public.b26_p2_execution_outbox AS o
                SET tenant_id = d.tenant_id,
                    webhook_ingress_identity_id = d.webhook_ingress_identity_id,
                    updated_at = now()
                FROM public.b23_match_task_dispatches AS d
                WHERE d.task_id = o.dispatch_task_id
                  AND (o.tenant_id IS DISTINCT FROM d.tenant_id
                       OR o.webhook_ingress_identity_id IS DISTINCT FROM d.webhook_ingress_identity_id);
                GET DIAGNOSTICS _n_repaired_outbox = ROW_COUNT;
                UPDATE public.b26_p2_task_authority_directory AS dir
                SET tenant_id = d.tenant_id,
                    webhook_ingress_identity_id = d.webhook_ingress_identity_id,
                    window_start = d.window_start,
                    window_end = d.window_end
                FROM public.b23_match_task_dispatches AS d
                WHERE d.task_id = dir.task_id
                  AND (dir.tenant_id IS DISTINCT FROM d.tenant_id
                       OR dir.webhook_ingress_identity_id IS DISTINCT FROM d.webhook_ingress_identity_id
                       OR dir.window_start IS DISTINCT FROM d.window_start
                       OR dir.window_end IS DISTINCT FROM d.window_end);
                GET DIAGNOSTICS _n_repaired_dir = ROW_COUNT;

                -- 5d. Install the tuple law. Validation inspects every
                -- existing row: any surviving incoherence fails here
                -- and the loop re-converges (parent-side delete race).
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_b26_p2_outbox_execution_tuple'
                    ) THEN
                        ALTER TABLE public.b26_p2_execution_outbox
                            ADD CONSTRAINT fk_b26_p2_outbox_execution_tuple
                            FOREIGN KEY (dispatch_task_id, tenant_id, webhook_ingress_identity_id)
                            REFERENCES public.b23_match_task_dispatches
                                (task_id, tenant_id, webhook_ingress_identity_id)
                            ON DELETE CASCADE;
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_b26_p2_directory_execution_tuple'
                    ) THEN
                        ALTER TABLE public.b26_p2_task_authority_directory
                            ADD CONSTRAINT fk_b26_p2_directory_execution_tuple
                            FOREIGN KEY (task_id, tenant_id, webhook_ingress_identity_id)
                            REFERENCES public.b23_match_task_dispatches
                                (task_id, tenant_id, webhook_ingress_identity_id)
                            ON DELETE CASCADE;
                    END IF;
                    -- Receipts are projections of D too: same tuple law.
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint
                        WHERE conname = 'fk_b26_p2_receipt_execution_tuple'
                    ) THEN
                        ALTER TABLE public.b26_p2_conduction_receipts
                            ADD CONSTRAINT fk_b26_p2_receipt_execution_tuple
                            FOREIGN KEY (task_id, tenant_id, webhook_ingress_identity_id)
                            REFERENCES public.b23_match_task_dispatches
                                (task_id, tenant_id, webhook_ingress_identity_id)
                            ON DELETE CASCADE;
                    END IF;
                EXCEPTION WHEN OTHERS THEN
                    attempt := attempt + 1;
                    IF attempt >= 8 THEN
                        RAISE;
                    END IF;
                    RAISE NOTICE 'b26_p2_coherence_v_retry attempt=%', attempt;
                    CONTINUE;
                END;
                SELECT count(*) INTO _fk_present FROM pg_constraint
                WHERE conname IN (
                    'fk_b26_p2_outbox_execution_tuple',
                    'fk_b26_p2_directory_execution_tuple',
                    'fk_b26_p2_receipt_execution_tuple'
                );
                IF _fk_present = 3 THEN
                    EXIT;
                END IF;
                attempt := attempt + 1;
                IF attempt >= 8 THEN
                    RAISE EXCEPTION 'b26_p2_coherence_v_not_convergent';
                END IF;
            END LOOP;
            -- 5e. The two-leg IV FKs are superseded by the tuple law:
            -- the tuple path through dispatches (which itself FKs
            -- ingress) is now the single parent. Drop the redundant
            -- legs so no sibling mechanism can validate membership
            -- without identity.
            ALTER TABLE public.b26_p2_execution_outbox
                DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_dispatch_task_identity;
            ALTER TABLE public.b26_p2_execution_outbox
                DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_tenant_ingress_composite;
            ALTER TABLE public.b26_p2_task_authority_directory
                DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_dispatch_task_identity;
            ALTER TABLE public.b26_p2_task_authority_directory
                DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_tenant_ingress_composite;
            SELECT count(*) INTO _remaining
            FROM (
                SELECT o.dispatch_task_id AS task_id, o.tenant_id,
                       o.webhook_ingress_identity_id AS ingress_id
                FROM public.b26_p2_execution_outbox AS o
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = o.dispatch_task_id
                      AND d.tenant_id = o.tenant_id
                      AND d.webhook_ingress_identity_id = o.webhook_ingress_identity_id
                )
                UNION ALL
                SELECT dir.task_id, dir.tenant_id, dir.webhook_ingress_identity_id
                FROM public.b26_p2_task_authority_directory AS dir
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = dir.task_id
                      AND d.tenant_id = dir.tenant_id
                      AND d.webhook_ingress_identity_id = dir.webhook_ingress_identity_id
                )
            ) AS incoherent;
            RAISE NOTICE 'b26_p2_corrective_v_census outbox_quarantined=% directory_quarantined=% outbox_repaired=% directory_repaired=% attempts=% residual_incoherent=%',
                _q_outbox_total, _q_dir_total, _n_repaired_outbox, _n_repaired_dir,
                attempt + 1, _remaining;
            IF _remaining <> 0 THEN
                RAISE EXCEPTION 'b26_p2_coherence_v_residual_incoherent:%', _remaining;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_outbox_transitions'
            ) THEN
                ALTER TABLE public.b26_p2_execution_outbox
                    ENABLE TRIGGER trg_b26_p2_outbox_transitions;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_outbox FORCE ROW LEVEL SECURITY"
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
    # The admission directory stays RLS-disabled (pre-IV state
    # preserved); the new operational tables return to ENABLE + FORCE.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_quarantine FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_conduction_receipts FORCE ROW LEVEL SECURITY"
    )

    # 6. Directory write-time coherence + strict immutability. The
    # writer's own tenant GUC is the visibility root: the canonical
    # dispatch row for NEW.task_id must be visible under it and the
    # full tuple plus window must match, else refuse fail-closed.
    # IS DISTINCT FROM keeps NULL (UNKNOWN) from becoming acceptance.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_directory_coherence()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _d_tenant uuid;
            _d_ingress uuid;
            _d_ws timestamptz;
            _d_we timestamptz;
        BEGIN
            IF NEW.task_id IS NULL OR NEW.tenant_id IS NULL
               OR NEW.webhook_ingress_identity_id IS NULL
               OR NEW.window_start IS NULL OR NEW.window_end IS NULL THEN
                RAISE EXCEPTION 'b26_p2_directory_authority_null_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.task_id IS DISTINCT FROM NEW.task_id THEN
                    RAISE EXCEPTION 'b26_p2_directory_task_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                    RAISE EXCEPTION 'b26_p2_directory_tenant_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                    RAISE EXCEPTION 'b26_p2_directory_ingress_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.window_start IS DISTINCT FROM NEW.window_start
                   OR OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                    RAISE EXCEPTION 'b26_p2_directory_window_immutable'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            SELECT d.tenant_id, d.webhook_ingress_identity_id,
                   d.window_start, d.window_end
              INTO _d_tenant, _d_ingress, _d_ws, _d_we
              FROM public.b23_match_task_dispatches AS d
             WHERE d.task_id = NEW.task_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_directory_no_canonical_execution'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM _d_tenant
               OR NEW.webhook_ingress_identity_id IS DISTINCT FROM _d_ingress
               OR NEW.window_start IS DISTINCT FROM _d_ws
               OR NEW.window_end IS DISTINCT FROM _d_we THEN
                RAISE EXCEPTION 'b26_p2_directory_forked_authority_refused'
                    USING ERRCODE = '42501';
            END IF;
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
                WHERE tgname = 'trg_b26_p2_directory_coherence'
            ) THEN
                CREATE TRIGGER trg_b26_p2_directory_coherence
                BEFORE INSERT OR UPDATE ON public.b26_p2_task_authority_directory
                FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_directory_coherence();
            END IF;
        END $$;
        """
    )

    # 7. Conducted-gate clause on the dispatch delivery law: transitions
    # INTO conducted are admitted only from the migration owner -- i.e.
    # inside b26_p2_mark_conducted() (SECURITY DEFINER, owner
    # migration_owner) or by a migration. Direct runtime UPDATEs into
    # conducted (any app role, any GUC) refuse. All other transitions
    # keep the IV law byte-identically.
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
            IF OLD.window_start IS DISTINCT FROM NEW.window_start THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_dispatch_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.delivery_state IS DISTINCT FROM NEW.delivery_state THEN
                IF OLD.delivery_state = 'pending_publish'
                   AND NEW.delivery_state = 'published' THEN
                    NULL;
                ELSIF OLD.delivery_state = 'published'
                   AND NEW.delivery_state = 'conducted' THEN
                    -- Corrective V: only the conduction gate (owner
                    -- execution context) may assert conducted. A
                    -- superuser-equivalent owner session (migrations,
                    -- governed repair) is likewise admitted; every
                    -- other principal must pass through the gate.
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
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
                    -- Corrective V: same gate law as dispatch above.
                    IF current_user NOT IN ('migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_conducted_requires_gate'
                            USING ERRCODE = '42501';
                    END IF;
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

    # 8. The conduction gate: the single server-side path that may
    # assert conducted. Owned by the migrating principal; fixed
    # search_path; no dynamic SQL; EXECUTE granted to app_worker only.
    # session_user (unforgeable by SET ROLE) binds the caller to the
    # worker login. The tenant GUC is bootstrapped from the
    # bearer-keyed directory (tuple-bound to the canonical dispatch,
    # so it cannot select a foreign visibility root) and restored on
    # exit; all authority reads then run under that tenant.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_mark_conducted(p_task_id text)
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _outbox_state text;
            _receipt_count integer;
            _verdict_count integer;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_conducted_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            -- Caller capability: only the worker login (or governed
            -- owner sessions: migrations, repair) may invoke the gate.
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_conducted_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- Bearer-keyed root: the directory carries no RLS by
            -- design, so it resolves without a caller GUC.
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            -- Bootstrap the tenant visibility root from the canonical
            -- tuple (directory is tuple-bound; it cannot name a
            -- foreign tenant for this task). Transaction-local so no
            -- caller session state leaks.
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state INTO _dispatch_state
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT o.state INTO _outbox_state
                  FROM public.b26_p2_execution_outbox AS o
                 WHERE o.dispatch_task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_outbox'
                        USING ERRCODE = '42501';
                END IF;
                -- Crash-boundary idempotence: a gate that already fired
                -- for this task converges without a second transition.
                IF _dispatch_state = 'conducted' AND _outbox_state = 'conducted' THEN
                    PERFORM set_config('app.current_tenant_id',
                                       COALESCE(_prev_guc, ''), true);
                    RETURN 'already_conducted';
                END IF;
                IF _dispatch_state IS DISTINCT FROM 'published'
                   OR _outbox_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_not_published'
                        USING ERRCODE = '42501';
                END IF;
                -- Task-specific consequence: the conduction receipt
                -- matching this exact tuple must exist (worker
                -- persisted it after B2.3 + P2 success).
                SELECT count(*) INTO _receipt_count
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task
                   AND r.tenant_id = _tenant
                   AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_receipt'
                        USING ERRCODE = '42501';
                END IF;
                -- Task-specific consequence: B2.3 verdicts for the
                -- bound (tenant, ingress) must exist. Verdicts are
                -- written only by the engine under admitted authority,
                -- so their presence proves the governed consequence.
                SELECT count(*) INTO _verdict_count
                  FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress;
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_b23_consequence'
                        USING ERRCODE = '42501';
                END IF;
                UPDATE public.b23_match_task_dispatches AS d
                   SET delivery_state = 'conducted', updated_at = now()
                 WHERE d.task_id = _task AND d.delivery_state = 'published';
                UPDATE public.b26_p2_execution_outbox AS o
                   SET state = 'conducted', updated_at = now()
                 WHERE o.dispatch_task_id = _task AND o.state = 'published';
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN 'conducted';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_mark_conducted(text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text) TO app_worker;
            END IF;
        END $$;
        """
    )

    # 9. Governed staleness signal: published twin rows older than the
    # threshold are operationally actionable (not silently healthy).
    # Plain (non-DEFINER) function: callers invoke it under their own
    # tenant GUC (health loops tenants; the relay sweep already runs
    # per-tenant), so RLS/KUC physics is unchanged. Alters no state.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_stale_unconducted(
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS TABLE (
            task_id character varying(155),
            tenant_id uuid,
            state character varying(32),
            age_seconds double precision,
            updated_at timestamp with time zone
        )
        LANGUAGE sql
        STABLE
        SET search_path TO 'public', 'pg_temp'
        AS $$
            SELECT d.task_id, d.tenant_id, d.delivery_state,
                   EXTRACT(EPOCH FROM (now() - GREATEST(d.updated_at, o.updated_at))),
                   GREATEST(d.updated_at, o.updated_at)
            FROM public.b23_match_task_dispatches AS d
            JOIN public.b26_p2_execution_outbox AS o
              ON o.dispatch_task_id = d.task_id
             AND o.tenant_id = d.tenant_id
             AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id
            WHERE d.delivery_state = 'published'
              AND o.state = 'published'
              AND GREATEST(d.updated_at, o.updated_at)
                  < now() - (GREATEST(COALESCE(p_stale_after_seconds, 300), 1) || ' seconds')::interval
              -- Terminal task failure is owned by the DLQ + result
              -- backend (failed, actionable there), not by the
              -- never-consumed signal: a FAILED task is not silent
              -- in-flight work.
              AND NOT EXISTS (
                    SELECT 1 FROM public.celery_taskmeta AS m
                     WHERE m.task_id = d.task_id
                       AND m.status = 'FAILURE'
              )
            ORDER BY GREATEST(d.updated_at, o.updated_at) ASC
        $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_user"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_relay;
            END IF;
        END $$;
        """
    )

    # 10. Least-privilege recovery principals. The relay recovers and
    # publishes EXISTING execution authority (SELECT + delivery-column
    # UPDATE + broker DML); it never mints execution authority (no
    # INSERT anywhere, no gate/resolver EXECUTE). Beat schedules relay
    # work (broker DML only); it holds no application-table authority
    # at all. Transport tables are not execution authority. (CONNECT
    # rides the default PUBLIC grant governed by the authority
    # boundary preparation; USAGE below is the schema-level grant.)
    # Existence-guarded: bare-role lanes without provisioned logins
    # migrate cleanly and converge on reprovision.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT USAGE ON SCHEMA public TO app_relay;
                GRANT SELECT ON TABLE public.tenants TO app_relay;
                GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_relay;
                GRANT SELECT ON TABLE public.b26_p2_execution_outbox TO app_relay;
                GRANT SELECT ON TABLE public.webhook_ingress_identities TO app_relay;
                GRANT UPDATE (delivery_state, publish_attempts,
                              last_publish_error, updated_at)
                    ON TABLE public.b23_match_task_dispatches TO app_relay;
                GRANT UPDATE (state, publish_attempts,
                              last_publish_error, next_retry_at, updated_at)
                    ON TABLE public.b26_p2_execution_outbox TO app_relay;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_message TO app_relay;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_queue TO app_relay;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_relay;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_relay;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                GRANT USAGE ON SCHEMA public TO app_beat;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_message TO app_beat;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.kombu_queue TO app_beat;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta TO app_beat;
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.celery_tasksetmeta TO app_beat;
                -- Broker transport mints queue rows via sequences.
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_beat;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_relay;
            END IF;
        END $$;
        """
    )
    # Receipt/quarantine readability for the worker and audit roles.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT, INSERT ON TABLE public.b26_p2_conduction_receipts TO app_worker;
                GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_conduction_receipts TO app_ro"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_ro"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_execution_quarantine TO app_user"
    )


def downgrade() -> None:
    # Reverse order of upgrade. All destructive steps carry the
    # CI:DESTRUCTIVE_OK marker (reversible rollback, non-production
    # direction only).
    op.execute(
        "REVOKE SELECT ON TABLE public.b26_p2_execution_quarantine FROM app_user"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V quarantine readability.
    )
    op.execute(
        "REVOKE SELECT ON TABLE public.b26_p2_execution_quarantine FROM app_ro"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V quarantine readability.
    )
    op.execute(
        "REVOKE SELECT ON TABLE public.b26_p2_conduction_receipts FROM app_ro"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V receipt readability.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE ALL ON TABLE public.b26_p2_execution_quarantine FROM app_worker;
                REVOKE ALL ON TABLE public.b26_p2_conduction_receipts FROM app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V receipt/quarantine grants.
    )
    for _table in (
        "public.kombu_message",
        "public.kombu_queue",
        "public.celery_taskmeta",
        "public.celery_tasksetmeta",
    ):
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN"
            f" REVOKE ALL ON TABLE {_table} FROM app_beat; END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery transport grants.
        )
        op.execute(
            f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
            f" REVOKE ALL ON TABLE {_table} FROM app_relay; END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery transport grants.
        )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
        " REVOKE UPDATE ON TABLE public.b26_p2_execution_outbox FROM app_relay;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V relay delivery grants.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
        " REVOKE UPDATE ON TABLE public.b23_match_task_dispatches FROM app_relay;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V relay delivery grants.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
        " REVOKE SELECT ON TABLE public.webhook_ingress_identities FROM app_relay;"
        " REVOKE SELECT ON TABLE public.b26_p2_execution_outbox FROM app_relay;"
        " REVOKE SELECT ON TABLE public.b23_match_task_dispatches FROM app_relay;"
        " REVOKE SELECT ON TABLE public.tenants FROM app_relay;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V relay reads.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN"
        " REVOKE USAGE ON SCHEMA public FROM app_beat;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery principals.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
        " REVOKE USAGE ON SCHEMA public FROM app_relay;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery principals.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN"
        " REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_relay;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery transport grants.
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN"
        " REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_beat;"
        " END IF; END $$;"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V recovery transport grants.
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM app_user"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V staleness signal.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) FROM app_relay;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V staleness signal.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_stale_unconducted(integer)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V staleness signal.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                REVOKE EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text) FROM app_worker;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V conduction gate.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_mark_conducted(text)"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V conduction gate.
    )
    # Restore the IV transition law (no gate clause) BEFORE the
    # vocabulary step-down below: the step-down writes
    # conducted -> published, which the V law forbids for runtime
    # principals only when moving INTO conducted -- the direction
    # here is out of conducted, but the IV body is the governed
    # predecessor and must own the step-down writes regardless.
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
            IF OLD.window_start IS DISTINCT FROM NEW.window_start THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.window_end IS DISTINCT FROM NEW.window_end THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_immutable'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.publish_attempts < OLD.publish_attempts THEN
                RAISE EXCEPTION 'b26_p2_dispatch_attempts_regression'
                    USING ERRCODE = '42501';
            END IF;
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
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V gate clause.
    )
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
        """  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V gate clause.
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_directory_coherence ON public.b26_p2_task_authority_directory"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V directory coherence.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_directory_coherence()"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V directory coherence.
    )
    # Restore the IV two-leg coherence FKs before dropping the tuple
    # law (downgraded universe must validate under IV physics).
    # RLS note: FK validation at ADD CONSTRAINT time runs under the
    # migrating principal's RLS visibility (proven live: validation
    # with enforcement on and no tenant GUC fails closed on every
    # child row, even coherent ones). The re-add therefore runs with
    # enforcement transiently disabled and restores the exact pre-V
    # state byte-identically afterwards (the directory stays
    # RLS-disabled, its pre-IV state).
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DISABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DISABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DISABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DISABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_execution_tuple"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V tuple law.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_task_authority_directory DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_execution_tuple"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V tuple law.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts DROP CONSTRAINT IF EXISTS fk_b26_p2_receipt_execution_tuple"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V tuple law.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS uq_b23_dispatch_execution_tuple"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V tuple key.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches DROP CONSTRAINT IF EXISTS ck_b23_dispatch_window_present"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V window presence.
    )
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
        """  # CI:DESTRUCTIVE_OK - reversible rollback restoring Corrective IV coherence legs.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_outbox ENABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_outbox FORCE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.b23_match_task_dispatches ENABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE ONLY public.b23_match_task_dispatches FORCE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities ENABLE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    op.execute(
        "ALTER TABLE ONLY public.webhook_ingress_identities FORCE ROW LEVEL SECURITY"  # CI:DESTRUCTIVE_OK - reversible rollback RLS window for Corrective V tuple-law removal.
    )
    # The admission directory stays RLS-disabled (pre-IV state preserved).
    # Quarantined evidence lives in the quarantine table, which the
    # downgrade below drops as live schema (reversibility lane only;
    # production upgrades never downgrade). Receipts likewise drop
    # with the gate.
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b26_p2_conduction_receipts ON public.b26_p2_conduction_receipts"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V receipts.
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_conduction_receipts"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V receipts.
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b26_p2_execution_quarantine ON public.b26_p2_execution_quarantine"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V quarantine.
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_execution_quarantine"  # CI:DESTRUCTIVE_OK - reversible rollback for Corrective V quarantine.
    )
