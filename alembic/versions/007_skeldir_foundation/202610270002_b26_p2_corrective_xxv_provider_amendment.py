"""B2.6-P2 Corrective XXV-2: lawful provider amendment of captured money.

Revision ID: 202610270002
Revises: 202610270001

Closes the positive half of A2/B10, whose root cause was an identity law that
treated every second authenticated event over one commerce identity as a
collision:

* `b26_p2_authenticate_ingress_atomic_v2` refused the second event with
  `b26_p2_atomic_commerce_identity_conflict_refused`, so no authenticated row
  ever carried an amended amount;
* the correction kernel reads the amount from an authenticated ingress row, so
  with no such row the shipping correction surface was a monetary no-op
  (`200 accepted`, `revenue_event_written=false`, money unchanged);
* with no money change there was no supersession row, so no checkpoint could
  advance, which in turn made A3's multi-checkpoint progression, A7's
  stale-issuance race, A8's crash window and B12's requalified second read all
  unreachable.

Both independent XXIV audits recorded the same wall: Nicholas as
`b26_p2_atomic_commerce_identity_conflict_refused`, Trey as a byte-different
second event silently adopted as a duplicate.

This revision separates provider AMENDMENT from commerce-identity COLLISION.
The admission conditions are the provider's own distinctions (different event
reference, different signed bytes, non-decreasing instant, same currency, same
event family); everything else keeps the strict refusal. The superseded row
keeps its authenticated money and its XXV source attestation and merely stops
being current, so nothing authentic is replaced or erased.

The function is re-issued from its deployed definition with exactly that one
change, so every other law inside it is identical to the one the audits
examined.

Two supporting laws are required for that admission to be executable at all,
and they were found by executing the amendment against the deployed schema,
not by reading it:

* ``uq_b26_p2_xvii_commerce_identity`` was a unique index over every
  ``authenticated_known`` row, so the superseded row kept the commerce-identity
  slot occupied and the amending row could never be promoted. The index now
  governs the *current* authenticated row only (``b26_p2_demotion_reason IS
  NULL``); superseded history stays in the table, authenticated and attested.
* ``b26_p2_propagate_verdict_authority()`` ran as the table owner without a
  tenant GUC, so under FORCE RLS the demotion updated zero verdicts. It now
  binds the affected tenant for the propagation statement, exactly as the
  regime-retirement propagation already does. Without that, the demoted
  verdict would keep claiming ``current`` and the correction kernel would have
  no lawful place to start.
"""

from __future__ import annotations
from alembic import op
from sqlalchemy import text


revision = "202610270002"
down_revision = "202610270001"
branch_labels = None
depends_on = None


def _ensure_role(role: str, *, bypass_rls: bool = False) -> None:
    bind = op.get_bind()
    row = (
        bind.execute(
            text(
                "SELECT rolcanlogin, rolbypassrls FROM pg_roles"
                " WHERE rolname = :role"
            ),
            {"role": role},
        )
        .mappings()
        .first()
    )
    if row is None:
        attributes = "NOLOGIN" + (" BYPASSRLS" if bypass_rls else "")
        op.execute(f'CREATE ROLE "{role}" {attributes}')
        return
    if bypass_rls and not bool(row["rolbypassrls"]):
        raise RuntimeError(
            f"required_role_missing_bypassrls:{role}"
        )


def upgrade() -> None:
    # XXV-2a. One *current* authenticated source per commerce identity.
    #
    # The former index covered every authenticated_known row. A provider
    # amendment must retain the superseded row as authentic history while the
    # amending row becomes the current authority, so the uniqueness that
    # matters is over current rows. Dropping the old index first is required:
    # PostgreSQL cannot widen a partial predicate in place.
    op.execute(
        "DROP INDEX IF EXISTS public.uq_b26_p2_xvii_commerce_identity"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_b26_p2_xvii_commerce_identity
            ON public.webhook_ingress_identities (
                tenant_id,
                provider,
                normalized_commerce_reference_kind,
                normalized_commerce_reference_value
            )
         WHERE b26_p2_provenance_status = 'authenticated_known'
           AND b26_p2_demotion_reason IS NULL
        """
    )

    # XXV-2b. Make demotion conduct to the linked verdict.
    #
    # This function is SECURITY DEFINER and owns the UPDATE, but FORCE RLS on
    # b23_match_verdicts still applies to the owner. The deployed body had no
    # tenant GUC, so under a caller that had not set one it updated zero rows:
    # a demoted source's verdict kept claiming "current". The tenant is now
    # bound for the propagation statement and the caller's setting restored.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_propagate_verdict_authority()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
        DECLARE
            _prev_guc text;
        BEGIN
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', NEW.tenant_id::text, true);
            UPDATE public.b23_match_verdicts AS v
               SET b26_p2_source_authority_state =
                   public.b26_p2_derive_verdict_authority(NEW.id)
             WHERE v.webhook_ingress_identity_id = NEW.id
               AND v.tenant_id = NEW.tenant_id;
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_prev_guc, ''), true
            );
            RETURN NEW;
        END $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_propagate_verdict_authority() FROM PUBLIC"
    )

    # XXV-2b2. Let a lawful provider amendment relink a conducted verdict.
    #
    # The temporal-conservation trigger refuses every link move on a
    # conducted verdict, which is the right default: a consequence's source
    # is not arbitrary. A provider amendment is the one supersession the
    # shipping surface is allowed to express, and the trigger re-checks every
    # admission condition plus the exact supersession reason before allowing
    # the move. The new source must have no conducted dispatch; the existing
    # branch below still refuses that case.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_enforce_verdict_temporal_conservation()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'pg_catalog', 'public'
AS $function$
        DECLARE
            _tenant uuid;
            _ingress uuid;
            _old_qual boolean;
            _new_qual boolean;
            _link_moved boolean;
            _old_ref_present boolean;
            _new_ref_present boolean;
            _ref_presence_flipped boolean;
            _amendment_link boolean;
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

                -- XXV-2 (A2/B10): a provider amendment may relink a conducted
                -- verdict to its successor source. Every condition the
                -- amendment admission enforced is re-checked here, and the old
                -- source must name exactly the new source's event in its
                -- supersession reason. The new source has no conducted
                -- dispatch (it is not independently matched), which the next
                -- branch still enforces.
                _amendment_link :=
                    _link_moved
                    AND OLD.webhook_ingress_identity_id IS NOT NULL
                    AND NEW.webhook_ingress_identity_id IS NOT NULL
                    AND OLD.tenant_id IS NOT DISTINCT FROM NEW.tenant_id
                    AND EXISTS (
                        SELECT 1
                          FROM public.webhook_ingress_identities AS oldi
                          JOIN public.webhook_ingress_identities AS newi
                            ON newi.id = NEW.webhook_ingress_identity_id
                           AND newi.tenant_id = OLD.tenant_id
                         WHERE oldi.id = OLD.webhook_ingress_identity_id
                           AND oldi.tenant_id = OLD.tenant_id
                           AND oldi.b26_p2_demotion_reason =
                               'superseded_by_provider_amendment:'
                               || newi.provider_native_event_reference
                           AND newi.provider IS NOT DISTINCT FROM oldi.provider
                           AND newi.normalized_commerce_reference_kind
                               IS NOT DISTINCT FROM
                               oldi.normalized_commerce_reference_kind
                           AND newi.normalized_commerce_reference_value
                               IS NOT DISTINCT FROM
                               oldi.normalized_commerce_reference_value
                           AND newi.verified_amount_currency
                               IS NOT DISTINCT FROM
                               oldi.verified_amount_currency
                           AND newi.event_timestamp >= oldi.event_timestamp
                           AND public.b26_p2_ingress_has_current_authority(
                                   newi.id)
                    );
                IF ((_old_qual AND NOT _new_qual) OR (_old_qual AND _link_moved))
                   AND NOT _amendment_link THEN
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
                -- XIV: conducted commerce-reference value rewrite. Presence
                -- flips are refused below; a present-to-present value change
                -- on a conducted lineage is an equal violation of the
                -- UPDATE_REFUSED disposition and fails with the same
                -- regression law. Non-conducted (B2.3-correctable) rows are
                -- unaffected: the EXISTS test finds no conducted dispatch.
                IF OLD.canonical_commerce_reference IS DISTINCT FROM NEW.canonical_commerce_reference
                   AND _old_qual AND _new_qual
                   AND _old_ref_present AND _new_ref_present
                   AND NOT _link_moved THEN
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
        END $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_enforce_verdict_temporal_conservation()"
        " FROM PUBLIC"
    )

    # XXV-2b3. Align the DB lifecycle seam with the published v4 contract.
    # The XXII upgrade branch required updated_at == created_at; the
    # contract and the parser admit a 60-second creation window. The
    # reversed-chronology refusal is retained; only the forward window is
    # widened to 60 seconds.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_enforce_lifecycle_admission(p_provider text, p_family text, p_financial_status text, p_cancelled_at timestamp with time zone, p_refunds_present boolean, p_created_at timestamp with time zone, p_updated_at timestamp with time zone, p_require_creation_proof boolean)
 RETURNS void
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO 'pg_catalog', 'public'
AS $function$
        BEGIN
            IF p_cancelled_at IS NOT NULL THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_cancelled_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(p_refunds_present, false) THEN
                RAISE EXCEPTION 'b26_p2_lifecycle_refunded_not_creation'
                    USING ERRCODE = '42501';
            END IF;
            IF lower(public.b26_p2_ascii_strip(COALESCE(p_provider, '')))
                   = 'shopify'
               AND lower(public.b26_p2_ascii_strip(COALESCE(p_family, '')))
                   = 'orders.create' THEN
                IF p_require_creation_proof THEN
                    IF p_financial_status IS NULL
                       OR lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                    IF p_created_at IS NULL OR p_updated_at IS NULL THEN
                        RAISE EXCEPTION 'b26_p2_lifecycle_moment_missing'
                            USING ERRCODE = '42501';
                    END IF;
                ELSE
                    IF p_financial_status IS NOT NULL
                       AND lower(public.b26_p2_ascii_strip(p_financial_status))
                          NOT IN ('pending', 'authorized', 'paid',
                                  'partially_paid', 'voided', 'refunded',
                                  'partially_refunded') THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_status_not_creation'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                IF p_created_at IS NOT NULL AND p_updated_at IS NOT NULL THEN
                    IF p_updated_at < p_created_at THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_reversed_chronology'
                            USING ERRCODE = '42501';
                    END IF;
                    IF (p_updated_at - p_created_at)
                           > interval '60 seconds' THEN
                        RAISE EXCEPTION
                            'b26_p2_lifecycle_not_creation_moment'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
            END IF;
            RETURN;
        END $function$
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_enforce_lifecycle_admission(text, text, text,"
        " timestamptz, boolean, timestamptz, timestamptz, boolean)"
        " FROM PUBLIC"
    )

    # XXV-2c. Admit a provider amendment; keep every other law of the
    # deployed atomic byte-for-byte identical.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_authenticate_ingress_atomic_v2(p_ingress uuid, p_provider text, p_event_ref text, p_body_sha256 text, p_sig_envelope_sha256 text, p_method text, p_version text, p_financial_status text, p_cancelled_at timestamp with time zone, p_refunds_present boolean, p_created_at timestamp with time zone, p_updated_at timestamp with time zone)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
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
            _amend_event_ref text;
            _amend_body text;
            _amend_ccy text;
            _amend_ts timestamptz;
            _amend_family text;
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
            -- XXV-2: commerce-identity collision and provider amendment are
            -- two different things, and conflating them cost the phase its
            -- positive obligation. Before this revision ANY second
            -- authenticated event over one commerce identity was refused, so
            -- a provider that amends a captured amount had no reachable way
            -- to move the system's money: no lawful amount-changing source
            -- existed, and with it went checkpoint growth, the crash window,
            -- stale-issuance racing and the requalified second read
            -- (directive XXV A2/A3/A7/A8/B10/B12).
            --
            -- An amendment is admitted only when the provider itself
            -- distinguishes it from the event already holding authority:
            --   * a different provider event reference (not a redelivery of
            --     the same event),
            --   * different signed bytes (not a replay of the same body),
            --   * an event instant no earlier than the current authority's
            --     (history moves forward, never backward),
            --   * the same currency (an amendment corrects an amount, it
            --     does not change the unit of the money), and
            --   * the same event family (a cross-family claim on one
            --     commerce identity is still a collision).
            -- Anything else keeps the strict refusal.
            --
            -- The prior row is SUPERSEDED, never replaced: its authenticated
            -- money and its attestation stay exactly as the provider sent
            -- them, and it simply stops being the current authority. That is
            -- what keeps this from becoming "arbitrary replacement of
            -- original authenticated money", which the directive forbids.
            SELECT i.id, i.provider_native_event_reference,
                   i.verified_amount_currency, i.event_timestamp,
                   lower(c.body_sha256), c.b26_p2_event_family
              INTO _conflict_id, _amend_event_ref, _amend_ccy, _amend_ts,
                   _amend_body, _amend_family
              FROM public.webhook_ingress_identities AS i
              LEFT JOIN public.b26_p2_provider_auth_consequence AS c
                     ON c.webhook_ingress_identity_id = i.id
                    AND c.tenant_id = i.tenant_id
             WHERE i.tenant_id = _tenant
               AND i.provider IS NOT DISTINCT FROM p_provider
               AND i.normalized_commerce_reference_kind IS NOT DISTINCT FROM _t_kind
               AND i.normalized_commerce_reference_value IS NOT DISTINCT FROM _t_value
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.id IS DISTINCT FROM p_ingress
             ORDER BY i.event_timestamp DESC, i.created_at DESC
             LIMIT 1
             FOR UPDATE OF i;
            IF _conflict_id IS NOT NULL THEN
                IF _amend_event_ref IS DISTINCT FROM p_event_ref
                   AND COALESCE(_amend_body, '')
                       IS DISTINCT FROM lower(p_body_sha256)
                   AND _t_ts >= _amend_ts
                   AND _t_ccy IS NOT DISTINCT FROM _amend_ccy
                   AND COALESCE(_family, '')
                       IS NOT DISTINCT FROM COALESCE(_amend_family, '')
                THEN
                    UPDATE public.webhook_ingress_identities AS i
                       SET b26_p2_demotion_reason =
                           'superseded_by_provider_amendment:' || p_event_ref
                     WHERE i.id = _conflict_id;
                ELSE
                    RAISE EXCEPTION
                        'b26_p2_atomic_commerce_identity_conflict_refused'
                        USING ERRCODE = '42501';
                END IF;
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
        END $function$
        """
    )


    # XXV-2d. HB-13: the login lookup must work before a user identity exists.
    #
    # `auth.lookup_user_auth_by_login_hash` is SECURITY DEFINER but was owned by
    # migration_owner, a non-BYPASSRLS role, while public.users is FORCE RLS
    # with a self-select policy keyed on a GUC that cannot be set before login.
    # An empty-but-set GUC also crashed the policy cast (`''::uuid`). The
    # lookup is owned by the dedicated NOLOGIN BYPASSRLS role created by the
    # provisioning script; that role gets only the read the function needs.
    # The migration principal's temporary SET ROLE membership is revoked after
    # the owner change, so it cannot replace the lookup afterwards. The owner
    # change and revocation are conditional so a data-carrying downgrade and
    # re-upgrade remain possible: after the first upgrade the functions are
    # already owned by app_auth_lookup and the migration principal no longer
    # holds the role, so re-running either statement unconditionally would
    # fail even though the state is already correct.
    _ensure_role("app_auth_lookup", bypass_rls=True)
    _ensure_role("app_user")
    can_own_auth_lookup = (
        op.get_bind()
        .execute(
            text(
                "SELECT rolsuper OR pg_has_role("
                "current_user, 'app_auth_lookup', 'member'"
                ") FROM pg_roles WHERE rolname = current_user"
            )
        )
        .scalar()
    )
    if not can_own_auth_lookup:
        raise RuntimeError(
            "migration_role_must_own_or_inherit_app_auth_lookup"
        )
    op.execute(
        "GRANT USAGE, CREATE ON SCHEMA auth TO app_auth_lookup"
    )
    op.execute(
        "GRANT SELECT ON TABLE public.users TO app_auth_lookup"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF (
                SELECT pg_get_userbyid(p.proowner)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'auth'
                  AND p.proname = 'lookup_user_auth_by_login_hash'
            ) IS DISTINCT FROM 'app_auth_lookup' THEN
                ALTER FUNCTION auth.lookup_user_auth_by_login_hash(text)
                    OWNER TO app_auth_lookup;
            END IF;
            IF (
                SELECT pg_get_userbyid(p.proowner)
                FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'auth'
                  AND p.proname = 'lookup_user_by_login_hash'
            ) IS DISTINCT FROM 'app_auth_lookup' THEN
                ALTER FUNCTION auth.lookup_user_by_login_hash(text)
                    OWNER TO app_auth_lookup;
            END IF;
        END $$;
        """
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION"
        " auth.lookup_user_auth_by_login_hash(text) TO app_user"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION"
        " auth.lookup_user_by_login_hash(text) TO app_user"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_auth_members m
                JOIN pg_roles r ON r.oid = m.roleid
                JOIN pg_roles u ON u.oid = m.member
                WHERE r.rolname = 'app_auth_lookup'
                  AND u.rolname = 'migration_owner'
            ) THEN
                REVOKE app_auth_lookup FROM migration_owner;
            END IF;
        END $$;
        """
    )
    op.execute(
        "DROP POLICY IF EXISTS users_self_select_policy ON public.users"
    )
    op.execute(
        """
        CREATE POLICY users_self_select_policy ON public.users
        FOR SELECT
        USING (
            id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        """
    )
    op.execute(
        "DROP POLICY IF EXISTS users_self_update_policy ON public.users"
    )
    op.execute(
        """
        CREATE POLICY users_self_update_policy ON public.users
        FOR UPDATE
        USING (
            id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        WITH CHECK (
            id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
        )
        """
    )


def downgrade() -> None:
    # The downgrade restores the strict pre-amendment refusal. It does not
    # un-supersede any row: a superseded row is authentic history, and the
    # XXIV downgrade law is that a downgrade revokes reach without destroying
    # signed authority records.
    #
    # The partial commerce-identity index and the tenant-bound authority
    # propagation are deliberately retained. Restoring the old all-rows unique
    # index would either fail (history now contains a lawful supersession) or
    # require deleting authentic provider evidence, and restoring the
    # unbound propagation would reintroduce a demotion that updates no
    # verdict under FORCE RLS. Both retained laws are strictly stronger for
    # the downgraded strict-admission function: it admits no amendments, so
    # the only rows this index can ever see are ones the strict function
    # itself authenticated.
    op.execute(
        """
CREATE OR REPLACE FUNCTION public.b26_p2_authenticate_ingress_atomic_v2(p_ingress uuid, p_provider text, p_event_ref text, p_body_sha256 text, p_sig_envelope_sha256 text, p_method text, p_version text, p_financial_status text, p_cancelled_at timestamp with time zone, p_refunds_present boolean, p_created_at timestamp with time zone, p_updated_at timestamp with time zone)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
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
        END $function$
        """
    )
