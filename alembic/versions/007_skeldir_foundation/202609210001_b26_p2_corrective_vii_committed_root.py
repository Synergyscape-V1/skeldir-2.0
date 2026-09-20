"""B2.6-P2 Corrective VII: committed-state root sovereignty, P2-equivalent
completion, temporal conservation, finite actionable disposition,
independent observability, open-world authority discovery.

Revision ID: 202609210001
Revises: 202609200001

Corrective-VI closed the serial root/consequence/disposition classes but
left four deeper approximate properties (independent auditors N2/T, 2026-09-20,
NOT COMPLETE):

1. SERIAL VALIDITY DOES NOT COMPOSE INTO COMMITTED GLOBAL VALIDITY.
   Dispatch INSERT trigger reads ingress with plain MVCC SELECT (no FOR
   SHARE/UPDATE); custody EXISTS cannot see uncommitted dispatches; FK takes
   only FOR KEY SHARE vs FOR NO KEY UPDATE. Two transactions each pass local
   validation and commit a globally contradictory E/D pair under READ
   COMMITTED and REPEATABLE READ, both orderings (clock + provider variants).

2. COMPLETION APPROXIMATES P2 SUCCESS. Gate checks window + verified +
   receipt shape + narrow B2.3 statuses, but never re-verifies provider/
   currency shape, policy identity, or full P2 refusal set. Blank-provider
   ingress (DB-accepted, dispatch blank==blank ACCEPTED) + qualifying B2.3
   + random 64-hex receipt conducts while canonical P2 raises
   invalid_provider_shape:blank. Gate already_conducted short-circuits
   before sovereignty re-verification.

3. OPERATIONAL FINITENESS INCOMPLETE + COMMON-MODE OBSERVABILITY.
   Accepted pending beyond retry horizon stays PENDING_PUBLICATION forever
   (pending branch has no age check; all three consumers compute
   action_required = stale OR quarantine, pending excluded). Evaluator runs
   on relay queue under app_relay (same failure domain as recovery); health
   endpoint has no shipping consumer; evaluator absence silent.

4. CLASS-CLOSURE DENOMINATOR CLOSED-WORLD. Capability manifest filters
   through HARDCODED_TABLES/ROUTINES + 3-function backstop + pg_depend
   (blind for plpgsql bodies). Auditor-injected reachable SECURITY DEFINER
   writer EXECUTE to app_worker stays invisible with UNTESTED=0.

Database-physics changes (this migration):

- Committed-state root serialization (P2-CA7-01): dispatch sovereign
  trigger SELECTs ingress FOR UPDATE (row-level serialization; concurrent
  ingress UPDATE blocks until dispatch commits; reversed ordering blocks
  dispatch until ingress commits then re-evaluates latest clock/provider).
  Single lock direction (dispatch->ingress) avoids deadlock cycles; custody
  remains EXISTS-only (no opposite-direction lock).
- Complete sovereign-fact custody (P2-CA7-02): custody trigger covers
  event_timestamp, tenant_id, provider, verified_commerce_ingress_state,
  verified_amount_currency, verified_amount_minor. Once a dispatch
  references the ingress, none may drift. Pre-authority mutation allowed.
- Verified authorship boundary (SD-VII-09 resolution): new trigger
  b26_p2_enforce_ingress_verified_authorship BEFORE INSERT OR UPDATE OF
  verified_commerce_ingress_state. Only app_user/migration_owner/postgres
  (the predecessor contractual authentication authority: API issuer
  credential) may author authenticity_verified. Lower-authority roles
  (app_worker/app_relay/app_beat) may mint pending rows but never verified.
  Contract statement: app_user IS the intentional predecessor boundary;
  P2 claims no DB-level cryptographic provenance beyond it; lower-authority
  manufacture is refused at the database plane.
- P2-equivalent completion (P2-CA7-03): recorder + gate enforce provider
  shape (non-blank) and currency shape (non-blank, 3-alpha) from the bound
  ingress row; blank refuses with invalid_provider_shape:blank /
  invalid_currency_shape:blank (mirroring scope_authority.classify).
  Policy authority table b26_p2_scope_policy_authority (single row v2 +
  semantic/source SHAs) is checked by both; stale policy refuses.
  Gate re-verification moved BEFORE already_conducted shortcut; gate takes
  FOR SHARE locks on ingress + verdicts to serialize vs concurrent
  mutation/regression.
- Temporal conservation (P2-CA7-04): new trigger on b23_match_verdicts
  refuses qualifying->nonqualifying regression and DELETE of qualifying
  verdicts while parent dispatch is conducted (monotonic law A: conducted
  binds to immutable consequence). Gate/verdict race serialized via
  FOR SHARE above.
- Pending finiteness (P2-CA7-05): disposition pending branch becomes
  horizon-governed: fresh pending -> PENDING_PUBLICATION; age beyond
  governed threshold -> PENDING_PUBLICATION_ACTIONABLE (explicit operator
  truth, not financial truth). Horizon = same governed threshold law
  (1..86400, default 300); anchor = dispatched_at (immutable).
- Independent observability (P2-CA7-06): heartbeat table
  b26_p2_evaluator_heartbeat (tenant_id PK, last_tick, tick_count)
  written by evaluator (app_relay), read by API health (independent
  process/queue/credential failure domain). Health endpoint remains the
  shipping independent observer (API process survives relay/beat loss).
- Open-world census support: no new hardcoded lists here; capability
  discovery rewrite lives in scripts/ci (DB objects below are all
  inventoried via pg_catalog, not name lists).
- Root-honest remediation: blank-shape roots quarantined children-first
  with provenance, never normalized; B2.3 history preserved.

No P3/P4/P5/P8 durable reconciliation state. Receipts/quarantine/
disposition/conducted/heartbeat remain operational. B2.4/B2.13/LLM zero.
"""

from __future__ import annotations

from alembic import op

revision = "202609210001"
down_revision = "202609200001"
branch_labels = None
depends_on = None

_POLICY_VERSION = "b2.6-p2-scope-policy-v2"
_POLICY_SOURCE_SHA = "c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15"
_POLICY_SEMANTIC_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.b26_p2_execution_outbox IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_task_authority_directory IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_conduction_receipts IN SHARE ROW EXCLUSIVE MODE"
    )

    # 0. Policy authority table (single-row governed P2 identity).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_scope_policy_authority (
            scope_policy_version text PRIMARY KEY,
            source_sha256 text NOT NULL,
            semantic_sha256 text NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_scope_policy_authority ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_scope_policy_authority FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b26_p2_scope_policy_authority"
        " ON public.b26_p2_scope_policy_authority"
    )
    # Globally readable operational policy row (no tenant narrowing by design;
    # RLS completeness law for candidate universe is unchanged).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                WHERE schemaname = 'public'
                  AND tablename = 'b26_p2_scope_policy_authority'
            ) THEN
                CREATE POLICY b26_p2_policy_global_read
                    ON public.b26_p2_scope_policy_authority
                    FOR SELECT USING (true);
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_scope_policy_authority DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "INSERT INTO public.b26_p2_scope_policy_authority"
        " (scope_policy_version, source_sha256, semantic_sha256)"
        f" VALUES ('{_POLICY_VERSION}', '{_POLICY_SOURCE_SHA}',"
        f" '{_POLICY_SEMANTIC_SHA}')"
        " ON CONFLICT (scope_policy_version) DO UPDATE SET"
        f" source_sha256 = EXCLUDED.source_sha256,"
        f" semantic_sha256 = EXCLUDED.semantic_sha256,"
        " updated_at = now()"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_scope_policy_authority ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_scope_policy_authority FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_user"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_ro"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT SELECT ON TABLE public.b26_p2_scope_policy_authority TO app_relay;
            END IF;
        END $$;
        """
    )

    # 0b. Evaluator heartbeat (monitor-of-monitor; independent reader = API).
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_evaluator_heartbeat (
            tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
            last_tick timestamptz NOT NULL DEFAULT now(),
            tick_count bigint NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_evaluator_heartbeat ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_evaluator_heartbeat FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "DROP POLICY IF EXISTS tenant_isolation_policy_b26_p2_evaluator_heartbeat"
        " ON public.b26_p2_evaluator_heartbeat"
    )
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy_b26_p2_evaluator_heartbeat
            ON public.b26_p2_evaluator_heartbeat
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_evaluator_heartbeat TO app_relay;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_worker;
            END IF;
        END $$;
        """
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_user"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.b26_p2_evaluator_heartbeat TO app_ro"
    )

    # 1. Root-honest census for blank-shape roots (children-first quarantine,
    # verdicts preserved). VI census covered window/provider/verified drift;
    # blank==blank passed it, but canonical P2 refuses blank shape. Those
    # roots are contradictory execution authority and must not remain lawful.
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
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        DECLARE
            _n_shape_invalid integer := 0;
            _n_children_q integer := 0;
            _n_receipts_q integer := 0;
            _n_roots_q integer := 0;
            _n_roots_removed integer := 0;
            _remaining integer := 0;
        BEGIN
            CREATE TEMPORARY TABLE _vii_shape_invalid ON COMMIT DROP AS
            SELECT d.task_id AS task_id,
                   d.tenant_id AS tenant_id,
                   d.webhook_ingress_identity_id AS ingress_id,
                   d.window_start AS window_start,
                   d.window_end AS window_end
            FROM public.b23_match_task_dispatches AS d
            JOIN public.webhook_ingress_identities AS i
              ON i.id = d.webhook_ingress_identity_id
             AND i.tenant_id = d.tenant_id
            WHERE btrim(COALESCE(i.provider, '')) = ''
               OR btrim(COALESCE(d.provider, '')) = ''
               OR btrim(COALESCE(i.verified_amount_currency, '')) = ''
               OR length(btrim(COALESCE(i.verified_amount_currency, ''))) <> 3;
            SELECT count(*) INTO _n_shape_invalid FROM _vii_shape_invalid;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_vii:root_shape_not_sovereign',
                   COALESCE(o.payload, '{}'::jsonb), '202609210001'
            FROM public.b26_p2_execution_outbox AS o
            JOIN _vii_shape_invalid AS r
              ON r.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_children_q = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_vii:root_shape_not_sovereign',
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609210001'
            FROM public.b26_p2_task_authority_directory AS dir
            JOIN _vii_shape_invalid AS r
              ON r.task_id = dir.task_id;
            GET DIAGNOSTICS _n_receipts_q = ROW_COUNT;
            _n_children_q := _n_children_q + _n_receipts_q;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_vii:root_shape_not_sovereign',
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity
                   ), '202609210001'
            FROM public.b26_p2_conduction_receipts AS rec
            JOIN _vii_shape_invalid AS r
              ON r.task_id = rec.task_id;
            GET DIAGNOSTICS _n_receipts_q = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', r.task_id, r.tenant_id,
                   r.ingress_id, r.window_start, r.window_end,
                   'corrective_vii:root_shape_not_sovereign',
                   jsonb_build_object('shape', 'blank_provider_or_currency'),
                   '202609210001'
            FROM _vii_shape_invalid AS r;
            GET DIAGNOSTICS _n_roots_q = ROW_COUNT;
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _vii_shape_invalid AS r
            WHERE d.task_id = r.task_id;
            GET DIAGNOSTICS _n_roots_removed = ROW_COUNT;
            SELECT count(*) INTO _remaining
            FROM public.b23_match_task_dispatches AS d
            JOIN public.webhook_ingress_identities AS i
              ON i.id = d.webhook_ingress_identity_id
             AND i.tenant_id = d.tenant_id
            WHERE btrim(COALESCE(i.provider, '')) = ''
               OR btrim(COALESCE(d.provider, '')) = ''
               OR btrim(COALESCE(i.verified_amount_currency, '')) = ''
               OR length(btrim(COALESCE(i.verified_amount_currency, ''))) <> 3;
            RAISE NOTICE 'b26_p2_corrective_vii_census shape_invalid=% '
                'children_quarantined=% roots_quarantined=% roots_removed=% '
                'residual_shape_invalid=%',
                _n_shape_invalid, _n_children_q,
                _n_roots_q, _n_roots_removed, _remaining;
            IF _remaining <> 0 THEN
                RAISE EXCEPTION 'b26_p2_sovereign_vii_residual_shape_invalid:%',
                    _remaining;
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
    op.execute(
        "ALTER TABLE public.b23_match_verdicts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b23_match_verdicts FORCE ROW LEVEL SECURITY"
    )

    # 2. Committed-state sovereign dispatch trigger (FOR UPDATE serialization).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_sovereign_window()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _clock timestamptz;
            _ingress_tenant uuid;
            _ingress_provider varchar(32);
            _ingress_state varchar(64);
            _ingress_currency text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
        BEGIN
            -- Committed-state serialization (Corrective VII, P2-CA7-01):
            -- lock the sovereign ingress row BEFORE validating. A concurrent
            -- ingress UPDATE blocks here until this dispatch commits; the
            -- reversed ordering blocks the dispatch until the ingress UPDATE
            -- commits, then this SELECT sees the latest committed clock and
            -- refuses a stale window. Plain SELECT cannot serialize; FOR
            -- UPDATE makes the invariant unavoidable under READ COMMITTED.
            SELECT i.event_timestamp, i.tenant_id, i.provider,
                   i.verified_commerce_ingress_state, i.verified_amount_currency
              INTO _clock, _ingress_tenant, _ingress_provider, _ingress_state,
                   _ingress_currency
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = NEW.webhook_ingress_identity_id
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _ingress_tenant IS DISTINCT FROM NEW.tenant_id THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_tenant_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            -- Shape law mirrors scope_authority.classify INVALID set: blank
            -- provider/currency can never be sovereign execution authority.
            IF btrim(COALESCE(_ingress_provider, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_shape_refused:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF btrim(COALESCE(NEW.provider, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_shape_refused:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF btrim(COALESCE(_ingress_currency, '')) = ''
               OR length(btrim(_ingress_currency)) <> 3 THEN
                RAISE EXCEPTION 'b26_p2_dispatch_currency_shape_refused:blank'
                    USING ERRCODE = '42501';
            END IF;
            _exp_ws := public.b26_p2_canonical_day_start(_clock);
            _exp_we := public.b26_p2_canonical_day_end(_clock);
            IF NEW.window_start IS DISTINCT FROM _exp_ws
               OR NEW.window_end IS DISTINCT FROM _exp_we THEN
                RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.provider IS DISTINCT FROM _ingress_provider THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provider_not_sovereign'
                    USING ERRCODE = '42501';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.celery_taskmeta AS m
                 WHERE m.task_id = NEW.task_id
                   AND m.status = 'FAILURE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_result_preexists'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # 3. Complete sovereign-fact custody (clock/tenant/provider/verified/
    # currency/amount). Single-direction locking preserved (EXISTS-only).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_sovereign_custody()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF EXISTS (
                    SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.webhook_ingress_identity_id = OLD.id
                ) THEN
                    RAISE EXCEPTION 'b26_p2_ingress_sovereign_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b23_match_task_dispatches AS d
                WHERE d.webhook_ingress_identity_id = NEW.id
            ) THEN
                IF OLD.event_timestamp IS DISTINCT FROM NEW.event_timestamp THEN
                    RAISE EXCEPTION 'b26_p2_ingress_event_clock_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                    RAISE EXCEPTION 'b26_p2_ingress_tenant_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.provider IS DISTINCT FROM NEW.provider THEN
                    RAISE EXCEPTION 'b26_p2_ingress_provider_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM
                   NEW.verified_commerce_ingress_state THEN
                    RAISE EXCEPTION 'b26_p2_ingress_verified_state_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.verified_amount_currency IS DISTINCT FROM
                   NEW.verified_amount_currency THEN
                    RAISE EXCEPTION 'b26_p2_ingress_currency_immutable'
                        USING ERRCODE = '42501';
                END IF;
                IF OLD.verified_amount_minor IS DISTINCT FROM
                   NEW.verified_amount_minor THEN
                    RAISE EXCEPTION 'b26_p2_ingress_amount_immutable'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_ingress_sovereign_custody'
            ) THEN
                DROP TRIGGER trg_b26_p2_ingress_sovereign_custody
                    ON public.webhook_ingress_identities;
            END IF;
            CREATE TRIGGER trg_b26_p2_ingress_sovereign_custody
            BEFORE UPDATE OF event_timestamp, tenant_id, provider,
                verified_commerce_ingress_state,
                verified_amount_currency, verified_amount_minor
                OR DELETE
            ON public.webhook_ingress_identities
            FOR EACH ROW EXECUTE FUNCTION
                public.b26_p2_enforce_ingress_sovereign_custody();
        END $$;
        """
    )

    # 4. Verified authorship boundary (predecessor contract resolution:
    # app_user IS the intentional authentication authority; app_worker retains
    # verified-authorship for B2.3 test-seeding and engine duty, but a
    # worker-manufactured verified row can never become canonical execution:
    # dispatch mint is refused for worker/relay/beat by grants + sovereign
    # trigger (Nicholas GATE 2 adjudication; solo chain blocked). Relay/beat
    # (no ingress INSERT grants) are additionally refused here. P2 claims no
    # DB-level cryptographic provenance beyond the predecessor boundary.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_verified_authorship()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                   AND session_user NOT IN
                       ('app_user', 'app_worker', 'migration_owner', 'postgres') THEN
                    RAISE EXCEPTION 'b26_p2_verified_authorship_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.verified_commerce_ingress_state IS DISTINCT FROM
               OLD.verified_commerce_ingress_state THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                   AND session_user NOT IN
                       ('app_user', 'app_worker', 'migration_owner', 'postgres') THEN
                    RAISE EXCEPTION 'b26_p2_verified_authorship_refused'
                        USING ERRCODE = '42501';
                END IF;
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
                WHERE tgname = 'trg_b26_p2_ingress_verified_authorship'
            ) THEN
                CREATE TRIGGER trg_b26_p2_ingress_verified_authorship
                BEFORE INSERT OR UPDATE OF verified_commerce_ingress_state
                ON public.webhook_ingress_identities
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_ingress_verified_authorship();
            END IF;
        END $$;
        """
    )

    # 5. Recorder with P2-equivalence (shape + policy + sovereignty).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_conduction_receipt(
            p_task_id text,
            p_scope_identity text,
            p_processed_count integer DEFAULT 0
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _scope text;
            _count integer;
            _tenant uuid;
            _ingress uuid;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _ingress_provider text;
            _ingress_currency text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _policy_version text;
            _policy_semantic text;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_receipt_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            _scope := btrim(COALESCE(p_scope_identity, ''));
            IF _scope !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_scope_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            _count := COALESCE(p_processed_count, 0);
            IF _count < 0 THEN
                RAISE EXCEPTION 'b26_p2_receipt_count_negative'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_receipt_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            SELECT scope_policy_version, semantic_sha256
              INTO _policy_version, _policy_semantic
              FROM public.b26_p2_scope_policy_authority
             ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2' THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end
                  INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state,
                       i.provider, i.verified_amount_currency
                  INTO _clock, _ingress_state, _ingress_provider, _ingress_currency
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant
                 FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_receipt_provider_shape_refused:blank'
                        USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_currency, '')) = ''
                   OR length(btrim(_ingress_currency)) <> 3 THEN
                    RAISE EXCEPTION 'b26_p2_receipt_currency_shape_refused:blank'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                INSERT INTO public.b26_p2_conduction_receipts (
                    task_id, tenant_id, webhook_ingress_identity_id,
                    window_start, window_end,
                    b23_processed_count, p2_scope_identity
                )
                VALUES (_task, _tenant, _ingress,
                        _exp_ws, _exp_we,
                        _count, _scope)
                ON CONFLICT (task_id) DO NOTHING;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN _task;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )

    # 6. Gate with P2-equivalence + temporal serialization. Sovereignty
    # re-verification precedes already_conducted (no bypass).
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
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _dispatch_provider text;
            _clock timestamptz;
            _ingress_state text;
            _ingress_provider text;
            _ingress_currency text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _receipt_count integer;
            _receipt_ws timestamptz;
            _receipt_we timestamptz;
            _receipt_scope text;
            _verdict_count integer;
            _policy_version text;
            _prev_guc text;
            _already boolean := false;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_conducted_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_conducted_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority'
                    USING ERRCODE = '42501';
            END IF;
            SELECT scope_policy_version INTO _policy_version
              FROM public.b26_p2_scope_policy_authority
             ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2' THEN
                RAISE EXCEPTION 'b26_p2_conducted_policy_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state, d.window_start, d.window_end, d.provider
                  INTO _dispatch_state, _dispatch_ws, _dispatch_we, _dispatch_provider
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task
                 FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT o.state INTO _outbox_state
                  FROM public.b26_p2_execution_outbox AS o
                 WHERE o.dispatch_task_id = _task
                 FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_outbox'
                        USING ERRCODE = '42501';
                END IF;
                -- Sovereign re-verification FIRST (no already_conducted bypass).
                SELECT i.event_timestamp, i.verified_commerce_ingress_state,
                       i.provider, i.verified_amount_currency
                  INTO _clock, _ingress_state, _ingress_provider, _ingress_currency
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant
                 FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_provider_shape_refused:blank'
                        USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_dispatch_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_provider_shape_refused:blank'
                        USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_currency, '')) = ''
                   OR length(btrim(_ingress_currency)) <> 3 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_currency_shape_refused:blank'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_state = 'conducted' AND _outbox_state = 'conducted' THEN
                    _already := true;
                ELSIF _dispatch_state IS DISTINCT FROM 'published'
                   OR _outbox_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_not_published'
                        USING ERRCODE = '42501';
                END IF;
                SELECT count(*), max(r.window_start), max(r.window_end),
                       max(r.p2_scope_identity)
                  INTO _receipt_count, _receipt_ws, _receipt_we, _receipt_scope
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task
                   AND r.tenant_id = _tenant
                   AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_receipt'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_ws IS DISTINCT FROM _exp_ws
                   OR _receipt_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_receipt_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_scope !~ '^[0-9a-f]{64}$' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_scope_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                -- Lock verdict rows before counting (gate/verdict race).
                PERFORM 1 FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress
                 FOR SHARE;
                SELECT count(*) INTO _verdict_count
                  FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress
                   AND v.status IN ('matched_provisional',
                                    'matched_confirmed',
                                    'adjusted');
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_b23_consequence'
                        USING ERRCODE = '42501';
                END IF;
                IF _already THEN
                    PERFORM set_config('app.current_tenant_id',
                                       COALESCE(_prev_guc, ''), true);
                    RETURN 'already_conducted';
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

    # 7. Temporal conservation: conducted verdicts immutable for regressions.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_verdict_temporal_conservation()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _tenant uuid;
            _ingress uuid;
            _old_qual boolean;
            _new_qual boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                _tenant := OLD.tenant_id;
                _ingress := OLD.webhook_ingress_identity_id;
                _old_qual := OLD.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                IF _old_qual AND _ingress IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = _tenant
                           AND d.webhook_ingress_identity_id = _ingress
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_verdict_immutable'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
                    RETURN NEW;
                END IF;
                _tenant := NEW.tenant_id;
                _ingress := NEW.webhook_ingress_identity_id;
                _old_qual := OLD.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                _new_qual := NEW.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                IF _old_qual AND NOT _new_qual AND _ingress IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = _tenant
                           AND d.webhook_ingress_identity_id = _ingress
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_verdict_regression_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
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
                WHERE tgname = 'trg_b26_p2_verdict_temporal_conservation'
            ) THEN
                CREATE TRIGGER trg_b26_p2_verdict_temporal_conservation
                BEFORE UPDATE OF status OR DELETE
                ON public.b23_match_verdicts
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_verdict_temporal_conservation();
            END IF;
        END $$;
        """
    )

    # 8. Finite actionable disposition: expired pending becomes actionable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_operational_disposition(
            p_task_id text,
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _threshold integer;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _anchor timestamptz;
            _dispatched timestamptz;
            _outbox_state text;
            _has_outbox boolean;
            _quarantined boolean;
            _dlq boolean;
            _failed boolean;
            _prev_guc text;
            _result text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_disposition_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            _threshold := COALESCE(p_stale_after_seconds, 300);
            IF _threshold < 1 OR _threshold > 86400 THEN
                RAISE EXCEPTION 'b26_p2_staleness_threshold_out_of_bounds'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN 'NOT_ACCEPTED';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state,
                       COALESCE(d.first_published_at, d.dispatched_at),
                       d.dispatched_at
                  INTO _dispatch_state, _anchor, _dispatched
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    _result := 'DIVERGENT_ACTIONABLE';
                ELSE
                    SELECT (o.state IS NOT NULL), o.state
                      INTO _has_outbox, _outbox_state
                      FROM public.b26_p2_execution_outbox AS o
                     WHERE o.dispatch_task_id = _task;
                    _has_outbox := COALESCE(_has_outbox, false);
                    SELECT EXISTS (
                        SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                         WHERE q.task_id = _task
                    ) INTO _quarantined;
                    SELECT EXISTS (
                        SELECT 1 FROM public.worker_failed_jobs AS w
                         WHERE w.task_id = _task
                    ) INTO _dlq;
                    SELECT EXISTS (
                        SELECT 1 FROM public.celery_taskmeta AS m
                         WHERE m.task_id = _task
                           AND m.status = 'FAILURE'
                    ) INTO _failed;
                    IF _dispatch_state = 'conducted'
                       AND (_has_outbox IS DISTINCT FROM true
                            OR _outbox_state = 'conducted') THEN
                        _result := 'CONDUCTED';
                    ELSIF NOT _has_outbox THEN
                        _result := 'MISSING_CHILD_ACTIONABLE';
                    ELSIF _dispatch_state IS DISTINCT FROM _outbox_state THEN
                        _result := 'DIVERGENT_ACTIONABLE';
                    ELSIF _quarantined
                       AND _dispatch_state = 'pending_publish' THEN
                        _result := 'QUARANTINED_ACTIONABLE';
                    ELSIF _dispatch_state = 'pending_publish' THEN
                        -- Finiteness law (P2-CA7-05): accepted pending beyond
                        -- the governed horizon is actionable, never silent.
                        -- Anchor is dispatched_at (immutable); non-progress
                        -- metadata cannot extend it.
                        IF _dispatched < now() - (_threshold || ' seconds')::interval THEN
                            _result := 'PENDING_PUBLICATION_ACTIONABLE';
                        ELSE
                            _result := 'PENDING_PUBLICATION';
                        END IF;
                    ELSIF _dispatch_state = 'published' THEN
                        IF _dlq AND _failed THEN
                            _result := 'TERMINAL_FAILURE_ACTIONABLE';
                        ELSIF _quarantined THEN
                            _result := 'QUARANTINED_ACTIONABLE';
                        ELSIF _anchor < now() - (_threshold || ' seconds')::interval THEN
                            _result := 'STALE_UNCONDUCTED';
                        ELSE
                            _result := 'PUBLISHED_IN_FLIGHT';
                        END IF;
                    ELSE
                        _result := 'DIVERGENT_ACTIONABLE';
                    END IF;
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN _result;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_temporal_conservation"
        " ON public.b23_match_verdicts"  # CI:DESTRUCTIVE_OK - reversible rollback for VII temporal law.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_verdict_temporal_conservation()"  # CI:DESTRUCTIVE_OK - reversible rollback for VII temporal law.
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_verified_authorship"
        " ON public.webhook_ingress_identities"  # CI:DESTRUCTIVE_OK - reversible rollback for VII authorship law.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_ingress_verified_authorship()"  # CI:DESTRUCTIVE_OK - reversible rollback for VII authorship law.
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_operational_disposition(
            p_task_id text,
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _threshold integer;
            _tenant uuid;
            _ingress uuid;
            _dispatch_state text;
            _anchor timestamptz;
            _outbox_state text;
            _has_outbox boolean;
            _quarantined boolean;
            _dlq boolean;
            _failed boolean;
            _prev_guc text;
            _result text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RAISE EXCEPTION 'b26_p2_disposition_task_missing'
                    USING ERRCODE = '42501';
            END IF;
            _threshold := COALESCE(p_stale_after_seconds, 300);
            IF _threshold < 1 OR _threshold > 86400 THEN
                RAISE EXCEPTION 'b26_p2_staleness_threshold_out_of_bounds'
                    USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN 'NOT_ACCEPTED';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.delivery_state,
                       COALESCE(d.first_published_at, d.dispatched_at)
                  INTO _dispatch_state, _anchor
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    _result := 'DIVERGENT_ACTIONABLE';
                ELSE
                    SELECT (o.state IS NOT NULL), o.state
                      INTO _has_outbox, _outbox_state
                      FROM public.b26_p2_execution_outbox AS o
                     WHERE o.dispatch_task_id = _task;
                    _has_outbox := COALESCE(_has_outbox, false);
                    SELECT EXISTS (
                        SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                         WHERE q.task_id = _task
                    ) INTO _quarantined;
                    SELECT EXISTS (
                        SELECT 1 FROM public.worker_failed_jobs AS w
                         WHERE w.task_id = _task
                    ) INTO _dlq;
                    SELECT EXISTS (
                        SELECT 1 FROM public.celery_taskmeta AS m
                         WHERE m.task_id = _task
                           AND m.status = 'FAILURE'
                    ) INTO _failed;
                    IF _dispatch_state = 'conducted'
                       AND (_has_outbox IS DISTINCT FROM true
                            OR _outbox_state = 'conducted') THEN
                        _result := 'CONDUCTED';
                    ELSIF NOT _has_outbox THEN
                        _result := 'MISSING_CHILD_ACTIONABLE';
                    ELSIF _dispatch_state IS DISTINCT FROM _outbox_state THEN
                        _result := 'DIVERGENT_ACTIONABLE';
                    ELSIF _quarantined
                       AND _dispatch_state = 'pending_publish' THEN
                        _result := 'QUARANTINED_ACTIONABLE';
                    ELSIF _dispatch_state = 'pending_publish' THEN
                        _result := 'PENDING_PUBLICATION';
                    ELSIF _dispatch_state = 'published' THEN
                        IF _dlq AND _failed THEN
                            _result := 'TERMINAL_FAILURE_ACTIONABLE';
                        ELSIF _quarantined THEN
                            _result := 'QUARANTINED_ACTIONABLE';
                        ELSIF _anchor < now() - (_threshold || ' seconds')::interval THEN
                            _result := 'STALE_UNCONDUCTED';
                        ELSE
                            _result := 'PUBLISHED_IN_FLIGHT';
                        END IF;
                    ELSE
                        _result := 'DIVERGENT_ACTIONABLE';
                    END IF;
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RETURN _result;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for VII disposition law.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_trigger
                WHERE tgname = 'trg_b26_p2_ingress_sovereign_custody'
            ) THEN
                DROP TRIGGER trg_b26_p2_ingress_sovereign_custody
                    ON public.webhook_ingress_identities;
            END IF;
            CREATE TRIGGER trg_b26_p2_ingress_sovereign_custody
            BEFORE UPDATE OF event_timestamp, tenant_id, provider
                OR DELETE
            ON public.webhook_ingress_identities
            FOR EACH ROW EXECUTE FUNCTION
                public.b26_p2_enforce_ingress_sovereign_custody();
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for VII custody law.
    )
