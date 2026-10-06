"""B2.6-P2 Corrective XIX: non-reconstructible current authority.

H-XIX-R1..R23 (Directive XIX): XVIII proved Skeldir can demote bad history,
recover genuine redelivery, and conduct the lawful replacement. XIX closes
the remaining causal seam: ``current`` was a cached three-column label that
a runtime role could reconstruct (caller-set GUC bearer mark), preserve
(evidence deletion left the predicate true), reinterpret (same-identity law
mutation green at exact-main topology), consume without authentication
(familyless provider-default family), re-mint below the floor (downgrade
re-armed direct DML), and overwrite without history (in-place supersession).

Conservation laws established here (physical identities, not conventions):

    CURRENT FINANCIAL AUTHORITY
        = LIVE EVIDENCE + AUTHENTICATED EVENT SEMANTICS
          + ACTIVE IMMUTABLE SEMANTIC REGIME + VALID IDENTITY BINDING
          + GOVERNED TRANSITION + CURRENT LIFECYCLE STATE
        (b26_p2_ingress_has_current_authority(): the central predicate now
        computes the complete conjunction live from evidence, witness,
        consequence (bound allowlisted family), root evidence, the active
        registry row, and the operational floor. Cached labels alone never
        authorize. NULL/UNKNOWN never authorizes.)

    CALLER CONTEXT IS NEVER AUTHORITY
        (authority-column writes require current_user = migration_owner /
        postgres, i.e. the sovereign SECURITY DEFINER transition or direct
        administration. No session/transaction variable is read by any
        guard. A forged mark cannot authorize a write the guard refuses;
        the privilege layer additionally denies runtime UPDATE on
        authority-bearing columns entirely -- table-level grants removed,
        operational columns re-granted individually.)

    REMOVE JUSTIFICATION -> REMOVE CURRENTNESS, TRANSACTIONALLY
        (AFTER DELETE / family-nulling UPDATE on every justification
        artifact demotes the linked ingress in the same transaction via a
        DEFINER revocation trigger; the existing propagation graph then
        re-derives every dependent verdict. Artifact content is immutable
        to runtime roles by privilege; deletion is conserved by trigger.)

    PUBLISHED LAW IDENTITY = ONE HISTORICALLY IMMUTABLE LAW
        (b26_p2_publication_history: append-only hash-chained ledger;
        registry UPDATE/DELETE only by direct owner administration, never
        through a deputy; CI history arms walk immutable ancestors instead
        of comparing against a mutable branch ref, so exact-main,
        detached, and shallow topologies enforce the same law.)

    FAMILY = AUTHENTICATED EVENT FACT
        (NULL/blank family claims refused at the sovereign transition --
        no provider-default inference; Python derivation requires an
        explicit native signal, or the provider-transported topic for
        providers whose protocol conveys family outside the signed body;
        the family source is recorded on the consequence row.)

    CORRECTION = NEW CURRENT TRUTH + IMMUTABLE OLD AUDIT HISTORY
        (b26_p2_verdict_supersession_ledger: every verdict amount/state/
        link change appends a tamper-evident prior-state record.)

    SUPPORTED DOWNGRADE = NO INVALID AUTHORITY MINTING
        (this migration's downgrade retains the fixed guards, the
        least-privilege revokes, and the complete predicate, and leaves
        the floor ahead of predecessor law so predecessor minting paths
        fail closed. Deep downgrade is restore-from-backup territory:
        serving is physically refused by the construction-authority boot
        gate, not by prose.)

    STATEMENT-SNAPSHOT LINEARIZATION
        (authority writes require READ COMMITTED so every stamp observes
        the latest committed justification; pre-cutover snapshots cannot
        publish post-cutover authority.)

Upgrade is linear (revises 202609300001). Family cutover law: rows minted
before XIX under the governed family-implicit disposition keep their bound
family value tagged xix-backfill:pre-xix-mint (grandfathered, auditable);
every mint at or above XIX requires an explicit authenticated family.
"""

from __future__ import annotations

from alembic import op

revision = "202609300002"
down_revision = "202609300001"
branch_labels = None
depends_on = None

_XIX_REGIME = "xvii-sovereign-v1"
_XIX_CONTRACT_VERSION = "v1"
_XIX_CONTRACT_DIGEST = (
    "c0f7e3b580dcaf91c7221aa522bf3ca968de7dcc8aa2bf0d5f22b6440ba8e924"
)
_XIX_FLOOR = "202609300002"

_XIX_RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)

_XIX_ALLOWLISTED_FAMILIES = (
    "payment_intent.succeeded", "orders.create",
    "payment.sale.completed", "order.completed",
)

_XIX_ALLOWLISTED_FAMILY_SOURCES = (
    "body-signal:type", "body-signal:event_type", "body-signal:status",
    "transport-topic:x-shopify-topic", "transport-topic:x-wc-webhook-topic",
    "xix-backfill:pre-xix-mint",
)


def _roles_sql_list() -> str:
    return ", ".join("'%s'" % r for r in _XIX_RUNTIME_ROLES)


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
    # XIX-1. Least-privilege authority columns (H-XIX-R2).
    # Table-level UPDATE implied column-level UPDATE, so the XVIII
    # column REVOKEs were ineffective. Remove table-level UPDATE from
    # runtime roles entirely, then re-grant UPDATE only on operational
    # (non-authority-bearing) columns to exactly the roles that held
    # effective UPDATE before XIX -- measured on a pristine XVIII lane:
    # ingress -> app_user, app_ingress (table UPDATE); verdicts ->
    # app_worker (table UPDATE); no other runtime role held UPDATE on
    # either table. The role sets are explicit (not derived from live
    # grants) so downgrade excursions and re-upgrades always converge
    # on the same posture; the column lists are catalog-enumerated so
    # the grant set cannot drift from the schema. SELECT/INSERT/DELETE
    # grants are untouched: production code never writes authority
    # columns outside the sovereign DEFINER transition.
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
    # Artifact content is immutable to runtime roles by privilege:
    # justification can be removed (conserved by XIX-6 triggers) but
    # never edited in place outside the sovereign transition.
    for _table in (
        "b26_p2_ingress_auth_witness",
        "b26_p2_provenance_evidence",
        "b26_p2_provider_auth_consequence",
        "b26_p2_auth_root_evidence",
    ):
        for _role in _XIX_RUNTIME_ROLES:
            op.execute(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
                " WHERE rolname = '%s') THEN EXECUTE 'REVOKE INSERT, UPDATE,"
                " DELETE, TRUNCATE ON TABLE public.%s FROM %s';"
                " END IF; END $$;" % (_role, _table, _role)
            )

    # ------------------------------------------------------------------
    # XIX-2. Non-forgeable transition guards (H-XIX-R1/R6/R21).
    # No guard reads caller-set session/transaction state: authority
    # requires current_user = migration_owner / postgres, i.e. the
    # sovereign SECURITY DEFINER transition executing as its owner, or
    # direct administration. The verdict guard additionally admits only
    # the value the central derivation computes for the linked source:
    # asserting a true projection is harmless, asserting anything else
    # is refused -- so no deputy path can forge consequence authority
    # regardless of privilege composition. Both guards require READ
    # COMMITTED so stamps observe the latest committed justification
    # (statement-snapshot linearization, H-XIX-R15).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_authority_transition()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            -- XIX: caller-supplied context (GUCs, headers, arguments)
            -- transports facts; it never constitutes authority. Only
            -- the sovereign transition (owner execution context) or
            -- direct administration may write authority state.
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            IF current_user IS DISTINCT FROM 'migration_owner'
               AND current_user IS DISTINCT FROM 'postgres' THEN
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
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_guard_verdict_authority_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _link_tenant uuid;
            _link_provider text;
            _link_ref text;
            _derived text;
        BEGIN
            IF current_setting('transaction_isolation', true)
               IS DISTINCT FROM 'read committed' THEN
                RAISE EXCEPTION 'b26_p2_authority_snapshot_not_linearizable'
                    USING ERRCODE = '42501';
            END IF;
            -- Relink re-derivation (lineage-bound, unchanged): a relink
            -- is a lineage claim verified against the new source, and
            -- the state is always recomputed -- never caller-asserted.
            IF NEW.webhook_ingress_identity_id
                   IS DISTINCT FROM OLD.webhook_ingress_identity_id THEN
                IF NEW.webhook_ingress_identity_id IS NOT NULL THEN
                    SELECT i.tenant_id, i.provider,
                           i.provider_native_event_reference
                      INTO _link_tenant, _link_provider, _link_ref
                      FROM public.webhook_ingress_identities AS i
                     WHERE i.id = NEW.webhook_ingress_identity_id;
                    IF NOT FOUND
                       OR _link_tenant IS DISTINCT FROM NEW.tenant_id
                       OR _link_provider IS DISTINCT FROM NEW.provider
                       OR _link_ref IS DISTINCT FROM
                          NEW.provider_native_event_reference THEN
                        RAISE EXCEPTION
                            'b26_p2_verdict_relink_lineage_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                NEW.b26_p2_source_authority_state :=
                    public.b26_p2_derive_verdict_authority(
                        NEW.webhook_ingress_identity_id);
                RETURN NEW;
            END IF;
            -- XIX: state-only writes are admitted iff they equal the
            -- deterministic projection of the linked source. A forged
            -- 'current' for a non-current source differs from the
            -- derivation and is refused; asserting the true projection
            -- is harmless. No identity token is consulted.
            _derived := public.b26_p2_derive_verdict_authority(
                NEW.webhook_ingress_identity_id);
            IF NEW.b26_p2_source_authority_state
                   IS DISTINCT FROM _derived THEN
                RAISE EXCEPTION 'b26_p2_verdict_authority_write_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIX-3. Family source binding (H-XIX-R7).
    # The consequence row records WHICH authenticated evidence
    # established the family: a body-native signal key, or the
    # provider-transported topic for protocols that convey family
    # outside the signed body. Pre-XIX bound rows are tagged by the
    # backfill below (cutover law: grandfathered, auditable).
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b26_p2_provider_auth_consequence"
        " ADD COLUMN IF NOT EXISTS b26_p2_family_source text DEFAULT NULL"
    )
    op.execute(
        """
        DO $$
        DECLARE _t uuid;
        BEGIN
            FOR _t IN SELECT id FROM public.tenants LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.b26_p2_provider_auth_consequence AS c
                   SET b26_p2_family_source = 'xix-backfill:pre-xix-mint'
                  WHERE c.tenant_id = _t
                    AND c.b26_p2_event_family IS NOT NULL
                    AND c.b26_p2_family_source IS NULL;
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIX-4. Operational floor at this revision (H-XIX-R12).
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO public.b26_p2_operational_floor AS f (id, floor_revision)
        VALUES (1, '%s')
        ON CONFLICT (id) DO UPDATE SET floor_revision = EXCLUDED.floor_revision
        """ % _XIX_FLOOR
    )

    # ------------------------------------------------------------------
    # XIX-5. Complete current-authority predicate (H-XIX-R3/R8/R20).
    # CURRENT = marker conjunction + live witness + live provenance
    # evidence + live consequence with bound allowlisted family + live
    # root evidence + active registry row for the bound regime +
    # operational floor at this revision. Registry status is runtime
    # authority (Model A): retiring a regime transactionally ends the
    # currentness of every row bound to it. 3VL discipline preserved:
    # every clause must be positively true; NULL/UNKNOWN never
    # authorizes (NOT EXISTS is false on NULL family).
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
    )

    # ------------------------------------------------------------------
    # XIX-6. Continuous evidence conservation (H-XIX-R4/R9/R22).
    # Removing a justification demotes the linked ingress in the same
    # transaction (reason-only write: prov_status untouched, so the
    # provenance downgrade bar is not tripped; the propagation graph
    # then re-derives every dependent verdict). Runs as DEFINER owner
    # so the revocation cannot be fenced by caller privilege.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_revoke_authority_on_evidence_loss()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _ingress uuid;
            _tenant uuid;
            _cause text;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                _ingress := OLD.webhook_ingress_identity_id;
                _tenant := OLD.tenant_id;
            ELSE
                _ingress := NEW.webhook_ingress_identity_id;
                _tenant := NEW.tenant_id;
            END IF;
            _cause := COALESCE(TG_ARGV[0], 'evidence-loss');
            UPDATE public.webhook_ingress_identities AS i
               SET b26_p2_demotion_reason = 'xix-evidence-revoked:' || _cause
             WHERE i.id = _ingress
               AND i.tenant_id = _tenant
               AND i.b26_p2_demotion_reason IS NULL;
            RETURN COALESCE(NEW, OLD);
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_revoke_authority_on_evidence_loss()"
        " FROM PUBLIC"
    )
    for _spec in (
        ("b26_p2_ingress_auth_witness", "witness-loss"),
        ("b26_p2_provenance_evidence", "provenance-loss"),
        ("b26_p2_provider_auth_consequence", "consequence-loss"),
        ("b26_p2_auth_root_evidence", "root-loss"),
    ):
        _table, _cause = _spec
        op.execute(
            "DROP TRIGGER IF EXISTS trg_b26_p2_xix_revoke_on_%s"
            " ON public.%s" % (_cause.replace("-", "_"), _table)
        )
        op.execute(
            """
            CREATE TRIGGER trg_b26_p2_xix_revoke_on_%s
            AFTER DELETE OR UPDATE ON public.%s
            FOR EACH ROW EXECUTE FUNCTION
            public.b26_p2_revoke_authority_on_evidence_loss('%s')
            """ % (_cause.replace("-", "_"), _table, _cause)
        )
    # Family nullification is justification loss even when the row
    # survives: a consequence row without a bound family cannot justify
    # currentness (the predicate requires a bound allowlisted family).
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_revoke_on_family_unbound"
        " ON public.b26_p2_provider_auth_consequence"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xix_revoke_on_family_unbound
        AFTER UPDATE OF b26_p2_event_family
        ON public.b26_p2_provider_auth_consequence
        FOR EACH ROW
        WHEN (NEW.b26_p2_event_family IS NULL)
        EXECUTE FUNCTION
        public.b26_p2_revoke_authority_on_evidence_loss('family-unbound')
        """
    )

    # ------------------------------------------------------------------
    # XIX-7. Immutable supersession ledger (H-XIX-R11).
    # Every verdict amount/state/link change appends a tamper-evident
    # prior-state record. Append-only: UPDATE/DELETE refused for every
    # principal including administration (corrections are new rows).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_verdict_supersession_ledger (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            verdict_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            provider text NOT NULL,
            provider_native_event_reference text NOT NULL,
            prior_attributed_amount_minor integer,
            new_attributed_amount_minor integer,
            prior_verified_amount_minor integer,
            new_verified_amount_minor integer,
            prior_authority_state text,
            new_authority_state text,
            prior_source_ingress uuid,
            new_source_ingress uuid,
            semantic_regime text NOT NULL DEFAULT 'xvii-sovereign-v1',
            recorded_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_verdict_supersession_ledger FROM PUBLIC"
    )
    for _role in _XIX_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'GRANT SELECT ON TABLE"
            " public.b26_p2_verdict_supersession_ledger TO %s';"
            " END IF; END $$;" % (_role, _role)
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_verdict_supersession()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP <> 'UPDATE' THEN
                RETURN NEW;
            END IF;
            IF OLD.attributed_amount_minor
                   IS NOT DISTINCT FROM NEW.attributed_amount_minor
               AND OLD.verified_amount_minor
                   IS NOT DISTINCT FROM NEW.verified_amount_minor
               AND OLD.b26_p2_source_authority_state
                   IS NOT DISTINCT FROM NEW.b26_p2_source_authority_state
               AND OLD.webhook_ingress_identity_id
                   IS NOT DISTINCT FROM NEW.webhook_ingress_identity_id THEN
                RETURN NEW;
            END IF;
            INSERT INTO public.b26_p2_verdict_supersession_ledger (
                verdict_id, tenant_id, provider,
                provider_native_event_reference,
                prior_attributed_amount_minor, new_attributed_amount_minor,
                prior_verified_amount_minor, new_verified_amount_minor,
                prior_authority_state, new_authority_state,
                prior_source_ingress, new_source_ingress
            ) VALUES (
                NEW.id, NEW.tenant_id, NEW.provider,
                NEW.provider_native_event_reference,
                OLD.attributed_amount_minor, NEW.attributed_amount_minor,
                OLD.verified_amount_minor, NEW.verified_amount_minor,
                OLD.b26_p2_source_authority_state,
                NEW.b26_p2_source_authority_state,
                OLD.webhook_ingress_identity_id,
                NEW.webhook_ingress_identity_id
            );
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_verdict_supersession()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_supersession_ledger"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xix_supersession_ledger
        AFTER UPDATE ON public.b23_match_verdicts
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_record_verdict_supersession()
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ledger_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF current_user IS DISTINCT FROM 'migration_owner'
                   AND current_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_ledger_insert_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'b26_p2_ledger_history_immutable_refused'
                USING ERRCODE = '42501';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_ledger_immutability()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_ledger_immutable"
        " ON public.b26_p2_verdict_supersession_ledger"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xix_ledger_immutable
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.b26_p2_verdict_supersession_ledger
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_ledger_immutability()
        """
    )

    # ------------------------------------------------------------------
    # XIX-8. Publication-history ledger + governed registry lifecycle
    # (H-XIX-R5/R6/R8). Append-only hash-chained publication history
    # covering every published law identity (semantic regime,
    # event-family law, contract hierarchy):
    # entry_hash = sha256(law_kind|law_id|law_version|law_digest
    #                     |activation_revision|prev_entry_hash).
    # UNIQUE(law_kind, law_id, law_version) makes a same-identity
    # meaning change PHYSICALLY impossible at the database layer:
    # lawful evolution appends a new version, never rewrites one.
    # Registry writes require direct owner administration (both
    # current_user and session_user are the owner): no DEFINER deputy
    # can retire or rewrite publication law. Status transitions remain
    # possible via forward migration (R1 -> R2 evolution), and the
    # predicate honors them transactionally (Model A).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_publication_history (
            law_kind text NOT NULL,
            law_id text NOT NULL,
            law_version text NOT NULL,
            law_digest text NOT NULL,
            activation_revision text NOT NULL,
            prev_entry_hash text,
            entry_hash text NOT NULL,
            recorded_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT b26_p2_publication_digest_shape
                CHECK (char_length(law_digest) = 64),
            CONSTRAINT b26_p2_publication_hash_shape
                CHECK (char_length(entry_hash) = 64),
            PRIMARY KEY (law_kind, law_id, law_version, entry_hash),
            CONSTRAINT b26_p2_publication_identity_single_valued
                UNIQUE (law_kind, law_id, law_version)
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_publication_history FROM PUBLIC"
    )
    for _role in _XIX_RUNTIME_ROLES:
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'GRANT SELECT ON TABLE"
            " public.b26_p2_publication_history TO %s';"
            " END IF; END $$;" % (_role, _role)
        )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_history_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF current_user IS DISTINCT FROM 'migration_owner'
                   AND current_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_history_insert_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'b26_p2_history_immutable_refused'
                USING ERRCODE = '42501';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_history_immutability()"
        " FROM PUBLIC"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_history_immutable"
        " ON public.b26_p2_publication_history"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_xix_history_immutable
        BEFORE INSERT OR UPDATE OR DELETE
        ON public.b26_p2_publication_history
        FOR EACH ROW EXECUTE FUNCTION
        public.b26_p2_enforce_history_immutability()
        """
    )
    # Genesis chain (prev-linked; literals computed under the documented
    # preimage law_kind|law_id|law_version|law_digest|activation|prev):
    # semantic regime R1, family-law v1, hierarchy v1 (activated by
    # XVIII/300001), then family-law v2, hierarchy v2 (activated here).
    op.execute(
        """
        INSERT INTO public.b26_p2_publication_history AS h (
            law_kind, law_id, law_version, law_digest,
            activation_revision, prev_entry_hash, entry_hash
        )
        VALUES
        ('semantic-regime', 'xvii-sovereign-v1', 'v1',
         'c0f7e3b580dcaf91c7221aa522bf3ca968de7dcc8aa2bf0d5f22b6440ba8e924',
         '202609300001', NULL,
         '2ac2b6bf88829f5c3a4ce72d0bfb4b481419779a31651ec94c5ba21f82fb131c'),
        ('event-family-law', 'b26-p2-event-family-law', 'v1',
         'a06e0001a22dbc1620e0f468857828817400aa5a1416dab21d337e75321cac18',
         '202609300001',
         '2ac2b6bf88829f5c3a4ce72d0bfb4b481419779a31651ec94c5ba21f82fb131c',
         '39d7b8b9340b22ae4c690af28503107d0676657e21f30a048d30827fec6ed2e3'),
        ('contract-hierarchy', 'b26-p2-contract-hierarchy', 'v1',
         '5015beea4be1b91095147a792e90e4ca90ce9cc34e535407e419abbee9366b24',
         '202609300001',
         '39d7b8b9340b22ae4c690af28503107d0676657e21f30a048d30827fec6ed2e3',
         '73de49425c20e322cede432eb349c2bcd2d05a76c7b13322eb1e12b5baab5e15'),
        ('event-family-law', 'b26-p2-event-family-law', 'v2',
         '8ad0cbb85ac3747a119f261f4db68d14029e0ddee5effddc3f423010c5f76d01',
         '202609300002',
         '73de49425c20e322cede432eb349c2bcd2d05a76c7b13322eb1e12b5baab5e15',
         '069d1df4d397f10cc73df8b63c06aa7ca2d5add7b6e23fefe5b17a756a08299d'),
        ('contract-hierarchy', 'b26-p2-contract-hierarchy', 'v2',
         '779a39fc1b2b61b77e5c34da125aeec05a460a0fd287186d9d6e73ac41a1a4a8',
         '202609300002',
         '069d1df4d397f10cc73df8b63c06aa7ca2d5add7b6e23fefe5b17a756a08299d',
         'd1696cde33d46304e2a62794b2edd58b168e0af157050754634a9ef34f3c3097')
        ON CONFLICT ON CONSTRAINT b26_p2_publication_identity_single_valued
        DO NOTHING
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_registry_governance()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            -- XIX: publication law changes only by direct owner
            -- administration (forward migration). A DEFINER deputy
            -- (current_user = owner, session_user = caller) cannot
            -- satisfy both conjuncts.
            IF current_user IS DISTINCT FROM 'migration_owner'
               AND current_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_registry_mutation_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_registry_deputy_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN COALESCE(NEW, OLD);
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_registry_governance()"
        " FROM PUBLIC"
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
        public.b26_p2_enforce_registry_governance()
        """
    )


    # ------------------------------------------------------------------
    # XIX-9. Sovereign atomic at XIX law (H-XIX-R7/R12/R15).
    # Changes from XVIII: (a) floor revision 202609300002; (b) absent
    # or blank family claims are REFUSED
    # (b26_p2_atomic_family_unbound_refused) -- no provider-default
    # inference; every positive family assertion must arrive as an
    # explicit root-supplied claim; (c) the claim's evidence source
    # travels in app.b26_p2_event_family_source (strict allowlist) and
    # is bound into the consequence row; (d) the bearer mark is gone:
    # the stamp needs no exemption because the guard admits owner
    # execution context, which the DEFINER transition inherently has;
    # (e) authority writes require READ COMMITTED (linearization).
    # ------------------------------------------------------------------
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
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_atomic_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- XIX floor: a downgraded schema (floor row/table absent or
            -- behind) cannot mint authority.
            BEGIN
                PERFORM 1 FROM public.b26_p2_operational_floor AS f
                 WHERE f.id = 1 AND f.floor_revision = '202609300002';
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
        END $$;
        """
    )
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
        " WHERE rolname = 'app_ingress') THEN EXECUTE 'GRANT EXECUTE ON"
        " FUNCTION public.b26_p2_authenticate_ingress_atomic("
        "uuid, text, text, text, text, text, text) TO app_ingress';"
        " END IF; END $$;"
    )

    # ------------------------------------------------------------------
    # XIX-10. Legacy attester at XIX law (H-XIX-R7/R12/R15).
    # Same changes as the atomic: floor 202609300002, absent family
    # refused (no default), family source allowlisted and bound, no
    # bearer mark, READ COMMITTED linearization.
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
            IF session_user NOT IN (
                'app_ingress', 'migration_owner', 'postgres'
            ) THEN
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
                 WHERE f.id = 1 AND f.floor_revision = '202609300002';
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
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIX-11. Dispatch reads the single central law (H-XIX-R9).
    # The marker conjunction is replaced by the complete predicate so
    # dispatch can never disagree with batch/coverage/Trust reads; the
    # family/witness/quarantine/root checks remain as defense in depth.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_provenance()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _family text;
            _witness text;
        BEGIN
            IF NOT public.b26_p2_ingress_has_current_authority(
                NEW.webhook_ingress_identity_id) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_source_not_current'
                    USING ERRCODE = '42501';
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
            IF NOT EXISTS (
                SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                 WHERE r.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
            ) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_root_missing' USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )


def downgrade() -> None:
    # Single-step supported downgrade: authority-safe retention. The
    # fixed guards, the least-privilege revokes, and the complete
    # predicate are RETAINED (they reference only XVIII-schema objects);
    # the floor stays ahead of predecessor law so predecessor minting
    # paths fail closed; XIX-only revocation/ledger/history triggers
    # and functions are removed while their tables are retained as
    # audit history. No GRANT restores runtime authority writes.
    for _table, _cause in (
        ("b26_p2_ingress_auth_witness", "witness_loss"),
        ("b26_p2_provenance_evidence", "provenance_loss"),
        ("b26_p2_provider_auth_consequence", "consequence_loss"),
        ("b26_p2_auth_root_evidence", "root_loss"),
    ):
        op.execute(
            "DROP TRIGGER IF EXISTS trg_b26_p2_xix_revoke_on_%s"
            " ON public.%s" % (_cause.replace("-", "_"), _table)
        )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_revoke_on_family_unbound"
        " ON public.b26_p2_provider_auth_consequence"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_revoke_authority_on_evidence_loss()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_supersession_ledger"
        " ON public.b23_match_verdicts"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_verdict_supersession()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_ledger_immutable"
        " ON public.b26_p2_verdict_supersession_ledger"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_ledger_immutability()"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_xix_history_immutable"
        " ON public.b26_p2_publication_history"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_history_immutability()"
    )
    # Restore the insert-only registry bar on the way down (retirement
    # resumes only at or above XIX): direct-owner writes refused again
    # except fresh governed inserts.
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
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_registry_governance()"
    )
    # Re-assert the least-privilege posture (idempotent): a downgrade
    # must never re-arm runtime authority writes.
    for _role in (
        "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
        "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
    ):
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'REVOKE UPDATE"
            " (b26_p2_provenance_status, b26_p2_semantic_regime,"
            " b26_p2_demotion_reason)"
            " ON public.webhook_ingress_identities FROM %s';"
            " END IF; END $$;" % (_role, _role)
        )
        op.execute(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles"
            " WHERE rolname = '%s') THEN EXECUTE 'REVOKE UPDATE"
            " (b26_p2_source_authority_state)"
            " ON public.b23_match_verdicts FROM %s';"
            " END IF; END $$;" % (_role, _role)
        )
