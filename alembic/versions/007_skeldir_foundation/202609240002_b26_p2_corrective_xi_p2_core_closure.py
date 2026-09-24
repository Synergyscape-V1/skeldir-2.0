"""B2.6-P2 Corrective XI: P2-core closure for P3 predecessor trust.

Revision ID: 202609240002
Revises: 202609240001

Tightly scoped P2-core closure (NOT general hardening). Closes exactly the
four residual deterministic truth classes blocking P3:

A. AUTHENTICATION PROVENANCE. ``unknown`` ingress could become
   ``authenticated_known`` through an application assertion (direct attester
   call binding the row's own idempotency key, no provider evidence). XI
   requires a deterministic authentication witness that only the governed
   authenticated-ingress consequence can create:
   ``b26_p2_ingress_auth_witness`` rows are authored solely by
   ``b26_p2_record_ingress_auth_witness`` (EXECUTE app_ingress only), and
   ``b26_p2_attest_provenance_evidence`` promotes only when a witness
   exists. Representation is not authentication evidence.

B. INGRESS CAPABILITY ISOLATION. ``app_user`` combined ordinary
   application authority with authentication-authoring authority, and the
   generic worker inherited the API DSN. XI introduces the dedicated
   ``app_ingress`` login: only ``app_ingress``/``migration_owner``/
   ``postgres`` may author ``authenticity_verified`` or execute the
   witness/attester. The generic worker no longer holds the API DSN
   (Procfile pins ``DATABASE_URL=$WORKER_DATABASE_URL``). ``app_ingress``
   holds ingress-only grants: it cannot write B2.3 verdicts, mark P2
   conducted, mutate policy, cross tenants, or sign TrustEnvelopes.

   Predecessor-compatible topology rule: the strict allowlists above
   apply where the ingress principal exists (every governed lane and
   the shipped topology; role existence is a catalog fact, and the XI
   isolation validator REDs on the missing principal wherever XI is
   adjudicated). Lanes that never provision the role keep Corrective-X
   semantics bit-for-bit (verified live on a role-less cluster). No
   governed lane can silently lack strict isolation.

C. SEMANTIC -> TEMPORAL TOTALITY. Canonical P2 semantics live in SQL, so
   SQL-side semantic dependencies must enter temporal/version governance.
   XI adds the generated semantic-dependency manifest mechanism
   (``validate_b26_p2_xi_semantic_temporal`` derives the live SQL read-set
   from ``pg_proc`` and requires every read to be covered by a temporal
   trigger ``UPDATE OF`` list or an explicit treatment; unknown reads RED).
   Current semantic columns remain trigger-governed (verdict conservation
   + ingress custody); post-conduction semantic mutation is refused until
   the sanctioned re-adjudication path runs. XI does not merely list
   ``match_quality``: any new SQL read without temporal treatment REDs.

D. HISTORICAL INVARIANT TOTALITY. The census is the CURRENT invariant
   universe evaluated over final truth-capable state (generic oracle
   ``b26_p2_xi_invariant_oracle``), not the migration's repair branches.
   Witnessless authenticated rows, garbage policy-sha receipts, divergent
   terminal twins, blank foundations, and stale bindings are quarantined
   (ingress-level quarantine included) or the migration fails. The
   migration classifies/quarantines uncertainty; it never manufactures
   provenance or semantic certainty (no witness backfill).

P3 ELIGIBILITY. ``b26_p2_state_eligible_for_p3(task)`` mechanically
defines P2 state eligible for P3 reasoning (authenticated + witnessed +
tenant-valid + canonically bound + policy-current + fresh +
non-quarantined). P3 consumes it; P3 cannot override it.

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved.
"""

from __future__ import annotations

from alembic import op

revision = "202609240002"
down_revision = "202609240001"
branch_labels = None
depends_on = None

_POLICY_VERSION = "b2.6-p2-scope-policy-v2"
_POLICY_SEMANTIC_SHA = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)


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
        "LOCK TABLE public.b26_p2_provenance_evidence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XI1. Dedicated authenticated-ingress principal. Ordinary callers
    # cannot construct its capability: EXECUTE on the witness/attester
    # is granted to app_ingress alone (plus migration admins), and the
    # authorship triggers below key on session_user, which SET ROLE
    # cannot forge (no membership grants are created here).
    #
    # Role lifecycle note: migrations never CREATE ROLE (many lanes
    # migrate under identities without CREATEROLE). The governed
    # provisioner (prepare_migration_authority_boundary.py) creates
    # the app_ingress login; every grant below is existence-guarded
    # so role-less lanes still migrate. Lanes without the role run
    # predecessor-compatible ingestion semantics; the XI isolation
    # validator REDs on the missing principal wherever XI is
    # adjudicated, so no governed lane can silently lack it.
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT USAGE ON SCHEMA public TO app_ingress;
            ELSE
                RAISE NOTICE 'b26_p2_xi_no_ingress_role:predecessor_compatible_lane';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                REVOKE ALL ON TABLE public.b26_p2_provenance_evidence FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_conduction_receipts FROM app_ingress;
                REVOKE ALL ON TABLE public.b23_match_task_dispatches FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_execution_outbox FROM app_ingress;
                REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_ingress;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XI2. Authentication witness relation. A witness row proves a
    # governed authenticated-ingress consequence ran; it is unforgeable
    # because no runtime principal holds INSERT on this table -- rows
    # appear only through the SECURITY DEFINER witness function, whose
    # EXECUTE is held by app_ingress (and migration admins) alone.
    # The witness token is random per ingress (gen_random_uuid entropy
    # folded through sha256); it is a capability, never a secret, and
    # no raw provider secret material is retained anywhere.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_ingress_auth_witness (
            webhook_ingress_identity_id uuid NOT NULL PRIMARY KEY
                REFERENCES public.webhook_ingress_identities(id)
                ON DELETE CASCADE,
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            witness_hash text NOT NULL
                CONSTRAINT ck_b26_p2_witness_hash_not_blank
                CHECK (char_length(witness_hash) > 0),
            witnessed_at timestamptz NOT NULL DEFAULT now(),
            witnessed_by name NOT NULL,
            CONSTRAINT fk_b26_p2_witness_tenant_ingress
                FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                REFERENCES public.webhook_ingress_identities(tenant_id, id)
                ON DELETE CASCADE
        )
        """
    )
    # Default privileges grant SELECT,INSERT on new tables to app_user;
    # the witness must be unforgeable, so strip every runtime grant.
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_ingress_auth_witness FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        DECLARE _r text;
        BEGIN
            FOREACH _r IN ARRAY ARRAY[
                'app_user', 'app_worker', 'app_relay', 'app_beat',
                'app_rw', 'app_ro', 'app_ingress',
                'app_dispatch_publisher', 'app_celery_transport'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _r) THEN
                    EXECUTE format(
                        'REVOKE ALL ON TABLE public.b26_p2_ingress_auth_witness FROM %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_ingress_auth_witness ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_ingress_auth_witness FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_ingress_auth_witness'
                   AND policyname = 'tenant_isolation_policy_b26_p2_ingress_auth_witness'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_ingress_auth_witness
                    ON public.b26_p2_ingress_auth_witness
                    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
                    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_ingress_auth_witness(
            p_ingress uuid
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
            _provider text;
            _existing text;
            _witness text;
            _prev_guc text;
        BEGIN
            -- H-R6: SECURITY DEFINER context is bounded explicitly.
            -- Only the ingress principal (and migration admins) may
            -- author authentication evidence. session_user cannot be
            -- forged with SET ROLE (no membership exists). The
            -- ingress role is provisioned by the governed provisioner;
            -- lanes that never provision it cannot reach this
            -- function (no EXECUTE grant exists for them there).
            IF session_user NOT IN ('app_ingress', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_witness_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider
              INTO _tenant, _idem, _state, _provider
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_witness_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            IF _state IS DISTINCT FROM 'authenticity_verified' THEN
                RAISE EXCEPTION 'b26_p2_witness_ingress_unverified'
                    USING ERRCODE = '42501';
            END IF;
            -- H-R5: three-valued SQL is fail-closed. Blank shape can
            -- never carry authentication evidence.
            IF public.b26_p2_ascii_strip(COALESCE(_provider, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_witness_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT w.witness_hash INTO _existing
              FROM public.b26_p2_ingress_auth_witness AS w
             WHERE w.webhook_ingress_identity_id = p_ingress;
            IF FOUND THEN
                RETURN _existing;
            END IF;
            _witness := encode(
                digest(
                    gen_random_uuid()::text || '|' || p_ingress::text
                    || '|' || _tenant::text || '|' || COALESCE(_idem, ''),
                    'sha256'
                ),
                'hex'
            );
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                INSERT INTO public.b26_p2_ingress_auth_witness AS w (
                    webhook_ingress_identity_id, tenant_id,
                    witness_hash, witnessed_by
                )
                VALUES (p_ingress, _tenant, _witness, session_user)
                ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                SELECT w.witness_hash INTO _existing
                  FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress;
                RETURN _existing;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RAISE;
            END;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid)
                    TO app_ingress;
            END IF;
        END $$;
        """
    )
    # Least privilege: the witness table is written only by the
    # definer function (owner writes bypass caller grants). Readers:
    # none at the table level; the attester/eligibility functions
    # (definer) observe it. No runtime SELECT grant is issued.
    op.execute(
        "ALTER TABLE public.b26_p2_provenance_evidence ADD COLUMN IF NOT EXISTS evidence_witness_hash text"
    )

    # ------------------------------------------------------------------
    # XI3. Evidence-backed attestation (BLOCKER CLASS A law). UNKNOWN
    # becomes AUTHENTICATED only because a governed authentication
    # consequence exists: caller must be the ingress principal AND a
    # witness row must exist for the ingress. Caller assertions alone
    # promote nothing. Genuine signed re-ingestion restores authority
    # by recording a witness first, then attesting.
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
            _prov text;
            _witness text;
            _prev_guc text;
        BEGIN
            -- H-R1 principal separation with predecessor-compatible
            -- topology rule: where the dedicated ingress principal
            -- exists (every governed lane and the shipped topology),
            -- ordinary application authority (app_user) can no longer
            -- author authentication evidence, even with a valid ref.
            -- Lanes that never provision the role keep predecessor
            -- (Corrective X) semantics bit-for-bit; the XI isolation
            -- validator REDs on the missing principal wherever XI is
            -- adjudicated, so no governed lane can silently lack it.
            -- Role existence is a catalog fact, not caller discipline.
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                IF session_user NOT IN (
                    'app_ingress', 'migration_owner', 'postgres'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                IF session_user NOT IN (
                    'app_user', 'migration_owner', 'postgres'
                ) THEN
                    RAISE EXCEPTION 'b26_p2_evidence_caller_refused'
                        USING ERRCODE = '42501';
                END IF;
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
            -- The authentication consequence: a witness row created by
            -- the ingress boundary. No witness, no promotion -- the
            -- claim "authentication happened" is not evidence. On
            -- predecessor-compatible lanes (no ingress role) the
            -- Corrective-X evidence rule applies unchanged.
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                SELECT w.witness_hash INTO _witness
                  FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_evidence_witness_missing'
                        USING ERRCODE = '42501';
                END IF;
            ELSE
                _witness := NULL;
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
                    evidence_kind, evidence_ref, evidence_witness_hash
                )
                VALUES (p_ingress, _tenant, p_kind, p_ref, _witness)
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    evidence_kind = EXCLUDED.evidence_kind,
                    evidence_ref = EXCLUDED.evidence_ref,
                    evidence_witness_hash = EXCLUDED.evidence_witness_hash,
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
            -- Predecessor-compatible topology rule: the EXECUTE
            -- grant follows the same role census as the trigger
            -- allowlists, so lanes without the ingress principal keep
            -- Corrective-X attestation semantics bit-for-bit.
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                    REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text)
                        FROM app_user;
                END IF;
                GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text)
                    TO app_ingress;
            ELSE
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                    GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text)
                        TO app_user;
                END IF;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XI4. Ingress authorship isolation (BLOCKER CLASS B law). Only the
    # process boundary that verifies provider authentication (the API
    # ingress path on the dedicated ingress credential) may create
    # authentication-authoritative durable state. Generic workers hold
    # no such capability: they fail into unknown_legacy (fail-closed),
    # never into authority.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_verified_authorship()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _authors text[];
        BEGIN
            -- Predecessor-compatible topology rule (see attester):
            -- strict ingress authorship where the role exists,
            -- Corrective-X authorship otherwise.
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                _authors := ARRAY['app_ingress', 'migration_owner', 'postgres'];
            ELSE
                _authors := ARRAY['app_user', 'migration_owner', 'postgres'];
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                    AND NOT (session_user = ANY (_authors)) THEN
                    RAISE EXCEPTION 'b26_p2_verified_authorship_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.verified_commerce_ingress_state IS DISTINCT FROM
               OLD.verified_commerce_ingress_state THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                    AND NOT (session_user = ANY (_authors)) THEN
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
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_provenance()
        RETURNS trigger
        LANGUAGE plpgsql SET search_path TO 'pg_catalog', 'public' AS $$
        DECLARE
            _authors text[];
        BEGIN
            -- Predecessor-compatible topology rule (see attester).
            IF EXISTS (
                SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
            ) THEN
                _authors := ARRAY['app_ingress', 'migration_owner', 'postgres'];
            ELSE
                _authors := ARRAY['app_user', 'migration_owner', 'postgres'];
            END IF;
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    NEW.b26_p2_provenance_status := 'pending_not_applicable';
                    RETURN NEW;
                END IF;
                -- XI law: verified authorship is ingress-isolated
                -- where the role exists. Non-ingress verified writes
                -- are refused at the authorship trigger; this trigger
                -- stays consistent by marking only ingress-authored
                -- rows known.
                IF session_user = ANY (_authors) THEN
                    NEW.b26_p2_provenance_status := 'authenticated_known';
                ELSE
                    NEW.b26_p2_provenance_status := 'unknown_legacy';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                   AND NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    IF session_user = ANY (_authors) THEN
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
                    -- XI law: promotion requires witness-backed
                    -- evidence, never a bare status write and never a
                    -- witnessless evidence echo. H-R5: NULL witness
                    -- is not FALSE evidence; IS DISTINCT FROM keeps
                    -- UNKNOWN from becoming TRUE. On
                    -- predecessor-compatible lanes the Corrective-X
                    -- evidence rule applies unchanged.
                    IF OLD.b26_p2_provenance_status = 'unknown_legacy'
                       AND NEW.b26_p2_provenance_status = 'authenticated_known'
                       AND NOT (
                            EXISTS (
                                SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                                 WHERE e.webhook_ingress_identity_id = OLD.id
                                   AND e.evidence_witness_hash IS NOT NULL
                                   AND char_length(e.evidence_witness_hash) > 0
                                   AND EXISTS (
                                        SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                                         WHERE w.webhook_ingress_identity_id = OLD.id
                                           AND w.witness_hash IS NOT DISTINCT FROM e.evidence_witness_hash
                                   )
                            )
                            OR (
                                NOT EXISTS (
                                    SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress'
                                )
                                AND EXISTS (
                                    SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                                     WHERE e.webhook_ingress_identity_id = OLD.id
                                )
                            )
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
    # Ingress table access for the dedicated principal: enough to
    # persist HMAC-verified arrivals and read them back, nothing more.
    # Verdict/receipt/dispatch/outbox/policy writes are never granted
    # (authority conservation: ingress authenticates, nothing more).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                -- SELECT + INSERT persist HMAC-verified arrivals; UPDATE
                -- effects duplicate-adoption and precursor promotion of
                -- the ingress principal's own rows only (sovereign
                -- custody, authorship, and provenance triggers bound
                -- every such write; the XB/XI battery proves refusal
                -- outside the ingress boundary).
                GRANT SELECT, INSERT, UPDATE ON TABLE public.webhook_ingress_identities TO app_ingress;
                GRANT SELECT ON TABLE public.tenants TO app_ingress;
                -- Trigger-plane visibility (read-only): the ingress
                -- triggers evaluate as the caller and must observe the
                -- dispatch twin (custody) and the evidence trail
                -- (provenance) under the caller's tenant GUC. SELECT
                -- mints nothing; writes remain ungranted everywhere.
                GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ingress;
                GRANT SELECT ON TABLE public.b26_p2_provenance_evidence TO app_ingress;
                -- Read-only witness visibility for the ingress
                -- principal: trigger-plane promotion checks evaluate
                -- as the caller, so the governed refusal identity
                -- (promotion_refused vs witness_missing) is precise
                -- instead of collapsing to permission-denied. The
                -- hash is inert without attester EXECUTE, which no
                -- non-ingress principal holds.
                GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XI5. P3 eligibility boundary. P3 consumes this predicate; P3 has
    # no capability to override it (no grants on the underlying state
    # are issued to any P3 principal -- none exists yet -- and the
    # function is read-only). A task is eligible only when every P2
    # fact it depends on is currently trustworthy.
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
            -- Tenant-scoped reads (P2 tables carry FORCE RLS): bind
            -- the caller-declared tenant first. A spoofed tenant
            -- scopes every read away from the task and every check
            -- below fails closed to FALSE.
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
            -- Authenticated, witnessed provenance.
            BEGIN
            SELECT i.b26_p2_provenance_status INTO _prov
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = _ingress;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
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
        "REVOKE ALL ON FUNCTION public.b26_p2_state_eligible_for_p3(text, uuid) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        DECLARE _r text;
        BEGIN
            FOREACH _r IN ARRAY ARRAY[
                'app_user', 'app_worker', 'app_relay', 'app_beat', 'app_ingress'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _r) THEN
                    EXECUTE format(
                        'GRANT EXECUTE ON FUNCTION public.b26_p2_state_eligible_for_p3(text, uuid) TO %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XI6. Quarantine-aware canonical identity (BLOCKER CLASS D/C law).
    # Quarantined ingress cannot found new truth: it is excluded from
    # the canonical aggregate and from the blank-shape fail-closed
    # check. Windows without quarantine hash exactly as before.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_canonical_scope_identity_for_window(p_tenant uuid, p_ws timestamptz, p_we timestamptz) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'pg_catalog', 'public' AS $$
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
                -- XI: quarantined ingress is explicitly
                -- non-authoritative and excluded from both the
                -- blank-shape gate and the canonical aggregate.
                IF EXISTS (
                    SELECT 1 FROM public.webhook_ingress_identities AS i
                     WHERE i.tenant_id = p_tenant
                       AND i.verified_commerce_ingress_state = 'authenticity_verified'
                       AND NOT EXISTS (
                            SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                             WHERE q.webhook_ingress_identity_id = i.id
                       )
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
                      AND NOT EXISTS (
                           SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                            WHERE q.webhook_ingress_identity_id = i.id
                      )
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
    # XI7. Dispatch quarantine exclusion: quarantined ingress or a
    # quarantined task identity can never (re)enter truth-capable
    # dispatch. H-R10 P3 visibility seam is closed at the same
    # boundary: P3 eligibility (XI5) refuses quarantined state, and P2
    # refuses to mint it.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_dispatch_quarantine_exclusion()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF NEW.webhook_ingress_identity_id IS NOT NULL
               AND EXISTS (
                    SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                     WHERE q.webhook_ingress_identity_id = NEW.webhook_ingress_identity_id
               ) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_quarantined_ingress_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF EXISTS (
                SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                 WHERE q.task_id = NEW.task_id
            ) THEN
                RAISE EXCEPTION 'b26_p2_dispatch_quarantined_task_refused'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_quarantine_exclusion
            ON public.b23_match_task_dispatches
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_dispatch_quarantine_exclusion
        BEFORE INSERT OR UPDATE OF webhook_ingress_identity_id, tenant_id
        ON public.b23_match_task_dispatches
        FOR EACH ROW
        EXECUTE FUNCTION public.b26_p2_enforce_dispatch_quarantine_exclusion()
        """
    )
    # Trigger-plane guards fire through the trigger mechanism only;
    # no runtime principal holds a direct path to the guard body.
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_enforce_dispatch_quarantine_exclusion() FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # XI8. Ingress-level quarantine support. The quarantine source law
    # gains the ingress relation so poison foundations carry an
    # explicit non-authoritative disposition without rewriting B2.3
    # verdict history.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DROP CONSTRAINT IF EXISTS ck_b26_p2_quarantine_source"
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_quarantine
        ADD CONSTRAINT ck_b26_p2_quarantine_source
        CHECK (source_relation = ANY (ARRAY[
            'b26_p2_execution_outbox'::text,
            'b26_p2_task_authority_directory'::text,
            'b23_match_task_dispatches'::text,
            'b26_p2_conduction_receipts'::text,
            'webhook_ingress_identities'::text
        ]))
        """
    )

    # ------------------------------------------------------------------
    # XI9. Generic post-upgrade invariant census (BLOCKER CLASS D law).
    # The oracle below scans FINAL truth-capable state against CURRENT
    # XI invariants; the migration's repair branches are not the
    # oracle. Any survivor fails the migration (no hybrid universe).
    # Uncertainty is classified/quarantined, never manufactured: no
    # witness is backfilled, no provenance rewritten, no semantic
    # meaning assigned, no B2.3 row touched.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xi_invariant_oracle()
        RETURNS TABLE (violation_kind text, task_ref text, detail text)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            -- D-A: authenticated foundation without a witness can found
            -- no new truth (dispatch-bearing or dispatchless: the
            -- identity aggregate reads dispatchless verified rows).
            RETURN QUERY
            SELECT 'xi_witnessless_authenticated_foundation'::text,
                   COALESCE(d.task_id::text, 'ingress:' || i.id::text),
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
              LEFT JOIN public.b23_match_task_dispatches AS d
                ON d.webhook_ingress_identity_id = i.id
               AND d.tenant_id = i.tenant_id
             WHERE i.verified_commerce_ingress_state = 'authenticity_verified'
               AND i.b26_p2_provenance_status = 'authenticated_known'
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                     WHERE w.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                     WHERE q.webhook_ingress_identity_id = i.id
               );
            -- D-B: blank-shape authenticated foundation.
            RETURN QUERY
            SELECT 'xi_blank_authenticated_foundation'::text,
                   COALESCE(d.task_id::text, 'ingress:' || i.id::text),
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
              LEFT JOIN public.b23_match_task_dispatches AS d
                ON d.webhook_ingress_identity_id = i.id
               AND d.tenant_id = i.tenant_id
             WHERE i.verified_commerce_ingress_state = 'authenticity_verified'
               AND i.b26_p2_provenance_status = 'authenticated_known'
               AND (public.b26_p2_ascii_strip(COALESCE(i.provider, '')) = ''
                    OR public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, '')) = ''
                    OR length(public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, ''))) <> 3)
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                     WHERE q.webhook_ingress_identity_id = i.id
               );
            -- D-C: divergent terminal twins (conducted dispatch beside
            -- a non-conducted outbox twin, or vice versa).
            RETURN QUERY
            SELECT 'xi_divergent_terminal_twins'::text, d.task_id::text,
                   ('dispatch=' || d.delivery_state::text || ',outbox=' || COALESCE(o.state::text, 'missing'))::text
              FROM public.b23_match_task_dispatches AS d
              LEFT JOIN public.b26_p2_execution_outbox AS o
                ON o.dispatch_task_id = d.task_id
             WHERE (d.delivery_state = 'conducted'
                    AND COALESCE(o.state::text, 'missing') IS DISTINCT FROM 'conducted')
                OR (o.state = 'conducted'
                    AND d.delivery_state IS DISTINCT FROM 'conducted');
            -- D-D: garbage policy-sha receipt stamped canonically bound.
            RETURN QUERY
            SELECT 'xi_garbage_policy_receipt'::text, r.task_id::text,
                   ('policy_sha=' || COALESCE(r.policy_semantic_sha256, 'null'))::text
              FROM public.b26_p2_conduction_receipts AS r
             WHERE r.ix_meaning_status = 'canonically_bound'
               AND r.policy_semantic_sha256 IS DISTINCT FROM
                   'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99';
            -- D-E: stale terminal binding (receipt disagrees with live
            -- canonical identity).
            RETURN QUERY
            SELECT 'xi_stale_terminal_binding'::text, r.task_id::text,
                   'receipt_identity_not_current'::text
              FROM public.b26_p2_conduction_receipts AS r
              JOIN public.b23_match_task_dispatches AS d
                ON d.task_id = r.task_id
             WHERE d.delivery_state = 'conducted'
               AND r.ix_meaning_status = 'canonically_bound'
               AND r.p2_scope_identity IS DISTINCT FROM
                   public.b26_p2_canonical_scope_identity_for_window(
                       r.tenant_id, r.window_start, r.window_end
                   );
            -- D-F: conducted without a canonically bound consequence.
            RETURN QUERY
            SELECT 'xi_conducted_without_consequence'::text, d.task_id::text,
                   'missing_canonically_bound_receipt'::text
              FROM public.b23_match_task_dispatches AS d
             WHERE d.delivery_state = 'conducted'
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_conduction_receipts AS r
                     WHERE r.task_id = d.task_id
                       AND r.ix_meaning_status = 'canonically_bound'
               );
            -- D-G: unknown-provenance truth-capable dispatch.
            RETURN QUERY
            SELECT 'xi_unknown_provenance_truth'::text, d.task_id::text,
                   ('ingress=' || i.id::text)::text
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.delivery_state IN ('published', 'conducted', 'pending_publish')
               AND i.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known';
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xi_invariant_oracle() FROM PUBLIC"
    )
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
        "ALTER TABLE public.b26_p2_ingress_auth_witness DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_provenance_evidence DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        DECLARE
            _n_children integer := 0;
            _n_roots integer := 0;
            _n_receipts integer := 0;
            _n_ingress integer := 0;
            _survivors integer := 0;
            _v_kind text;
            _v_ref text;
            _v_detail text;
        BEGIN
            -- Task-level contradictions: quarantine children first.
            -- Includes conducted dispatches about to lose their receipt
            -- to the receipt-trustworthiness sweep below (a conducted
            -- terminal without a canonically bound consequence must be
            -- re-adjudicated, never left standing).
            CREATE TEMPORARY TABLE _xi_task_contra ON COMMIT DROP AS
            SELECT DISTINCT d.task_id AS task_id
              FROM public.b23_match_task_dispatches AS d
              JOIN public.webhook_ingress_identities AS i
                ON i.id = d.webhook_ingress_identity_id
               AND i.tenant_id = d.tenant_id
             WHERE d.delivery_state IN ('published', 'conducted', 'pending_publish')
               AND (
                    i.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known'
                    OR NOT EXISTS (
                        SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                         WHERE w.webhook_ingress_identity_id = i.id
                    )
                    OR public.b26_p2_ascii_strip(COALESCE(i.provider, '')) = ''
                    OR public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, '')) = ''
                    OR length(public.b26_p2_ascii_strip(COALESCE(i.verified_amount_currency, ''))) <> 3
               )
            UNION
            SELECT DISTINCT d.task_id AS task_id
              FROM public.b23_match_task_dispatches AS d
              JOIN public.b26_p2_conduction_receipts AS rec
                ON rec.task_id = d.task_id
             WHERE d.delivery_state = 'conducted'
               AND (
                    rec.ix_meaning_status IS DISTINCT FROM 'canonically_bound'
                    OR rec.policy_semantic_sha256 IS DISTINCT FROM
                       'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99'
               );
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_execution_outbox', o.dispatch_task_id, o.tenant_id,
                   o.webhook_ingress_identity_id, NULL, NULL,
                   'corrective_xi:task_contradiction',
                   COALESCE(o.payload, '{}'::jsonb), '202609240002'
              FROM public.b26_p2_execution_outbox AS o
              JOIN _xi_task_contra AS c
                ON c.task_id = o.dispatch_task_id;
            GET DIAGNOSTICS _n_children = ROW_COUNT;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_task_authority_directory', dir.task_id, dir.tenant_id,
                   dir.webhook_ingress_identity_id, dir.window_start, dir.window_end,
                   'corrective_xi:task_contradiction',
                   jsonb_build_object(
                       'window_start', dir.window_start::text,
                       'window_end', dir.window_end::text
                   ), '202609240002'
              FROM public.b26_p2_task_authority_directory AS dir
              JOIN _xi_task_contra AS c
                ON c.task_id = dir.task_id;
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b23_match_task_dispatches', d.task_id, d.tenant_id,
                   d.webhook_ingress_identity_id, d.window_start, d.window_end,
                   'corrective_xi:task_contradiction',
                   jsonb_build_object('kind', 'task_contradiction'), '202609240002'
              FROM public.b23_match_task_dispatches AS d
              JOIN _xi_task_contra AS c
                ON c.task_id = d.task_id;
            GET DIAGNOSTICS _n_roots = ROW_COUNT;
            -- Ingress-level poison foundations FIRST: explicit
            -- non-authoritative disposition (REQUIRES_REAUTHENTICATION).
            -- No witness is backfilled, no provenance rewritten. This
            -- ordering matters: the canonical recomputation below
            -- excludes quarantined ingress, so poison (including
            -- dispatchless blank foundations that would otherwise raise
            -- the blank-shape gate mid-sweep) is fenced before any
            -- receipt is re-derived.
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'webhook_ingress_identities', 'ingress:' || i.id::text, i.tenant_id,
                   i.id, NULL, NULL,
                   'corrective_xi:requires_reauthentication',
                   jsonb_build_object(
                       'provider', i.provider,
                       'provenance_status', i.b26_p2_provenance_status
                   ), '202609240002'
              FROM public.webhook_ingress_identities AS i
             WHERE i.verified_commerce_ingress_state = 'authenticity_verified'
               AND i.b26_p2_provenance_status = 'authenticated_known'
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                     WHERE w.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                    SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                     WHERE q.webhook_ingress_identity_id = i.id
               );
            GET DIAGNOSTICS _n_ingress = ROW_COUNT;
            -- Receipt-level contradictions: garbage policy sha or stale
            -- binding. B2.3 verdict history is never rewritten.
            INSERT INTO public.b26_p2_execution_quarantine (
                source_relation, task_id, tenant_id,
                webhook_ingress_identity_id, window_start, window_end,
                reason, original_payload, migration_identity
            )
            SELECT 'b26_p2_conduction_receipts', rec.task_id, rec.tenant_id,
                   rec.webhook_ingress_identity_id, rec.window_start, rec.window_end,
                   'corrective_xi:receipt_not_trustworthy',
                   jsonb_build_object(
                       'b23_processed_count', rec.b23_processed_count,
                       'p2_scope_identity', rec.p2_scope_identity,
                       'policy_semantic_sha256', rec.policy_semantic_sha256
                   ), '202609240002'
              FROM public.b26_p2_conduction_receipts AS rec
             WHERE rec.ix_meaning_status IS DISTINCT FROM 'canonically_bound'
                OR rec.policy_semantic_sha256 IS DISTINCT FROM
                   'fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99'
                OR rec.p2_scope_identity IS DISTINCT FROM
                   public.b26_p2_canonical_scope_identity_for_window(
                       rec.tenant_id, rec.window_start, rec.window_end);
            GET DIAGNOSTICS _n_receipts = ROW_COUNT;
            -- Children-first deletes.
            DELETE FROM public.b23_match_task_dispatches AS d
            USING _xi_task_contra AS c
            WHERE d.task_id = c.task_id;
            DELETE FROM public.b26_p2_conduction_receipts AS rec
            USING public.b26_p2_execution_quarantine AS q
            WHERE q.source_relation = 'b26_p2_conduction_receipts'
              AND q.migration_identity = '202609240002'
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
            -- Divergent twins that survived the deletes fail the lane.
            SELECT count(*) INTO _survivors
              FROM public.b23_match_task_dispatches AS d
              LEFT JOIN public.b26_p2_execution_outbox AS o
                ON o.dispatch_task_id = d.task_id
             WHERE (d.delivery_state = 'conducted'
                    AND COALESCE(o.state::text, 'missing') IS DISTINCT FROM 'conducted')
                OR (o.state = 'conducted'
                    AND d.delivery_state IS DISTINCT FROM 'conducted');
            IF _survivors > 0 THEN
                RAISE EXCEPTION 'b26_p2_corrective_xi_divergent_survivors:%', _survivors
                    USING ERRCODE = '42501';
            END IF;
            -- Generic final-state oracle: CURRENT invariants over
            -- surviving truth-capable state. The repair branches above
            -- are not the oracle.
            FOR _v_kind, _v_ref, _v_detail IN
                SELECT * FROM public.b26_p2_xi_invariant_oracle()
            LOOP
                RAISE EXCEPTION 'b26_p2_corrective_xi_oracle_survivor:%:%:%',
                    _v_kind, _v_ref, _v_detail
                    USING ERRCODE = '42501';
            END LOOP;
            RAISE NOTICE 'b26_p2_corrective_xi_census children=% roots=% receipts=% ingress=%',
                _n_children, _n_roots, _n_receipts, _n_ingress;
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
    op.execute(
        "ALTER TABLE public.b26_p2_ingress_auth_witness ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_ingress_auth_witness FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_provenance_evidence ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_provenance_evidence FORCE ROW LEVEL SECURITY"
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_dispatch_quarantine_exclusion ON public.b23_match_task_dispatches"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_dispatch_quarantine_exclusion()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xi_invariant_oracle()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_state_eligible_for_p3(text, uuid)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_state_eligible_for_p3(text)"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text)
                    TO app_user;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_provenance_evidence DROP COLUMN IF EXISTS evidence_witness_hash"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_ingress_auth_witness(uuid)"
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_ingress_auth_witness"
    )
    # Rollback removes XI dispositions before narrowing the source
    # law back to the predecessor vocabulary; otherwise the
    # reverted CHECK would fail on surviving XI-era rows. RLS is
    # FORCE on the quarantine table, so the rollback disables it
    # around the delete (a GUC-less DELETE would silently remove
    # nothing and the narrowed CHECK would then fail). B2.3 verdict
    # history is untouched by either direction.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DELETE FROM public.b26_p2_execution_quarantine"
        " WHERE migration_identity = '202609240002'"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DROP CONSTRAINT IF EXISTS ck_b26_p2_quarantine_source"
    )
    op.execute(
        """
        ALTER TABLE public.b26_p2_execution_quarantine
        ADD CONSTRAINT ck_b26_p2_quarantine_source
        CHECK (source_relation = ANY (ARRAY[
            'b26_p2_execution_outbox'::text,
            'b26_p2_task_authority_directory'::text,
            'b23_match_task_dispatches'::text,
            'b26_p2_conduction_receipts'::text
        ]))
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_execution_quarantine FORCE ROW LEVEL SECURITY"
    )
