"""B2.6-P2 Corrective IX: context-robust, hypothesis-anchored remediation.

Revision ID: 202609230001
Revises: 202609220001

Governing law: NON-SELF-AUTHENTICATING CONSEQUENCE AUTHORITY. No principal
may author a representation R and rely on R itself as proof that consequence
C occurred. VIII closed large surfaces; IX closes the representation-trust
residue proven by independent audits 40/41:

A. Canonical P2 consequence: worker-supplied scope digest (random/foreign/
   stale/bogus-count) conducts without canonical evaluation. IX adds a
   sovereign DB recomputation of the canonical scope identity from live
   ingress+verdict+policy state and requires receipt/gate scope equality.
   Normal worker wiring (derive_governed_scope -> receipt) is preserved;
   the capability relation is closed (forgery refused at the plane).

B. Temporal footprint: P2 reads canonical_commerce_reference presence but
   the trigger guards only (tenant, ingress, status). IX governs reference
   presence flips under conducted parents (value-preserving corrections
   remain free, preserving B2.3 sovereignty).

C. Historical honesty: pre-IX verified ingress lacks authorship provenance.
   IX adds explicit provenance status (unknown_legacy vs authenticated_known)
   and refuses new dispatch on unknown roots until re-established. Receipt
   meaning for pre-IX rows is marked unknown, never backfilled into certainty.

D. Observability honesty: evaluation freshness vs scheduler liveness are
   separated (new scheduler heartbeat writable only by app_beat; manual
   evaluation cannot masquerade as scheduler liveness).

No P3/P4/P5/P8 state. Receipts/quarantine/disposition/conducted/heartbeat
remain operational. B2.4/B2.13/LLM zero.
"""

from __future__ import annotations

from alembic import op

revision = "202609230001"
down_revision = "202609220001"
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
    op.execute(
        "LOCK TABLE public.b23_match_task_dispatches IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # A1. Canonical scope recomputation (sovereign DB mirror of Python
    # derive_governed_scope for policy v2). Single authority consumed by
    # Python (via gate verification) and completion alike. RLS-aware via
    # tenant GUC save/restore; fail-closed on blank shapes and policy drift.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_canonical_scope_identity_for_window(
            p_tenant uuid,
            p_ws timestamptz,
            p_we timestamptz
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _policy_version text;
            _policy_semantic text;
            _ws_iso text;
            _we_iso text;
            _base text;
            _lines text;
            _payload text;
            _prev_guc text;
        BEGIN
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', p_tenant::text, true);
            BEGIN
                SELECT scope_policy_version, semantic_sha256
                  INTO _policy_version, _policy_semantic
                  FROM public.b26_p2_scope_policy_authority
                 ORDER BY scope_policy_version DESC LIMIT 1;
                IF NOT FOUND
                   OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2'
                   OR _policy_semantic IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
                    PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc,''), true);
                    RAISE EXCEPTION 'b26_p2_canonical_scope_policy_not_bound' USING ERRCODE='42501';
                END IF;
                _ws_iso := to_char(p_ws AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"+00:00"');
                _we_iso := to_char(p_we AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS"+00:00"');
                _base := 'b2.6-p2-scope-identity-v3' || '|' || p_tenant::text || '|' || _ws_iso || '|' || _we_iso
                         || '|' || 'b2.6-p2-scope-policy-v2' || '|' || _policy_semantic
                         || '|' || 'source_verified_gross_not_canonical_net'
                         || '|' || 'b2.2_ingress_verified_amount_minor'
                         || '|' || 'b2.3_match_verdicts.canonical_net_verified_amount_minor_only';
                IF EXISTS (
                    SELECT 1 FROM public.webhook_ingress_identities AS i
                     WHERE i.tenant_id = p_tenant
                       AND i.verified_commerce_ingress_state = 'authenticity_verified'
                       AND (btrim(COALESCE(i.provider,'')) = '' OR btrim(COALESCE(i.verified_amount_currency,'')) = '' OR length(btrim(COALESCE(i.verified_amount_currency,''))) <> 3)
                ) THEN
                    PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc,''), true);
                    RAISE EXCEPTION 'b26_p2_canonical_scope_blank_shape' USING ERRCODE='42501';
                END IF;
                SELECT string_agg(line, '|' ORDER BY line) INTO _lines FROM (
                    SELECT
                        i.id::text || ':' || _all._prov || ':' || _all._prov || ':' || _all._cur || ':' || _all._disp || ':' || _all._reason || ':' || i.verified_amount_minor::text AS line
                    FROM public.webhook_ingress_identities AS i,
                    LATERAL (SELECT lower(btrim(i.provider)) AS _prov, upper(btrim(i.verified_amount_currency)) AS _cur) AS _norm,
                    LATERAL (SELECT EXISTS (
                            SELECT 1 FROM public.b23_match_verdicts AS v
                             WHERE v.tenant_id = p_tenant
                               AND v.webhook_ingress_identity_id = i.id
                               AND v.status IN ('matched_provisional','matched_confirmed','adjusted')
                               AND btrim(COALESCE(v.canonical_commerce_reference,'')) <> ''
                        ) AS _has_ref) AS _r,
                    LATERAL (SELECT CASE
                                WHEN _norm._prov NOT IN ('paypal','shopify','stripe','woocommerce') THEN 'EXCLUDED_PROVIDER'
                                WHEN _norm._cur <> 'USD' THEN 'EXCLUDED_CURRENCY'
                                WHEN NOT (i.event_timestamp >= p_ws AND i.event_timestamp < p_we) THEN 'EXCLUDED_WINDOW'
                                WHEN NOT _r._has_ref THEN 'UNRESOLVED'
                                ELSE 'IN_SCOPE' END AS _cls) AS _c,
                    LATERAL (SELECT CASE _c._cls
                                WHEN 'EXCLUDED_PROVIDER' THEN 'EXPLICITLY_EXCLUDED'
                                WHEN 'EXCLUDED_CURRENCY' THEN 'EXPLICITLY_EXCLUDED'
                                WHEN 'EXCLUDED_WINDOW' THEN 'EXPLICITLY_EXCLUDED'
                                WHEN 'UNRESOLVED' THEN 'SUPPORTED_BUT_UNRESOLVED'
                                ELSE 'SUPPORTED_AND_IN_SCOPE' END AS _disp,
                               CASE _c._cls
                                WHEN 'EXCLUDED_PROVIDER' THEN 'unsupported_provider_excluded'
                                WHEN 'EXCLUDED_CURRENCY' THEN 'unsupported_currency_excluded'
                                WHEN 'EXCLUDED_WINDOW' THEN 'outside_governed_window_excluded'
                                WHEN 'UNRESOLVED' THEN 'source_identity_unresolved'
                                ELSE 'supported_in_scope' END AS _reason) AS _fr,
                    LATERAL (SELECT _fr._disp AS _disp, _fr._reason AS _reason) AS _final,
                    LATERAL (SELECT _norm._prov AS _prov, _norm._cur AS _cur, _final._disp AS _disp, _final._reason AS _reason) AS _all
                    WHERE i.tenant_id = p_tenant
                      AND i.verified_commerce_ingress_state = 'authenticity_verified'
                ) AS sub;
                IF _lines IS NULL THEN
                    _payload := _base;
                ELSE
                    _payload := _base || '|' || _lines;
                END IF;
                _payload := encode(digest(_payload, 'sha256'), 'hex');
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc,''), true);
                RETURN _payload;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc,''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz) TO app_user;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # E1. Historical provenance honesty: explicit unknown vs authenticated.
    # No backfill of certainty: existing rows become unknown_legacy; only
    # app_user/migration_owner/postgres verified inserts become known.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.webhook_ingress_identities
        ADD COLUMN IF NOT EXISTS b26_p2_provenance_status text NOT NULL DEFAULT 'unknown_legacy'
        """
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_conduction_receipts
        ADD COLUMN IF NOT EXISTS ix_meaning_status text NOT NULL DEFAULT 'unknown_legacy_backfill'
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_provenance()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    NEW.b26_p2_provenance_status := 'pending_not_applicable';
                    RETURN NEW;
                END IF;
                IF session_user IN ('app_user', 'migration_owner', 'postgres') THEN
                    NEW.b26_p2_provenance_status := 'authenticated_known';
                ELSE
                    NEW.b26_p2_provenance_status := 'unknown_legacy';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                   AND NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    IF session_user IN ('app_user', 'migration_owner', 'postgres') THEN
                        NEW.b26_p2_provenance_status := 'authenticated_known';
                    ELSE
                        NEW.b26_p2_provenance_status := 'unknown_legacy';
                    END IF;
                END IF;
                -- Provenance may only move unknown->known under app_user authority
                -- (explicit re-verification); known->unknown is forbidden.
                IF OLD.b26_p2_provenance_status IS DISTINCT FROM NEW.b26_p2_provenance_status THEN
                    IF OLD.b26_p2_provenance_status = 'authenticated_known'
                       AND NEW.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known' THEN
                        RAISE EXCEPTION 'b26_p2_provenance_downgrade_refused' USING ERRCODE = '42501';
                    END IF;
                    IF OLD.b26_p2_provenance_status = 'unknown_legacy'
                       AND NEW.b26_p2_provenance_status = 'authenticated_known'
                       AND session_user NOT IN ('app_user', 'migration_owner', 'postgres') THEN
                        RAISE EXCEPTION 'b26_p2_provenance_promotion_refused' USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_provenance ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_ingress_provenance
        BEFORE INSERT OR UPDATE OF verified_commerce_ingress_state, b26_p2_provenance_status
        ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_ingress_provenance()
        """
    )
    # Existing rows: all verified become unknown_legacy (honest: authorship
    # unrecoverable from VII/VIII bytes); pending become not_applicable.
    op.execute(
        """
        UPDATE public.webhook_ingress_identities AS i
           SET b26_p2_provenance_status = CASE
               WHEN i.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
               THEN 'pending_not_applicable'
               ELSE 'unknown_legacy'
           END
         WHERE i.b26_p2_provenance_status = 'unknown_legacy'
            OR i.b26_p2_provenance_status IS NULL
        """
    )
    # Dispatch guard: new execution authority cannot be founded on unknown provenance.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_provenance()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _prov text;
        BEGIN
            SELECT i.b26_p2_provenance_status INTO _prov
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = NEW.webhook_ingress_identity_id
               AND i.tenant_id = NEW.tenant_id;
            IF FOUND AND _prov = 'unknown_legacy' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provenance_unknown' USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_provenance ON public.b23_match_task_dispatches"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_dispatch_provenance
        BEFORE INSERT ON public.b23_match_task_dispatches
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_dispatch_provenance()
        """
    )

    # ------------------------------------------------------------------
    # A2. Recorder with canonical scope binding (replaces VIII recorder).
    # Caller scope must equal sovereign recomputation; meaning_status set
    # to canonically_bound on success. ON CONFLICT allows lawful retry to
    # converge to fresh scope when the window grew between derive and record
    # (update only when not yet conducted and new scope is canonical).
    # ------------------------------------------------------------------
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_conduction_receipt(text, text, integer)"
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
            _canonical text;
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
                -- IX canonical consequence binding: caller scope must equal
                -- sovereign recomputation for this tenant window.
                _canonical := public.b26_p2_canonical_scope_identity_for_window(_tenant, _exp_ws, _exp_we);
                IF _scope IS DISTINCT FROM _canonical THEN
                    RAISE EXCEPTION 'b26_p2_receipt_scope_not_canonical'
                        USING ERRCODE = '42501';
                END IF;
                INSERT INTO public.b26_p2_conduction_receipts (
                    task_id, tenant_id, webhook_ingress_identity_id,
                    window_start, window_end,
                    b23_processed_count, p2_scope_identity,
                    policy_semantic_sha256, ix_meaning_status
                )
                VALUES (_task, _tenant, _ingress,
                        _exp_ws, _exp_we,
                        _count, _scope,
                        _caller_sha, 'canonically_bound')
                ON CONFLICT (task_id) DO UPDATE SET
                    b23_processed_count = EXCLUDED.b23_processed_count,
                    p2_scope_identity = EXCLUDED.p2_scope_identity,
                    policy_semantic_sha256 = EXCLUDED.policy_semantic_sha256,
                    ix_meaning_status = 'canonically_bound'
                 WHERE public.b26_p2_conduction_receipts.task_id = EXCLUDED.task_id
                   AND NOT EXISTS (
                       SELECT 1 FROM public.b23_match_task_dispatches AS d
                        WHERE d.task_id = EXCLUDED.task_id
                          AND d.delivery_state = 'conducted'
                   );
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
        "REVOKE ALL ON FUNCTION public.b26_p2_record_conduction_receipt(text, text, integer, text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_conduction_receipt(text, text, integer, text) TO app_worker;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # A3. Gate with canonical scope binding on every conduction.
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
            _canonical text;
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
                IF _receipt_sha IS DISTINCT FROM _policy_semantic THEN
                    RAISE EXCEPTION 'b26_p2_conducted_policy_semantic_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                -- IX canonical binding: receipt scope must equal sovereign
                -- recomputation for this tenant window at gate time.
                _canonical := public.b26_p2_canonical_scope_identity_for_window(_tenant, _exp_ws, _exp_we);
                IF _receipt_scope IS DISTINCT FROM _canonical THEN
                    RAISE EXCEPTION 'b26_p2_conducted_scope_not_canonical'
                        USING ERRCODE = '42501';
                END IF;
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
    # B/D. Temporal conservation extended to P2-read reference presence.
    # Value-preserving reference corrections remain free (B2.3 sovereignty);
    # presence flips under conducted parents refuse. Trigger list derived
    # from the P2 semantic footprint (status + link + reference presence).
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
            _old_ref_present boolean;
            _new_ref_present boolean;
            _ref_presence_flipped boolean;
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
                _old_ref_present := btrim(COALESCE(OLD.canonical_commerce_reference, '')) <> '';
                _new_ref_present := btrim(COALESCE(NEW.canonical_commerce_reference, '')) <> '';
                _ref_presence_flipped := _old_ref_present IS DISTINCT FROM _new_ref_present;
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
                -- IX: P2-read reference presence is temporal footprint.
                -- A presence flip (blank<->non-blank) under a conducted
                -- parent changes P2 disposition (IN_SCOPE vs UNRESOLVED) and
                -- must refuse; value-preserving rewrites stay free.
                IF _ref_presence_flipped THEN
                    IF OLD.webhook_ingress_identity_id IS NOT NULL AND (_old_qual OR _new_qual) THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = OLD.tenant_id
                               AND d.webhook_ingress_identity_id = OLD.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_reference_presence_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                    IF NEW.webhook_ingress_identity_id IS NOT NULL AND (_old_qual OR _new_qual)
                       AND (OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                            OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id) THEN
                        IF EXISTS (
                            SELECT 1 FROM public.b23_match_task_dispatches AS d
                             WHERE d.tenant_id = NEW.tenant_id
                               AND d.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
                               AND d.delivery_state = 'conducted'
                        ) THEN
                            RAISE EXCEPTION 'b26_p2_conducted_reference_presence_refused'
                                USING ERRCODE = '42501';
                        END IF;
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_temporal_conservation ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_temporal_conservation
        BEFORE INSERT OR UPDATE OF status, webhook_ingress_identity_id, tenant_id, canonical_commerce_reference
            OR DELETE
        ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_enforce_verdict_temporal_conservation()
        """
    )

    # ------------------------------------------------------------------
    # G. Scheduler liveness separated from evaluation freshness.
    # Only app_beat may tick scheduler liveness; manual evaluation as
    # app_relay cannot manufacture scheduler health.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_scheduler_heartbeat (
            tenant_id uuid PRIMARY KEY REFERENCES public.tenants(id) ON DELETE CASCADE,
            last_tick timestamptz NOT NULL DEFAULT now(),
            tick_count bigint NOT NULL DEFAULT 0,
            updated_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_scheduler_heartbeat ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_scheduler_heartbeat FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_scheduler_heartbeat'
                   AND policyname = 'tenant_isolation_policy_b26_p2_scheduler_heartbeat'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_scheduler_heartbeat
                    ON public.b26_p2_scheduler_heartbeat
                    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
                    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_scheduler_heartbeat()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _tenant uuid;
            _prev_guc text;
        BEGIN
            IF session_user NOT IN ('app_beat', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_scheduler_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            IF _prev_guc IS NULL OR btrim(COALESCE(_prev_guc, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_scheduler_tenant_missing'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _tenant := _prev_guc::uuid;
            EXCEPTION WHEN OTHERS THEN
                RAISE EXCEPTION 'b26_p2_scheduler_tenant_malformed'
                    USING ERRCODE = '42501';
            END;
            INSERT INTO public.b26_p2_scheduler_heartbeat AS h (
                tenant_id, last_tick, tick_count, updated_at
            )
            VALUES (_tenant, now(), 1, now())
            ON CONFLICT (tenant_id) DO UPDATE SET
                last_tick = now(),
                tick_count = h.tick_count + 1,
                updated_at = now();
            RETURN 'scheduled';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_scheduler_heartbeat() FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_scheduler_heartbeat() TO app_beat;
            END IF;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_scheduler_heartbeat FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_scheduler_heartbeat TO app_beat;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT ON TABLE public.b26_p2_scheduler_heartbeat TO app_user;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_relay') THEN
                GRANT SELECT ON TABLE public.b26_p2_scheduler_heartbeat TO app_relay;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # IX census: quarantine dispatches founded on unknown provenance.
    # Children-first; B2.3 verdict history preserved, never rewritten.
    # Scope-history is NOT censused by live recomputation (window growth
    # would false-positive lawful history); scope forgery is closed
    # going-forward by the canonical gate above.
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
            _n_children integer := 0;
            _n_roots integer := 0;
        BEGIN
            CREATE TEMPORARY TABLE _ix_contradictions ON COMMIT DROP AS
            SELECT d.task_id AS task_id, 'unknown_provenance_root' AS kind
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE i.b26_p2_provenance_status = 'unknown_legacy'
               AND d.delivery_state IN ('published', 'conducted', 'pending_publish');
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_ix:' || c.kind,
                   COALESCE(o.payload, '{}'::jsonb), '202609230001'
              FROM public.b26_p2_execution_outbox AS o
              JOIN _ix_contradictions AS c
                ON c.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_children = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_ix:' || c.kind,
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609230001'
              FROM public.b26_p2_task_authority_directory AS dir
              JOIN _ix_contradictions AS c
                ON c.task_id = dir.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_ix:' || c.kind,
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity
                   ), '202609230001'
              FROM public.b26_p2_conduction_receipts AS rec
              JOIN _ix_contradictions AS c
                ON c.task_id = rec.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', d.task_id, d.tenant_id,
                   d.webhook_ingress_identity_id, d.window_start, d.window_end,
                   'corrective_ix:' || c.kind,
                   jsonb_build_object('kind', c.kind), '202609230001'
              FROM public.b23_match_task_dispatches AS d
              JOIN _ix_contradictions AS c
                ON c.task_id = d.task_id;
            GET DIAGNOSTICS _n_roots = ROW_COUNT;
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _ix_contradictions AS c
            WHERE d.task_id = c.task_id;
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
            RAISE NOTICE 'b26_p2_corrective_ix_census children=% roots=%',
                _n_children, _n_roots;
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
    # Restore VIII recorder (no canonical binding, ON CONFLICT DO NOTHING,
    # no meaning status) before dropping IX columns/functions it depends on.
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
                RAISE EXCEPTION 'b26_p2_receipt_task_missing' USING ERRCODE = '42501';
            END IF;
            _scope := btrim(COALESCE(p_scope_identity, ''));
            IF _scope !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_scope_not_bound' USING ERRCODE = '42501';
            END IF;
            _count := COALESCE(p_processed_count, 0);
            IF _count < 0 THEN
                RAISE EXCEPTION 'b26_p2_receipt_count_negative' USING ERRCODE = '42501';
            END IF;
            _caller_sha := btrim(COALESCE(p_policy_semantic_sha256, ''));
            IF _caller_sha !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_semantic_binding_required' USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_receipt_caller_refused' USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority' USING ERRCODE = '42501';
            END IF;
            SELECT scope_policy_version, source_sha256, semantic_sha256 INTO _policy_version, _policy_source, _policy_semantic
              FROM public.b26_p2_scope_policy_authority ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2'
               OR _policy_source IS DISTINCT FROM 'c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15'
               OR _policy_semantic IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_not_bound' USING ERRCODE = '42501';
            END IF;
            IF _caller_sha IS DISTINCT FROM _policy_semantic THEN
                RAISE EXCEPTION 'b26_p2_receipt_policy_semantic_not_bound' USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch' USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state, i.provider, i.verified_amount_currency
                  INTO _clock, _ingress_state, _ingress_provider, _ingress_currency
                  FROM public.webhook_ingress_identities AS i WHERE i.id = _ingress AND i.tenant_id = _tenant FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing' USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified' USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_receipt_provider_shape_refused:blank' USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_currency, '')) = '' OR length(btrim(_ingress_currency)) <> 3 THEN
                    RAISE EXCEPTION 'b26_p2_receipt_currency_shape_refused:blank' USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign' USING ERRCODE = '42501';
                END IF;
                INSERT INTO public.b26_p2_conduction_receipts (
                    task_id, tenant_id, webhook_ingress_identity_id,
                    window_start, window_end,
                    b23_processed_count, p2_scope_identity,
                    policy_semantic_sha256
                )
                VALUES (_task, _tenant, _ingress, _exp_ws, _exp_we, _count, _scope, _caller_sha)
                ON CONFLICT (task_id) DO NOTHING;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN _task;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
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
                RAISE EXCEPTION 'b26_p2_conducted_task_missing' USING ERRCODE = '42501';
            END IF;
            IF session_user NOT IN ('app_worker', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_conducted_caller_refused' USING ERRCODE = '42501';
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_no_authority' USING ERRCODE = '42501';
            END IF;
            SELECT scope_policy_version, source_sha256, semantic_sha256 INTO _policy_version, _policy_source, _policy_semantic
              FROM public.b26_p2_scope_policy_authority ORDER BY scope_policy_version DESC LIMIT 1;
            IF NOT FOUND
               OR _policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2'
               OR _policy_source IS DISTINCT FROM 'c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15'
               OR _policy_semantic IS DISTINCT FROM 'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
                RAISE EXCEPTION 'b26_p2_conducted_policy_not_bound' USING ERRCODE = '42501';
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
                  FROM public.b23_match_task_dispatches AS d WHERE d.task_id = _task FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_dispatch' USING ERRCODE = '42501';
                END IF;
                SELECT o.state INTO _outbox_state FROM public.b26_p2_execution_outbox AS o
                 WHERE o.dispatch_task_id = _task FOR UPDATE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_outbox' USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state, i.provider, i.verified_amount_currency
                  INTO _clock, _ingress_state, _ingress_provider, _ingress_currency
                  FROM public.webhook_ingress_identities AS i WHERE i.id = _ingress AND i.tenant_id = _tenant FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing' USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_ingress_unverified' USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_provider_shape_refused:blank' USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_dispatch_provider, '')) = '' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_provider_shape_refused:blank' USING ERRCODE = '42501';
                END IF;
                IF btrim(COALESCE(_ingress_currency, '')) = '' OR length(btrim(_ingress_currency)) <> 3 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_currency_shape_refused:blank' USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_window_not_sovereign' USING ERRCODE = '42501';
                END IF;
                IF _dispatch_state = 'conducted' AND _outbox_state = 'conducted' THEN
                    _already := true;
                ELSIF _dispatch_state IS DISTINCT FROM 'published' OR _outbox_state IS DISTINCT FROM 'published' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_not_published' USING ERRCODE = '42501';
                END IF;
                SELECT count(*), max(r.window_start), max(r.window_end), max(r.p2_scope_identity), max(r.policy_semantic_sha256)
                  INTO _receipt_count, _receipt_ws, _receipt_we, _receipt_scope, _receipt_sha
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task AND r.tenant_id = _tenant AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_receipt' USING ERRCODE = '42501';
                END IF;
                IF _receipt_ws IS DISTINCT FROM _exp_ws OR _receipt_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_receipt_not_bound' USING ERRCODE = '42501';
                END IF;
                IF _receipt_scope !~ '^[0-9a-f]{64}$' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_scope_not_bound' USING ERRCODE = '42501';
                END IF;
                IF _receipt_sha IS DISTINCT FROM _policy_semantic THEN
                    RAISE EXCEPTION 'b26_p2_conducted_policy_semantic_not_bound' USING ERRCODE = '42501';
                END IF;
                PERFORM 1 FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant AND v.webhook_ingress_identity_id = _ingress FOR SHARE;
                SELECT count(*) INTO _verdict_count FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant AND v.webhook_ingress_identity_id = _ingress
                   AND v.status IN ('matched_provisional','matched_confirmed','adjusted');
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_no_b23_consequence' USING ERRCODE = '42501';
                END IF;
                IF _already THEN
                    PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                    RETURN 'already_conducted';
                END IF;
                UPDATE public.b23_match_task_dispatches AS d SET delivery_state = 'conducted', updated_at = now()
                 WHERE d.task_id = _task AND d.delivery_state = 'published';
                UPDATE public.b26_p2_execution_outbox AS o SET state = 'conducted', updated_at = now()
                 WHERE o.dispatch_task_id = _task AND o.state = 'published';
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'conducted';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_provenance ON public.b23_match_task_dispatches"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_dispatch_provenance()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_provenance ON public.webhook_ingress_identities"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_ingress_provenance()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_canonical_scope_identity_for_window(uuid, timestamptz, timestamptz)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_scheduler_heartbeat()"
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_scheduler_heartbeat"  # CI:DESTRUCTIVE_OK - reversible rollback removes the IX-only scheduler-liveness table (operational state, never financial truth).
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities DROP COLUMN IF EXISTS b26_p2_provenance_status"  # CI:DESTRUCTIVE_OK - reversible rollback for IX provenance law.
    )
    op.execute(
        "ALTER TABLE public.b26_p2_conduction_receipts DROP COLUMN IF EXISTS ix_meaning_status"  # CI:DESTRUCTIVE_OK - reversible rollback for IX meaning honesty.
    )
    # Restore VIII temporal trigger footprint (status/link only).
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_temporal_conservation ON public.b23_match_verdicts"
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
