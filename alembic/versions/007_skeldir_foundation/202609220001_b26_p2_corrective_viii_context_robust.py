"""B2.6-P2 Corrective VIII: context-robust, hypothesis-anchored remediation.

Revision ID: 202609220001
Revises: 202609210001

Corrective-VII closed the named issuance/consequence/disposition paths but,
per independent greenfield audits 38 (Nicholas) and 39 (Trey), left the
class open in dimensions the remediation author did not pre-enumerate:

1. AUTHENTICATED-ROOT SUBSTITUTION. The verified-authorship trigger
   allowlists ('app_user','app_worker','migration_owner','postgres'), so a
   lower-authority runtime principal (app_worker) can INSERT a fully
   `authenticity_verified` ingress row. A later genuine signed webhook for
   the same (tenant, idempotency) identity is refused on the unique
   constraint while the poisoned sovereign values persist, and the
   duplicate path re-drives publication from the pre-existing row and acks
   provider success. The VII report sentence "worker can never author
   verified" is FALSE for the shipped bytes. B2.3 production code never
   INSERTs ingress rows (only the API ingestion path does), so removing the
   worker from the allowlist closes the mint without inverting any
   production duty. Pending precursors remain mintable by the worker; their
   adoption is governed below.

2. DUPLICATE ADOPTION WITHOUT SOVEREIGN COMPARISON. No database law
   compares the sovereign commerce values of a colliding ingress row. This
   migration adds BEFORE-INSERT duplicate-adoption law: verified-vs-verified
   mismatch fails closed (`b26_p2_ingress_authenticated_conflict`);
   pending-precursor-vs-verified-arrival raises an explicit promote signal
   (`b26_p2_ingress_precursor_present_promote_required`) so the API either
   promotes the precursor to the authenticated values under app_user
   authority or dispositions the conflict explicitly. Lower-authority
   values can never silently become canonical through duplicate adoption.

3. POLICY LABEL WITHOUT POLICY MEANING. Recorder and gate bind
   `scope_policy_version` only; the stored semantic/source SHAs are never
   compared. A semantic change under the same version conducts stale.
   This migration: (a) freezes same-version meaning mutation by trigger;
   (b) requires every conduction receipt to carry the caller-observed
   policy semantic SHA, compared against the live row AND against
   hardcoded expected constants; (c) requires the gate to re-verify the
   receipt's bound SHA against the live row on every conduction (including
   the already_conducted path).

4. TEMPORAL CONSEQUENCE WITHOUT IDENTITY. The verdict conservation
   trigger fires only on UPDATE OF status, so moving the sole qualifying
   verdict to another ingress (status untouched) orphans `conducted` from
   its consequence, and qualifying INSERTs (phantoms) grow the set
   silently. Derived P2-relevant B2.3 footprint for one execution:
   (tenant_id, webhook_ingress_identity_id, qualifying status membership).
   Verdict amount/currency/reference/match_quality columns are NOT in the
   footprint: canonical P2 reads ingress money only and the scope identity
   binds provider/rail/currency/disposition/reason/amount from the ingress
   row, so B2.3-internal corrections there neither stale the terminal nor
   justify freezing (freezing them would invert B2.3 sovereignty). This
   migration extends the trigger to identity/tenant moves and to
   qualifying INSERT phantoms while leaving non-footprint columns free.

5. CASE-LIST HISTORY. The VII migration quarantines only blank-shape
   roots. This migration runs a generic invariant census over every
   dispatch (window mismatch, shape, unverified root, tenant/provider
   mismatch, false conducted without qualifying consequence, receipt
   without policy binding, orphan children) and quarantines children-first
   with `corrective_viii:<kind>` provenance (B2.3 verdict history always
   preserved, never rewritten), failing closed on any residual.

6. SELF-AUTHENTICATING OBSERVABILITY. The evaluator heartbeat is a bare
   timestamp writable by the monitored relay credential. This migration
   revokes direct heartbeat writes from app_relay and exposes one
   SECURITY DEFINER evaluation function that recomputes the operational
   counts itself: invoking it IS the governed evaluation, so no credential
   can manufacture healthy evidence without observing. The heartbeat row
   additionally carries the evaluated counts as evidence.

No P3/P4/P5/P8 durable reconciliation state. Receipts/quarantine/
disposition/conducted/heartbeat remain operational. B2.4/B2.13/LLM zero.
"""

from __future__ import annotations

from alembic import op

revision = "202609220001"
down_revision = "202609210001"
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
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b23_match_verdicts IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # A1. Verified-authorship closure: the predecessor authentication
    # authority is the API issuer credential (app_user). B2.3 production
    # code never INSERTs ingress rows (only the API ingestion path does),
    # so app_worker authorship is removed from BOTH arms. Pending rows
    # remain mintable by lower-authority roles; their adoption is governed
    # by the duplicate-adoption trigger below.
    # ------------------------------------------------------------------
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
                        ('app_user', 'migration_owner', 'postgres') THEN
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
                        ('app_user', 'migration_owner', 'postgres') THEN
                    RAISE EXCEPTION 'b26_p2_verified_authorship_refused'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # A2. Duplicate-adoption law (BEFORE INSERT, i.e. before the unique
    # constraint fires). Sovereign comparison set: every commerce-meaning
    # column plus tenant/state. Row-identity columns (id, event_id,
    # verified_at) are adoption bindings, not compared: a legitimate
    # arrival adopts the canonical row and binds its own event.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_duplicate_adoption()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _existing public.webhook_ingress_identities%ROWTYPE;
            _mismatch boolean := false;
        BEGIN
            SELECT * INTO _existing
              FROM public.webhook_ingress_identities AS e
             WHERE e.tenant_id = NEW.tenant_id
               AND e.idempotency_key = NEW.idempotency_key
             LIMIT 1;
            IF NOT FOUND THEN
                SELECT * INTO _existing
                  FROM public.webhook_ingress_identities AS e
                 WHERE e.tenant_id = NEW.tenant_id
                   AND e.event_id = NEW.event_id
                 LIMIT 1;
            END IF;
            IF NOT FOUND THEN
                RETURN NEW;
            END IF;
            IF _existing.id = NEW.id THEN
                RETURN NEW;
            END IF;
            _mismatch :=
                   _existing.provider IS DISTINCT FROM NEW.provider
                OR _existing.verified_amount_currency IS DISTINCT FROM NEW.verified_amount_currency
                OR _existing.verified_amount_minor IS DISTINCT FROM NEW.verified_amount_minor
                OR _existing.event_timestamp IS DISTINCT FROM NEW.event_timestamp
                OR _existing.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference
                OR _existing.provider_native_commerce_reference IS DISTINCT FROM NEW.provider_native_commerce_reference
                OR _existing.normalized_commerce_reference_kind IS DISTINCT FROM NEW.normalized_commerce_reference_kind
                OR _existing.normalized_commerce_reference_value IS DISTINCT FROM NEW.normalized_commerce_reference_value
                OR _existing.tenant_id IS DISTINCT FROM NEW.tenant_id;
            IF _existing.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_ingress_precursor_present_promote_required'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF _mismatch
               OR (NEW.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified') THEN
                RAISE EXCEPTION 'b26_p2_ingress_authenticated_conflict'
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
                WHERE tgname = 'trg_b26_p2_ingress_duplicate_adoption'
            ) THEN
                CREATE TRIGGER trg_b26_p2_ingress_duplicate_adoption
                BEFORE INSERT
                ON public.webhook_ingress_identities
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_ingress_duplicate_adoption();
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # B1. Policy meaning immutability: the same semantic version cannot
    # change meaning. New meaning requires a new version row.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_policy_immutability()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF NEW.scope_policy_version IS NOT DISTINCT FROM OLD.scope_policy_version
                   AND (NEW.source_sha256 IS DISTINCT FROM OLD.source_sha256
                        OR NEW.semantic_sha256 IS DISTINCT FROM OLD.semantic_sha256) THEN
                    RAISE EXCEPTION 'b26_p2_policy_semantic_mutation_refused'
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
                WHERE tgname = 'trg_b26_p2_policy_immutability'
            ) THEN
                CREATE TRIGGER trg_b26_p2_policy_immutability
                BEFORE UPDATE
                ON public.b26_p2_scope_policy_authority
                FOR EACH ROW EXECUTE FUNCTION
                    public.b26_p2_enforce_policy_immutability();
            END IF;
        END $$;
        """
    )
    # Least-privilege grants are existence-guarded: lanes that run a
    # subset of the role graph (other phases' jobs) must migrate without
    # undefined-role errors, exactly as the VII migration guards its own
    # conditional grants.
    op.execute(
        """
        DO $$
        DECLARE
            _role text;
        BEGIN
            FOREACH _role IN ARRAY ARRAY[
                'app_user', 'app_worker', 'app_relay',
                'app_beat', 'app_ro', 'app_rw'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _role) THEN
                    EXECUTE format(
                        'REVOKE UPDATE, DELETE ON TABLE'
                        ' public.b26_p2_scope_policy_authority FROM %I',
                        _role
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # B2. Receipts bind the exact policy meaning consumed. Existing VII
    # receipts predate meaning binding; they were all recorded under the
    # same v2 semantics, so backfilling the current semantic SHA is an
    # honest provenance repair (no meaning change has occurred under v2).
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b26_p2_conduction_receipts
        ADD COLUMN IF NOT EXISTS policy_semantic_sha256 text
        """
    )
    # RLS is FORCE on receipts: the backfill must run with RLS disabled
    # (same pattern as the census below), otherwise it silently matches
    # zero rows and the NOT NULL constraint fails the upgrade.
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "UPDATE public.b26_p2_conduction_receipts"
        f" SET policy_semantic_sha256 = '{_POLICY_SEMANTIC_SHA}'"
        " WHERE policy_semantic_sha256 IS NULL"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_conduction_receipts FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts"
        " ALTER COLUMN policy_semantic_sha256 SET NOT NULL"
    )

    # ------------------------------------------------------------------
    # B3. Recorder with policy-meaning binding. The caller must present
    # the semantic SHA it classified under; the function verifies it
    # against the live row AND against the governed constants, so file,
    # row, and caller must agree on every conduction. The VII 3-argument
    # overload is dropped: leaving it would preserve an unbound path
    # (overload blindness) that silently bypasses meaning binding.
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_record_conduction_receipt(text, text, integer)"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_conduction_receipt(
            p_task_id text,
            p_scope_identity text,
            p_processed_count integer DEFAULT 0,
            p_policy_semantic_sha256 text DEFAULT NULL
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
            _caller_sha text;
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
            _policy_source text;
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
            _caller_sha := btrim(COALESCE(p_policy_semantic_sha256, ''));
            IF _caller_sha !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_semantic_binding_required'
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
            SELECT scope_policy_version, source_sha256, semantic_sha256
              INTO _policy_version, _policy_source, _policy_semantic
              FROM public.b26_p2_scope_policy_authority
             ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2'
               OR _policy_source IS DISTINCT FROM 'c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15'
               OR _policy_semantic IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            IF _caller_sha IS DISTINCT FROM _policy_semantic THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_semantic_not_bound'
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
                    b23_processed_count, p2_scope_identity,
                    policy_semantic_sha256
                )
                VALUES (_task, _tenant, _ingress,
                        _exp_ws, _exp_we,
                        _count, _scope,
                        _caller_sha)
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
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_record_conduction_receipt(text, text, integer, text)"
        " FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_record_conduction_receipt(text, text, integer, text)
                    TO app_worker;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # B4/C0. Gate with policy-meaning binding on EVERY conduction,
    # including the already_conducted idempotent path.
    # ------------------------------------------------------------------
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
            _receipt_sha text;
            _verdict_count integer;
            _policy_version text;
            _policy_source text;
            _policy_semantic text;
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
            SELECT scope_policy_version, source_sha256, semantic_sha256
              INTO _policy_version, _policy_source, _policy_semantic
              FROM public.b26_p2_scope_policy_authority
             ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2'
               OR _policy_source IS DISTINCT FROM 'c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15'
               OR _policy_semantic IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
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
                       max(r.p2_scope_identity), max(r.policy_semantic_sha256)
                  INTO _receipt_count, _receipt_ws, _receipt_we, _receipt_scope, _receipt_sha
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
                -- Meaning binding on every conduction, including idempotent
                -- replays: a stale-meaning receipt can never re-conduct.
                IF _receipt_sha IS DISTINCT FROM _policy_semantic THEN
                    RAISE EXCEPTION 'b26_p2_conducted_policy_semantic_not_bound'
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

    # ------------------------------------------------------------------
    # C. Temporal conservation with consequence identity. Guarded P2
    # footprint: (tenant_id, webhook_ingress_identity_id, qualifying
    # status membership). Non-footprint B2.3 corrections (amounts,
    # currency, references, quality, timestamps) remain free, preserving
    # B2.3 correction sovereignty. Qualifying INSERTs against a conducted
    # parent are refused: the set cannot grow silently beneath a terminal.
    # ------------------------------------------------------------------
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
            _link_moved boolean;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                _tenant := NEW.tenant_id;
                _ingress := NEW.webhook_ingress_identity_id;
                _new_qual := NEW.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                IF _new_qual AND _ingress IS NOT NULL THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = _tenant
                           AND d.webhook_ingress_identity_id = _ingress
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_set_insert_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
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
                _link_moved :=
                    (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id)
                    OR (OLD.tenant_id IS DISTINCT FROM NEW.tenant_id);
                _old_qual := OLD.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                _new_qual := NEW.status IN ('matched_provisional',
                                            'matched_confirmed', 'adjusted');
                -- Old-link conducted parent: regression or removal of the
                -- consequence it stands on is refused.
                IF (_old_qual AND NOT _new_qual) OR (_old_qual AND _link_moved) THEN
                    IF OLD.webhook_ingress_identity_id IS NOT NULL THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = OLD.tenant_id
                               AND d.webhook_ingress_identity_id = OLD.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_verdict_regression_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                END IF;
                -- New-link conducted parent: moving a qualifying consequence
                -- under a terminal, or qualifying it there, is refused.
                IF _new_qual AND NEW.webhook_ingress_identity_id IS NOT NULL
                   AND (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                        OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
                        OR (NOT _old_qual)) THEN
                    IF EXISTS (
                        SELECT 1 FROM public.b23_match_task_dispatches AS d
                         WHERE d.tenant_id = NEW.tenant_id
                           AND d.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
                           AND d.delivery_state = 'conducted'
                    ) THEN
                        RAISE EXCEPTION 'b26_p2_conducted_verdict_identity_refused'
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
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_temporal_conservation"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_temporal_conservation
        BEFORE INSERT OR UPDATE OF status, webhook_ingress_identity_id, tenant_id
            OR DELETE
        ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_verdict_temporal_conservation()
        """
    )

    # ------------------------------------------------------------------
    # F. Evaluation-bound heartbeat: direct heartbeat writes are revoked
    # from the monitored relay credential; the single SECURITY DEFINER
    # function recomputes the operational counts itself, so invoking it
    # IS the governed evaluation. A bare timestamp can no longer be
    # manufactured without observing.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b26_p2_evaluator_heartbeat
        ADD COLUMN IF NOT EXISTS pending_actionable_count bigint NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS stale_unconducted_count bigint NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS quarantine_count bigint NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_evaluator_heartbeat(
            p_stale_after_seconds integer DEFAULT 300
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _threshold integer;
            _tenant uuid;
            _pending_actionable bigint;
            _stale bigint;
            _quarantine bigint;
            _prev_guc text;
        BEGIN
            IF session_user NOT IN ('app_relay', 'app_beat', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_heartbeat_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            _threshold := COALESCE(p_stale_after_seconds, 300);
            IF _threshold < 1 OR _threshold > 86400 THEN
                RAISE EXCEPTION 'b26_p2_staleness_threshold_out_of_bounds'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            IF _prev_guc IS NULL OR btrim(COALESCE(_prev_guc, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_heartbeat_tenant_missing'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _tenant := _prev_guc::uuid;
            EXCEPTION WHEN OTHERS THEN
                RAISE EXCEPTION 'b26_p2_heartbeat_tenant_malformed'
                    USING ERRCODE = '42501';
            END;
            -- The counts below are recomputed from the live tables on
            -- every call: the row is evaluation evidence, never a bare
            -- timestamp the caller chose.
            SELECT count(*) INTO _pending_actionable
              FROM public.b23_match_task_dispatches AS d
             WHERE d.tenant_id = _tenant
               AND d.delivery_state = 'pending_publish'
               AND d.dispatched_at < now() - (_threshold || ' seconds')::interval;
            SELECT count(*) INTO _stale
              FROM public.b23_match_task_dispatches AS d
              JOIN public.b26_p2_execution_outbox AS o
                ON o.dispatch_task_id = d.task_id
               AND o.tenant_id = d.tenant_id
               AND o.webhook_ingress_identity_id = d.webhook_ingress_identity_id
             WHERE d.tenant_id = _tenant
               AND d.delivery_state = 'published'
               AND o.state = 'published'
               AND COALESCE(d.first_published_at, d.dispatched_at)
                   < now() - (_threshold || ' seconds')::interval;
            SELECT count(*) INTO _quarantine
              FROM public.b26_p2_execution_quarantine AS q
             WHERE q.tenant_id = _tenant;
            INSERT INTO public.b26_p2_evaluator_heartbeat AS h (
                tenant_id, last_tick, tick_count, updated_at,
                pending_actionable_count, stale_unconducted_count,
                quarantine_count
            )
            VALUES (_tenant, now(), 1, now(),
                    _pending_actionable, _stale, _quarantine)
            ON CONFLICT (tenant_id) DO UPDATE SET
                last_tick = now(),
                tick_count = h.tick_count + 1,
                updated_at = now(),
                pending_actionable_count = EXCLUDED.pending_actionable_count,
                stale_unconducted_count = EXCLUDED.stale_unconducted_count,
                quarantine_count = EXCLUDED.quarantine_count;
            RETURN 'evaluated';
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE INSERT, UPDATE, DELETE
                    ON TABLE public.b26_p2_evaluator_heartbeat
                    FROM app_relay;
            END IF;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_evaluator_heartbeat(integer)"
        " FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT EXECUTE ON FUNCTION
                    public.b26_p2_record_evaluator_heartbeat(integer)
                    TO app_relay;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_evaluator_heartbeat(integer) TO app_beat;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # D. Generic post-upgrade invariant census over EVERY dispatch.
    # Children-first quarantine with corrective_viii:<kind> provenance;
    # B2.3 verdict history is always preserved, never rewritten. Any
    # residual fails the upgrade closed.
    # ------------------------------------------------------------------
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
            _n_viol integer := 0;
            _n_children integer := 0;
            _n_roots integer := 0;
            _n_removed integer := 0;
            _remaining integer := 0;
        BEGIN
            CREATE TEMPORARY TABLE _viii_contradictions ON COMMIT DROP AS
            -- Window mismatch: dispatch not canonical of the live ingress clock.
            SELECT d.task_id AS task_id, 'window_mismatch' AS kind
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.window_start IS DISTINCT FROM public.b26_p2_canonical_day_start(i.event_timestamp)
                OR d.window_end IS DISTINCT FROM public.b26_p2_canonical_day_end(i.event_timestamp)
            UNION
            -- Shape: blank provider/currency (VII class, re-censused).
            SELECT d.task_id, 'root_shape_not_sovereign'
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE btrim(COALESCE(i.provider, '')) = ''
                OR btrim(COALESCE(d.provider, '')) = ''
                OR btrim(COALESCE(i.verified_amount_currency, '')) = ''
                OR length(btrim(COALESCE(i.verified_amount_currency, ''))) <> 3
            UNION
            -- Unverified root carrying execution authority.
            SELECT d.task_id, 'root_unverified'
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE i.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
            UNION
            -- Tenant/provider fork between dispatch and ingress.
            SELECT d.task_id, 'root_authority_fork'
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
             WHERE i.tenant_id IS DISTINCT FROM d.tenant_id
                OR i.provider IS DISTINCT FROM d.provider
            UNION
            -- False conducted: terminal without a qualifying consequence.
            SELECT d.task_id, 'false_conducted_no_consequence'
              FROM public.b23_match_task_dispatches AS d
             WHERE d.delivery_state = 'conducted'
               AND NOT EXISTS (
                   SELECT 1 FROM public.b23_match_verdicts AS v
                    WHERE v.tenant_id = d.tenant_id
                      AND v.webhook_ingress_identity_id = d.webhook_ingress_identity_id
                      AND v.status IN ('matched_provisional', 'matched_confirmed', 'adjusted')
               )
            UNION
            -- Conducted with receipt bound to a stale policy meaning.
            SELECT d.task_id, 'conducted_policy_semantic_stale'
              FROM public.b23_match_task_dispatches AS d
              JOIN public.b26_p2_conduction_receipts AS r
                ON r.task_id = d.task_id
             WHERE d.delivery_state = 'conducted'
               AND r.policy_semantic_sha256 IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99'
            UNION
            -- Conducted without any receipt at all.
            SELECT d.task_id, 'conducted_receipt_missing'
              FROM public.b23_match_task_dispatches AS d
             WHERE d.delivery_state = 'conducted'
               AND NOT EXISTS (
                   SELECT 1 FROM public.b26_p2_conduction_receipts AS r
                    WHERE r.task_id = d.task_id
               );
            SELECT count(*) INTO _n_viol FROM _viii_contradictions;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_viii:' || c.kind,
                   COALESCE(o.payload, '{}'::jsonb), '202609220001'
              FROM public.b26_p2_execution_outbox AS o
              JOIN _viii_contradictions AS c
                ON c.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_children = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_viii:' || c.kind,
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609220001'
              FROM public.b26_p2_task_authority_directory AS dir
              JOIN _viii_contradictions AS c
                ON c.task_id = dir.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_viii:' || c.kind,
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity
                   ), '202609220001'
              FROM public.b26_p2_conduction_receipts AS rec
              JOIN _viii_contradictions AS c
                ON c.task_id = rec.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', d.task_id, d.tenant_id,
                   d.webhook_ingress_identity_id, d.window_start, d.window_end,
                   'corrective_viii:' || c.kind,
                   jsonb_build_object('kind', c.kind), '202609220001'
              FROM public.b23_match_task_dispatches AS d
              JOIN _viii_contradictions AS c
                ON c.task_id = d.task_id;
            GET DIAGNOSTICS _n_roots = ROW_COUNT;
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _viii_contradictions AS c
            WHERE d.task_id = c.task_id;
            GET DIAGNOSTICS _n_removed = ROW_COUNT;
            -- Orphan children without any dispatch root (no silent graveyard).
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_viii:orphan_child_without_dispatch',
                   COALESCE(o.payload, '{}'::jsonb), '202609220001'
              FROM public.b26_p2_execution_outbox AS o
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
                   'corrective_viii:orphan_child_without_dispatch',
                   jsonb_build_object('orphan', true), '202609220001'
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE NOT EXISTS (
                   SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = dir.task_id
               );
            DELETE FROM public.b26_p2_execution_outbox AS o
             WHERE NOT EXISTS (
                   SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = o.dispatch_task_id
               );
            DELETE FROM public.b26_p2_task_authority_directory AS dir
             WHERE NOT EXISTS (
                   SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = dir.task_id
               );
            DELETE FROM public.b26_p2_conduction_receipts AS rec
             WHERE NOT EXISTS (
                   SELECT 1 FROM public.b23_match_task_dispatches AS d
                    WHERE d.task_id = rec.task_id
               );
            SELECT count(*) INTO _remaining
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.window_start IS DISTINCT FROM public.b26_p2_canonical_day_start(i.event_timestamp)
                OR d.window_end IS DISTINCT FROM public.b26_p2_canonical_day_end(i.event_timestamp)
                OR btrim(COALESCE(i.provider, '')) = ''
                OR btrim(COALESCE(d.provider, '')) = ''
                OR btrim(COALESCE(i.verified_amount_currency, '')) = ''
                OR length(btrim(COALESCE(i.verified_amount_currency, ''))) <> 3
                OR i.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                OR i.provider IS DISTINCT FROM d.provider;
            SELECT count(*) INTO _n_viol
              FROM public.b23_match_task_dispatches AS d
             WHERE d.delivery_state = 'conducted'
               AND NOT EXISTS (
                   SELECT 1 FROM public.b23_match_verdicts AS v
                    WHERE v.tenant_id = d.tenant_id
                      AND v.webhook_ingress_identity_id = d.webhook_ingress_identity_id
                      AND v.status IN ('matched_provisional', 'matched_confirmed', 'adjusted')
               );
            _remaining := _remaining + _n_viol;
            RAISE NOTICE 'b26_p2_corrective_viii_census violations=% children=% roots=% removed=% residual=%',
                _n_viol, _n_children, _n_roots, _n_removed, _remaining;
            IF _remaining <> 0 THEN
                RAISE EXCEPTION 'b26_p2_sovereign_viii_residual_contradiction:%',
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


def downgrade() -> None:
    # Restore the VII 3-argument recorder (exact VII body): the upgrade
    # drops that overload so no unbound path survives; downgrade must
    # bring it back for VII fidelity (re-upgrade then restores VIII).
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_record_conduction_receipt(text, text, integer, text)"
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

    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_duplicate_adoption"
        " ON public.webhook_ingress_identities"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII adoption law.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_ingress_duplicate_adoption()"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII adoption law.
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_policy_immutability"
        " ON public.b26_p2_scope_policy_authority"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII policy law.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_policy_immutability()"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII policy law.
    )
    # Restore the exact VII gate body (the upgrade replaced it with
    # the meaning-bound form that reads the VIII receipt column).
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

    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_temporal_conservation"
        " ON public.b23_match_verdicts"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII temporal law.
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_temporal_conservation
        BEFORE UPDATE OF status OR DELETE
        ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_verdict_temporal_conservation()
        """  # CI:DESTRUCTIVE_OK - reversible rollback restores VII temporal law.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                REVOKE EXECUTE ON FUNCTION
                    public.b26_p2_record_evaluator_heartbeat(integer)
                    FROM app_relay;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback for VIII heartbeat law.
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT SELECT, INSERT, UPDATE ON TABLE
                    public.b26_p2_evaluator_heartbeat TO app_relay;
            END IF;
        END $$;
        """  # CI:DESTRUCTIVE_OK - reversible rollback restores VII heartbeat writes.
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_evaluator_heartbeat(integer)"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII heartbeat law.
    )
    # Schema additions revert for VII fidelity (re-upgrade re-adds and
    # backfills them); otherwise the restored VII recorder cannot INSERT.
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts"
        " DROP COLUMN IF EXISTS policy_semantic_sha256"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII meaning binding.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_evaluator_heartbeat"
        " DROP COLUMN IF EXISTS pending_actionable_count,"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII heartbeat evidence.
        " DROP COLUMN IF EXISTS stale_unconducted_count,"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII heartbeat evidence.
        " DROP COLUMN IF EXISTS quarantine_count"  # CI:DESTRUCTIVE_OK - reversible rollback for VIII heartbeat evidence.
    )
