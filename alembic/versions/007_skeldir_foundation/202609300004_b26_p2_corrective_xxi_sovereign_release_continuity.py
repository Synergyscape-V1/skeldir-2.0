"""B2.6-P2 Corrective XXI: sovereign release compatibility, positive event
evidence, historical continuity and end-to-end financial authority
conservation.

H-XXI-01..14 (Directive XXI): XX closed the named instances; the audits
show the class survives as composition across versions, unsigned
transport meaning, maintenance-mutable history, rollback
reinterpretation, and proof-plane substitution.

Conservation laws established here (physical identities, not conventions):

    VERSION-COMPATIBLE MINTING (Law A)
        (The minting interface is release-bound by construction: the
        v1 atomic/attester signatures no longer exist at this head, so
        no previously built executable can invoke them -- an obsolete
        call fails with undefined-function before any state changes.
        The v2 signatures additionally carry body-derived lifecycle
        attestation the database enforces itself. The auth-root process
        additionally refuses boot against an incompatible schema. No
        caller-supplied version string confers anything.)

    POSITIVE EVENT MEANING (Law B)
        (Shopify creation requires a body that positively reads as a
        creation -- creation financial status, no terminal markers,
        coincident creation/update instants -- jointly with the
        transported topic; the topic alone never confers family. The
        rule is enforced in Python derivation, at the family choke,
        and at the database minting seam over attested lifecycle
        parameters. Contract event-family-law.v3.json governs the law.)

    MONOTONIC DISQUALIFICATION (Law D)
        (Backfill rows carry a persisted governed demotion policy
        (xxi-evidence-insufficient:pre-xxi-family) instead of relying
        solely on the current predicate text. Every predicate revision
        -- past, present, and restored -- refuses a non-null demotion
        reason, so supported rollback cannot silently promote
        disqualified history without new sufficient evidence. Genuine
        redelivery mints new rows and is unaffected.)

    OBSERVABLE HISTORY (Laws C + deployment-time continuity)
        (The supersession ledger gains a monotonic sequence; gaps are
        structurally detectable. A git-committed anchor file pins the
        early chain prefix -- outside any database principal's reach.
        A scheduled beat task records ledger count/tip/violations with
        unforgeable authorship; Trust issuance degrades when the
        observation is stale, violated, or inconsistent with live
        state. The guarantee is honestly two-tier: deployment-time
        continuity (CI anchor gate) + bounded runtime recency (beat
        horizon with fail-closed degradation). No administrator-
        resistant live immutability is claimed beyond this.)

    SINGLE CURRENTNESS (Law E, retained + extended)
        (Predicate, P3 delegation, Trust/Bayesian/kernel double-gating,
        and retirement propagation are unchanged from XX. Rollback
        reader unity is proven at the supported downgrade state.)

    EFFECT-LEVEL PROOF (Law F)
        (The XXI composition gate calls the real Trust adapter and the
        real P3 eligibility logic live, verifies ledger extension
        against the committed anchor, and censes downgrade-state reader
        unity -- no reimplementation oracles, no token-only checks for
        load-bearing behavior.)

Trusted-computing-base declaration: runtime principals are PREVENTED
(privilege + triggers + ABI absence, proven by live DML/call probes);
migration_owner/postgres maintenance is OBSERVED (disable/erase/
rewrite detected via observer + sequence gaps + beat-count contradiction
+ file-anchor prefix mismatch -- it cannot be done silently, though a
persistent active forger operating continuously between anchors retains
a bounded tail window, declared in the evidence report); true
PostgreSQL superuser remains outside any enforceable boundary.

Upgrade is linear (revises 202609300003). Published history is
append-only: this file never modifies any earlier revision; the
migration manifest gains 202609300004 while existing entries stay
byte-frozen. Family-law v3 + hierarchy v3 are appended to the
publication file chain and seeded into the ledger with exact digests.
"""

from __future__ import annotations

from alembic import op

revision = "202609300004"
down_revision = "202609300003"
branch_labels = None
depends_on = None

_XXI_FLOOR = "202609300004"
_XXI_PREDECESSOR_FLOOR = "202609300003"

_XXI_RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)

_XXI_DEMOTION_REASON = "xxi-evidence-insufficient:pre-xxi-family"

_XXI_HISTORY_OBSERVATION_INTERVAL_S = 300
_XXI_HISTORY_OBSERVATION_HORIZON_S = 1200


def _roles_sql_list() -> str:
    return ", ".join("'%s'" % r for r in _XXI_RUNTIME_ROLES)


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provider_auth_consequence IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b23_match_verdicts IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_verdict_supersession_ledger IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XXI-1. Re-assert least privilege (idempotent posture carry).
    # Table-level UPDATE removed, operational columns re-granted from
    # the live catalog; explicit per-role REVOKE ALL on ledgers,
    # registry, floor, and the new beat observation table.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE
            _role text;
            _col text;
        BEGIN
            FOR _role IN SELECT unnest(ARRAY[%s]) LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = _role
                ) THEN
                    CONTINUE;
                END IF;
                EXECUTE format(
                    'REVOKE UPDATE ON TABLE'
                    ' public.webhook_ingress_identities FROM %%I',
                    _role);
            END LOOP;
            FOR _role IN SELECT unnest(ARRAY['app_user', 'app_ingress']) LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = _role
                ) THEN
                    CONTINUE;
                END IF;
                FOR _col IN
                    SELECT column_name
                      FROM information_schema.columns
                     WHERE table_schema = 'public'
                       AND table_name = 'webhook_ingress_identities'
                       AND column_name NOT IN (
                           'b26_p2_provenance_status',
                           'b26_p2_semantic_regime',
                           'b26_p2_demotion_reason')
                LOOP
                    EXECUTE format(
                        'GRANT UPDATE (%%I) ON TABLE'
                        ' public.webhook_ingress_identities TO %%I',
                        _col, _role);
                END LOOP;
            END LOOP;
        END $$;
        """ % _roles_sql_list()
    )
    op.execute(
        """
        DO $$
        DECLARE
            _role text;
            _col text;
        BEGIN
            FOR _role IN SELECT unnest(ARRAY[%s]) LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = _role
                ) THEN
                    CONTINUE;
                END IF;
                EXECUTE format(
                    'REVOKE UPDATE ON TABLE public.b23_match_verdicts'
                    ' FROM %%I',
                    _role);
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker') THEN
                FOR _col IN
                    SELECT column_name
                      FROM information_schema.columns
                     WHERE table_schema = 'public'
                       AND table_name = 'b23_match_verdicts'
                       AND column_name
                           NOT IN ('b26_p2_source_authority_state')
                LOOP
                    EXECUTE format(
                        'GRANT UPDATE (%%I) ON TABLE'
                        ' public.b23_match_verdicts TO app_worker',
                        _col);
                END LOOP;
            END IF;
        END $$;
        """ % _roles_sql_list()
    )
    for _role in _XXI_RUNTIME_ROLES:
        for _ledger in (
            "b26_p2_verdict_supersession_ledger",
            "b26_p2_publication_history",
            "b26_p2_semantic_regime_registry",
            "b26_p2_operational_floor",
        ):
            op.execute(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
                " THEN EXECUTE 'REVOKE ALL ON TABLE public.%s FROM %s';"
                " END IF; END $$;" % (_role, _ledger, _role)
            )

    # ------------------------------------------------------------------
    # XXI-2. Release-bound minting ABI (Laws A/B).
    # The v1 atomic/attester signatures are retired: any executable
    # built against them fails with undefined-function before any
    # state changes -- no version string to forge, no convention to
    # ignore. The v2 signatures carry body-derived lifecycle
    # attestation the database enforces itself (helper below), so even
    # a direct-credential caller cannot mint terminal or
    # non-creation-moment Shopify evidence. CREATE OR REPLACE
    # preserves ownership; EXECUTE is granted to app_ingress only.
    # ------------------------------------------------------------------
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_enforce_lifecycle_admission(
    p_provider text,
    p_family text,
    p_financial_status text,
    p_cancelled_at timestamptz,
    p_refunds_present boolean,
    p_created_at timestamptz,
    p_updated_at timestamptz,
    p_require_creation_proof boolean
)
RETURNS void
LANGUAGE plpgsql
IMMUTABLE
SET search_path TO 'pg_catalog', 'public'
AS $$
BEGIN
    -- XXI (H-XXI-03): lifecycle admission is enforced at the minting
    -- seam, not just in Python derivation. Terminal lifecycle markers
    -- are never creation-family evidence, for any provider: a
    -- cancelled or refunded body cannot found current authority even
    -- when every other check passes (defense in depth behind the
    -- derivation layer, which refuses these shapes first).
    IF p_cancelled_at IS NOT NULL THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
            USING ERRCODE = '42501';
    END IF;
    IF COALESCE(p_refunds_present, false) THEN
        RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
            USING ERRCODE = '42501';
    END IF;
    -- Positive Shopify creation law: the transported topic asserts
    -- creation, but only a body that positively reads as a creation
    -- earns it. At mint time (p_require_creation_proof) the moments
    -- and status must be fully present; at re-attestation only
    -- positive contradictions refuse (the original mint already
    -- established the creation; unknown fields cannot).
    IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, ''))) = 'shopify'
       AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
           = 'orders.create' THEN
        IF p_require_creation_proof THEN
            IF p_financial_status IS NULL
               OR lower(public.b26_p2_ascii_strip(p_financial_status))
                  NOT IN ('pending', 'authorized', 'paid',
                          'partially_paid') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF abs(extract(epoch FROM (p_updated_at - p_created_at))) > 300 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        ELSE
            IF p_financial_status IS NOT NULL
               AND lower(public.b26_p2_ascii_strip(p_financial_status))
                   NOT IN ('pending', 'authorized', 'paid',
                           'partially_paid', 'voided', 'refunded',
                           'partially_refunded') THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_status_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL
               AND abs(extract(epoch FROM (p_updated_at - p_created_at)))
                   > 300 THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_not_creation_moment'
                    USING ERRCODE = '42501';
            END IF;
        END IF;
    END IF;
    RETURN;
END $$;
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_authenticate_ingress_atomic_v2(p_ingress uuid, p_provider text, p_event_ref text, p_body_sha256 text, p_sig_envelope_sha256 text, p_method text, p_version text, p_financial_status text, p_cancelled_at timestamptz, p_refunds_present boolean, p_created_at timestamptz, p_updated_at timestamptz)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $$
        DECLARE
            _tenant uuid;
            _idem text;
            _state text;
            _row_provider text;
            _prov text;
            _t_kind text;
            _t_value text;
            _t_cref text;
            _t_amount integer;
            _t_ccy text;
            _t_scale integer;
            _t_ts timestamptz;
            _t_ts_canon text;
            _sem_regime text;
            _demotion text;
            _family text;
            _family_source text;
            _fam_provider text;
            _c_provider text;
            _c_event text;
            _c_body text;
            _c_sig text;
            _c_method text;
            _c_version text;
            _witness text;
            _expected text;
            _prev_guc text;
            _dup_id uuid;
            _conflict_id uuid;
        BEGIN
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            -- The ingress credential alone may invoke the transition;
            -- the table owner (direct administration, any topology)
            -- and the cluster superuser may also invoke it; every
            -- other session role is refused at the function boundary.
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM public.b26_p2_table_owner(
                   'public.webhook_ingress_identities'::regclass)
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_atomic_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XXI floor: a downgraded schema (floor row/table absent or
            -- behind) cannot mint authority.
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision >= '202609300004';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                        USING ERRCODE = '42501';
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                    USING ERRCODE = '42501';
            END;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider,
                   i.b26_p2_provenance_status,
                   i.normalized_commerce_reference_kind,
                   i.normalized_commerce_reference_value,
                   i.provider_native_commerce_reference,
                   i.verified_amount_minor,
                   i.verified_amount_currency,
                   i.verified_amount_scale,
                   i.event_timestamp,
                   i.b26_p2_semantic_regime,
                   i.b26_p2_demotion_reason
              INTO _tenant, _idem, _state, _row_provider, _prov,
                   _t_kind, _t_value, _t_cref, _t_amount, _t_ccy, _t_scale,
                   _t_ts, _sem_regime, _demotion
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_atomic_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            IF _demotion IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_atomic_demoted_ingress_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_provider IS DISTINCT FROM _row_provider THEN
                RAISE EXCEPTION 'b26_p2_atomic_provider_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(char_length(p_body_sha256), 0) <> 64
               OR COALESCE(char_length(p_sig_envelope_sha256), 0) <> 64 THEN
                RAISE EXCEPTION 'b26_p2_atomic_sha_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_event_ref, '')) = ''
               OR public.b26_p2_ascii_strip(COALESCE(p_method, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX: sovereign event-family allowlist. The family's only
            -- authority is this transition over provider + the
            -- root-supplied explicit claim (transaction-local GUCs
            -- app.b26_p2_event_family / app.b26_p2_event_family_source,
            -- derived by the root from authenticated bytes or the
            -- provider-transported topic): relay route selection cannot
            -- confer it, and provider name alone cannot confer it. An
            -- absent claim is REFUSED -- never defaulted.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _family_source := current_setting(
                    'app.b26_p2_event_family_source', true);
            EXCEPTION WHEN OTHERS THEN
                _family_source := NULL;
            END;
            IF _family_source IS NULL
               OR NOT (
                   _family_source = 'body-signal:type'
                   OR _family_source = 'body-signal:event_type'
                   OR _family_source = 'body-signal:status'
                   OR _family_source
                      = 'transport-topic:x-shopify-topic'
                   OR _family_source
                      = 'transport-topic:x-wc-webhook-topic') THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_source_refused'
                    USING ERRCODE = '42501';
            END IF;
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(p_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('order.completed', 'order_completed') THEN
                    _family := 'order.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XXI (H-XXI-03): lifecycle admission at the seam.
            PERFORM public.b26_p2_enforce_lifecycle_admission(
                _fam_provider, _family, p_financial_status,
                p_cancelled_at, p_refunds_present,
                p_created_at, p_updated_at, true);
            -- Serialize authentications of identical bytes.
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_bytes:' || _tenant::text),
                hashtext(lower(p_body_sha256))
            );
            -- Serialize authentications of the same provider event and
            -- the same commerce identity, so concurrent conflicting
            -- first-authentications cannot both pass the checks below.
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_event:' || _tenant::text
                         || '|' || COALESCE(p_provider, '')),
                hashtext(COALESCE(p_event_ref, ''))
            );
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_commerce:' || _tenant::text
                         || '|' || COALESCE(p_provider, '')),
                hashtext(COALESCE(_t_kind, '')
                         || '|' || COALESCE(_t_value, ''))
            );
            SELECT i.id INTO _dup_id
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_provider_auth_consequence AS c
                ON c.webhook_ingress_identity_id = i.id
               AND c.tenant_id = i.tenant_id
             WHERE i.tenant_id = _tenant
               AND lower(c.body_sha256) IS NOT DISTINCT FROM lower(p_body_sha256)
               AND c.provider_event_reference IS NOT DISTINCT FROM p_event_ref
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_sovereign_duplicate_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.id INTO _conflict_id
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_provider_auth_consequence AS c
                ON c.webhook_ingress_identity_id = i.id
               AND c.tenant_id = i.tenant_id
             WHERE i.tenant_id = _tenant
               AND i.provider IS NOT DISTINCT FROM p_provider
               AND i.provider_native_event_reference IS NOT DISTINCT FROM p_event_ref
               AND lower(c.body_sha256) IS DISTINCT FROM lower(p_body_sha256)
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_event_identity_conflict_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.id INTO _conflict_id
              FROM public.webhook_ingress_identities AS i
             WHERE i.tenant_id = _tenant
               AND i.provider IS NOT DISTINCT FROM p_provider
               AND i.normalized_commerce_reference_kind IS NOT DISTINCT FROM _t_kind
               AND i.normalized_commerce_reference_value IS NOT DISTINCT FROM _t_value
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_commerce_identity_conflict_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT c.provider, c.provider_event_reference, c.body_sha256,
                       c.signature_envelope_sha256, c.auth_method, c.auth_version
                  INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
                  FROM public.b26_p2_provider_auth_consequence AS c
                 WHERE c.webhook_ingress_identity_id = p_ingress;
                IF NOT FOUND THEN
                    INSERT INTO public.b26_p2_provider_auth_consequence AS c (
                        webhook_ingress_identity_id, tenant_id, provider,
                        provider_event_reference, body_sha256,
                        signature_envelope_sha256, auth_method, auth_version,
                        b26_p2_event_family, b26_p2_family_source, recorded_by
                    )
                    VALUES (p_ingress, _tenant, p_provider, p_event_ref,
                            lower(p_body_sha256), lower(p_sig_envelope_sha256),
                            p_method, COALESCE(p_version, 'v1'), _family,
                            _family_source, session_user)
                    ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                    SELECT c.provider, c.provider_event_reference, c.body_sha256,
                           c.signature_envelope_sha256, c.auth_method, c.auth_version
                      INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
                      FROM public.b26_p2_provider_auth_consequence AS c
                     WHERE c.webhook_ingress_identity_id = p_ingress;
                ELSE
                    IF _c_provider IS DISTINCT FROM p_provider
                       OR _c_event IS DISTINCT FROM p_event_ref
                       OR lower(_c_body) IS DISTINCT FROM lower(p_body_sha256)
                       OR lower(_c_sig) IS DISTINCT FROM lower(p_sig_envelope_sha256)
                       OR _c_method IS DISTINCT FROM p_method
                       OR COALESCE(_c_version, 'v1') IS DISTINCT FROM COALESCE(p_version, 'v1') THEN
                        RAISE EXCEPTION 'b26_p2_atomic_cons_immutable_refused'
                            USING ERRCODE = '42501';
                    END IF;
                    UPDATE public.b26_p2_provider_auth_consequence AS c
                       SET b26_p2_event_family = _family,
                           b26_p2_family_source = _family_source
                     WHERE c.webhook_ingress_identity_id = p_ingress
                       AND c.b26_p2_event_family IS NULL;
                END IF;
                _t_ts_canon := to_char(_t_ts AT TIME ZONE 'UTC',
                                       'YYYY-MM-DD HH24:MI:SS.US');
                SELECT w.witness_hash INTO _witness
                  FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress;
                _expected := encode(digest(
                        _tenant::text || '|' || p_ingress::text || '|'
                        || _c_provider || '|' || _c_event || '|'
                        || lower(_c_body) || '|' || lower(_c_sig) || '|'
                        || _c_method || '|' || COALESCE(_c_version, 'v1') || '|'
                        || COALESCE(_t_kind, '') || '|'
                        || COALESCE(_t_value, '') || '|'
                        || COALESCE(_t_amount::text, '') || '|'
                        || COALESCE(_t_ccy, '') || '|'
                        || COALESCE(_t_scale::text, '') || '|'
                        || COALESCE(_t_ts_canon, ''),
                        'sha256'), 'hex');
                IF NOT FOUND THEN
                    INSERT INTO public.b26_p2_ingress_auth_witness AS w (
                        webhook_ingress_identity_id, tenant_id,
                        witness_hash, witnessed_by
                    )
                    VALUES (p_ingress, _tenant, _expected, session_user)
                    ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                    SELECT w.witness_hash INTO _witness
                      FROM public.b26_p2_ingress_auth_witness AS w
                     WHERE w.webhook_ingress_identity_id = p_ingress;
                ELSIF _witness IS DISTINCT FROM _expected THEN
                    UPDATE public.b26_p2_ingress_auth_witness AS w
                       SET witness_hash = _expected,
                           witnessed_by = session_user
                     WHERE w.webhook_ingress_identity_id = p_ingress;
                    _witness := _expected;
                END IF;
                INSERT INTO public.b26_p2_provenance_evidence AS e (
                    webhook_ingress_identity_id, tenant_id,
                    evidence_kind, evidence_ref, evidence_witness_hash
                )
                VALUES (p_ingress, _tenant, 'signed_provider_reingestion', _idem, _witness)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    evidence_witness_hash = EXCLUDED.evidence_witness_hash,
                    attested_at = now();
                INSERT INTO public.b26_p2_auth_root_evidence AS r (
                    tenant_id, webhook_ingress_identity_id, idempotency_key,
                    provider, provider_native_event_reference,
                    body_sha256, signature_envelope_sha256,
                    auth_method, auth_version
                )
                VALUES (_tenant, p_ingress, _idem,
                        _c_provider, _c_event,
                        lower(_c_body), lower(_c_sig),
                        _c_method, COALESCE(_c_version, 'v1'))
                ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                -- XIX: stamp the governed semantic regime and clear any
                -- historical demotion reason. No bearer mark is set or
                -- needed: this DEFINER transition executes as the owner,
                -- which is exactly the context the guard admits.
                -- (Reachable only for non-demoted rows: demoted rows
                -- were refused above, so this stamp can never bless
                -- stale money.)
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_attest_provenance_evidence_v2(p_ingress uuid, p_kind text, p_ref text, p_financial_status text, p_cancelled_at timestamptz, p_refunds_present boolean, p_created_at timestamptz, p_updated_at timestamptz)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $$
        DECLARE
            _tenant uuid;
            _idem text;
            _state text;
            _prov_status text;
            _demotion text;
            _t_kind text;
            _t_value text;
            _t_amount integer;
            _t_ccy text;
            _t_scale integer;
            _t_ts timestamptz;
            _t_ts_canon text;
            _row_provider text;
            _family text;
            _family_source text;
            _fam_provider text;
            _witness text;
            _c_provider text;
            _c_event text;
            _c_body text;
            _c_sig text;
            _c_method text;
            _c_version text;
            _expected text;
            _prev_guc text;
        BEGIN
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            -- Single ingress-boundary law (dynamic owner): only the
            -- ingress credential, the table owner, and the cluster
            -- superuser may attest.
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM public.b26_p2_table_owner(
                   'public.webhook_ingress_identities'::regclass)
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_kind IS DISTINCT FROM 'signed_provider_reingestion'
               AND p_kind IS DISTINCT FROM 'governed_attestation' THEN
                RAISE EXCEPTION 'b26_p2_evidence_kind_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_kind = 'governed_attestation'
               AND session_user = 'app_ingress' THEN
                RAISE EXCEPTION 'b26_p2_evidence_governed_admin_only'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision >= '202609300004';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                        USING ERRCODE = '42501';
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                    USING ERRCODE = '42501';
            END;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.b26_p2_provenance_status,
                   i.b26_p2_demotion_reason, i.provider,
                   i.normalized_commerce_reference_kind,
                   i.normalized_commerce_reference_value,
                   i.verified_amount_minor,
                   i.verified_amount_currency,
                   i.verified_amount_scale,
                   i.event_timestamp
              INTO _tenant, _idem, _state, _prov_status, _demotion, _row_provider,
                   _t_kind, _t_value, _t_amount, _t_ccy, _t_scale, _t_ts
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
            IF _demotion IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_evidence_demoted_ingress_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_ref, '')) = ''
               OR p_ref IS DISTINCT FROM _idem THEN
                RAISE EXCEPTION 'b26_p2_evidence_ref_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            SELECT w.witness_hash INTO _witness
              FROM public.b26_p2_ingress_auth_witness AS w
             WHERE w.webhook_ingress_identity_id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_evidence_witness_missing'
                    USING ERRCODE = '42501';
            END IF;
            SELECT c.provider, c.provider_event_reference, c.body_sha256,
                   c.signature_envelope_sha256, c.auth_method, c.auth_version
              INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
              FROM public.b26_p2_provider_auth_consequence AS c
             WHERE c.webhook_ingress_identity_id = p_ingress
               AND c.tenant_id = _tenant;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_evidence_no_auth_consequence'
                    USING ERRCODE = '42501';
            END IF;
            -- XXI: the re-attestation preimage is the atomic mint
            -- preimage bit-for-bit (commerce suffix included); a shorter
            -- recomputation could never match an atomically-minted
            -- witness and would deaden genuine re-ingestion. Rows
            -- bound by the legacy recorder path (which supplies no
            -- commerce context) carry the short preimage instead: both
            -- are accepted here because each stored witness dictates
            -- which one must match -- a short witness never matches a
            -- long-stored row and vice versa. Accepting the
            -- recorder-bound form does NOT promote it: the XIV
            -- promotion trigger still refuses the authenticated stamp
            -- without auth-root evidence (provenance_promotion_refused),
            -- which only the atomic creates.
            _t_ts_canon := to_char(_t_ts AT TIME ZONE 'UTC',
                                   'YYYY-MM-DD HH24:MI:SS.US');
            _expected := encode(digest(
                _tenant::text || '|' || p_ingress::text || '|'
                || _c_provider || '|' || _c_event || '|'
                || lower(_c_body) || '|' || lower(_c_sig) || '|'
                || _c_method || '|' || COALESCE(_c_version, 'v1') || '|'
                || COALESCE(_t_kind, '') || '|'
                || COALESCE(_t_value, '') || '|'
                || COALESCE(_t_amount::text, '') || '|'
                || COALESCE(_t_ccy, '') || '|'
                || COALESCE(_t_scale::text, '') || '|'
                || COALESCE(_t_ts_canon, ''),
                'sha256'), 'hex');
            IF _witness IS DISTINCT FROM _expected THEN
                _expected := encode(digest(
                    _tenant::text || '|' || p_ingress::text || '|'
                    || _c_provider || '|' || _c_event || '|'
                    || lower(_c_body) || '|' || lower(_c_sig) || '|'
                    || _c_method || '|' || COALESCE(_c_version, 'v1'),
                    'sha256'), 'hex');
            END IF;
            IF _witness IS DISTINCT FROM _expected THEN
                RAISE EXCEPTION 'b26_p2_evidence_witness_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX family: an explicit allowlisted claim is required and
            -- bound into the consequence row; absent claims are refused.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _family_source := current_setting(
                    'app.b26_p2_event_family_source', true);
            EXCEPTION WHEN OTHERS THEN
                _family_source := NULL;
            END;
            IF _family_source IS NULL
               OR NOT (
                   _family_source = 'body-signal:type'
                   OR _family_source = 'body-signal:event_type'
                   OR _family_source = 'body-signal:status'
                   OR _family_source
                      = 'transport-topic:x-shopify-topic'
                   OR _family_source
                      = 'transport-topic:x-wc-webhook-topic') THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_source_refused'
                    USING ERRCODE = '42501';
            END IF;
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(_row_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('order.completed', 'order_completed') THEN
                    _family := 'order.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XXI (H-XXI-03): contradiction-only lifecycle
            -- re-check at re-attestation (the original mint
            -- already established positive creation).
            PERFORM public.b26_p2_enforce_lifecycle_admission(
                _row_provider, _family, p_financial_status,
                p_cancelled_at, p_refunds_present,
                p_created_at, p_updated_at, false);
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                UPDATE public.b26_p2_provider_auth_consequence AS c
                   SET b26_p2_event_family = _family,
                       b26_p2_family_source = _family_source
                 WHERE c.webhook_ingress_identity_id = p_ingress
                   AND c.b26_p2_event_family IS NULL;
                INSERT INTO public.b26_p2_provenance_evidence AS e (
                    webhook_ingress_identity_id, tenant_id,
                    evidence_kind, evidence_ref, evidence_witness_hash
                )
                VALUES (p_ingress, _tenant, p_kind, p_ref, _witness)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    evidence_witness_hash = EXCLUDED.evidence_witness_hash,
                    attested_at = now();
                -- XIX: the stamp carries no bearer mark (see atomic).
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$
        """
    )
    # XXI-2b. Root-evidence gate admits the v2 minting frame only
    # (the retired v1 frame can no longer occur at this head).
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            _ctx text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Lawful path 1: migration-admin maintenance (seeders /
                -- provisioners running as migration_owner/postgres).
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    -- Lawful path 2: the single sovereign transition. The
                    -- trigger fires inside the atomic's transaction, so
                    -- PG_CONTEXT contains the atomic's exact frame. A
                    -- substring test would also match wrappers,
                    -- comments, or same-name overloads; the anchored
                    -- expression below admits only the exact 12-argument
                    -- v2 sovereign signature. The retired v1 signature
                    -- no longer exists at this head, so no stale binary
                    -- can present it. Any other SECURITY DEFINER
                    -- routine (an administrator-authored deputy, a future
                    -- helper, a confused deputy) carries its own frame
                    -- instead and is refused here with
                    -- b26_p2_auth_root_evidence_transition_refused.
                    GET DIAGNOSTICS _ctx = PG_CONTEXT;
                    IF _ctx IS NULL OR _ctx !~ 'PL/pgSQL function b26_p2_authenticate_ingress_atomic_v2\(uuid,text,text,text,text,text,text,text,timestamp with time zone,boolean,timestamp with time zone,timestamp with time zone\)' THEN
                        RAISE EXCEPTION 'b26_p2_auth_root_evidence_transition_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
                   OR OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                   OR OLD.provider IS DISTINCT FROM NEW.provider
                   OR OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference
                   OR OLD.body_sha256 IS DISTINCT FROM NEW.body_sha256
                   OR OLD.signature_envelope_sha256 IS DISTINCT FROM NEW.signature_envelope_sha256
                   OR OLD.auth_method IS DISTINCT FROM NEW.auth_method
                   OR COALESCE(OLD.auth_version, 'v1') IS DISTINCT FROM COALESCE(NEW.auth_version, 'v1') THEN
                    RAISE EXCEPTION 'b26_p2_auth_root_evidence_immutable_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_auth_root_evidence_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_authenticate_ingress_atomic(uuid,text,text,text,"
        "text,text,text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_attest_provenance_evidence(uuid,text,text)"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_lifecycle_admission("
        "text,text,text,timestamptz,boolean,timestamptz,timestamptz,boolean)"
        " FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic_v2("
        "uuid,text,text,text,text,text,text,"
        "text,timestamptz,boolean,timestamptz,timestamptz)"
        " FROM PUBLIC"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence_v2("
        "uuid,text,text,"
        "text,timestamptz,boolean,timestamptz,timestamptz)"
        " FROM PUBLIC"
    )
    for _role in ("app_ingress",):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_authenticate_ingress_atomic_v2(uuid,text,text,"
            "text,text,text,text,"
            "text,timestamptz,boolean,timestamptz,timestamptz) TO %s';"
            " END IF; END $$;" % (_role, _role)
        )
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_attest_provenance_evidence_v2(uuid,text,text,"
            "text,timestamptz,boolean,timestamptz,timestamptz) TO %s';"
            " END IF; END $$;" % (_role, _role)
        )

    # ------------------------------------------------------------------
    # XXI-3. Monotonic disqualification as data (Law D).
    # Backfill-tagged rows (family evidence assigned by migration, not
    # by provider) receive a persisted governed demotion policy. Every
    # predicate revision -- past, present, and restored -- refuses a
    # non-null demotion reason, so supported rollback cannot silently
    # promote this history without new sufficient evidence. Genuine
    # redelivery mints new rows and is unaffected. The propagation
    # trigger re-derives dependent verdicts in the same transaction.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE
            _t uuid;
            _n bigint;
            _total bigint := 0;
        BEGIN
            FOR _t IN SELECT t.id FROM public.tenants AS t
            LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                WITH upd AS (
                    UPDATE public.webhook_ingress_identities AS i
                       SET b26_p2_demotion_reason = '%s'
                      FROM public.b26_p2_provider_auth_consequence AS c
                     WHERE c.webhook_ingress_identity_id = i.id
                       AND i.tenant_id = _t
                       AND c.tenant_id = _t
                       AND i.b26_p2_demotion_reason IS NULL
                       AND c.b26_p2_family_source = 'xix-backfill:pre-xix-mint'
                     RETURNING i.id
                ) SELECT count(*) INTO _n FROM upd;
                _total := _total + COALESCE(_n, 0);
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
            RAISE NOTICE 'b26_p2_xxi_backfill_demotion_transitioned:%%', _total;
        END $$;
        """ % _XXI_DEMOTION_REASON
    )

    # ------------------------------------------------------------------
    # XXI-4. Ledger monotonic sequence + continuity observer (Law C).
    # BIGSERIAL assigns every future append an owner-independent
    # ordering; bulk-erase-without-restart leaves a structural gap,
    # delete+reinsert leaves a gap, in-place rewrite leaves hashes the
    # file anchor (XXI validator) and beat tip (below) contradict. The
    # observer reports gaps; it does not claim what no rows can show
    # (empty-ledger vacuity is declared and covered by the beat count
    # contradiction instead).
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
        " ADD COLUMN IF NOT EXISTS seq BIGSERIAL"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_verify_history_continuity()
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                HAVING count(*) > 0
                   AND max(l.seq) - min(l.seq) + 1 <> count(*)
            ) THEN
                violation := 'supersession_sequence_gap';
                RETURN NEXT;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.entry_hash IS NULL
            ) THEN
                violation := 'supersession_chain_unchained_row';
                RETURN NEXT;
            END IF;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_verify_history_continuity()"
        " FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # XXI-5. Beat observation table (Law C operational half).
    # Append-only observations with unforgeable authorship
    # (session_user at INSERT). The scheduled beat task records
    # ledger count/tip/violations; Trust issuance degrades unless a
    # fresh beat-authored clean observation agrees with live state.
    # All writes go through the DEFINER entry point below (no direct
    # INSERT grant exists for any role: observations cannot be forged
    # around the observer). API/worker readers get SELECT for the
    # builder check.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_history_integrity_observations (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            observed_at timestamptz NOT NULL DEFAULT now(),
            ledger_count bigint NOT NULL,
            ledger_tip text,
            observer_violations text NOT NULL DEFAULT '',
            author name NOT NULL DEFAULT session_user
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_history_integrity_observations"
        " FROM PUBLIC"
    )
    for _role in _XXI_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'REVOKE ALL ON TABLE"
            " public.b26_p2_history_integrity_observations FROM %s';"
            " END IF; END $$;" % (_role, _role)
        )
    # Writers: all observation writes go through the DEFINER entry
    # point above (authorship is the caller's session_user either
    # way). No direct INSERT grant exists for any role: the table is
    # append-only through the function. API/worker readers get SELECT
    # for the builder check.
    for _role in ("app_worker", "app_user"):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT SELECT ON TABLE"
            " public.b26_p2_history_integrity_observations TO %s';"
            " END IF; END $$;" % (_role, _role)
        )
    # Owner-context observation entry point (Law C operational half).
    # Callers (beat executor) hold no ledger table rights at all: the
    # DEFINER function reads the ledgers as owner, while the beat row's
    # author remains the CALLER's session_user (unforgeable), so a
    # maintenance principal cannot file worker-authored observations.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_observe_history_integrity()
        RETURNS TABLE (
            observation_id bigint,
            observed_at timestamptz,
            ledger_count bigint,
            ledger_tip text,
            violations text
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _viol text := '';
            _v text;
            _n bigint;
            _tip text;
            _id bigint;
            _ts timestamptz;
        BEGIN
            FOR _v IN SELECT violation
                        FROM public.b26_p2_verify_history_protection()
            LOOP
                _viol := _viol || _v || ';';
            END LOOP;
            FOR _v IN SELECT violation
                        FROM public.b26_p2_verify_history_continuity()
            LOOP
                _viol := _viol || _v || ';';
            END LOOP;
            SELECT count(*),
                   (SELECT l.entry_hash
                      FROM public.b26_p2_verdict_supersession_ledger AS l
                     ORDER BY l.seq DESC LIMIT 1)
              INTO _n, _tip
              FROM public.b26_p2_verdict_supersession_ledger;
            INSERT INTO public.b26_p2_history_integrity_observations
                (ledger_count, ledger_tip, observer_violations)
            VALUES (_n, _tip, _viol)
            RETURNING id,
                      public.b26_p2_history_integrity_observations.observed_at
               INTO _id, _ts;
            observation_id := _id;
            observed_at := _ts;
            ledger_count := _n;
            ledger_tip := _tip;
            violations := _viol;
            RETURN NEXT;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_observe_history_integrity()"
        " FROM PUBLIC"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_worker')"
        " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
        " public.b26_p2_observe_history_integrity() TO app_worker';"
        " END IF; END $$;"
    )
    # Owner-context continuity read for Trust issuance (Law C runtime
    # half). The builder must compare the beat-recorded global count/tip
    # against live state, but runtime roles hold no direct rights on the
    # ledger (XXI-1) and must never receive them; a direct SELECT would
    # fail with permission denied and break issuance. This DEFINER
    # function exposes exactly (count, tip) -- no row contents -- as the
    # table owner, so tenant scoping and privilege posture cannot skew
    # the comparison.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_read_history_continuity()
        RETURNS TABLE (n bigint, tip text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            SELECT count(*),
                   (SELECT l.entry_hash
                      FROM public.b26_p2_verdict_supersession_ledger AS l
                     ORDER BY l.seq DESC LIMIT 1)
              INTO n, tip
              FROM public.b26_p2_verdict_supersession_ledger;
            RETURN NEXT;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_read_history_continuity()"
        " FROM PUBLIC"
    )
    for _role in ("app_user", "app_worker"):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_read_history_continuity() TO %s';"
            " END IF; END $$;" % (_role, _role)
        )

    # ------------------------------------------------------------------
    # XXI-6. Operational floor at this revision (head revision; session
    # state dies with the migration session per the XX cascade-hygiene
    # law). The data-carrying re-derivation runs AFTER XXI-7 installs
    # the canonical predicate: re-deriving first would evaluate the
    # still-installed XX predicate (floor '202609300003') against the
    # advanced floor and stamp every verdict non-current.
    # ------------------------------------------------------------------
    op.execute(
        "DELETE FROM public.b26_p2_operational_floor WHERE id = 1"
    )
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        """ % _XXI_FLOOR
    )

    # ------------------------------------------------------------------
    # XXI-7. Canonical predicate at this revision (floor advance only;
    # the explicit-source condition is unchanged).
    # ------------------------------------------------------------------
    op.execute(
        """

        CREATE OR REPLACE FUNCTION public.b26_p2_ingress_has_current_authority(
            p_ingress uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _prov text;
            _regime text;
            _reason text;
        BEGIN
            SELECT i.b26_p2_provenance_status, i.b26_p2_semantic_regime,
                   i.b26_p2_demotion_reason
              INTO _prov, _regime, _reason
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RETURN FALSE;
            END IF;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
                RETURN FALSE;
            END IF;
            IF _regime IS DISTINCT FROM 'xvii-sovereign-v1' THEN
                RETURN FALSE;
            END IF;
            IF _reason IS NOT NULL THEN
                RETURN FALSE;
            END IF;
            -- XX: the bound regime must be live in the registry
            -- (retirement ends currentness transactionally).
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_semantic_regime_registry AS r
                 WHERE r.regime_id = _regime
                   AND r.status = 'active'
            ) THEN
                RETURN FALSE;
            END IF;
            -- XX: the operational floor must hold at this revision
            -- (downgrade ends current readability fail-closed).
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300004';
                IF NOT FOUND THEN
                    RETURN FALSE;
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RETURN FALSE;
            END;
            -- XX: every load-bearing justification must still exist.
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                 WHERE e.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            -- XX (H-XX-C): the bound family must rest on explicit
            -- authenticated evidence. Grandfathered pre-XIX backfill rows
            -- (xix-backfill:pre-xix-mint) keep their audit record but no
            -- longer satisfy currentness: the migration assigned that
            -- label, no provider evidence established the family.
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                 WHERE c.webhook_ingress_identity_id = p_ingress
                   AND c.b26_p2_event_family IN (
                       'payment_intent.succeeded', 'orders.create',
                       'payment.sale.completed', 'order.completed')
                   AND c.b26_p2_family_source IN (
                       'body-signal:type', 'body-signal:event_type',
                       'body-signal:status',
                       'transport-topic:x-shopify-topic',
                       'transport-topic:x-wc-webhook-topic')
            ) THEN
                RETURN FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                 WHERE r.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            RETURN TRUE;
        END $$;
        
        """
    )

    # ------------------------------------------------------------------
    # XXI-7b. Data-carrying re-derivation under the installed XXI
    # predicate. Runs here -- after the floor advance (XXI-6) AND the
    # predicate install (XXI-7) -- so every verdict is evaluated by the
    # law it will actually serve. Rows already coherent under XXI law
    # are untouched (the supersession trigger fires only on change), so
    # this step appends no spurious correction history.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE
            _t uuid;
        BEGIN
            FOR _t IN SELECT t.id FROM public.tenants AS t
            LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.b23_match_verdicts AS v
                   SET b26_p2_source_authority_state =
                       public.b26_p2_derive_verdict_authority(v.webhook_ingress_identity_id)
                  FROM public.webhook_ingress_identities AS i
                 WHERE v.webhook_ingress_identity_id = i.id
                   AND v.tenant_id = i.tenant_id
                   AND v.tenant_id = _t;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XXI-8. Publication-law v3 seed rows (family v3 + hierarchy v3).
    # Digests match the committed file chain exactly (computed at
    # authoring time with the validator's preimage law); UNIQUE on
    # (kind,id,version) keeps same-identity rewrites physically
    # impossible; owner-context INSERT is admitted by the history
    # immutability trigger's sovereign-writer rule.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO public.b26_p2_publication_history AS h (law_kind, law_id, law_version, law_digest, activation_revision, prev_entry_hash, entry_hash)
        VALUES ('event-family-law', 'b26-p2-event-family-law', 'v3', 'c0fd524cd3cc3d5f5509fdc5142ad32e5e30e06ddf5949918ed082572531624b', '202609300004', 'd1696cde33d46304e2a62794b2edd58b168e0af157050754634a9ef34f3c3097', '0b99e1e84d44eb1d68977c611a3d38035fce5c04af33933fb42bb278b1b81162')
        ON CONFLICT ON CONSTRAINT b26_p2_publication_identity_single_valued DO NOTHING;
        INSERT INTO public.b26_p2_publication_history AS h (law_kind, law_id, law_version, law_digest, activation_revision, prev_entry_hash, entry_hash)
        VALUES ('contract-hierarchy', 'b26-p2-contract-hierarchy', 'v3', '07562b472f69ea938bf5dcd4d0dfb43ed3c95e310e11a7f30250e0222b657aa7', '202609300004', '0b99e1e84d44eb1d68977c611a3d38035fce5c04af33933fb42bb278b1b81162', '0a4fa016ea46cf893c4c79f7cd6de909545aa6948ef064efbae38a639e9907b8')
        ON CONFLICT ON CONSTRAINT b26_p2_publication_identity_single_valued DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # XXI-9. Topology adjudicators track the retired ABI (Law A reach).
    # The XII/XIII/XIV topology_check functions assert the minting
    # topology by name (has_function_privilege on the atomic/attester
    # signatures). With v1 retired, the name lookup itself errors,
    # which callers (API boot in main.py, the XII/XIII/XIV gates)
    # would misread as "no strict topology" and silently skip the
    # strict evaluation. The adjudicators are therefore repointed at
    # the v2 ABI with identical logic: v2 present and executable by
    # the ingress principal, v2 unattainable by app_user. Grants and
    # ownership are preserved by CREATE OR REPLACE. The witness
    # recorder and consequence recorder references are unchanged
    # (those functions still exist at this head).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xii_topology_check()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xii_ingress_topology_absent'
                    USING ERRCODE = 'P0001';
            END IF;
            IF NOT has_function_privilege(
                'app_ingress',
                'public.b26_p2_record_ingress_auth_witness(uuid, text, text, text)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF has_function_privilege(
                'app_user',
                'public.b26_p2_attest_provenance_evidence_v2(uuid, text, text, text, timestamptz, boolean, timestamptz, timestamptz)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN 'xii_topology_strict';
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xiii_topology_check()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_absent'
                    USING ERRCODE = 'P0001';
            END IF;
            IF NOT has_function_privilege(
                'app_ingress',
                'public.b26_p2_record_ingress_auth_witness(uuid, text, text, text)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF NOT has_function_privilege(
                'app_ingress',
                'public.b26_p2_authenticate_ingress_atomic_v2(uuid, text, text, text, text, text, text, text, timestamptz, boolean, timestamptz, timestamptz)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF has_function_privilege(
                'app_user',
                'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF has_function_privilege(
                'app_user',
                'public.b26_p2_attest_provenance_evidence_v2(uuid, text, text, text, timestamptz, boolean, timestamptz, timestamptz)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN 'xiii_topology_strict';
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xiv_topology_check()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_absent'
                    USING ERRCODE = 'P0001';
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_tables
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_auth_root_evidence'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF NOT has_function_privilege(
                'app_ingress',
                'public.b26_p2_authenticate_ingress_atomic_v2(uuid, text, text, text, text, text, text, text, timestamptz, boolean, timestamptz, timestamptz)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF has_function_privilege(
                'app_user',
                'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            IF has_function_privilege(
                'app_user',
                'public.b26_p2_attest_provenance_evidence_v2(uuid, text, text, text, timestamptz, boolean, timestamptz, timestamptz)',
                'EXECUTE'
            ) THEN
                RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                    USING ERRCODE = 'P0001';
            END IF;
            RETURN 'xiv_topology_strict';
        END $$;
        """
    )
    # The XII provisioner is still executed live (the XII topology
    # gate's contract-B idempotence proof); its v1 GRANT/REVOKE lines
    # would error on the retired names, so it tracks the v2 ABI with
    # identical posture (GRANT v2 to app_ingress, REVOKE v2 from
    # app_user). The XIII/XIV provisioners have no live callers and
    # stay frozen.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xii_provision_ingress_topology()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _col text;
        BEGIN
            IF session_user NOT IN ('migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_xii_provision_refused'
                    USING ERRCODE = '42501';
            END IF;
            GRANT USAGE ON SCHEMA public TO app_ingress;
            GRANT SELECT, INSERT ON TABLE public.webhook_ingress_identities TO app_ingress;
            -- XXI: no table-level UPDATE (XXI-1 least privilege).
            -- Operational columns are re-granted from the live
            -- catalog with the authority columns excluded, exactly
            -- reproducing the migration posture idempotently: a
            -- table-level UPDATE here would re-open the authority
            -- columns the XX composition gate censuses.
            FOR _col IN
                SELECT column_name
                  FROM information_schema.columns
                 WHERE table_schema = 'public'
                   AND table_name = 'webhook_ingress_identities'
                   AND column_name NOT IN (
                       'b26_p2_provenance_status',
                       'b26_p2_semantic_regime',
                       'b26_p2_demotion_reason')
            LOOP
                EXECUTE format(
                    'GRANT UPDATE (%I) ON TABLE'
                    ' public.webhook_ingress_identities TO app_ingress',
                    _col);
            END LOOP;
            GRANT SELECT ON TABLE public.tenants TO app_ingress;
            GRANT SELECT ON TABLE public.attribution_events TO app_ingress;
            GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_provenance_evidence TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence_v2(uuid, text, text, text, timestamptz, boolean, timestamptz, timestamptz) TO app_ingress;
            -- XXI: the XX-era body revoked the consequence recorder
            -- from app_ingress here; XIII (root-of-trust closure)
            -- deliberately re-granted it (record path needs ingress
            -- authorship, canonical_authority (consequence)), so the
            -- revoke is dropped: re-asserting it would clobber live
            -- posture and break every ingress record path.
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence_v2(uuid, text, text, text, timestamptz, boolean, timestamptz, timestamptz) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM app_user;
            RETURN 'xii_topology_provisioned';
        END $$;
        """
    )


def downgrade() -> None:
    # Supported single-step rollback: XXI -> 202609300003. Restores
    # the v1 minting ABI (exact XX-era bodies: the retargeted XIX
    # texts), the 300003 predicate, and the 300003 floor; retains
    # every XXI conservation object (demotion-data rows keep their
    # policy reason -- monotonicity survives rollback by data, not by
    # predicate text; P3 delegation, chain/observer/continuity/beat
    # surface, revokes). No GRANT restores runtime authority writes.
    # The downgrade writes NO session tenant context (cascade-hygiene
    # law): floor restore uses DELETE + INSERT.
    #
    # Supported boundary ends here: 300003 -> 300002 executes the
    # frozen XX downgrade (pure-XIX predicate text). The persisted
    # demotion policy keeps disqualified rows non-current there too
    # (verified by reader census), but deeper rollback is declared
    # restore-from-backup territory: no serviceable binary serves it
    # (boot gates refuse; deployment builds the current tree only).
    # Drop order is load-bearing: the v2 minting functions depend on
    # the lifecycle helper (pg_depend), so the callers must go first.
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_authenticate_ingress_atomic_v2("
        "uuid,text,text,text,text,text,text,"
        "text,timestamptz,boolean,timestamptz,timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_attest_provenance_evidence_v2("
        "uuid,text,text,"
        "text,timestamptz,boolean,timestamptz,timestamptz)")
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_enforce_lifecycle_admission("
        "text,text,text,timestamptz,boolean,timestamptz,timestamptz,boolean)")
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_authenticate_ingress_atomic(p_ingress uuid, p_provider text, p_event_ref text, p_body_sha256 text, p_sig_envelope_sha256 text, p_method text, p_version text DEFAULT 'v1'::text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $$
        DECLARE
            _tenant uuid;
            _idem text;
            _state text;
            _row_provider text;
            _prov text;
            _t_kind text;
            _t_value text;
            _t_cref text;
            _t_amount integer;
            _t_ccy text;
            _t_scale integer;
            _t_ts timestamptz;
            _t_ts_canon text;
            _sem_regime text;
            _demotion text;
            _family text;
            _family_source text;
            _fam_provider text;
            _c_provider text;
            _c_event text;
            _c_body text;
            _c_sig text;
            _c_method text;
            _c_version text;
            _witness text;
            _expected text;
            _prev_guc text;
            _dup_id uuid;
            _conflict_id uuid;
        BEGIN
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            -- The ingress credential alone may invoke the transition;
            -- the table owner (direct administration, any topology)
            -- and the cluster superuser may also invoke it; every
            -- other session role is refused at the function boundary.
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM public.b26_p2_table_owner(
                   'public.webhook_ingress_identities'::regclass)
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_atomic_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX floor: a downgraded schema (floor row/table absent or
            -- behind) cannot mint authority.
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision >= '202609300002';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                        USING ERRCODE = '42501';
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                    USING ERRCODE = '42501';
            END;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider,
                   i.b26_p2_provenance_status,
                   i.normalized_commerce_reference_kind,
                   i.normalized_commerce_reference_value,
                   i.provider_native_commerce_reference,
                   i.verified_amount_minor,
                   i.verified_amount_currency,
                   i.verified_amount_scale,
                   i.event_timestamp,
                   i.b26_p2_semantic_regime,
                   i.b26_p2_demotion_reason
              INTO _tenant, _idem, _state, _row_provider, _prov,
                   _t_kind, _t_value, _t_cref, _t_amount, _t_ccy, _t_scale,
                   _t_ts, _sem_regime, _demotion
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress
             FOR UPDATE;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_atomic_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            IF _demotion IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_atomic_demoted_ingress_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_provider IS DISTINCT FROM _row_provider THEN
                RAISE EXCEPTION 'b26_p2_atomic_provider_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(char_length(p_body_sha256), 0) <> 64
               OR COALESCE(char_length(p_sig_envelope_sha256), 0) <> 64 THEN
                RAISE EXCEPTION 'b26_p2_atomic_sha_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_event_ref, '')) = ''
               OR public.b26_p2_ascii_strip(COALESCE(p_method, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX: sovereign event-family allowlist. The family's only
            -- authority is this transition over provider + the
            -- root-supplied explicit claim (transaction-local GUCs
            -- app.b26_p2_event_family / app.b26_p2_event_family_source,
            -- derived by the root from authenticated bytes or the
            -- provider-transported topic): relay route selection cannot
            -- confer it, and provider name alone cannot confer it. An
            -- absent claim is REFUSED -- never defaulted.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _family_source := current_setting(
                    'app.b26_p2_event_family_source', true);
            EXCEPTION WHEN OTHERS THEN
                _family_source := NULL;
            END;
            IF _family_source IS NULL
               OR NOT (
                   _family_source = 'body-signal:type'
                   OR _family_source = 'body-signal:event_type'
                   OR _family_source = 'body-signal:status'
                   OR _family_source
                      = 'transport-topic:x-shopify-topic'
                   OR _family_source
                      = 'transport-topic:x-wc-webhook-topic') THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_source_refused'
                    USING ERRCODE = '42501';
            END IF;
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(p_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('order.completed', 'order_completed') THEN
                    _family := 'order.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- Serialize authentications of identical bytes.
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_bytes:' || _tenant::text),
                hashtext(lower(p_body_sha256))
            );
            -- Serialize authentications of the same provider event and
            -- the same commerce identity, so concurrent conflicting
            -- first-authentications cannot both pass the checks below.
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_event:' || _tenant::text
                         || '|' || COALESCE(p_provider, '')),
                hashtext(COALESCE(p_event_ref, ''))
            );
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_commerce:' || _tenant::text
                         || '|' || COALESCE(p_provider, '')),
                hashtext(COALESCE(_t_kind, '')
                         || '|' || COALESCE(_t_value, ''))
            );
            SELECT i.id INTO _dup_id
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_provider_auth_consequence AS c
                ON c.webhook_ingress_identity_id = i.id
               AND c.tenant_id = i.tenant_id
             WHERE i.tenant_id = _tenant
               AND lower(c.body_sha256) IS NOT DISTINCT FROM lower(p_body_sha256)
               AND c.provider_event_reference IS NOT DISTINCT FROM p_event_ref
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_sovereign_duplicate_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.id INTO _conflict_id
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_provider_auth_consequence AS c
                ON c.webhook_ingress_identity_id = i.id
               AND c.tenant_id = i.tenant_id
             WHERE i.tenant_id = _tenant
               AND i.provider IS NOT DISTINCT FROM p_provider
               AND i.provider_native_event_reference IS NOT DISTINCT FROM p_event_ref
               AND lower(c.body_sha256) IS DISTINCT FROM lower(p_body_sha256)
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_event_identity_conflict_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.id INTO _conflict_id
              FROM public.webhook_ingress_identities AS i
             WHERE i.tenant_id = _tenant
               AND i.provider IS NOT DISTINCT FROM p_provider
               AND i.normalized_commerce_reference_kind IS NOT DISTINCT FROM _t_kind
               AND i.normalized_commerce_reference_value IS NOT DISTINCT FROM _t_value
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             LIMIT 1;
            IF FOUND THEN
                RAISE EXCEPTION 'b26_p2_atomic_commerce_identity_conflict_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT c.provider, c.provider_event_reference, c.body_sha256,
                       c.signature_envelope_sha256, c.auth_method, c.auth_version
                  INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
                  FROM public.b26_p2_provider_auth_consequence AS c
                 WHERE c.webhook_ingress_identity_id = p_ingress;
                IF NOT FOUND THEN
                    INSERT INTO public.b26_p2_provider_auth_consequence AS c (
                        webhook_ingress_identity_id, tenant_id, provider,
                        provider_event_reference, body_sha256,
                        signature_envelope_sha256, auth_method, auth_version,
                        b26_p2_event_family, b26_p2_family_source, recorded_by
                    )
                    VALUES (p_ingress, _tenant, p_provider, p_event_ref,
                            lower(p_body_sha256), lower(p_sig_envelope_sha256),
                            p_method, COALESCE(p_version, 'v1'), _family,
                            _family_source, session_user)
                    ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                    SELECT c.provider, c.provider_event_reference, c.body_sha256,
                           c.signature_envelope_sha256, c.auth_method, c.auth_version
                      INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
                      FROM public.b26_p2_provider_auth_consequence AS c
                     WHERE c.webhook_ingress_identity_id = p_ingress;
                ELSE
                    IF _c_provider IS DISTINCT FROM p_provider
                       OR _c_event IS DISTINCT FROM p_event_ref
                       OR lower(_c_body) IS DISTINCT FROM lower(p_body_sha256)
                       OR lower(_c_sig) IS DISTINCT FROM lower(p_sig_envelope_sha256)
                       OR _c_method IS DISTINCT FROM p_method
                       OR COALESCE(_c_version, 'v1') IS DISTINCT FROM COALESCE(p_version, 'v1') THEN
                        RAISE EXCEPTION 'b26_p2_atomic_cons_immutable_refused'
                            USING ERRCODE = '42501';
                    END IF;
                    UPDATE public.b26_p2_provider_auth_consequence AS c
                       SET b26_p2_event_family = _family,
                           b26_p2_family_source = _family_source
                     WHERE c.webhook_ingress_identity_id = p_ingress
                       AND c.b26_p2_event_family IS NULL;
                END IF;
                _t_ts_canon := to_char(_t_ts AT TIME ZONE 'UTC',
                                       'YYYY-MM-DD HH24:MI:SS.US');
                SELECT w.witness_hash INTO _witness
                  FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress;
                _expected := encode(digest(
                        _tenant::text || '|' || p_ingress::text || '|'
                        || _c_provider || '|' || _c_event || '|'
                        || lower(_c_body) || '|' || lower(_c_sig) || '|'
                        || _c_method || '|' || COALESCE(_c_version, 'v1') || '|'
                        || COALESCE(_t_kind, '') || '|'
                        || COALESCE(_t_value, '') || '|'
                        || COALESCE(_t_amount::text, '') || '|'
                        || COALESCE(_t_ccy, '') || '|'
                        || COALESCE(_t_scale::text, '') || '|'
                        || COALESCE(_t_ts_canon, ''),
                        'sha256'), 'hex');
                IF NOT FOUND THEN
                    INSERT INTO public.b26_p2_ingress_auth_witness AS w (
                        webhook_ingress_identity_id, tenant_id,
                        witness_hash, witnessed_by
                    )
                    VALUES (p_ingress, _tenant, _expected, session_user)
                    ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                    SELECT w.witness_hash INTO _witness
                      FROM public.b26_p2_ingress_auth_witness AS w
                     WHERE w.webhook_ingress_identity_id = p_ingress;
                ELSIF _witness IS DISTINCT FROM _expected THEN
                    UPDATE public.b26_p2_ingress_auth_witness AS w
                       SET witness_hash = _expected,
                           witnessed_by = session_user
                     WHERE w.webhook_ingress_identity_id = p_ingress;
                    _witness := _expected;
                END IF;
                INSERT INTO public.b26_p2_provenance_evidence AS e (
                    webhook_ingress_identity_id, tenant_id,
                    evidence_kind, evidence_ref, evidence_witness_hash
                )
                VALUES (p_ingress, _tenant, 'signed_provider_reingestion', _idem, _witness)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    evidence_witness_hash = EXCLUDED.evidence_witness_hash,
                    attested_at = now();
                INSERT INTO public.b26_p2_auth_root_evidence AS r (
                    tenant_id, webhook_ingress_identity_id, idempotency_key,
                    provider, provider_native_event_reference,
                    body_sha256, signature_envelope_sha256,
                    auth_method, auth_version
                )
                VALUES (_tenant, p_ingress, _idem,
                        _c_provider, _c_event,
                        lower(_c_body), lower(_c_sig),
                        _c_method, COALESCE(_c_version, 'v1'))
                ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                -- XIX: stamp the governed semantic regime and clear any
                -- historical demotion reason. No bearer mark is set or
                -- needed: this DEFINER transition executes as the owner,
                -- which is exactly the context the guard admits.
                -- (Reachable only for non-demoted rows: demoted rows
                -- were refused above, so this stamp can never bless
                -- stale money.)
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$
        """
    )
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_attest_provenance_evidence(p_ingress uuid, p_kind text, p_ref text)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $$
        DECLARE
            _tenant uuid;
            _idem text;
            _state text;
            _prov_status text;
            _demotion text;
            _row_provider text;
            _family text;
            _family_source text;
            _fam_provider text;
            _witness text;
            _c_provider text;
            _c_event text;
            _c_body text;
            _c_sig text;
            _c_method text;
            _c_version text;
            _expected text;
            _prev_guc text;
        BEGIN
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            -- Single ingress-boundary law (dynamic owner): only the
            -- ingress credential, the table owner, and the cluster
            -- superuser may attest.
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM public.b26_p2_table_owner(
                   'public.webhook_ingress_identities'::regclass)
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_kind IS DISTINCT FROM 'signed_provider_reingestion'
               AND p_kind IS DISTINCT FROM 'governed_attestation' THEN
                RAISE EXCEPTION 'b26_p2_evidence_kind_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF p_kind = 'governed_attestation'
               AND session_user = 'app_ingress' THEN
                RAISE EXCEPTION 'b26_p2_evidence_governed_admin_only'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision >= '202609300002';
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                        USING ERRCODE = '42501';
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RAISE EXCEPTION 'b26_p2_downgrade_serving_refused'
                    USING ERRCODE = '42501';
            END;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.b26_p2_provenance_status,
                   i.b26_p2_demotion_reason, i.provider
              INTO _tenant, _idem, _state, _prov_status, _demotion, _row_provider
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
            IF _demotion IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_evidence_demoted_ingress_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_ref, '')) = ''
               OR p_ref IS DISTINCT FROM _idem THEN
                RAISE EXCEPTION 'b26_p2_evidence_ref_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            SELECT w.witness_hash INTO _witness
              FROM public.b26_p2_ingress_auth_witness AS w
             WHERE w.webhook_ingress_identity_id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_evidence_witness_missing'
                    USING ERRCODE = '42501';
            END IF;
            SELECT c.provider, c.provider_event_reference, c.body_sha256,
                   c.signature_envelope_sha256, c.auth_method, c.auth_version
              INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
              FROM public.b26_p2_provider_auth_consequence AS c
             WHERE c.webhook_ingress_identity_id = p_ingress
               AND c.tenant_id = _tenant;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_evidence_no_auth_consequence'
                    USING ERRCODE = '42501';
            END IF;
            _expected := encode(digest(
                _tenant::text || '|' || p_ingress::text || '|'
                || _c_provider || '|' || _c_event || '|'
                || lower(_c_body) || '|' || lower(_c_sig) || '|'
                || _c_method || '|' || COALESCE(_c_version, 'v1'),
                'sha256'), 'hex');
            IF _witness IS DISTINCT FROM _expected THEN
                RAISE EXCEPTION 'b26_p2_evidence_witness_not_bound'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX family: an explicit allowlisted claim is required and
            -- bound into the consequence row; absent claims are refused.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _family_source := current_setting(
                    'app.b26_p2_event_family_source', true);
            EXCEPTION WHEN OTHERS THEN
                _family_source := NULL;
            END;
            IF _family_source IS NULL
               OR NOT (
                   _family_source = 'body-signal:type'
                   OR _family_source = 'body-signal:event_type'
                   OR _family_source = 'body-signal:status'
                   OR _family_source
                      = 'transport-topic:x-shopify-topic'
                   OR _family_source
                      = 'transport-topic:x-wc-webhook-topic') THEN
                RAISE EXCEPTION 'b26_p2_atomic_family_source_refused'
                    USING ERRCODE = '42501';
            END IF;
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(_row_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF lower(public.b26_p2_ascii_strip(_family))
                      IN ('order.completed', 'order_completed') THEN
                    _family := 'order.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                    USING ERRCODE = '42501';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                UPDATE public.b26_p2_provider_auth_consequence AS c
                   SET b26_p2_event_family = _family,
                       b26_p2_family_source = _family_source
                 WHERE c.webhook_ingress_identity_id = p_ingress
                   AND c.b26_p2_event_family IS NULL;
                INSERT INTO public.b26_p2_provenance_evidence AS e (
                    webhook_ingress_identity_id, tenant_id,
                    evidence_kind, evidence_ref, evidence_witness_hash
                )
                VALUES (p_ingress, _tenant, p_kind, p_ref, _witness)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    evidence_witness_hash = EXCLUDED.evidence_witness_hash,
                    attested_at = now();
                -- XIX: the stamp carries no bearer mark (see atomic).
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$
        """
    )
    # XXI downgrade: restore the v1-frame root-evidence gate alongside the v1 minting ABI.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability() RETURNS trigger
    LANGUAGE plpgsql
    SET search_path TO 'pg_catalog', 'public'
    AS $$
        DECLARE
            _ctx text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Lawful path 1: migration-admin maintenance (seeders /
                -- provisioners running as migration_owner/postgres).
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    -- Lawful path 2: the single sovereign transition. The
                    -- trigger fires inside the atomic's transaction, so
                    -- PG_CONTEXT contains the atomic's exact frame. A
                    -- substring test would also match wrappers,
                    -- comments, or same-name overloads; the anchored
                    -- expression below admits only the exact 7-argument
                    -- sovereign signature. Any other SECURITY DEFINER
                    -- routine (an administrator-authored deputy, a future
                    -- helper, a confused deputy) carries its own frame
                    -- instead and is refused here with
                    -- b26_p2_auth_root_evidence_transition_refused.
                    GET DIAGNOSTICS _ctx = PG_CONTEXT;
                    IF _ctx IS NULL OR _ctx !~ 'PL/pgSQL function b26_p2_authenticate_ingress_atomic\(uuid,text,text,text,text,text,text\)' THEN
                        RAISE EXCEPTION 'b26_p2_auth_root_evidence_transition_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
                   OR OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                   OR OLD.provider IS DISTINCT FROM NEW.provider
                   OR OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference
                   OR OLD.body_sha256 IS DISTINCT FROM NEW.body_sha256
                   OR OLD.signature_envelope_sha256 IS DISTINCT FROM NEW.signature_envelope_sha256
                   OR OLD.auth_method IS DISTINCT FROM NEW.auth_method
                   OR COALESCE(OLD.auth_version, 'v1') IS DISTINCT FROM COALESCE(NEW.auth_version, 'v1') THEN
                    RAISE EXCEPTION 'b26_p2_auth_root_evidence_immutable_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_auth_root_evidence_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic("
        "uuid,text,text,text,text,text,text) FROM PUBLIC"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress')"
        " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
        " public.b26_p2_authenticate_ingress_atomic(uuid,text,text,text,"
        "text,text,text) TO app_ingress';"
        " END IF; END $$;"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence("
        "uuid,text,text) FROM PUBLIC"
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress')"
        " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
        " public.b26_p2_attest_provenance_evidence(uuid,text,text)"
        " TO app_ingress';"
        " END IF; END $$;"
    )
    op.execute(
        """

        CREATE OR REPLACE FUNCTION public.b26_p2_ingress_has_current_authority(
            p_ingress uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _prov text;
            _regime text;
            _reason text;
        BEGIN
            SELECT i.b26_p2_provenance_status, i.b26_p2_semantic_regime,
                   i.b26_p2_demotion_reason
              INTO _prov, _regime, _reason
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RETURN FALSE;
            END IF;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
                RETURN FALSE;
            END IF;
            IF _regime IS DISTINCT FROM 'xvii-sovereign-v1' THEN
                RETURN FALSE;
            END IF;
            IF _reason IS NOT NULL THEN
                RETURN FALSE;
            END IF;
            -- XX: the bound regime must be live in the registry
            -- (retirement ends currentness transactionally).
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_semantic_regime_registry AS r
                 WHERE r.regime_id = _regime
                   AND r.status = 'active'
            ) THEN
                RETURN FALSE;
            END IF;
            -- XX: the operational floor must hold at this revision
            -- (downgrade ends current readability fail-closed).
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300003';
                IF NOT FOUND THEN
                    RETURN FALSE;
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RETURN FALSE;
            END;
            -- XX: every load-bearing justification must still exist.
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                 WHERE e.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            -- XX (H-XX-C): the bound family must rest on explicit
            -- authenticated evidence. Grandfathered pre-XIX backfill rows
            -- (xix-backfill:pre-xix-mint) keep their audit record but no
            -- longer satisfy currentness: the migration assigned that
            -- label, no provider evidence established the family.
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                 WHERE c.webhook_ingress_identity_id = p_ingress
                   AND c.b26_p2_event_family IN (
                       'payment_intent.succeeded', 'orders.create',
                       'payment.sale.completed', 'order.completed')
                   AND c.b26_p2_family_source IN (
                       'body-signal:type', 'body-signal:event_type',
                       'body-signal:status',
                       'transport-topic:x-shopify-topic',
                       'transport-topic:x-wc-webhook-topic')
            ) THEN
                RETURN FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                 WHERE r.webhook_ingress_identity_id = p_ingress
            ) THEN
                RETURN FALSE;
            END IF;
            RETURN TRUE;
        END $$;
        
        """
    )
    op.execute(
        "DELETE FROM public.b26_p2_operational_floor WHERE id = 1"
    )
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        """ % _XXI_PREDECESSOR_FLOOR
    )
    for _role in _XXI_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'REVOKE UPDATE"
            " (b26_p2_provenance_status, b26_p2_semantic_regime,"
            " b26_p2_demotion_reason)"
            " ON public.webhook_ingress_identities FROM %s'; END IF; END $$;"
            % (_role, _role)
        )
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'REVOKE UPDATE (b26_p2_source_authority_state)"
            " ON public.b23_match_verdicts FROM %s'; END IF; END $$;"
            % (_role, _role)
        )

    # The XXI-9 topology adjudicators tracked the v2 ABI; the
    # downgrade restores v1, so the adjudicators track back to the
    # exact XX-era bodies (byte-identical to the XII/XIII/XIV
    # migrations). Without this, has_function_privilege on the
    # restored-absent v2 names would error and every topology
    # consumer would silently skip strict evaluation.
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.b26_p2_xii_topology_check()
            RETURNS text
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path TO 'pg_catalog', 'public'
            AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xii_ingress_topology_absent'
                        USING ERRCODE = 'P0001';
                END IF;
                IF NOT has_function_privilege(
                    'app_ingress',
                    'public.b26_p2_record_ingress_auth_witness(uuid, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF has_function_privilege(
                    'app_user',
                    'public.b26_p2_attest_provenance_evidence(uuid, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                RETURN 'xii_topology_strict';
            END $$;
        """
    )
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.b26_p2_xiii_topology_check()
            RETURNS text
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path TO 'pg_catalog', 'public'
            AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_absent'
                        USING ERRCODE = 'P0001';
                END IF;
                IF NOT has_function_privilege(
                    'app_ingress',
                    'public.b26_p2_record_ingress_auth_witness(uuid, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF NOT has_function_privilege(
                    'app_ingress',
                    'public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF has_function_privilege(
                    'app_user',
                    'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF has_function_privilege(
                    'app_user',
                    'public.b26_p2_attest_provenance_evidence(uuid, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiii_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                RETURN 'xiii_topology_strict';
            END $$;
        """
    )
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.b26_p2_xiv_topology_check()
            RETURNS text
            LANGUAGE plpgsql
            SECURITY DEFINER
            SET search_path TO 'pg_catalog', 'public'
            AS $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_absent'
                        USING ERRCODE = 'P0001';
                END IF;
                IF NOT EXISTS (
                    SELECT 1 FROM pg_tables
                     WHERE schemaname = 'public'
                       AND tablename = 'b26_p2_auth_root_evidence'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF NOT has_function_privilege(
                    'app_ingress',
                    'public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF has_function_privilege(
                    'app_user',
                    'public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                IF has_function_privilege(
                    'app_user',
                    'public.b26_p2_attest_provenance_evidence(uuid, text, text)',
                    'EXECUTE'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_xiv_ingress_topology_dead'
                        USING ERRCODE = 'P0001';
                END IF;
                RETURN 'xiv_topology_strict';
            END $$;
        """
    )

    # XXI-9 tracked the live XII provisioner to the v2 ABI; the
    # downgrade restores v1, so the provisioner tracks back to its
    # exact XX-era body (byte-identical to the XII migration).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xii_provision_ingress_topology()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF session_user NOT IN ('migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_xii_provision_refused'
                    USING ERRCODE = '42501';
            END IF;
            GRANT USAGE ON SCHEMA public TO app_ingress;
            GRANT SELECT, INSERT, UPDATE ON TABLE public.webhook_ingress_identities TO app_ingress;
            GRANT SELECT ON TABLE public.tenants TO app_ingress;
            GRANT SELECT ON TABLE public.attribution_events TO app_ingress;
            GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_provenance_evidence TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_ingress;
            REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM app_ingress;
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM app_user;
            RETURN 'xii_topology_provisioned';
        END $$;
        """
    )
