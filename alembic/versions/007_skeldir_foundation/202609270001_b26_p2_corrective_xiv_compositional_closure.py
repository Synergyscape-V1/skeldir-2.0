"""B2.6-P2 Corrective XIV: compositional sovereignty and end-to-end conduction closure.

Revision ID: 202609270001
Revises: 202609260001

Closes the XIII survivor classes at their compositional roots (Directive XIV,
blockers A-F):

A. PRODUCTION AUTH-ROOT CONDUCTION. The dedicated authentication trust root
   becomes operable (its persistence shape satisfies the ingress schema via
   the immutable auth-root evidence identity + full commerce handoff) and the
   sole production path. The general API acts only as a non-authoritative
   byte relay (no authenticated-ingress DB capability); the root verifies
   provider signatures and persists authority. No downstream commerce state
   can claim authenticated authority without an immutable auth-root evidence
   identity (enforced by the provenance promotion guard).

B. SINGLE AUTHORITY PATH. Exactly one externally callable runtime primitive
   may transition ingress from non-authoritative to authoritative
   authenticated state: b26_p2_authenticate_ingress_atomic. Legacy
   recorder/witness/attest routines remain callable by grants but are
   physically incapable of producing terminal authenticated authority alone:
   promotion to authenticated_known requires an auth-root evidence row that
   only the atomic transition creates in the same transaction. Any
   combination of non-atomic helpers without the atomic fails closed with
   b26_p2_provenance_promotion_refused (effect-level, not grant-level).

C. HISTORICAL AUTHORITY TRANSITION. Every pre-XIV authenticated lineage
   whose authority cannot be independently proven (no auth-root evidence)
   becomes explicitly non-authoritative: swept into
   b26_p2_execution_quarantine with reason historically_unverifiable_xiv,
   preserving amount/count/provenance in original_payload for auditability.
   Quarantined state cannot dispatch anew (dispatch trigger refuses),
   cannot produce a new P2 receipt (receipt path requires dispatch), is not
   current, is not P3 eligible (P3 predicate already refuses quarantined),
   and never enters future immutable reconciliation truth as authenticated.
   The invariant oracle detects complete-but-unverifiable lineages, not only
   partial rows.

D. CLOSED SEMANTIC MEANING. Enforced in the validator plane (see
   scripts/ci/validate_b26_p2_xiv_*.py) and pinned by this migration's
   topology/oracle surface. No semantic function changes here; the migration
   provides the evidence/topology substrate the semantic gates build on.

E. BEHAVIORAL TEMPORAL COMPLETENESS. The temporal harness reads the semantic
   contract and generates/invokes a real behavioral probe per disposition
   (see validator). This migration adds the dispatch quarantine refusal so
   every disposition has an executed effect.

F. GOVERNANCE. This migration does not alter the merge approval law.

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved. Tenant RLS
FORCE on the new table. Integer-minor money untouched.
"""

from __future__ import annotations

from alembic import op

revision = "202609270001"
down_revision = "202609260001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_execution_quarantine IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XIV1. Immutable auth-root evidence identity.
    #
    # The authentication trust root creates exactly one evidence row per
    # authenticated ingress in the same transaction as the authoritative
    # transition (inside the atomic function, SECURITY DEFINER as
    # migration_owner). No runtime principal holds direct INSERT/UPDATE/
    # DELETE on this table: writes occur only through the DEFINER atomic
    # transition, gated on session_user. Reads are observability only.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_auth_root_evidence (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            webhook_ingress_identity_id uuid NOT NULL,
            idempotency_key text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_idem_not_blank
                CHECK (char_length(idempotency_key) > 0),
            provider text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_provider_not_blank
                CHECK (char_length(provider) > 0),
            provider_native_event_reference text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_event_ref_not_blank
                CHECK (char_length(provider_native_event_reference) > 0),
            body_sha256 text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_body_sha_format
                CHECK (char_length(body_sha256) = 64),
            signature_envelope_sha256 text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_sig_format
                CHECK (char_length(signature_envelope_sha256) = 64),
            auth_method text NOT NULL
                CONSTRAINT ck_b26_p2_auth_root_evidence_method_not_blank
                CHECK (char_length(auth_method) > 0),
            auth_version text NOT NULL DEFAULT 'v1',
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT pk_b26_p2_auth_root_evidence
                PRIMARY KEY (webhook_ingress_identity_id),
            CONSTRAINT fk_b26_p2_auth_root_evidence_tenant_ingress
                FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                REFERENCES public.webhook_ingress_identities(tenant_id, id)
                ON DELETE CASCADE
        )
        """
    )
    op.execute("REVOKE ALL ON TABLE public.b26_p2_auth_root_evidence FROM PUBLIC")
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
                        'REVOKE ALL ON TABLE public.b26_p2_auth_root_evidence FROM %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
    # Read-only observability; zero authorship (no INSERT/UPDATE/DELETE).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT ON TABLE public.b26_p2_auth_root_evidence TO app_user;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT SELECT ON TABLE public.b26_p2_auth_root_evidence TO app_ingress;
            END IF;
        END $$;
        """
    )
    op.execute("ALTER TABLE public.b26_p2_auth_root_evidence ENABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_auth_root_evidence FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_auth_root_evidence'
                   AND policyname = 'tenant_isolation_policy_b26_p2_auth_root_evidence'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_auth_root_evidence
                    ON public.b26_p2_auth_root_evidence
                    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
                    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
            END IF;
        END $$;
        """
    )

    # Immutability: bound fields cannot be rewritten; deletes are
    # migration-admin only; recorded_by is not stored here (the atomic
    # transition's session_user is the trust root by grant law).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Writes occur only through the SECURITY DEFINER atomic
                -- transition (current_user is the owner inside DEFINER).
                -- Direct INSERTs as a runtime principal (current_user is
                -- the caller) are refused. session_user remains the
                -- caller inside DEFINER, so gate on current_user here.
                IF current_user IS DISTINCT FROM 'migration_owner'
                   AND current_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_auth_root_evidence_direct_refused'
                        USING ERRCODE = '42501';
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
        "DROP TRIGGER IF EXISTS trg_b26_p2_auth_root_evidence_immutability ON public.b26_p2_auth_root_evidence"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_auth_root_evidence_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.b26_p2_auth_root_evidence
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability()
        """
    )

    # ------------------------------------------------------------------
    # XIV2. Atomic transition binds root evidence in the same transaction.
    #
    # The single authoritative commit interface now creates the immutable
    # auth-root evidence row (idempotent on retry) before promoting
    # provenance. Crash before commit leaves fully pending state; after
    # leaves fully authenticated state with evidence. NULL-safe.
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
            _c_provider text;
            _c_event text;
            _c_body text;
            _c_sig text;
            _c_method text;
            _c_version text;
            _witness text;
            _expected text;
            _prev_guc text;
        BEGIN
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_atomic_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider,
                   i.b26_p2_provenance_status
              INTO _tenant, _idem, _state, _row_provider, _prov
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
                        recorded_by
                    )
                    VALUES (p_ingress, _tenant, p_provider, p_event_ref,
                            lower(p_body_sha256), lower(p_sig_envelope_sha256),
                            p_method, COALESCE(p_version, 'v1'), session_user)
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
                END IF;
                SELECT w.witness_hash INTO _witness
                  FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = p_ingress;
                IF NOT FOUND THEN
                    _expected := encode(digest(
                        _tenant::text || '|' || p_ingress::text || '|'
                        || _c_provider || '|' || _c_event || '|'
                        || lower(_c_body) || '|' || lower(_c_sig) || '|'
                        || _c_method || '|' || COALESCE(_c_version, 'v1'),
                        'sha256'), 'hex');
                    INSERT INTO public.b26_p2_ingress_auth_witness AS w (
                        webhook_ingress_identity_id, tenant_id,
                        witness_hash, witnessed_by
                    )
                    VALUES (p_ingress, _tenant, _expected, session_user)
                    ON CONFLICT (webhook_ingress_identity_id) DO NOTHING;
                    SELECT w.witness_hash INTO _witness
                      FROM public.b26_p2_ingress_auth_witness AS w
                     WHERE w.webhook_ingress_identity_id = p_ingress;
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

    # ------------------------------------------------------------------
    # XIV3. Promotion guard: no downstream commerce state can claim
    # authenticated authority without an immutable auth-root evidence
    # identity. Legacy recorder/witness/attest combinations without the
    # atomic transition create consequence/witness/evidence but never root
    # evidence, so their promotion UPDATE now fails closed with
    # b26_p2_provenance_promotion_refused (effect-level single authority).
    # ------------------------------------------------------------------
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
                NEW.b26_p2_provenance_status := 'pending_authentication';
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                   AND NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    NEW.b26_p2_provenance_status := 'pending_authentication';
                END IF;
                IF OLD.b26_p2_provenance_status IS DISTINCT FROM NEW.b26_p2_provenance_status THEN
                    IF OLD.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
                       AND NEW.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known' THEN
                        RAISE EXCEPTION 'b26_p2_provenance_downgrade_refused' USING ERRCODE = '42501';
                    END IF;
                    IF NEW.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
                       AND OLD.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known'
                       AND NOT EXISTS (
                                SELECT 1 FROM public.b26_p2_provenance_evidence AS e
                                 WHERE e.webhook_ingress_identity_id = OLD.id
                                   AND e.evidence_witness_hash IS NOT NULL
                                   AND char_length(e.evidence_witness_hash) > 0
                                   AND EXISTS (
                                        SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                                         WHERE w.webhook_ingress_identity_id = OLD.id
                                           AND w.witness_hash IS NOT DISTINCT FROM e.evidence_witness_hash
                                   )
                                   AND EXISTS (
                                        SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                                         WHERE c.webhook_ingress_identity_id = OLD.id
                                   )
                            ) THEN
                        RAISE EXCEPTION 'b26_p2_provenance_promotion_refused' USING ERRCODE = '42501';
                    END IF;
                    -- XIV: root-evidence binding. Even with full legacy
                    -- evidence, promotion requires the immutable
                    -- auth-root evidence identity created only by the
                    -- single authoritative commit interface in the same
                    -- transaction. Legacy paths without the atomic fail
                    -- here; the atomic creates root evidence before this
                    -- UPDATE fires, so it passes.
                    IF NEW.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
                       AND OLD.b26_p2_provenance_status IS DISTINCT FROM 'authenticated_known'
                       AND NOT EXISTS (
                                SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                                 WHERE r.webhook_ingress_identity_id = OLD.id
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
    # XIV4. Dispatch law: quarantined state cannot dispatch anew.
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
            _witness text;
        BEGIN
            SELECT i.b26_p2_provenance_status INTO _prov
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = NEW.webhook_ingress_identity_id
               AND i.tenant_id = NEW.tenant_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_dispatch_ingress_missing' USING ERRCODE = '42501';
            END IF;
            IF _prov IS DISTINCT FROM 'authenticated_known' THEN
                RAISE EXCEPTION 'b26_p2_dispatch_provenance_unknown' USING ERRCODE = '42501';
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
    # XIV5. Historical sweep: every pre-XIV authenticated lineage without
    # independently provable authority (no auth-root evidence) becomes
    # explicitly non-authoritative. Preserves amount/count/provenance in
    # original_payload for auditability; never deletes evidence. Quarantine
    # makes P3 FALSE (predicate refuses quarantined) and dispatch refused
    # (XIV4). Idempotent on re-run.
    # ------------------------------------------------------------------
    # Historical sweep respects tenant RLS (FORCE on ingress): iterate
    # tenants with the GUC bound per tenant. Idempotent on re-run.
    op.execute(
        """
        DO $$
        DECLARE _t uuid;
        BEGIN
            FOR _t IN SELECT id FROM public.tenants LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                INSERT INTO public.b26_p2_execution_quarantine AS q (
                    source_relation, task_id, tenant_id,
                    webhook_ingress_identity_id, reason,
                    original_payload, migration_identity
                )
                SELECT 'webhook_ingress_identities',
                       ('xiv-historical:' || i.id::text),
                       i.tenant_id,
                       i.id,
                       'historically_unverifiable_xiv',
                       jsonb_build_object(
                           'provider', i.provider,
                           'provider_native_event_reference', i.provider_native_event_reference,
                           'provider_native_commerce_reference', i.provider_native_commerce_reference,
                           'normalized_commerce_reference_kind', i.normalized_commerce_reference_kind,
                           'normalized_commerce_reference_value', i.normalized_commerce_reference_value,
                           'verified_amount_minor', i.verified_amount_minor,
                           'verified_amount_currency', i.verified_amount_currency,
                           'verified_amount_scale', i.verified_amount_scale,
                           'event_timestamp', i.event_timestamp::text,
                           'idempotency_key', i.idempotency_key,
                           'verified_commerce_ingress_state', i.verified_commerce_ingress_state,
                           'b26_p2_provenance_status', i.b26_p2_provenance_status,
                           'consequence', (SELECT count(*) FROM public.b26_p2_provider_auth_consequence AS c WHERE c.webhook_ingress_identity_id = i.id),
                           'witness', (SELECT count(*) FROM public.b26_p2_ingress_auth_witness AS w WHERE w.webhook_ingress_identity_id = i.id)
                       ),
                       '202609270001'
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.tenant_id = _t
                   AND i.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified'
                   AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
                   AND NOT EXISTS (
                            SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                             WHERE r.webhook_ingress_identity_id = i.id
                       )
                   AND NOT EXISTS (
                            SELECT 1 FROM public.b26_p2_execution_quarantine AS e
                             WHERE e.webhook_ingress_identity_id = i.id
                       );
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIV6. Oracle: detect complete-but-unverifiable lineages, not only
    # partial rows. Quarantined rows are correctly disposed (not violations).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xiii_invariant_oracle()
        RETURNS TABLE (violation_kind text, task_ref text, detail text)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            RETURN QUERY
            SELECT 'xiii_witness_without_consequence'::text,
                   ('ingress:' || i.id::text)::text,
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_ingress_auth_witness AS w
                ON w.webhook_ingress_identity_id = i.id
             WHERE i.verified_commerce_ingress_state = 'authenticity_verified'
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                      WHERE c.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                      WHERE q.webhook_ingress_identity_id = i.id
               );
            RETURN QUERY
            SELECT 'xiii_partial_auth_authoritative'::text,
                   ('ingress:' || i.id::text)::text,
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
             WHERE i.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified'
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                      WHERE c.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                      WHERE w.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                      WHERE q.webhook_ingress_identity_id = i.id
               );
            -- XIV: internally complete but historically unverifiable:
            -- authenticated with consequence + witness + legacy evidence
            -- yet no immutable auth-root evidence identity and not
            -- quarantined. This is the forged-XII survivor shape.
            RETURN QUERY
            SELECT 'xiv_complete_but_unverifiable'::text,
                   ('ingress:' || i.id::text)::text,
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
             WHERE i.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified'
               AND i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND EXISTS (
                     SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                      WHERE c.webhook_ingress_identity_id = i.id
               )
               AND EXISTS (
                     SELECT 1 FROM public.b26_p2_ingress_auth_witness AS w
                      WHERE w.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_auth_root_evidence AS r
                      WHERE r.webhook_ingress_identity_id = i.id
               )
               AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_execution_quarantine AS q
                      WHERE q.webhook_ingress_identity_id = i.id
               );
            RETURN;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIV7. Topology law: strict regime now includes the root-evidence
    # substrate. Provisioners converge to it idempotently.
    # ------------------------------------------------------------------
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
    op.execute("REVOKE ALL ON FUNCTION public.b26_p2_xiv_topology_check() FROM PUBLIC")
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
                        'GRANT EXECUTE ON FUNCTION public.b26_p2_xiv_topology_check() TO %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xiv_provision_ingress_topology()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF session_user NOT IN ('migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_xiv_provision_refused'
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
            GRANT SELECT ON TABLE public.b26_p2_auth_root_evidence TO app_ingress;
            GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_user;
            GRANT SELECT ON TABLE public.b26_p2_auth_root_evidence TO app_user;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) TO app_ingress;
            REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) FROM app_user;
            RETURN 'xiv_topology_provisioned';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xiv_provision_ingress_topology() FROM PUBLIC"
    )


def downgrade() -> None:
    # Remove every XIV-era quarantine disposition (historical sweep +
    # validator/negative-control probe rows share XIV reasons) so a
    # continued downgrade to predecessor law (XI narrows the source
    # CHECK back to the pre-XIV vocabulary) never strands rows the old
    # CHECK cannot admit. RLS is FORCE on the quarantine table, so the
    # rollback disables it around the delete (a GUC-less DELETE would
    # silently remove nothing and the narrowed CHECK would then fail,
    # the same pattern XI itself uses). B2.3 verdict history is
    # untouched.
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine DISABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "DELETE FROM public.b26_p2_execution_quarantine"
        " WHERE migration_identity IN ('202609270001', 'xiv-probe', 'xiv-nc')"
        " OR reason IN ('historically_unverifiable_xiv', 'xiv_probe_quarantine')"
    )
    op.execute(
        "ALTER TABLE public.b26_p2_execution_quarantine ENABLE ROW LEVEL SECURITY"
    )
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_xiv_provision_ingress_topology()")
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_xiv_topology_check()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_auth_root_evidence_immutability ON public.b26_p2_auth_root_evidence"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_auth_root_evidence_immutability()"
    )
    op.execute("DROP TABLE IF EXISTS public.b26_p2_auth_root_evidence")
    # NOTE: atomic/provenance/dispatch tightening above is intentionally NOT
    # rolled back here: a downgrade from XIV leaves the strict
    # root-evidence/promotion/dispatch law in place (fail-closed), and a
    # re-upgrade converges back to full XIV. Historical quarantine rows for
    # this migration are removed above so re-upgrade re-sweeps them.
