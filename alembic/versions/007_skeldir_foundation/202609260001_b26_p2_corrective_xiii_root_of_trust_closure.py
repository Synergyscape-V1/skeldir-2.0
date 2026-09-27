"""B2.6-P2 Corrective XIII: root-of-trust and closed-semantics P2-core closure.

Revision ID: 202609260001
Revises: 202609250001

Closes the XII survivor classes at their physical roots:

A. AUTH EVIDENCE AUTHORSHIP COLLAPSE (H-XIII-01). The XII recorder
   accepted caller-chosen digests from the generic application
   principal (app_user). XIII makes authenticated-ingress authorship
   physically impossible for app_user: direct INSERT revoked, recorder
   EXECUTE revoked from app_user and granted only to the dedicated
   authentication trust root (app_ingress), consequence rows immutable
   once recorded (no digest rewrite via ON CONFLICT UPDATE), provider
   binding enforced (consequence provider must equal ingress
   provider), and recorded_by forced to session_user.

B. AUTH TCB TOO LARGE / CAPABILITY LEAK (H-XIII-02/03). The API
   process no longer possesses the authenticated-ingress persistence
   credential (Procfile/compose manifests blank it; session pool
   constructs only for SKELDIR_PROCESS_ROLE=auth_ingress; startup
   refuses when a non-auth process mounts it). The database denies
   every non-ingress principal regardless, so the boundary is the
   union of DB grants and OS/process custody, never an importable
   ContextVar.

C. MULTI-COMMIT AUTHORITY GAP (H-XIII-04/05). INSERT-time provenance
   no longer marks authenticated_known: every verified INSERT lands
   as pending_authentication (explicitly non-dispatchable,
   non-P3-eligible). Promotion to authenticated_known occurs only
   through the evidence UPDATE guard that requires consequence +
   bound witness + evidence in the same check. Dispatch requires the
   exact terminal state (provenance IS NOT DISTINCT FROM
   'authenticated_known' AND witness exists), never verified-alone.

D. OPEN-WORLD SEMANTICS (H-XIII-06/07). Canonical P2 meaning is
   governed by contracts-internal/governance/
   b26_p2_xiii_semantic_contract.v1.json (closed language). The XIII
   semantic validator REDs structurally on dynamic SQL/EXECUTE,
   custom operators, unaliased/bare-column reads, undeclared
   helper/view/config indirection, and undeclared aggregate/set-level
   reads (including COUNT/EXISTS over governed relations).

E. TEMPORAL DENOMINATOR SPLIT (H-XIII-07). Every contract dependency
   carries exactly one temporal disposition; the XIII temporal
   validator enforces SEMANTIC_DEPENDENCIES minus
   TEMPORALLY_TESTED_DEPENDENCIES = EMPTY and executes a behavioral
   mutation per mutable dependency (including set-level events).

F. THREE-VALUED LOGIC / DEFINER / CRASH (H-XIII-08/09/10). All new
   state predicates use IS [NOT] DISTINCT FROM (NULL-safe); all new
   SECURITY DEFINER functions pin SET search_path TO pg_catalog,
   public; the atomic authentication function commits evidence +
   ingress state + identity binding in one transaction so every crash
   point converges to pending (retryable) or fully authenticated.

G. GOVERNANCE (H-XIII-12). This migration does not alter the merge
   approval law. The XIII acceptance law requires an externally
   authoritative approval (live branch protection requiring it plus a
   genuine second-human review, or a phase-owner amendment held
   outside the candidate) before merge. Candidate-owned contract
   edits cannot satisfy it.

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved.
Historical migrations immutable; this revision only adds and
redefines forward.
"""

from __future__ import annotations

from alembic import op

revision = "202609260001"
down_revision = "202609250001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # XIII0. Deployment law: lock the authentication plane.
    # ------------------------------------------------------------------
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provider_auth_consequence IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_ingress_auth_witness IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provenance_evidence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XIII1. Authorship closure: generic app_user has ZERO runtime
    # ability to author provider-authenticated truth. Only the
    # dedicated authentication trust root (app_ingress) may execute
    # the recorder; direct table INSERT is denied to every runtime
    # principal (writes occur only through the SECURITY DEFINER
    # recorder running as migration_owner, gated on session_user).
    # ------------------------------------------------------------------
    op.execute(
        """
        DO $$
        DECLARE _r text;
        BEGIN
            FOREACH _r IN ARRAY ARRAY[
                'app_user', 'app_worker', 'app_relay', 'app_beat',
                'app_rw', 'app_ro',
                'app_dispatch_publisher', 'app_celery_transport'
            ] LOOP
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = _r) THEN
                    EXECUTE format(
                        'REVOKE ALL ON TABLE public.b26_p2_provider_auth_consequence FROM %I',
                        _r
                    );
                    EXECUTE format(
                        'REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM %I',
                        _r
                    );
                END IF;
            END LOOP;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                EXECUTE 'REVOKE ALL ON TABLE public.b26_p2_provider_auth_consequence FROM app_ingress';
            END IF;
        END $$;
        """
    )
    # Read-only observability for both principals; no direct writes.
    # Dispatch (as app_user) and the dispatch trigger must read the
    # witness to enforce the terminal+witness law; this SELECT confers
    # zero authorship (no INSERT/UPDATE/DELETE, no EXECUTE).
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_user;
                GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_user;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_ingress;
                GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
            END IF;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) TO app_ingress;
            END IF;
        END $$;
        """
    )

    # Recorder: auth-root-only, provider-bound, immutable (no digest
    # rewrite). NULL-safe predicates throughout (H-XIII-08).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_provider_auth_consequence(
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
            _existing_provider text;
            _existing_event text;
            _existing_body text;
            _existing_sig text;
            _existing_method text;
            _existing_version text;
            _prev_guc text;
        BEGIN
            -- Only the dedicated authentication trust root may record
            -- the predecessor event. The generic application principal
            -- is physically incapable (grant + this gate).
            IF session_user IS DISTINCT FROM 'app_ingress'
               AND session_user IS DISTINCT FROM 'migration_owner'
               AND session_user IS DISTINCT FROM 'postgres' THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_provider, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_event_ref, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(char_length(p_body_sha256), 0) <> 64 THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_body_sha_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF COALESCE(char_length(p_sig_envelope_sha256), 0) <> 64 THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_sig_refused'
                    USING ERRCODE = '42501';
            END IF;
            IF public.b26_p2_ascii_strip(COALESCE(p_method, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider
              INTO _tenant, _idem, _state, _row_provider
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_ingress_missing'
                    USING ERRCODE = '42501';
            END IF;
            -- Provider binding: a PayPal consequence on a Stripe row
            -- is structurally refused (NULL-safe).
            IF p_provider IS DISTINCT FROM _row_provider THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_provider_mismatch'
                    USING ERRCODE = '42501';
            END IF;
            -- Immutability: an existing consequence is authoritative
            -- evidence and cannot be rewritten by its author. Identical
            -- re-record is idempotent; any digest/event/method drift
            -- is refused (prevents post-witness substitution).
            SELECT c.provider, c.provider_event_reference, c.body_sha256,
                   c.signature_envelope_sha256, c.auth_method, c.auth_version
              INTO _existing_provider, _existing_event, _existing_body,
                   _existing_sig, _existing_method, _existing_version
              FROM public.b26_p2_provider_auth_consequence AS c
             WHERE c.webhook_ingress_identity_id = p_ingress;
            IF FOUND THEN
                IF _existing_provider IS DISTINCT FROM p_provider
                   OR _existing_event IS DISTINCT FROM p_event_ref
                   OR lower(_existing_body) IS DISTINCT FROM lower(p_body_sha256)
                   OR lower(_existing_sig) IS DISTINCT FROM lower(p_sig_envelope_sha256)
                   OR _existing_method IS DISTINCT FROM p_method
                   OR COALESCE(_existing_version, 'v1') IS DISTINCT FROM COALESCE(p_version, 'v1') THEN
                    RAISE EXCEPTION 'b26_p2_auth_cons_immutable_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN 'recorded';
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
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
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN 'recorded';
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RAISE;
            END;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIII2. Consequence immutability trigger (defense in depth behind
    # the grant revocation): no runtime path may UPDATE bound fields
    # or DELETE evidence; recorded_by is forced to session_user.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_consequence_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF session_user IS DISTINCT FROM 'app_ingress'
                   AND session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_auth_cons_caller_refused'
                        USING ERRCODE = '42501';
                END IF;
                NEW.recorded_by := session_user;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.provider IS DISTINCT FROM NEW.provider
                   OR OLD.provider_event_reference IS DISTINCT FROM NEW.provider_event_reference
                   OR OLD.body_sha256 IS DISTINCT FROM NEW.body_sha256
                   OR OLD.signature_envelope_sha256 IS DISTINCT FROM NEW.signature_envelope_sha256
                   OR OLD.auth_method IS DISTINCT FROM NEW.auth_method
                   OR COALESCE(OLD.auth_version, 'v1') IS DISTINCT FROM COALESCE(NEW.auth_version, 'v1')
                   OR OLD.webhook_ingress_identity_id IS DISTINCT FROM NEW.webhook_ingress_identity_id
                   OR OLD.tenant_id IS DISTINCT FROM NEW.tenant_id THEN
                    RAISE EXCEPTION 'b26_p2_auth_cons_immutable_refused'
                        USING ERRCODE = '42501';
                END IF;
                NEW.recorded_by := OLD.recorded_by;
                RETURN NEW;
            END IF;
            IF TG_OP = 'DELETE' THEN
                -- Fixture cleanup and lawful retention run as migration
                -- admins; runtime principals can never delete evidence
                -- (they hold no DELETE grant, and this gate refuses them
                -- even where a grant exists).
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    RAISE EXCEPTION 'b26_p2_auth_cons_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_auth_consequence_immutability ON public.b26_p2_provider_auth_consequence"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_auth_consequence_immutability
        BEFORE INSERT OR UPDATE OR DELETE ON public.b26_p2_provider_auth_consequence
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_auth_consequence_immutability()
        """
    )

    # ------------------------------------------------------------------
    # XIII3. Provenance INSERT fix: no durable intermediate state is
    # authenticated_known. Every verified INSERT lands as
    # pending_authentication (explicitly non-dispatchable,
    # non-P3-eligible). Promotion occurs only through the evidence
    # UPDATE guard below, which requires consequence + bound witness
    # + evidence in the same check. NULL-safe throughout.
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
                -- XIII: INSERT-time authority is never granted. The
                -- authentication root's authoritative transition is the
                -- evidence UPDATE below; until then the row is pending
                -- and physically non-dispatchable (dispatch + P3 gates
                -- require authenticated_known AND witness).
                NEW.b26_p2_provenance_status := 'pending_authentication';
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                   AND NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    -- Promotion to verified lands pending; the evidence
                    -- guard below advances it only with full evidence.
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
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIII4. Dispatch law: dispatch may not select on verified-alone.
    # It requires the exact terminal authentication state AND witness
    # existence. NULL-safe (IS NOT DISTINCT FROM); missing ingress
    # refuses; pending rows are non-dispatchable by law.
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
    # XIII5. Atomic authentication transition: one database
    # transaction commits consequence + witness + evidence + terminal
    # provenance together. Only the authentication trust root may
    # execute it. Crash before commit leaves fully pending state
    # (lawful retry completes); crash after commit leaves fully
    # authenticated state. No intermediate state is dispatchable.
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
             WHERE i.id = p_ingress;
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
                -- Consequence (immutable: refuse rewrite).
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
                -- Witness (deterministic binding).
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
                -- Evidence + terminal provenance in the SAME transaction.
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
        "REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) TO app_ingress;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIII6. Topology law: strict regime now includes the XIII
    # authorship closure (app_user has no recorder EXECUTE; ingress
    # holds the atomic transition). Provisioner converges to it.
    # ------------------------------------------------------------------
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
        "REVOKE ALL ON FUNCTION public.b26_p2_xiii_topology_check() FROM PUBLIC"
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
                        'GRANT EXECUTE ON FUNCTION public.b26_p2_xiii_topology_check() TO %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xiii_provision_ingress_topology()
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF session_user NOT IN ('migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_xiii_provision_refused'
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
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) TO app_ingress;
            -- Dispatch (as app_user) reads the witness for the terminal
            -- law; SELECT confers zero authorship.
            GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) FROM app_user;
            RETURN 'xiii_topology_provisioned';
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xiii_provision_ingress_topology() FROM PUBLIC"
    )

    # Keep the XII provisioner converged to the XIII law (idempotent):
    # late provisioning installs the atomic grant and removes app_user
    # authorship even when invoked through the XII entrypoint.
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
            GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) TO app_ingress;
            GRANT EXECUTE ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) TO app_ingress;
            -- Dispatch (as app_user) reads the witness for the terminal
            -- law; SELECT confers zero authorship.
            GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM app_user;
            REVOKE ALL ON FUNCTION public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text) FROM app_user;
            RETURN 'xii_topology_provisioned';
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XIII7. Oracle extension: pending rows with witnesses, and
    # verified+known rows without full evidence, are survivors.
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
            -- Witness without consequence (self-certified token).
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
            -- INSERT-time authority: verified + known with zero
            -- consequence and zero witness (partial state conducting).
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
            RETURN;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xiii_invariant_oracle() FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xiii_invariant_oracle()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xiii_provision_ingress_topology()"
    )
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_xiii_topology_check()")
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_authenticate_ingress_atomic(uuid, text, text, text, text, text, text)"
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_auth_consequence_immutability ON public.b26_p2_provider_auth_consequence"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_enforce_auth_consequence_immutability()"
    )
    # NOTE: grant/function-body tightening above is intentionally NOT
    # rolled back here: a downgrade from XIII leaves the strict
    # authorship/provenance/dispatch law in place (fail-closed), and a
    # re-upgrade converges back to full XIII. Predecessor (XII)
    # app_user authorship is never reintroduced by this path.
