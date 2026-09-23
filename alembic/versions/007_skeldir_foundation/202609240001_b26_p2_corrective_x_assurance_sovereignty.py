"""B2.6-P2 Corrective X: assurance-plane sovereignty, single semantic authority.

Revision ID: 202609240001
Revises: 202609230001

Governing law: ASSURANCE-PLANE SOVEREIGNTY + SINGLE SEMANTIC AUTHORITY +
NON-SELF-CERTIFYING EFFECT PROOF. Corrective IX made the running lawful
path substantially correct; the residual class is candidate-authored proof
certifying candidate-authored behavior (representation laundering: pins,
hashes, manifests, allowlists, function names, digests, fixtures, and
candidate-side validators re-greened around an intact prohibited effect).

X establishes, at the physical layer:

A. ONE P2 SEMANTIC AUTHORITY (database-canonical). Python
   ``derive_governed_scope`` becomes a thin adapter over the SQL
   classifier/identity below and no longer independently classifies; the
   former pure-Python law library (``scope_authority.py``) is frozen
   byte-identical and provably unimported on the truth path (AST ban), so
   mutating it cannot move terminal truth. Normalization lives once, in
   ``b26_p2_ascii_strip`` + ``b26_p2_normalize_provider`` /
   ``b26_p2_normalize_currency`` + ``b26_p2_classify_candidate``; the
   observed ``strip()`` vs ``btrim()`` divergence is closed by deleting the
   second implementation, not by synchronizing two. Policy v2 bytes and
   semantic SHA are unchanged (no version churn).

B. EFFECT-BOUND CONDUCTED (trigger law). Any transition into
   ``conducted`` on dispatches/outbox, and any receipt write, must satisfy
   the canonical consequence invariant recomputed at effect time,
   regardless of which function, overload, helper, trigger, or direct
   UPDATE initiated the write. Weakening ``b26_p2_mark_conducted``,
   planting ``*_helper`` overloads, or regenerating pins cannot produce
   false conducted: the guard triggers refuse.

C. EVIDENCE-BACKED PROVENANCE. ``unknown_legacy -> authenticated_known``
   is refused for every direct UPDATE by every role; only
   ``b26_p2_attest_provenance_evidence`` (which records an evidence row
   bound to the row's own provider idempotency key) can promote, so bare
   status writes can never mint certainty. Same-event copies remain dead
   on the tenant idempotency UNIQUE; re-ingestion restores through the
   attester.

D. GENERIC POST-UPGRADE CENSUS. Every truth-capable row satisfies current
   X invariants or is explicitly quarantined (unknown roots, non-canonical
   receipts, conducted-without-consequence, blank-shape foundations);
   B2.3 verdict history is never rewritten. Survivors fail the migration.

E. SCHEDULER-PLANE HONESTY WIRING. Heartbeat rows carry the beating
   instance identity (operator correlation, not process proof); the beat
   scheduler executes the tick inline so the scheduled path has a shipped
   consumer (the beat process itself holds the app_beat credential).

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved (no new
TrustEnvelope authority; trust roles gain zero grants).
"""

from __future__ import annotations

from alembic import op

revision = "202609240001"
down_revision = "202609230001"
branch_labels = None
depends_on = None

_POLICY_VERSION = "b2.6-p2-scope-policy-v2"
_POLICY_SOURCE_SHA = "c22eaf98189a34cca6c4452f61402dd0a258a4688602ef92e4ab2dbd0a2f3c15"
_POLICY_SEMANTIC_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"

# Governed ASCII whitespace set for the P2 strip law
# (space, tab, LF, CR, FF, VT). Declared alias law is
# strip_ascii_lower_exact_match_only: Unicode-only whitespace (e.g. NBSP)
# is NOT stripped and therefore never normalizes into the universe.
_ASCII_WS_CLASS = " \t\n\r\f\v"


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b23_match_verdicts IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b23_match_task_dispatches IN SHARE ROW EXCLUSIVE MODE"
    )
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
        "LOCK TABLE public.b26_p2_execution_quarantine IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_scheduler_heartbeat IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # X1. Single normalization authority: ASCII strip law, implemented
    # ONCE. Every P2 semantic site (canonical identity, per-candidate
    # classifier, temporal presence) calls these; no btrim/strip copy
    # remains on any meaning-bearing path.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_ascii_strip(p_value text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        SELECT regexp_replace(
                 regexp_replace(COALESCE(p_value, ''), '^[ \\t\\n\\r\\f\\v]+', ''),
               '[ \\t\\n\\r\\f\\v]+$', '')
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_strip_provider_token(p_raw text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        SELECT lower(public.b26_p2_ascii_strip(p_raw))
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_strip_currency_token(p_raw text)
        RETURNS text
        LANGUAGE sql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        SELECT upper(public.b26_p2_ascii_strip(p_raw))
        $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_normalize_provider(p_raw text)
        RETURNS text
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _token text;
        BEGIN
            _token := public.b26_p2_strip_provider_token(p_raw);
            IF _token = '' THEN
                RAISE EXCEPTION 'b26_p2_provider_shape_refused:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF _token NOT IN ('paypal', 'shopify', 'stripe', 'woocommerce') THEN
                RAISE EXCEPTION 'b26_p2_unsupported_provider_excluded:%', _token
                    USING ERRCODE = '42501';
            END IF;
            RETURN _token;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_normalize_currency(p_raw text)
        RETURNS text
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _token text;
        BEGIN
            _token := public.b26_p2_strip_currency_token(p_raw);
            IF _token = '' THEN
                RAISE EXCEPTION 'b26_p2_currency_shape_refused:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF _token !~ '^[A-Z]{3}$' THEN
                RAISE EXCEPTION 'b26_p2_currency_shape_refused:%', _token
                    USING ERRCODE = '42501';
            END IF;
            IF _token <> 'USD' THEN
                RAISE EXCEPTION 'b26_p2_unsupported_currency_excluded:%', _token
                    USING ERRCODE = '42501';
            END IF;
            RETURN _token;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # X2. Single per-candidate semantic classifier. This is the only
    # implementation of the provider -> currency -> window -> reference
    # priority law. The Python worker calls it per candidate and never
    # branches on these semantics itself.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_classify_candidate(
            p_tenant uuid,
            p_provider_raw text,
            p_currency_raw text,
            p_event_time timestamptz,
            p_window_start timestamptz,
            p_window_end timestamptz,
            p_policy_version text,
            p_source_reference text
        )
        RETURNS TABLE(
            o_provider text,
            o_rail text,
            o_currency text,
            o_disposition text,
            o_reason text
        )
        LANGUAGE plpgsql
        IMMUTABLE
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _prov text;
            _cur text;
            _has_ref boolean;
        BEGIN
            IF p_policy_version IS DISTINCT FROM 'b2.6-p2-scope-policy-v2' THEN
                RAISE EXCEPTION 'b26_p2_invalid_scope_policy_version:%', COALESCE(p_policy_version, '<null>')
                    USING ERRCODE = '42501';
            END IF;
            IF p_window_start IS NULL OR p_window_end IS NULL
               OR p_window_start >= p_window_end THEN
                RAISE EXCEPTION 'b26_p2_invalid_window_authority:not_half_open'
                    USING ERRCODE = '42501';
            END IF;
            IF p_event_time IS NULL THEN
                RAISE EXCEPTION 'b26_p2_invalid_event_time_authority:null'
                    USING ERRCODE = '42501';
            END IF;
            _prov := public.b26_p2_strip_provider_token(p_provider_raw);
            _cur := public.b26_p2_strip_currency_token(p_currency_raw);
            IF _prov = '' THEN
                RAISE EXCEPTION 'b26_p2_invalid_provider_shape:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF _cur = '' THEN
                RAISE EXCEPTION 'b26_p2_invalid_currency_shape:blank'
                    USING ERRCODE = '42501';
            END IF;
            IF _prov NOT IN ('paypal', 'shopify', 'stripe', 'woocommerce') THEN
                o_provider := _prov; o_rail := _prov; o_currency := _cur;
                o_disposition := 'EXPLICITLY_EXCLUDED';
                o_reason := 'unsupported_provider_excluded';
                RETURN NEXT;
                RETURN;
            END IF;
            IF _cur <> 'USD' THEN
                o_provider := _prov; o_rail := _prov; o_currency := _cur;
                o_disposition := 'EXPLICITLY_EXCLUDED';
                o_reason := 'unsupported_currency_excluded';
                RETURN NEXT;
                RETURN;
            END IF;
            IF NOT (p_event_time >= p_window_start AND p_event_time < p_window_end) THEN
                o_provider := _prov; o_rail := _prov; o_currency := _cur;
                o_disposition := 'EXPLICITLY_EXCLUDED';
                o_reason := 'outside_governed_window_excluded';
                RETURN NEXT;
                RETURN;
            END IF;
            _has_ref := public.b26_p2_ascii_strip(COALESCE(p_source_reference, '')) <> '';
            IF NOT _has_ref THEN
                o_provider := _prov; o_rail := _prov; o_currency := _cur;
                o_disposition := 'SUPPORTED_BUT_UNRESOLVED';
                o_reason := 'source_identity_unresolved';
                RETURN NEXT;
                RETURN;
            END IF;
            o_provider := _prov; o_rail := _prov; o_currency := _cur;
            o_disposition := 'SUPPORTED_AND_IN_SCOPE';
            o_reason := 'supported_in_scope';
            RETURN NEXT;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_ascii_strip(text) FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_strip_provider_token(text) FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_strip_currency_token(text) FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_normalize_provider(text) FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_normalize_currency(text) FROM PUBLIC"
    )
    op.execute(
        """
        REVOKE ALL ON FUNCTION public.b26_p2_classify_candidate(
            uuid, text, text, timestamptz, timestamptz, timestamptz, text, text)
        FROM PUBLIC
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_ascii_strip(text) TO app_worker;
                GRANT EXECUTE ON FUNCTION public.b26_p2_strip_provider_token(text) TO app_worker;
                GRANT EXECUTE ON FUNCTION public.b26_p2_strip_currency_token(text) TO app_worker;
                GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_provider(text) TO app_worker;
                GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_currency(text) TO app_worker;
                GRANT EXECUTE ON FUNCTION public.b26_p2_classify_candidate(
                    uuid, text, text, timestamptz, timestamptz, timestamptz, text, text) TO app_worker;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_ascii_strip(text) TO app_user;
                GRANT EXECUTE ON FUNCTION public.b26_p2_strip_provider_token(text) TO app_user;
                GRANT EXECUTE ON FUNCTION public.b26_p2_strip_currency_token(text) TO app_user;
                GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_provider(text) TO app_user;
                GRANT EXECUTE ON FUNCTION public.b26_p2_normalize_currency(text) TO app_user;
                GRANT EXECUTE ON FUNCTION public.b26_p2_classify_candidate(
                    uuid, text, text, timestamptz, timestamptz, timestamptz, text, text) TO app_user;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # X3. Canonical identity rewritten onto the single normalization
    # authority. Structure, constants, and identity material identical to
    # IX; only the whitespace/normalization primitives change (btrim ->
    # ascii-strip law), closing the strip-vs-btrim class at the source.
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
                       AND (public.b26_p2_ascii_strip(COALESCE(i.provider,'')) = ''
                            OR public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency,'')) = ''
                            OR length(public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency,''))) <> 3)
                ) THEN
                    PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc,''), true);
                    RAISE EXCEPTION 'b26_p2_canonical_scope_blank_shape' USING ERRCODE='42501';
                END IF;
                SELECT string_agg(line, '|' ORDER BY line) INTO _lines FROM (
                    SELECT
                        i.id::text || ':' || _all._prov || ':' || _all._prov || ':' || _all._cur || ':' || _all._disp || ':' || _all._reason || ':' || i.verified_amount_minor::text AS line
                    FROM public.webhook_ingress_identities AS i,
                    LATERAL (SELECT public.b26_p2_strip_provider_token(i.provider) AS _prov,
                                    public.b26_p2_strip_currency_token(i.verified_amount_currency) AS _cur) AS _norm,
                    LATERAL (SELECT EXISTS (
                            SELECT 1 FROM public.b23_match_verdicts AS v
                             WHERE v.tenant_id = p_tenant
                               AND v.webhook_ingress_identity_id = i.id
                               AND v.status IN ('matched_provisional','matched_confirmed','adjusted')
                               AND public.b26_p2_ascii_strip(COALESCE(v.canonical_commerce_reference,'')) <> ''
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

    # ------------------------------------------------------------------
    # X4. Temporal presence aligned to the single law. The trigger's
    # blank<->non-blank flip detection must agree with the classifier on
    # every byte (tab-only references flip under ascii-strip); otherwise
    # a disposition-changing mutation stays free. Value-preserving
    # rewrites remain free (B2.3 sovereignty conserved).
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
                _old_ref_present := public.b26_p2_ascii_strip(COALESCE(OLD.canonical_commerce_reference, '')) <> '';
                _new_ref_present := public.b26_p2_ascii_strip(COALESCE(NEW.canonical_commerce_reference, '')) <> '';
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

    # ------------------------------------------------------------------
    # X5. Evidence-backed provenance. The evidence row (bound to the
    # row's own provider idempotency key) is the authority; no direct
    # UPDATE by any role can move unknown_legacy -> authenticated_known.
    # INSERT minting for API-verified rows is unchanged (same-event
    # copies remain dead on the tenant idempotency UNIQUE).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_provenance_evidence (
            webhook_ingress_identity_id uuid PRIMARY KEY
                REFERENCES public.webhook_ingress_identities(id) ON DELETE CASCADE,
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            evidence_kind text NOT NULL,
            evidence_ref text NOT NULL,
            attested_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_provenance_evidence ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_provenance_evidence FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_provenance_evidence'
                   AND policyname = 'tenant_isolation_policy_b26_p2_provenance_evidence'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_provenance_evidence
                    ON public.b26_p2_provenance_evidence
                    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
                    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
            END IF;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_provenance_evidence FROM PUBLIC"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_attest_provenance_evidence(
            p_ingress uuid,
            p_kind text,
            p_ref text
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _tenant uuid;
            _idem text;
            _state text;
            _prov text;
            _prev_guc text;
        BEGIN
            IF session_user NOT IN ('app_user', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_kind IS DISTINCT FROM 'signed_provider_reingestion'
               AND p_kind IS DISTINCT FROM 'governed_attestation' THEN
                RAISE EXCEPTION 'b26_p2_evidence_kind_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.b26_p2_provenance_status
              INTO _tenant, _idem, _state, _prov
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_evidence_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_evidence_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_ref, '')) = ''
               OR p_ref IS DISTINCT FROM _idem THEN
                RAISE EXCEPTION 'b26_p2_evidence_ref_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                INSERT INTO public.b26_p2_provenance_evidence AS e (
                    webhook_ingress_identity_id, tenant_id,
                    evidence_kind, evidence_ref
                )
                VALUES (p_ingress, _tenant, p_kind, p_ref)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    attested_at = now();
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known'
                 WHERE i.id = p_ingress;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_user;
            END IF;
        END $$;
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
                IF OLD.b26_p2_provenance_status IS DISTINCT FROM NEW.b26_p2_provenance_status THEN
                    IF OLD.b26_p2_provenance_status = 'authenticated_known'
                       AND NEW.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known' THEN
                        RAISE EXCEPTION 'b26_p2_provenance_downgrade_refused' USING ERRCODE = '42501';
                    END IF;
                    -- X law: promotion requires a recorded evidence event
                    -- bound to this ingress. No role allowlist: even
                    -- app_user cannot promote by bare status write.
                    IF OLD.b26_p2_provenance_status = 'unknown_legacy'
                       AND NEW.b26_p2_provenance_status = 'authenticated_known'
                       AND NOT EXISTS (
                            SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                             WHERE e.webhook_ingress_identity_id = OLD.id
                        ) THEN
                        RAISE EXCEPTION 'b26_p2_provenance_promotion_refused' USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # X6. Scheduler-plane instance identity (operator correlation).
    # The tick records which beat instance beat; process proof remains
    # the orchestrator's domain and is never claimed in health naming.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b26_p2_scheduler_heartbeat
        ADD COLUMN IF NOT EXISTS beat_instance_id uuid
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
            _inst_raw text;
            _inst uuid;
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
            IF _prev_guc IS NULL OR public.b26_p2_ascii_strip(COALESCE(_prev_guc, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_scheduler_tenant_missing'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _tenant := _prev_guc::uuid;
            EXCEPTION WHEN OTHERS THEN
                RAISE EXCEPTION 'b26_p2_scheduler_tenant_malformed'
                    USING ERRCODE = '42501';
            END;
            BEGIN
                _inst_raw := current_setting('app.beat_instance_id', true);
            EXCEPTION WHEN OTHERS THEN
                _inst_raw := NULL;
            END;
            BEGIN
                IF _inst_raw IS NULL OR public.b26_p2_ascii_strip(_inst_raw) = '' THEN
                    _inst := NULL;
                ELSE
                    _inst := _inst_raw::uuid;
                END IF;
            EXCEPTION WHEN OTHERS THEN
                _inst := NULL;
            END;
            INSERT INTO public.b26_p2_scheduler_heartbeat AS h (
                tenant_id, last_tick, tick_count, updated_at, beat_instance_id
            )
            VALUES (_tenant, now(), 1, now(), _inst)
            ON CONFLICT (tenant_id) DO UPDATE SET
                last_tick = now(),
                tick_count = h.tick_count + 1,
                updated_at = now(),
                beat_instance_id = COALESCE(EXCLUDED.beat_instance_id, h.beat_instance_id);
            RETURN 'scheduled';
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # X6b. Tenant enumeration for the beat-plane ticker (least
    # privilege, column-scoped). The scheduler-plane tick must list
    # tenants to tick per-tenant heartbeats; without SELECT(id) the
    # beat credential cannot enumerate them and the scheduled path is
    # dead at the grant plane no matter which process executes it.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                GRANT SELECT (id) ON TABLE public.tenants TO app_beat;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # X7. Effect-bound conducted invariant. Fires on EVERY conducted
    # transition of either twin, whoever wrote it: approved gate,
    # weakened gate, overload, helper, trigger, or direct UPDATE. The
    # invariant recomputes the canonical consequence at effect time.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_guard_conducted_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _ingress_prov text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _receipt_count integer;
            _receipt_scope text;
            _receipt_sha text;
            _verdict_count integer;
            _policy_version text;
            _policy_source text;
            _policy_semantic text;
            _canonical text;
            _prev_guc text;
        BEGIN
            IF TG_TABLE_NAME = 'b23_match_task_dispatches' THEN
                IF NEW.delivery_state IS DISTINCT FROM 'conducted'
                   OR OLD.delivery_state IS NOT DISTINCT FROM 'conducted' THEN
                    RETURN NEW;
                END IF;
                _task := NEW.task_id;
            ELSIF TG_TABLE_NAME = 'b26_p2_execution_outbox' THEN
                IF NEW.state IS DISTINCT FROM 'conducted'
                   OR OLD.state IS NOT DISTINCT FROM 'conducted' THEN
                    RETURN NEW;
                END IF;
                _task := NEW.dispatch_task_id;
            ELSE
                RETURN NEW;
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id
              INTO _tenant, _ingress
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_conducted_effect_refused:no_authority'
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
                RAISE EXCEPTION 'b26_p2_conducted_effect_refused:policy_not_bound'
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
                 WHERE d.task_id = _task
                 FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:no_dispatch'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state,
                       i.b26_p2_provenance_status
                  INTO _clock, _ingress_state, _ingress_prov
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant
                 FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_prov IS DISTINCT FROM 'authenticated_known' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:provenance_unknown'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                SELECT count(*), max(r.p2_scope_identity), max(r.policy_semantic_sha256)
                  INTO _receipt_count, _receipt_scope, _receipt_sha
                  FROM public.b26_p2_conduction_receipts AS r
                 WHERE r.task_id = _task
                   AND r.tenant_id = _tenant
                   AND r.webhook_ingress_identity_id = _ingress;
                IF _receipt_count <> 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:no_receipt'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_scope !~ '^[0-9a-f]{64}$' THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:scope_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                IF _receipt_sha IS DISTINCT FROM _policy_semantic THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:policy_semantic_not_bound'
                        USING ERRCODE = '42501';
                END IF;
                _canonical := public.b26_p2_canonical_scope_identity_for_window(_tenant, _exp_ws, _exp_we);
                IF _receipt_scope IS DISTINCT FROM _canonical THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:scope_not_canonical'
                        USING ERRCODE = '42501';
                END IF;
                SELECT count(*) INTO _verdict_count
                  FROM public.b23_match_verdicts AS v
                 WHERE v.tenant_id = _tenant
                   AND v.webhook_ingress_identity_id = _ingress
                   AND v.status IN ('matched_provisional',
                                    'matched_confirmed',
                                    'adjusted');
                IF _verdict_count < 1 THEN
                    RAISE EXCEPTION 'b26_p2_conducted_effect_refused:no_b23_consequence'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN NEW;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_conducted_effect_guard ON public.b23_match_task_dispatches"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_conducted_effect_guard
        BEFORE UPDATE OF delivery_state
        ON public.b23_match_task_dispatches
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_guard_conducted_transition()
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_conducted_effect_guard ON public.b26_p2_execution_outbox"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_conducted_effect_guard
        BEFORE UPDATE OF state
        ON public.b26_p2_execution_outbox
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_guard_conducted_transition()
        """
    )
    # Guard functions fire through the trigger mechanism, which requires
    # no EXECUTE grant (proven live): revoke the default PUBLIC grant so
    # no runtime principal holds a direct path to the guard bodies.
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_guard_conducted_transition() FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # X8. Receipt effect invariant. No reachable path persists
    # authoritative-looking receipt evidence without the canonical
    # consequence, even through a weakened recorder.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_guard_conduction_receipt()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _tenant uuid;
            _ingress uuid;
            _clock timestamptz;
            _ingress_state text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _policy_version text;
            _policy_source text;
            _policy_semantic text;
            _canonical text;
            _prev_guc text;
        BEGIN
            IF NEW.ix_meaning_status IS DISTINCT FROM 'canonically_bound' THEN
                RAISE EXCEPTION 'b26_p2_receipt_effect_refused:meaning_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.p2_scope_identity !~ '^[0-9a-f]{64}$' THEN
                RAISE EXCEPTION 'b26_p2_receipt_effect_refused:scope_not_bound'
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
                RAISE EXCEPTION 'b26_p2_receipt_effect_refused:policy_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.policy_semantic_sha256 IS DISTINCT FROM _policy_semantic THEN
                RAISE EXCEPTION 'b26_p2_receipt_effect_refused:policy_semantic_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            _tenant := NEW.tenant_id;
            _ingress := NEW.webhook_ingress_identity_id;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT i.event_timestamp, i.verified_commerce_ingress_state
                  INTO _clock, _ingress_state
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant
                 FOR SHARE;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_receipt_effect_refused:ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_receipt_effect_refused:ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF NEW.window_start IS DISTINCT FROM _exp_ws
                   OR NEW.window_end IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_receipt_effect_refused:window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                _canonical := public.b26_p2_canonical_scope_identity_for_window(_tenant, _exp_ws, _exp_we);
                IF NEW.p2_scope_identity IS DISTINCT FROM _canonical THEN
                    RAISE EXCEPTION 'b26_p2_receipt_effect_refused:scope_not_canonical'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN NEW;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_receipt_effect_guard ON public.b26_p2_conduction_receipts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_receipt_effect_guard
        BEFORE INSERT OR UPDATE ON public.b26_p2_conduction_receipts
        FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_guard_conduction_receipt()
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_guard_conduction_receipt() FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # X9. Generic post-upgrade invariant census over every truth-capable
    # row. Violations are quarantined children-first with explicit
    # reasons; B2.3 verdict history is preserved, never rewritten. Any
    # survivor fails the migration (no hybrid universe).
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
            _n_receipts integer := 0;
            _survivors integer := 0;
        BEGIN
            CREATE TEMPORARY TABLE _x_contradictions ON COMMIT DROP AS
            SELECT d.task_id AS task_id, 'unknown_provenance_root' AS kind
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE i.b26_p2_provenance_status = 'unknown_legacy'
               AND d.delivery_state IN ('published', 'conducted', 'pending_publish')
            UNION
            SELECT d.task_id AS task_id, 'blank_shape_foundation' AS kind
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.delivery_state IN ('published', 'conducted', 'pending_publish')
               AND (public.b26_p2_ascii_strip(COALESCE(i.provider, '')) = ''
                    OR public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, '')) = ''
                    OR length(public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, ''))) <> 3);
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_x:' || c.kind,
                   COALESCE(o.payload, '{}'::jsonb), '202609240001'
              FROM public.b26_p2_execution_outbox AS o
              JOIN _x_contradictions AS c
                ON c.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_children = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_x:' || c.kind,
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609240001'
              FROM public.b26_p2_task_authority_directory AS dir
              JOIN _x_contradictions AS c
                ON c.task_id = dir.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', d.task_id, d.tenant_id,
                   d.webhook_ingress_identity_id, d.window_start, d.window_end,
                   'corrective_x:' || c.kind,
                   jsonb_build_object('kind', c.kind), '202609240001'
              FROM public.b23_match_task_dispatches AS d
              JOIN _x_contradictions AS c
                ON c.task_id = d.task_id;
            GET DIAGNOSTICS _n_roots = ROW_COUNT;
            -- Non-canonical receipts: recompute live canonical per receipt.
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_x:receipt_not_canonical',
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity
                   ), '202609240001'
              FROM public.b26_p2_conduction_receipts AS rec
             WHERE rec.ix_meaning_status IS DISTINCT FROM 'canonically_bound'
                OR rec.p2_scope_identity IS DISTINCT FROM
                   public.b26_p2_canonical_scope_identity_for_window(
                       rec.tenant_id, rec.window_start, rec.window_end);
            GET DIAGNOSTICS _n_receipts = ROW_COUNT;
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _x_contradictions AS c
            WHERE d.task_id = c.task_id;
            DELETE FROM public.b26_p2_conduction_receipts AS rec
            USING public.b26_p2_execution_quarantine AS q
            WHERE q.source_relation = 'b26_p2_conduction_receipts'
              AND q.migration_identity = '202609240001'
              AND rec.task_id = q.task_id;
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
            -- Conducted-without-consequence must not survive silently.
            SELECT count(*) INTO _survivors
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.delivery_state = 'conducted'
               AND (i.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known'
                    OR NOT EXISTS (
                        SELECT 1 FROM public.b26_p2_conduction_receipts AS r
                         WHERE r.task_id = d.task_id
                           AND r.ix_meaning_status = 'canonically_bound'
                    ));
            IF _survivors > 0 THEN
                RAISE EXCEPTION 'b26_p2_corrective_x_census_survivors:%', _survivors
                    USING ERRCODE = '42501';
            END IF;
            RAISE NOTICE 'b26_p2_corrective_x_census children=% roots=% receipts=%',
                _n_children, _n_roots, _n_receipts;
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
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_beat') THEN
                REVOKE SELECT (id) ON TABLE public.tenants FROM app_beat;
            END IF;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_receipt_effect_guard ON public.b26_p2_conduction_receipts"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_guard_conduction_receipt()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_conducted_effect_guard ON public.b26_p2_execution_outbox"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_conducted_effect_guard ON public.b23_match_task_dispatches"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_guard_conducted_transition()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_attest_provenance_evidence(uuid, text, text)"
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_provenance_evidence"  # CI:DESTRUCTIVE_OK - reversible rollback removes the X-only evidence table (operational provenance state, never financial truth).
    )
    op.execute(
        "ALTER TABLE public.b26_p2_scheduler_heartbeat DROP COLUMN IF EXISTS beat_instance_id"  # CI:DESTRUCTIVE_OK - reversible rollback removes the X-only operator-correlation column.
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
    # Restore IX ingress-provenance law (session-allowlist promotion).
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
    # Restore IX temporal law (btrim presence).
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
        "DROP FUNCTION IF EXISTS public.b26_p2_classify_candidate(uuid, text, text, timestamptz, timestamptz, timestamptz, text, text)"
    )
    # Restore IX canonical law (btrim mirror) so IX<->X downgrade/re-upgrade
    # converges byte-for-byte on the pre-X authority.
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
        "DROP FUNCTION IF EXISTS public.b26_p2_normalize_provider(text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_normalize_currency(text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_strip_provider_token(text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_strip_currency_token(text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_ascii_strip(text)"
    )
