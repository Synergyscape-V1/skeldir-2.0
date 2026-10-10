"""B2.6-P2 Corrective XX: compositional authority closure.

H-XX-A..F (Directive XX): XIX closed the named instances (bearer GUC gone,
least-privilege effective, familyless mint refused, downgrade revokes at the
XIX boundary, hash-chained publication history, supersession ledger). The
independent audits show the class survives as composition failures: one
subsystem invalidates a source while another independently maintained
representation stays positive and a downstream consumer produces an
authoritative financial statement no longer justified by the source.

Conservation laws established here (physical identities, not conventions):

    ONE CURRENTNESS LAW FOR EVERY READER
        (b26_p2_ingress_has_current_authority() remains the single
        canonical predicate. XX extends it with the explicit-family-source
        condition: a consequence row bound under the grandfathered
        xix-backfill:pre-xix-mint tag no longer satisfies currentness.
        History is preserved -- rows, money, and genuine redelivery are
        untouched -- but downstream authority expresses the uncertainty
        honestly: backfill rows read non-current until genuine
        redelivery establishes explicit family evidence. Registry-status
        and floor transitions additionally propagate into dependent
        verdicts in the same transaction, so verdict-local caches cannot
        disagree with the predicate after a lawful retirement.)

    P3 FOLLOWS THE SAME LAW
        (b26_p2_state_eligible_for_p3() previously checked provenance,
        regime, and witness only. It now additionally requires the full
        canonical predicate for the bound ingress, so P3 eligibility
        cannot survive evidence loss, family invalidation, quarantine,
        registry retirement, or floor change that the predicate refuses.)

    CORRECTION HISTORY IS TAMPER-EVIDENT AND INDEPENDENTLY OBSERVABLE
        (b26_p2_verdict_supersession_ledger gains prev_entry_hash /
        entry_hash chained on every append, serialized by an advisory
        lock, backfilled for pre-XX rows. b26_p2_verify_history_protection()
        reports any disabled protection trigger, any runtime-held ledger
        privilege, and any chain break in either ledger as rows a hostile
        reader can query. Trusted-computing-base declaration: runtime
        principals are PREVENTED (privilege + triggers, proven by live
        DML probes); migration_owner/postgres maintenance is OBSERVED
        (disabling a protection trigger or rewriting a ledger is an
        independently observable violation via the verify function and
        the mandatory XX proof plane -- it cannot be done silently);
        true PostgreSQL superuser remains outside any enforceable
        boundary, as it can already DROP DATABASE. No
        administrator-resistant immutability is claimed beyond this.)

    SUPPORTED DOWNGRADE = ONE STEP, NO RESURRECTION
        (this migration's downgrade restores the XIX predicate body and
        the 300002 floor and retains every XX conservation object, which
        remains consistent against the XIX schema. The supported rollback
        boundary is XX -> 300002. Deeper rollback is restore-from-backup
        territory: serving is physically refused by the
        construction-authority boot gate (single-element compatible set),
        proven by live mixed-version boot probes, not by prose.)

    STATEMENT-SNAPSHOT LINEARIZATION (unchanged, XIX-8 retained).

Upgrade is linear (revises 202609300002). Published history is append-only:
this file never modifies any earlier revision; the migration manifest
gains an entry for 202609300003 while every existing entry is byte-frozen.
Family cutover law update: xix-backfill rows keep their audit tag but lose
current authority under the stricter law; genuine redelivery with explicit
family evidence establishes new current authority with supersession
preserved.
"""

from __future__ import annotations

from alembic import op

revision = "202609300003"
down_revision = "202609300002"
branch_labels = None
depends_on = None

_XX_REGIME = "xvii-sovereign-v1"
_XX_FLOOR = "202609300003"
_XX_PREDECESSOR_FLOOR = "202609300002"

_XX_RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)

_XX_EXPLICIT_FAMILY_SOURCES = (
    "body-signal:type", "body-signal:event_type", "body-signal:status",
    "transport-topic:x-shopify-topic", "transport-topic:x-wc-webhook-topic",
)

_XX_PREDICATE_V2 = """
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

# XIX predicate body, restored verbatim on the way down so the supported
# 300003 -> 300002 rollback serves exactly the XIX law (floor 300002, no
# explicit-source condition). Byte-identical to the XIX upgrade text.
_XX_PREDICATE_XIX_RESTORE = """
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
            -- XIX: the bound regime must be live in the registry
            -- (retirement ends currentness transactionally).
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_semantic_regime_registry AS r
                 WHERE r.regime_id = _regime
                   AND r.status = 'active'
            ) THEN
                RETURN FALSE;
            END IF;
            -- XIX: the operational floor must hold at this revision
            -- (downgrade ends current readability fail-closed).
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300002';
                IF NOT FOUND THEN
                    RETURN FALSE;
                END IF;
            EXCEPTION WHEN undefined_table THEN
                RETURN FALSE;
            END;
            -- XIX: every load-bearing justification must still exist.
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
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                 WHERE c.webhook_ingress_identity_id = p_ingress
                   AND c.b26_p2_event_family IN (
                       'payment_intent.succeeded', 'orders.create',
                       'payment.sale.completed', 'order.completed')
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


def _roles_sql_list() -> str:
    return ", ".join("'%s'" % r for r in _XX_RUNTIME_ROLES)


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

    # ------------------------------------------------------------------
    # XX-1. Re-assert the least-privilege posture (H-XX, defense in
    # depth). A downgrade must never re-arm runtime authority writes.
    # Idempotent re-issue of the exact XIX posture: table-level UPDATE
    # removed, operational (non-authority) columns re-granted from the
    # live catalog so the grant set cannot drift from the schema.
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
    for _role in _XX_RUNTIME_ROLES:
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
    # XX-2. Complete current-authority predicate, second generation
    # (H-XX-A/H-XX-C). Adds the explicit-family-source condition to the
    # XIX conjunction and advances the floor to this revision.
    # ------------------------------------------------------------------
    op.execute(_XX_PREDICATE_V2)
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_ingress_has_current_authority(uuid)"
        " FROM PUBLIC"
    )
    for _role in _XX_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_ingress_has_current_authority(uuid) TO %s';"
            " END IF; END $$;" % (_role, _role)
        )

    # ------------------------------------------------------------------
    # XX-2b. Minimum-serving floor law for the minting paths (H-XX-E).
    # The frozen XIX atomic and attester require floor = 202609300002,
    # which the XX floor advance would turn into a self-denial of
    # service. Retarget the two comparisons to a minimum-serving law
    # (floor >= 202609300002) by rewriting the frozen bodies in place
    # via pg_get_functiondef -- no frozen text is copied or edited by
    # hand, so the rewrite tracks the published bodies exactly. The
    # fail-closed properties are preserved: a dropped floor (deeper
    # downgrade) still refuses via undefined_table/NOT FOUND, an old
    # binary against this floor still refuses via its own equality,
    # and the retained bodies keep minting after the supported
    # XX -> 300002 rollback (no downgrade restoration needed, hence
    # no repeat of the XIX missing-helper failure mode).
    # ------------------------------------------------------------------
    for _fn in (
        "public.b26_p2_authenticate_ingress_atomic(uuid,text,text,text,"
        "text,text,text)",
        "public.b26_p2_attest_provenance_evidence(uuid,text,text)",
    ):
        op.execute(
            """
            DO $$
            DECLARE
                _def text;
            BEGIN
                SELECT pg_get_functiondef('%s'::regprocedure) INTO _def;
                IF position('202609300002' IN _def) = 0 THEN
                    RAISE EXCEPTION 'b26_p2_xx_floor_retarget_missing';
                END IF;
                -- Idempotent: the minimum-serving form contains '>=';
                -- rewrite only the strict-equality form once.
                IF position('f.floor_revision >= ''202609300002''' IN _def) = 0 THEN
                    _def := replace(
                        _def,
                        'f.floor_revision = ''202609300002''',
                        'f.floor_revision >= ''202609300002'''
                    );
                    EXECUTE _def;
                END IF;
            END $$;
            """ % _fn
        )
    # pre-XX body checked provenance, regime, and witness only; a
    # demoted, familyless-backfill, quarantined, retired-regime, or
    # below-floor source could remain P3-eligible while every other
    # reader refused it. Delegate the full conjunction to the canonical
    # predicate instead of duplicating its clauses.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # XX-3. P3 eligibility follows the same law (H-XX-A sibling). The
    # pre-XX body checked provenance, regime, and witness only; a
    # demoted, familyless-backfill, quarantined, retired-regime, or
    # below-floor source could remain P3-eligible while every other
    # reader refused it. Delegate the full conjunction to the canonical
    # predicate instead of duplicating its clauses.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_state_eligible_for_p3(
            p_task_id text,
            p_tenant uuid
        )
        RETURNS boolean
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _tenant uuid;
            _ingress uuid;
            _ws timestamptz;
            _we timestamptz;
            _prov text;
            _regime text;
            _receipt_identity text;
            _receipt_policy text;
            _receipt_meaning text;
            _live_identity text;
            _prev_guc text;
        BEGIN
            IF public.b26_p2_ascii_strip(COALESCE(p_task_id, '')) = '' THEN
                RETURN FALSE;
            END IF;
            IF p_tenant IS NULL THEN
                RETURN FALSE;
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', p_tenant::text, true);
            BEGIN
            SELECT d.tenant_id, d.webhook_ingress_identity_id,
                   d.window_start, d.window_end
              INTO _tenant, _ingress, _ws, _we
              FROM public.b23_match_task_dispatches AS d
             WHERE d.task_id = p_task_id;
            IF NOT FOUND THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF _tenant IS DISTINCT FROM p_tenant THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            END;
            -- Authenticated, witnessed, regime-governed provenance.
            BEGIN
            SELECT i.b26_p2_provenance_status, i.b26_p2_semantic_regime
              INTO _prov, _regime
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = _ingress;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF _regime IS DISTINCT FROM 'xvii-sovereign-v1' THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = _ingress
            ) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            -- XX (H-XX-A): the bound source must satisfy the complete
            -- canonical currentness law -- demotion, family-source,
            -- quarantine-adjacent evidence, registry, and floor -- not
            -- just the three clauses above.
            IF NOT public.b26_p2_ingress_has_current_authority(_ingress) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            -- Tenant identity valid.
            IF _tenant IS NULL
               OR NOT EXISTS (
                    SELECT 1 FROM public.tenants AS t WHERE t.id = _tenant
               ) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            -- Canonical execution identity valid: receipt bound, current,
            -- canonically meaningful, policy-current.
            SELECT r.p2_scope_identity, r.policy_semantic_sha256,
                   r.ix_meaning_status
              INTO _receipt_identity, _receipt_policy, _receipt_meaning
              FROM public.b26_p2_conduction_receipts AS r
             WHERE r.task_id = p_task_id;
            IF NOT FOUND THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF _receipt_meaning IS DISTINCT FROM 'canonically_bound' THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF _receipt_policy IS DISTINCT FROM
               'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99' THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            BEGIN
                _live_identity :=
                    public.b26_p2_canonical_scope_identity_for_window(
                        _tenant, _ws, _we
                    );
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END;
            IF _receipt_identity IS DISTINCT FROM _live_identity THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            -- Historical state not quarantined/stale.
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                 WHERE q.task_id = p_task_id
            ) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                 WHERE q.webhook_ingress_identity_id = _ingress
            ) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_prev_guc, ''), true
            );
            RETURN TRUE;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END;
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_prev_guc, ''), true
            );
            RETURN FALSE;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_state_eligible_for_p3(text, uuid)"
        " FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # XX-3b. Consequence provider/source coherence (H-XX-B). The
    # woocommerce transported-topic fallback is removed from the
    # sovereign derivation; enforce the same law at the persistence
    # seam so a direct-atomic caller cannot mint what the derivation
    # refuses. Shopify transport-topic remains admitted (its protocol
    # conveys family outside the signed body) subject to the
    # body-lifecycle guard enforced pre-persistence.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_consequence_family_coherence()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NEW.provider IS DISTINCT FROM 'woocommerce'
               AND NEW.provider IS DISTINCT FROM 'shopify'
               AND NEW.provider IS DISTINCT FROM 'stripe'
               AND NEW.provider IS DISTINCT FROM 'paypal' THEN
                RETURN NEW;
            END IF;
            IF NEW.provider = 'woocommerce'
               AND NEW.b26_p2_family_source = 'transport-topic:x-wc-webhook-topic' THEN
                RAISE EXCEPTION 'b26_p2_woocommerce_transport_family_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_enforce_consequence_family_coherence()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xx_consequence_family_coherence"
        " ON public.b26_p2_provider_auth_consequence"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xx_consequence_family_coherence
        BEFORE INSERT OR UPDATE OF b26_p2_event_family, b26_p2_family_source
        ON public.b26_p2_provider_auth_consequence
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_consequence_family_coherence()
        """
    )
    # floor transitions previously left verdict-local caches positive
    # until an ingress row itself was written. Re-derive dependent
    # verdicts in the same transaction as the law change, reusing the
    # exact XIX propagation pattern (DEFINER, explicit tenant
    # predicate, derive function -- no new privilege).
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # XX-4. Law-change propagation (H-XX-A). Registry retirement and
    # floor transitions previously left verdict-local caches positive
    # until an ingress row itself was written. Re-derive dependent
    # verdicts in the same transaction as the law change, reusing the
    # exact XIX propagation pattern (DEFINER, explicit tenant
    # predicate, derive function -- no new privilege) with one
    # addition the XIX pattern never needed: the law change carries
    # no tenant context (owner administration sets no GUC), while the
    # verdict table enforces FORCE RLS. The function therefore walks
    # the tenant registry explicitly, setting transaction-local tenant
    # context per tenant (saving and restoring the caller's value),
    # so propagation is effective rather than silently empty.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_propagate_verdict_authority_on_regime_change()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _t uuid;
            _prev_guc text;
        BEGIN
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            -- Driver is the tenant registry (no RLS): the ingress and
            -- verdict tables enforce FORCE RLS, so listing affected
            -- tenants from them would fail or silently empty under
            -- owner administration without tenant context. Walk every
            -- tenant with explicit transaction-local context; tenants
            -- without affected rows update zero rows.
            FOR _t IN SELECT t.id FROM public.tenants AS t
            LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.b23_match_verdicts AS v
                   SET b26_p2_source_authority_state =
                       public.b26_p2_derive_verdict_authority(v.webhook_ingress_identity_id)
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.b26_p2_semantic_regime = NEW.regime_id
                   AND v.webhook_ingress_identity_id = i.id
                   AND v.tenant_id = i.tenant_id
                   AND v.tenant_id = _t;
            END LOOP;
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_prev_guc, ''), true
            );
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_propagate_verdict_authority_on_regime_change()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xx_propagate_on_regime_change"
        " ON public.b26_p2_semantic_regime_registry"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xx_propagate_on_regime_change
        AFTER UPDATE OF status ON public.b26_p2_semantic_regime_registry
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_propagate_verdict_authority_on_regime_change()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_propagate_verdict_authority_on_floor_change()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _t uuid;
            _prev_guc text;
        BEGIN
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            -- Driver is the tenant registry (no RLS); see the regime
            -- propagation function for why ingress cannot drive this.
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
            PERFORM set_config(
                'app.current_tenant_id', COALESCE(_prev_guc, ''), true
            );
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION"
        " public.b26_p2_propagate_verdict_authority_on_floor_change()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xx_propagate_on_floor_change"
        " ON public.b26_p2_operational_floor"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xx_propagate_on_floor_change
        AFTER UPDATE ON public.b26_p2_operational_floor
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_propagate_verdict_authority_on_floor_change()
        """
    )

    # ------------------------------------------------------------------
    # XX-5. Tamper-evident supersession chain (H-XX-D). The XIX ledger
    # records prior/new state but carries no integrity chain of its
    # own; rewriting it is invisible to every runtime reader. Chain
    # every append (prev_entry_hash/entry_hash over a documented
    # preimage, serialized by an advisory lock) and backfill pre-XX
    # rows in recorded order. Verification lives in
    # b26_p2_verify_history_protection() below and in the mandatory XX
    # proof plane -- never in the artifact being verified alone.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
        " ADD COLUMN IF NOT EXISTS prev_entry_hash text DEFAULT NULL"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
        " ADD COLUMN IF NOT EXISTS entry_hash text DEFAULT NULL"
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_chain_verdict_supersession()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _prev text;
            _preimage text;
        BEGIN
            -- Serialize chain appends within the transaction scope so
            -- concurrent corrections cannot fork the chain.
            PERFORM pg_advisory_xact_lock(82173645, 300003);
            SELECT l.entry_hash INTO _prev
              FROM public.b26_p2_verdict_supersession_ledger AS l
             ORDER BY l.recorded_at DESC, l.id DESC
             LIMIT 1;
            NEW.prev_entry_hash := _prev;
            _preimage := COALESCE(NEW.verdict_id::text, '')
                || '|' || COALESCE(NEW.prior_attributed_amount_minor::text, 'NULL')
                || '|' || COALESCE(NEW.new_attributed_amount_minor::text, 'NULL')
                || '|' || COALESCE(NEW.prior_verified_amount_minor::text, 'NULL')
                || '|' || COALESCE(NEW.new_verified_amount_minor::text, 'NULL')
                || '|' || COALESCE(NEW.prior_authority_state, 'NULL')
                || '|' || COALESCE(NEW.new_authority_state, 'NULL')
                || '|' || COALESCE(_prev, '');
            NEW.entry_hash :=
                encode(digest(_preimage, 'sha256'), 'hex');
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_chain_verdict_supersession()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xx_supersession_chain"
        " ON public.b26_p2_verdict_supersession_ledger"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xx_supersession_chain
        BEFORE INSERT ON public.b26_p2_verdict_supersession_ledger
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_chain_verdict_supersession()
        """
    )
    # Backfill the chain for pre-XX rows in recorded order. Rows are
    # chained oldest-first; the oldest pre-XX row anchors at ''.
    op.execute(
        """
        DO $$
        DECLARE
            _r record;
            _prev text := NULL;
            _preimage text;
            _hash text;
        BEGIN
            FOR _r IN SELECT l.id, l.verdict_id,
                             l.prior_attributed_amount_minor,
                             l.new_attributed_amount_minor,
                             l.prior_verified_amount_minor,
                             l.new_verified_amount_minor,
                             l.prior_authority_state,
                             l.new_authority_state
                        FROM public.b26_p2_verdict_supersession_ledger AS l
                       WHERE l.entry_hash IS NULL
                       ORDER BY l.recorded_at ASC, l.id ASC
            LOOP
                SELECT l2.entry_hash INTO _prev
                  FROM public.b26_p2_verdict_supersession_ledger AS l2
                 WHERE l2.entry_hash IS NOT NULL
                   AND (l2.recorded_at, l2.id) < (
                       SELECT l3.recorded_at, l3.id
                         FROM public.b26_p2_verdict_supersession_ledger AS l3
                        WHERE l3.id = _r.id
                   )
                 ORDER BY l2.recorded_at DESC, l2.id DESC
                 LIMIT 1;
                _preimage := COALESCE(_r.verdict_id::text, '')
                    || '|' || COALESCE(_r.prior_attributed_amount_minor::text, 'NULL')
                    || '|' || COALESCE(_r.new_attributed_amount_minor::text, 'NULL')
                    || '|' || COALESCE(_r.prior_verified_amount_minor::text, 'NULL')
                    || '|' || COALESCE(_r.new_verified_amount_minor::text, 'NULL')
                    || '|' || COALESCE(_r.prior_authority_state, 'NULL')
                    || '|' || COALESCE(_r.new_authority_state, 'NULL')
                    || '|' || COALESCE(_prev, '');
                _hash := encode(digest(_preimage, 'sha256'), 'hex');
                UPDATE public.b26_p2_verdict_supersession_ledger AS l
                   SET prev_entry_hash = _prev,
                       entry_hash = _hash
                 WHERE l.id = _r.id;
                _prev := _hash;
            END LOOP;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XX-6. Independent history-protection observer (H-XX-D/H-XX-F).
    # A hostile reader runs this function to disprove the integrity
    # claim: it reports disabled protection triggers, runtime-held
    # ledger privileges, publication-chain linkage breaks, and
    # supersession-chain breaks as rows. Empty result = no observed
    # violation. It reads the catalog and recomputes chains; it trusts
    # no ledger content about itself.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_verify_history_protection()
        RETURNS TABLE (violation text)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _role text;
            _missing text;
        BEGIN
            -- 6a. Protection triggers must exist and be enabled. A
            -- non-superuser owner disabling one is the exact F-D vector;
            -- the disable itself is catalog-visible here.
            FOR _missing IN SELECT unnest(ARRAY[
                'trg_b26_p2_xix_supersession_ledger|b23_match_verdicts',
                'trg_b26_p2_xix_ledger_immutable|b26_p2_verdict_supersession_ledger',
                'trg_b26_p2_xix_history_immutable|b26_p2_publication_history',
                'trg_b26_p2_registry_immutable|b26_p2_semantic_regime_registry',
                'trg_b26_p2_xx_supersession_chain|b26_p2_verdict_supersession_ledger',
                'trg_b26_p2_xx_propagate_on_regime_change|b26_p2_semantic_regime_registry',
                'trg_b26_p2_xx_propagate_on_floor_change|b26_p2_operational_floor',
                'trg_b26_p2_xx_consequence_family_coherence|b26_p2_provider_auth_consequence',
                'trg_b26_p2_xix_revoke_on_witness_loss|b26_p2_ingress_auth_witness',
                'trg_b26_p2_xix_revoke_on_witness_loss_update|b26_p2_ingress_auth_witness',
                'trg_b26_p2_xix_revoke_on_provenance_loss|b26_p2_provenance_evidence',
                'trg_b26_p2_xix_revoke_on_provenance_loss_update|b26_p2_provenance_evidence',
                'trg_b26_p2_xix_revoke_on_consequence_loss|b26_p2_provider_auth_consequence',
                'trg_b26_p2_xix_revoke_on_consequence_loss_update|b26_p2_provider_auth_consequence',
                'trg_b26_p2_xix_revoke_on_root_loss|b26_p2_auth_root_evidence',
                'trg_b26_p2_xix_revoke_on_root_loss_update|b26_p2_auth_root_evidence',
                'trg_b26_p2_verdict_authority_stamp|b23_match_verdicts',
                'trg_b26_p2_verdict_authority_propagate|webhook_ingress_identities',
                'trg_b26_p2_verdict_authority_guard|b23_match_verdicts'
            ]) LOOP
                IF NOT EXISTS (
                    SELECT 1 FROM pg_trigger AS t
                    JOIN pg_class AS c ON c.oid = t.tgrelid
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                   WHERE n.nspname = 'public'
                     AND t.tgname = split_part(_missing, '|', 1)
                     AND c.relname = split_part(_missing, '|', 2)
                     AND t.tgenabled = 'O'
                ) THEN
                    violation := 'history_protection_trigger_not_enabled:' || _missing;
                    RETURN NEXT;
                END IF;
            END LOOP;
            -- 6b. No runtime principal may hold mutating privilege on
            -- either ledger or the publication history.
            FOREACH _role IN ARRAY ARRAY[
                'app_user', 'app_ingress', 'app_worker', 'app_relay',
                'app_beat', 'app_dispatch_publisher', 'app_trust_issuer',
                'app_trust_signer'
            ] LOOP
                IF EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = _role
                ) AND (
                    has_table_privilege(_role,
                        'public.b26_p2_verdict_supersession_ledger', 'INSERT')
                    OR has_table_privilege(_role,
                        'public.b26_p2_verdict_supersession_ledger', 'UPDATE')
                    OR has_table_privilege(_role,
                        'public.b26_p2_verdict_supersession_ledger', 'DELETE')
                    OR has_table_privilege(_role,
                        'public.b26_p2_verdict_supersession_ledger', 'TRUNCATE')
                    OR has_table_privilege(_role,
                        'public.b26_p2_publication_history', 'INSERT')
                    OR has_table_privilege(_role,
                        'public.b26_p2_publication_history', 'UPDATE')
                    OR has_table_privilege(_role,
                        'public.b26_p2_publication_history', 'DELETE')
                    OR has_table_privilege(_role,
                        'public.b26_p2_publication_history', 'TRUNCATE')
                ) THEN
                    violation := 'history_ledger_runtime_privilege:' || _role;
                    RETURN NEXT;
                END IF;
            END LOOP;
            -- 6c. Publication-chain linkage: genesis anchors at NULL
            -- prev; every other row's prev must equal a strictly older
            -- row's entry hash; entry hashes must be 64-hex shaped.
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_publication_history AS h
                 WHERE h.entry_hash IS NULL
                    OR h.entry_hash !~ '^[0-9a-f]{64}$'
            ) THEN
                violation := 'publication_chain_hash_misshapen';
                RETURN NEXT;
            END IF;
            IF (SELECT count(*) FROM public.b26_p2_publication_history
                 WHERE prev_entry_hash IS NULL) != 1 THEN
                violation := 'publication_chain_genesis_not_single';
                RETURN NEXT;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_publication_history AS h
                 WHERE h.prev_entry_hash IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM public.b26_p2_publication_history AS p
                        WHERE p.entry_hash = h.prev_entry_hash
                   )
            ) THEN
                violation := 'publication_chain_linkage_broken';
                RETURN NEXT;
            END IF;
            -- 6d. Supersession-chain recomputation: every chained row
            -- must equal the documented preimage digest.
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.entry_hash IS NULL
            ) THEN
                violation := 'supersession_chain_unchained_row';
                RETURN NEXT;
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.entry_hash IS DISTINCT FROM encode(digest(
                       COALESCE(l.verdict_id::text, '')
                       || '|' || COALESCE(l.prior_attributed_amount_minor::text, 'NULL')
                       || '|' || COALESCE(l.new_attributed_amount_minor::text, 'NULL')
                       || '|' || COALESCE(l.prior_verified_amount_minor::text, 'NULL')
                       || '|' || COALESCE(l.new_verified_amount_minor::text, 'NULL')
                       || '|' || COALESCE(l.prior_authority_state, 'NULL')
                       || '|' || COALESCE(l.new_authority_state, 'NULL')
                       || '|' || COALESCE(l.prev_entry_hash, ''),
                       'sha256'), 'hex')
            ) THEN
                violation := 'supersession_chain_digest_mismatch';
                RETURN NEXT;
            END IF;
            -- 6e. Supersession linkage: non-genesis prev must resolve.
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS l
                 WHERE l.prev_entry_hash IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM public.b26_p2_verdict_supersession_ledger AS p
                        WHERE p.entry_hash = l.prev_entry_hash
                   )
            ) THEN
                violation := 'supersession_chain_linkage_broken';
                RETURN NEXT;
            END IF;
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_verify_history_protection()"
        " FROM PUBLIC"
    )
    for _role in _XX_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '%s')"
            " THEN EXECUTE 'GRANT EXECUTE ON FUNCTION"
            " public.b26_p2_verify_history_protection() TO %s';"
            " END IF; END $$;" % (_role, _role)
        )

    # ------------------------------------------------------------------
    # XX-7. Operational floor at this revision (H-XIX-R12 carried
    # forward). The floor stays ahead of predecessor law so the frozen
    # predecessor minting paths fail closed; law-change propagation
    # re-derives dependents in the same transaction.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        ON CONFLICT (id) DO UPDATE SET floor_revision = EXCLUDED.floor_revision
        """ % _XX_FLOOR
    )


def downgrade() -> None:
    # Supported single-step rollback: XX -> 202609300002. Restore the
    # XIX predicate body (family-source condition removed, floor
    # 300002) and the 300002 floor. Every other XX object is retained:
    # the strengthened P3 still resolves against the restored
    # predicate; the law-change propagation triggers still resolve
    # against the retained derive function; the chain columns and
    # verify function are inert audit/observer surface; the revokes are
    # strictly stronger than XIX. No GRANT restores runtime authority
    # writes. Deeper rollback is restore-from-backup territory (boot
    # gate refuses to serve it).
    op.execute(_XX_PREDICATE_XIX_RESTORE)
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        ON CONFLICT (id) DO UPDATE SET floor_revision = EXCLUDED.floor_revision
        """ % _XX_PREDECESSOR_FLOOR
    )
    for _role in _XX_RUNTIME_ROLES:
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
