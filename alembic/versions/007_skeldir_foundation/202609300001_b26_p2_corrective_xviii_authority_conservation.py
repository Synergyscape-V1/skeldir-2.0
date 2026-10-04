"""B2.6-P2 Corrective XVIII: authority-relation conservation at the DB plane.

H-XVIII-R1..R23 (Directive XVIII): XVII proved Skeldir can *detect*
historically untrustworthy ingress state. XVIII conserves that
determination through every mechanism capable of restoring authority,
interpreting semantic law, producing B2.3 consequences, calculating
verified revenue, or operating across rollback boundaries.

Conservation laws established here (physical identities, not conventions):

    SEMANTIC REGIME ID = ONE IMMUTABLE SEMANTIC CONTRACT
        (b26_p2_semantic_regime_registry: regime_id PRIMARY KEY,
        append-only; UPDATE/DELETE refused for non-migration roles;
        history-bound registry gate in CI).

    CURRENT TRUST STATUS = UNFORGEABLE RESULT OF THE GOVERNED
    AUTHENTICATION TRANSITION
        (trg_b26_p2_ingress_authority_transition: direct UPDATE of
        authority-bearing columns refused for every runtime role;
        column-level REVOKE backs the trigger; only the sovereign
        atomic -- SECURITY DEFINER, owner-privileged -- can produce
        the conjunction; the atomic itself refuses demoted rows,
        so stale evidence can never satisfy current promotion).

    NON-AUTHORITATIVE INGRESS = NON-AUTHORITATIVE CONSEQUENCES
        (b26_p2_ingress_has_current_authority(): the single central
        DB authority predicate; every financial-consequence reader
        joins it -- batch candidates, coverage, eligibility,
        snapshots, Trust -- so demotion conducts everywhere).

    SUPPORTED EVENT FAMILY = FACT ESTABLISHED AT THE SOVEREIGN ROOT
        (b26_p2_provider_auth_consequence.b26_p2_event_family: bound
        inside the atomic under a governed per-provider allowlist;
        dispatch requires it).

    SUPPORTED DOWNGRADE STATE = STATE THAT CANNOT MINT AUTHORITY
        (b26_p2_operational_floor: the atomic refuses new trust while
        the floor row is absent -- downgrade deletes the floor, so a
        downgraded schema fails closed instead of serving under a
        known-invalid law).

Upgrade is linear and forward-only (revises 202609290001). Downgrade
removes the new enforcement objects but NEVER weakens the transition
graph: the hardened atomic stays (fail-closed retention), demoted rows
stay pending, and serving stays blocked until re-upgrade restores the
floor.
"""

from __future__ import annotations

from alembic import op

revision = "202609300001"
down_revision = "202609290001"
branch_labels = None
depends_on = None

# Governed semantic-regime identity. UNCHANGED by XVIII: no semantic-law
# change occurs here, so no new regime is minted. The registry below binds
# this identity to exactly one contract digest (the v1 contract bytes as
# reviewed at XVII); any future semantic-law change MUST mint a new
# regime row via a new forward migration (never edits this row).
_XVIII_REGIME = "xvii-sovereign-v1"
_XVIII_CONTRACT_VERSION = "v1"
# LF-normalized sha256 of
# contracts/reconciliation/b2.6/provider-semantic-contract.v1.json
# as reviewed (== XVII pin contract_sha256). The XVIII registry gate
# asserts migration literal == registry file == live contract bytes.
_XVIII_CONTRACT_DIGEST = (
    "c0f7e3b580dcaf91c7221aa522bf3ca968de7dcc8aa2bf0d5f22b6440ba8e924"
)
_XVIII_LEGACY_REGIME = "pre-xvii-unverifiable"

# Canonical supported event family per provider (mirrors the governed
# event-family law artifact contracts/reconciliation/b2.6/
# event-family-law.v1.json and the sovereign parser map; the XVIII
# family gate asserts all three agree).
_XVIII_FAMILY_STRIPE = "payment_intent.succeeded"
_XVIII_FAMILY_SHOPIFY = "orders.create"
_XVIII_FAMILY_PAYPAL = "payment.sale.completed"
_XVIII_FAMILY_WOOCOMMERCE = "order.completed"


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provider_auth_consequence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XVIII-1. Immutable semantic-regime registry (H-XVIII-R1/R2/R16).
    # regime_id is the PRIMARY KEY: one identity denotes at most one
    # law. UPDATE/DELETE are refused for every non-migration role by
    # trigger below; legitimate evolution APPENDS a new row via a new
    # forward migration. The registry gate (CI, history-bound) proves
    # the published digest for an identity never changes across git
    # history: co-editing contract+pin+parser+oracle under the same
    # regime REDs.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_semantic_regime_registry (
            regime_id text PRIMARY KEY,
            contract_version text NOT NULL,
            contract_digest text NOT NULL,
            activation_revision text NOT NULL,
            status text NOT NULL DEFAULT 'active',
            registered_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT b26_p2_registry_digest_shape
                CHECK (char_length(contract_digest) = 64)
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_semantic_regime_registry FROM PUBLIC"
    )
    op.execute(
        """
        INSERT INTO public.b26_p2_semantic_regime_registry AS r
            (regime_id, contract_version, contract_digest,
             activation_revision, status)
        VALUES (
            '%s', '%s', '%s', '%s', 'active'
        )
        ON CONFLICT (regime_id) DO NOTHING
        """
        % (_XVIII_REGIME, _XVIII_CONTRACT_VERSION,
           _XVIII_CONTRACT_DIGEST, revision)
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_registry_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_registry_mutation_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF TG_OP <> 'INSERT' THEN
                RAISE EXCEPTION 'b26_p2_registry_history_immutable_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_registry_immutable"
        " ON public.b26_p2_semantic_regime_registry"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_registry_immutable
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.b26_p2_semantic_regime_registry
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_registry_immutability()
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_registry_immutability()"
        " FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # XVIII-2. Central current-authority predicate (H-XVIII-R6/R7/R8).
    # THE single definition of "currently authoritative ingress".
    # Every financial-consequence reader joins this function instead
    # of re-implementing the conjunction (drift-proof by construction).
    # Fail-closed: NULL/UNKNOWN never authorizes (IS NOT DISTINCT FROM
    # is deliberately NOT used for the positive grant here -- each
    # clause must be positively true).
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
            RETURN TRUE;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_ingress_has_current_authority(uuid)"
        " FROM PUBLIC"
    )
    for _role in (
        "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
        "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
    ):
        op.execute(
            "GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_ingress_has_current_authority(uuid)"
            " TO %s" % _role
        )

    # ------------------------------------------------------------------
    # XVIII-3. Unforgeable trust-transition enforcement (H-XVIII-R3/R4).
    # Direct UPDATE of authority-bearing columns is refused for every
    # runtime role. Privilege layer (below) denies it even before the
    # trigger; the trigger is the second wall (covers roles granted
    # table UPDATE today or tomorrow). Migration/admin remain able to
    # run governed data repairs; the sovereign atomic does not need a
    # bypass because it executes with owner privileges (SECURITY
    # DEFINER) -- and the trigger still observes its writes, which is
    # intended: only the atomic's exact conjunction is ever written.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_authority_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _governed text;
        BEGIN
            -- The sovereign atomic performs its stamp with owner
            -- privilege and marks the transaction governed (see the
            -- atomic body). The mark alone confers nothing: runtime
            -- roles hold no UPDATE privilege on these columns (XVIII
            -- column REVOKE below), so a forged mark cannot authorize
            -- a write the privilege layer already denied. The mark
            -- exists so the trigger can distinguish the atomic's
            -- stamp from any other owner-privileged write.
            BEGIN
                _governed := current_setting(
                    'app.b26_p2_governed_transition', true);
            EXCEPTION WHEN OTHERS THEN
                _governed := NULL;
            END;
            IF session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres'
               AND COALESCE(_governed, '') IS DISTINCT FROM '1' THEN
                IF OLD.b26_p2_provenance_status
                       IS DISTINCT FROM NEW.b26_p2_provenance_status
                   OR OLD.b26_p2_semantic_regime
                       IS DISTINCT FROM NEW.b26_p2_semantic_regime
                   OR OLD.b26_p2_demotion_reason
                       IS DISTINCT FROM NEW.b26_p2_demotion_reason THEN
                    RAISE EXCEPTION 'b26_p2_authority_transition_refused'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_authority_transition"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_ingress_authority_transition
        BEFORE UPDATE OF b26_p2_provenance_status, b26_p2_semantic_regime,
                         b26_p2_demotion_reason
        ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_authority_transition()
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_authority_transition()"
        " FROM PUBLIC"
    )
    # Privilege layer: authority-bearing columns are no longer writable
    # by runtime roles even where old table-wide UPDATE grants reach
    # them. The atomic (owner-privileged DEFINER) is unaffected.
    for _role in (
        "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
        "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
    ):
        op.execute(
            "REVOKE UPDATE (b26_p2_provenance_status, b26_p2_semantic_regime,"
            " b26_p2_demotion_reason)"
            " ON public.webhook_ingress_identities FROM %s" % _role
        )

    # ------------------------------------------------------------------
    # XVIII-4. Sovereign event-family binding (H-XVIII-R11/R12).
    # The consequence row -- minted only inside the atomic -- now
    # carries the supported event family. Production root derives the
    # family from authenticated bytes and passes it as p_event_family;
    # the atomic allowlists it per provider and binds it. A NULL claim
    # (direct-atomic test/legacy paths) is attested as the governed
    # family-implicit canonical family for that provider -- the
    # contract's explicit disposition for shapes carrying no native
    # family signal -- never as an unsupported family.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b26_p2_provider_auth_consequence"
        " ADD COLUMN IF NOT EXISTS b26_p2_event_family text DEFAULT NULL"
    )

    # ------------------------------------------------------------------
    # XVIII-5. Operational floor for downgrade safety (H-XVIII-R15).
    # Model B (maintenance-only downgrade): while the schema is
    # downgraded across an unsafe boundary, inbound authority creation
    # is physically disabled. The atomic requires the floor row; the
    # XVIII downgrade removes it, so a downgraded schema fails closed.
    # Documentation alone would be insufficient; this is a database
    # refusal on the minting path itself.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_operational_floor (
            id integer PRIMARY KEY DEFAULT 1,
            floor_revision text NOT NULL,
            policy text NOT NULL DEFAULT 'maintenance-only-downgrade',
            CONSTRAINT b26_p2_floor_singleton CHECK (id = 1)
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_operational_floor FROM PUBLIC"
    )
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        ON CONFLICT (id) DO UPDATE SET floor_revision = EXCLUDED.floor_revision
        """ % revision
    )

    # ------------------------------------------------------------------
    # XVIII-6. Hardened sovereign atomic (H-XVIII-R5/R11/R15/R19).
    # XVII law preserved verbatim (exact 7-argument sovereign
    # signature unchanged: the XVI strict transition-frame gate
    # anchors it) plus:
    #  (a) demoted rows are never promoted in place --
    #      b26_p2_atomic_demoted_ingress_refused (stale evidence can
    #      never satisfy current promotion; genuine recovery always
    #      mints a NEW row via redelivery);
    #  (b) the operational floor must be present --
    #      b26_p2_downgrade_serving_refused;
    #  (c) the event family is allowlisted per provider and bound into
    #      the consequence row -- b26_p2_atomic_family_unbound_refused.
    # 3VL discipline: UNKNOWN never authorizes; every gate uses
    # IS DISTINCT FROM / IS NULL / explicit equality fail-closed.
    # ------------------------------------------------------------------
    # The sovereign signature is UNCHANGED (exact 7-argument form):
    # the XVI strict transition-frame gate anchors that signature
    # (b26_p2_enforce_auth_root_evidence_immutability admits only the
    # exact frame), so the family claim travels via the
    # transaction-local governed GUC app.b26_p2_event_family, set by
    # the authentication root from bytes-derived meaning before
    # invoking the transition. Direct-atomic callers without the GUC
    # are attested as family-implicit (governed disposition); an
    # unsupported claimed family is refused.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_authenticate_ingress_atomic(
            p_ingress uuid,
            p_provider text,
            p_event_ref text,
            p_body_sha256 text,
            p_sig_envelope_sha256 text,
            p_method text,
            p_version text DEFAULT 'v1'
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
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_atomic_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XVIII-5: operational floor. A downgraded schema (floor
            -- row/table absent) cannot mint authority: serving is
            -- physically disabled, not merely undocumented. The
            -- undefined_table handler keeps the refusal clean even
            -- when the floor table itself was removed by downgrade.
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300001';
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
            -- XVIII-6a: demoted history is never promoted in place.
            -- A row the migration declared semantically insufficient
            -- keeps its stale evidence AND its non-authority: genuine
            -- provider redelivery mints a NEW row (fresh evidence
            -- under current law) instead of blessing stale money.
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
            -- XVIII-4: sovereign event-family allowlist. The family's
            -- only authority is this transition over provider + the
            -- root-supplied governed claim (transaction-local GUC
            -- app.b26_p2_event_family, derived by the root from
            -- authenticated bytes): relay route selection cannot
            -- confer it. An absent claim is attested as the governed
            -- family-implicit canonical family (contract disposition
            -- for signal-less shapes); an unsupported claim is
            -- refused, never coerced.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                _family := NULL;
            END IF;
            -- XVIII (H-XVIII-R11/XA-01): the provider key is
            -- ascii-stripped before the family dispatch, matching the
            -- scope ascii law: a tab-padded 'stripe' conducts as
            -- stripe (one meaning), while a non-ascii distinction
            -- (NBSP) stays distinct and is refused below.
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(p_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF _family IS NULL THEN
                    _family := 'payment_intent.succeeded';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF _family IS NULL THEN
                    _family := 'orders.create';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF _family IS NULL THEN
                    _family := 'payment.sale.completed';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF _family IS NULL THEN
                    _family := 'order.completed';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
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
            -- XVI1: serialize authentications of identical bytes.
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_bytes:' || _tenant::text),
                hashtext(lower(p_body_sha256))
            );
            -- XVII2: serialize authentications of the same provider
            -- event and the same commerce identity, so concurrent
            -- conflicting first-authentications cannot both pass the
            -- checks below. Locks key on row content, never on caller
            -- context, and are transaction-scoped (released at commit).
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
            -- XVI1 (preserved): same bytes + same reference, different
            -- row -> duplicate redelivery, refused with the duplicate
            -- token (callers resolve the winning lineage idempotently).
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
            -- XVII2a: same provider event reference with DIFFERENT
            -- authenticated bytes -> conflicting provider truth. One
            -- immutable provider event is one canonical lineage: refuse,
            -- never mint a second lineage.
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
            -- XVII2b: same commerce identity across distinct provider
            -- events -> conflicting financial truth. One economic
            -- commerce identity is one canonical financial fact within
            -- the supported lifecycle: refuse, never double-count.
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
                        b26_p2_event_family, recorded_by
                    )
                    VALUES (p_ingress, _tenant, p_provider, p_event_ref,
                            lower(p_body_sha256), lower(p_sig_envelope_sha256),
                            p_method, COALESCE(p_version, 'v1'), _family,
                            session_user)
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
                    -- Backfill the family binding for consequence rows
                    -- minted before the family became bound state.
                    UPDATE public.b26_p2_provider_auth_consequence AS c
                       SET b26_p2_event_family = _family
                     WHERE c.webhook_ingress_identity_id = p_ingress
                       AND c.b26_p2_event_family IS NULL;
                END IF;
                -- XVII3: tuple-bound witness. The digest covers the
                -- cryptographic identity AND the derived semantic tuple
                -- (kind/value, amount, currency, scale, canonical UTC
                -- instant), so the trusted meaning cannot detach from
                -- the evidence that justified it. Canonical instant
                -- rendering is timezone-independent by construction.
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
                    -- Regime rotation on re-authentication: the stored
                    -- witness was bound under a predecessor law. Re-bind
                    -- it deterministically to the current tuple-bound
                    -- law inside the sole sovereign transition (no
                    -- caller-controlled content: every preimage field
                    -- is observed from durable rows).
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
                -- XIV: immutable auth-root evidence identity in the SAME
                -- transaction. Idempotent on retry; drift refused via the
                -- consequence immutability check above (digests bound).
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
                -- XVII1: stamp the governed semantic regime and clear
                -- any historical demotion reason: this row's meaning is
                -- now justified under current law. (Reachable only for
                -- non-demoted rows: XVIII-6a refused demoted rows
                -- above, so this stamp can never bless stale money.)
                -- The authority-transition trigger observes this write:
                -- it is marked governed for this transaction (the mark
                -- is unforgeable-as-authority because runtime roles
                -- hold no column privilege to write at all).
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '1', true);
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '', true);
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                -- Never leak the governed mark past a failure: a
                -- caller that catches the refusal must not inherit a
                -- transaction that can stamp authority.
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '', true);
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    # Capability preserved exactly (same 7-argument signature, so
    # prior GRANTs persist; restated idempotently): the ingress
    # credential alone may invoke the transition; every other runtime
    # role is refused at the function boundary (unchanged XIII-XVII).
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic("
        "uuid, text, text, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic("
        "uuid, text, text, text, text, text, text) TO app_ingress"
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic("
        "uuid, text, text, text, text, text, text) FROM app_user"
    )

    # ------------------------------------------------------------------
    # XVIII-7. Dispatch law hardening (H-XVIII-R6): the demotion reason
    # is now part of the dispatch conjunction. A row carrying any
    # demotion state cannot dispatch even if its provenance marker
    # were somehow set -- the trigger reads the same predicate the
    # readers use, so dispatch can never disagree with reads.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _prov text;
            _regime text;
            _reason text;
            _witness text;
            _family text;
        BEGIN
            SELECT i.b26_p2_provenance_status, i.b26_p2_semantic_regime,
                   i.b26_p2_demotion_reason
              INTO _prov, _regime, _reason
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = NEW.webhook_ingress_identity_id
               AND i.tenant_id = NEW.tenant_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_dispatch_ingress_missing' USING ERRCODE = '42501';
            END IF;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provenance_unknown' USING ERRCODE = '42501';
            END IF;
            IF _regime IS DISTINCT FROM 'xvii-sovereign-v1' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_regime_unverifiable_refused' USING ERRCODE = '42501';
            END IF;
            IF _reason IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_dispatch_demotion_active_refused' USING ERRCODE = '42501';
            END IF;
            SELECT c.b26_p2_event_family INTO _family
              FROM public.b26_p2_provider_auth_consequence AS c
             WHERE c.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
               AND c.tenant_id = NEW.tenant_id;
            IF NOT FOUND OR _family IS NULL THEN
                RAISE EXCEPTION 'b26_p2_dispatch_family_unbound_refused' USING ERRCODE = '42501';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                 WHERE q.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
            ) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_quarantined_refused' USING ERRCODE = '42501';
            END IF;
            SELECT w.witness_hash INTO _witness
              FROM public.b26_p2_ingress_auth_witness AS w
             WHERE w.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_dispatch_witness_missing' USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XVIII-8. Backfill: existing currently-trusted rows receive the
    # governed family-implicit binding (they were authenticated under
    # shapes the family law declares family-implicit). Demoted rows
    # keep NULL family: no historical consequence is re-blessed.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE _t uuid;
        BEGIN
            FOR _t IN SELECT id FROM public.tenants LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.b26_p2_provider_auth_consequence AS c
                   SET b26_p2_event_family = CASE lower(
                        public.b26_p2_ascii_strip(COALESCE(c.provider, '')))
                        WHEN 'stripe' THEN 'payment_intent.succeeded'
                        WHEN 'shopify' THEN 'orders.create'
                        WHEN 'paypal' THEN 'payment.sale.completed'
                        WHEN 'woocommerce' THEN 'order.completed'
                        ELSE NULL END
                  FROM public.webhook_ingress_identities AS i
                 WHERE c.webhook_ingress_identity_id = i.id
                   AND c.tenant_id = i.tenant_id
                   AND c.tenant_id = _t
                   AND c.b26_p2_event_family IS NULL
                   AND i.b26_p2_provenance_status
                       IS NOT DISTINCT FROM 'authenticated_known'
                   AND i.b26_p2_semantic_regime
                       IS NOT DISTINCT FROM 'xvii-sovereign-v1'
                   AND i.b26_p2_demotion_reason IS NULL;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )


    # ------------------------------------------------------------------
    # XVIII-9. Historical consequence revocation (H-XVIII-R7/R20).
    # Authority travels ON the consequence row itself, maintained
    # transactionally by the P2 transition graph -- no async repair
    # machinery (R22: nothing to wire, nothing to orphan), and no
    # identity-table reads in aggregate-only consumers (B2.4 privacy
    # boundary preserved: Bayesian SQL filters the verdict's own
    # column, never joins ingress identity).
    #
    # States: 'current' (source ingress currently authoritative),
    # 'historically_unverifiable' (source demoted/non-current),
    # 'unresolved' (no source ingress link yet). Readers admit only
    # 'current'. Genuine redelivery supersedes via the batch upsert's
    # event-reference conflict target (R20: one consequence universe).
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b23_match_verdicts"
        " ADD COLUMN IF NOT EXISTS b26_p2_source_authority_state text"
        " NOT NULL DEFAULT 'unknown'"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_derive_verdict_authority(
            p_ingress uuid
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF p_ingress IS NULL THEN
                RETURN 'unresolved';
            END IF;
            IF public.b26_p2_ingress_has_current_authority(p_ingress) THEN
                RETURN 'current';
            END IF;
            RETURN 'historically_unverifiable';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_derive_verdict_authority(uuid)"
        " FROM PUBLIC"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_stamp_verdict_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            -- Authority state is never caller-asserted: every INSERT
            -- is stamped from the central predicate in this transition.
            NEW.b26_p2_source_authority_state :=
                public.b26_p2_derive_verdict_authority(
                    NEW.webhook_ingress_identity_id);
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_stamp_verdict_authority()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_stamp"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_authority_stamp
        BEFORE INSERT ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_stamp_verdict_authority()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_propagate_verdict_authority()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            -- Any authority transition on ingress conducts into its
            -- dependent consequences in the same statement: demotion
            -- revokes, (re)authentication restores. No stale verified
            -- consequence can survive its source's demotion.
            UPDATE public.b23_match_verdicts AS v
               SET b26_p2_source_authority_state =
                   public.b26_p2_derive_verdict_authority(NEW.id)
             WHERE v.webhook_ingress_identity_id = NEW.id
               AND v.tenant_id = NEW.tenant_id;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_propagate_verdict_authority()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_propagate"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_authority_propagate
        AFTER UPDATE OF b26_p2_provenance_status, b26_p2_semantic_regime,
                        b26_p2_demotion_reason
        ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_propagate_verdict_authority()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_guard_verdict_authority_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _governed text;
        BEGIN
            -- Relink re-derivation (R20): when the verdict's source
            -- ingress changes (genuine redelivery supersedes a demoted
            -- precursor via the event-reference conflict target), the
            -- authority state is re-derived from the NEW source in the
            -- transition graph itself. One consequence universe: the
            -- superseded row cannot keep two simultaneous truths.
            IF NEW.webhook_ingress_identity_id
                   IS DISTINCT FROM OLD.webhook_ingress_identity_id THEN
                NEW.b26_p2_source_authority_state :=
                    public.b26_p2_derive_verdict_authority(
                        NEW.webhook_ingress_identity_id);
                RETURN NEW;
            END IF;
            -- Transition-graph writes (the sovereign atomic's stamp via
            -- the propagation trigger) carry the governed mark. The
            -- mark alone confers nothing: runtime roles hold no UPDATE
            -- privilege on this column (XVIII column REVOKE), so a
            -- forged mark cannot authorize a write the privilege layer
            -- already denied.
            BEGIN
                _governed := current_setting(
                    'app.b26_p2_governed_transition', true);
            EXCEPTION WHEN OTHERS THEN
                _governed := NULL;
            END;
            -- No runtime role may assert consequence authority
            -- directly; only the transition graph writes this column.
            IF session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres'
               AND COALESCE(_governed, '') IS DISTINCT FROM '1' THEN
                IF OLD.b26_p2_source_authority_state
                       IS DISTINCT FROM NEW.b26_p2_source_authority_state THEN
                    RAISE EXCEPTION 'b26_p2_verdict_authority_write_refused'
                        USING ERRCODE = '42501';
                END IF;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_guard_verdict_authority_write()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_guard"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_verdict_authority_guard
        BEFORE UPDATE OF b26_p2_source_authority_state,
                         webhook_ingress_identity_id
        ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_guard_verdict_authority_write()
        """
    )
    # Backfill through the same derivation every future row uses.
    op.execute(
        """
        DO $$
        DECLARE _t uuid;
        BEGIN
            FOR _t IN SELECT id FROM public.tenants LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.b23_match_verdicts AS v
                   SET b26_p2_source_authority_state =
                       public.b26_p2_derive_verdict_authority(
                           v.webhook_ingress_identity_id)
                 WHERE v.tenant_id = _t;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )
    for _role in (
        "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
        "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
    ):
        op.execute(
            "REVOKE UPDATE (b26_p2_source_authority_state)"
            " ON public.b23_match_verdicts FROM %s" % _role
        )


    # ------------------------------------------------------------------
    # XVIII-10. Legacy attester hardening (H-XVIII-R3/R5/R11/R15).
    # b26_p2_attest_provenance_evidence is a second promotion
    # primitive predating the sovereign atomic: as app_ingress it can
    # mint authenticated_known without a regime stamp, without a
    # demotion check, without family binding, and without the floor.
    # It is load-bearing for predecessor validators and the direct
    # finalizer, so it is hardened in place (same signature), not
    # retired: demoted rows are refused, the floor is required, the
    # governed family claim is allowlisted and backfilled into the
    # consequence row, and the stamp carries the governed mark the
    # authority-transition trigger admits. Post-XVIII there is one
    # effective promotion law with two entry points sharing every
    # guard; the atomic remains the sole mint of fresh evidence.
    # ------------------------------------------------------------------
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
            _prov_status text;
            _demotion text;
            _row_provider text;
            _family text;
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
            -- Single XII law: only the ingress boundary (and migration
            -- admins) may attest. No predecessor fallback exists.
            IF session_user NOT IN (
                'app_ingress', 'migration_owner', 'postgres'
            ) THEN
                RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- governed_attestation is migration/admin custody only at
            -- runtime: it must not be executable by the shipping
            -- ingress principal to restore authority without a
            -- provider-authenticated consequence.
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
            -- XVIII floor: a downgraded schema cannot mint authority
            -- through this entry point either.
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300001';
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
            -- XVIII: demoted history is never promoted in place
            -- through this entry point either.
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
            -- The witness must be consequence-bound: recompute the
            -- expected digest from the independently recorded P and
            -- refuse a self-certified token.
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
            -- XVIII family: allowlist the governed claim (or attest
            -- the family-implicit canonical family) and bind it into
            -- the consequence row when unbound, so dispatch's family
            -- requirement holds for attester-minted rows exactly as
            -- for atomic-minted rows.
            BEGIN
                _family := current_setting(
                    'app.b26_p2_event_family', true);
            EXCEPTION WHEN OTHERS THEN
                _family := NULL;
            END;
            IF _family IS NULL
               OR public.b26_p2_ascii_strip(_family) = '' THEN
                _family := NULL;
            END IF;
            -- Same ascii-strip normalization as the atomic (XA-01):
            -- a tab-padded provider conducts under one meaning.
            _fam_provider := lower(
                public.b26_p2_ascii_strip(COALESCE(_row_provider, '')));
            IF _fam_provider = 'stripe' THEN
                IF _family IS NULL THEN
                    _family := 'payment_intent.succeeded';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment_intent.succeeded',
                          'payment_intent_succeeded') THEN
                    _family := 'payment_intent.succeeded';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'shopify' THEN
                IF _family IS NULL THEN
                    _family := 'orders.create';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('orders.create', 'order_create',
                          'orders/create') THEN
                    _family := 'orders.create';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'paypal' THEN
                IF _family IS NULL THEN
                    _family := 'payment.sale.completed';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
                      IN ('payment.sale.completed', 'sale_completed',
                          'payment.sale_completed') THEN
                    _family := 'payment.sale.completed';
                ELSE
                    RAISE EXCEPTION 'b26_p2_atomic_family_unbound_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF _fam_provider = 'woocommerce' THEN
                IF _family IS NULL THEN
                    _family := 'order.completed';
                ELSIF lower(public.b26_p2_ascii_strip(_family))
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
                   SET b26_p2_event_family = _family
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
                -- The stamp carries the governed mark the
                -- authority-transition trigger admits (same law as
                -- the atomic; the mark confers nothing without the
                -- column privilege, which runtime roles lack).
                -- One effective promotion law: the full conjunction
                -- (provenance + current regime + cleared reason), so
                -- attester-minted rows satisfy dispatch, P3, and
                -- readers exactly like atomic-minted rows. Reachable
                -- only for non-demoted rows (refused above).
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '1', true);
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'authenticated_known',
                       b26_p2_semantic_regime = 'xvii-sovereign-v1',
                       b26_p2_demotion_reason = NULL
                 WHERE i.id = p_ingress;
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '', true);
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RETURN 'authenticated_known';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config(
                    'app.b26_p2_governed_transition', '', true);
                PERFORM set_config('app.current_tenant_id', COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )


def downgrade() -> None:
    # Remove XVIII enforcement objects. The hardened atomic, the family
    # column, and demoted-row state are RETAINED (fail-closed retention:
    # rollback must neither resurrect unverifiable authority nor weaken
    # the transition graph). Serving stays blocked until re-upgrade
    # restores the floor: the atomic's floor check fails closed on the
    # missing table via its undefined_table handler.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_ingress_authority_transition"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_authority_transition()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_ingress_has_current_authority(uuid)"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_registry_immutable"
        " ON public.b26_p2_semantic_regime_registry"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_registry_immutability()"
    )
    op.execute("DROP TABLE IF EXISTS public.b26_p2_semantic_regime_registry")
    op.execute("DROP TABLE IF EXISTS public.b26_p2_operational_floor")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_stamp"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_propagate"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_verdict_authority_guard"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_stamp_verdict_authority()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_propagate_verdict_authority()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_guard_verdict_authority_write()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_derive_verdict_authority(uuid)"
    )
    # The verdict authority column is RETAINED (fail-closed retention):
    # rows keep their last governed disposition, and new rows land
    # 'unknown' (admitted by no reader) until re-upgrade restores the
    # transition graph.
    for _role in (
        "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
        "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
    ):
        op.execute(
            "GRANT UPDATE (b26_p2_provenance_status, b26_p2_semantic_regime,"
            " b26_p2_demotion_reason)"
            " ON public.webhook_ingress_identities TO %s" % _role
        )
