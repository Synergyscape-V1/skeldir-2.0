"""B2.6-P2 Corrective XII: fact-anchored P2-core closure.

Revision ID: 202609250001
Revises: 202609240002

Closes the XI self-certification class: a mechanism may represent a fact
but may not manufacture the fact's own prerequisite and then certify its
own representation.

A. PROVIDER-BOUND AUTHENTICATION EVIDENCE. New
   ``b26_p2_provider_auth_consequence`` relation records the predecessor
   event P (successful provider-signature verification over actual
   provider bytes) as authored by the API application principal
   (app_user) in the HMAC-verified webhook path. The witness is now
   deterministically bound to that consequence
   (tenant/provider/event/ingress/body/method); possession of the
   ingress credential alone cannot complete the chain. ``governed_
   attestation`` is migration/admin custody only at runtime.

B. SINGLE AUTHENTICATION REGIME. All authentication law below is
   strict (no role-existence branching): a lane without the required
   ingress principal migrates with a dead authentication plane and a
   refusing application startup, never predecessor service. Late
   provisioning deterministically installs the exact governed grants
   via ``b26_p2_xii_provision_ingress_topology()`` (contract B).

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved.
Historical migrations immutable; this revision only adds and
redefines forward.
"""

from __future__ import annotations

from alembic import op

revision = "202609250001"
down_revision = "202609240002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # XII0. Single-regime deployment law (Directive §7.2): the
    # authentication LAW below is strict on every lane (no
    # role-existence branching anywhere), so a lane without the
    # ingress principal serves predecessor law nowhere. Unavailability
    # of such a lane is enforced at the serving layers, not by
    # refusing the migration itself: the application refuses startup
    # at the XII head without the principal
    # (backend/app/main.py::_startup_xii_topology_guard), direct
    # database authentication is dead (strict authorship + EXECUTE
    # law), and late provisioning converges deterministically via
    # b26_p2_xii_provision_ingress_topology() (contract B). Refusing
    # the migration here would couple every non-P2 test lane to P2
    # deployment concerns; the fail-closed obligation is discharged
    # where service begins, which §7.2 expressly allows.
    # ------------------------------------------------------------------
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_ingress_auth_witness IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provenance_evidence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XII1. Provider-authentication consequence relation (predecessor
    # event P). Authored by the API application principal in the
    # HMAC-verified webhook path; consumed (never created) by the
    # ingress boundary. No raw provider secrets are retained: only the
    # body digest, a digest of the presented signature envelope, and
    # the binding identities.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.b26_p2_provider_auth_consequence (
            webhook_ingress_identity_id uuid NOT NULL,
            tenant_id uuid NOT NULL
                REFERENCES public.tenants(id) ON DELETE CASCADE,
            provider text NOT NULL
                CONSTRAINT ck_b26_p2_auth_cons_provider_not_blank
                CHECK (char_length(provider) > 0),
            provider_event_reference text NOT NULL
                CONSTRAINT ck_b26_p2_auth_cons_event_ref_not_blank
                CHECK (char_length(provider_event_reference) > 0),
            body_sha256 text NOT NULL
                CONSTRAINT ck_b26_p2_auth_cons_body_sha_format
                CHECK (char_length(body_sha256) = 64),
            signature_envelope_sha256 text NOT NULL
                CONSTRAINT ck_b26_p2_auth_cons_sig_format
                CHECK (char_length(signature_envelope_sha256) = 64),
            auth_method text NOT NULL
                CONSTRAINT ck_b26_p2_auth_cons_method_not_blank
                CHECK (char_length(auth_method) > 0),
            auth_version text NOT NULL DEFAULT 'v1',
            verified_at timestamptz NOT NULL DEFAULT now(),
            recorded_by name NOT NULL,
            CONSTRAINT pk_b26_p2_provider_auth_consequence
                PRIMARY KEY (webhook_ingress_identity_id),
            CONSTRAINT fk_b26_p2_auth_cons_tenant_ingress
                FOREIGN KEY (tenant_id, webhook_ingress_identity_id)
                REFERENCES public.webhook_ingress_identities(tenant_id, id)
                ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "REVOKE ALL ON TABLE public.b26_p2_provider_auth_consequence FROM PUBLIC"
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
                        'REVOKE ALL ON TABLE public.b26_p2_provider_auth_consequence FROM %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
    # P is authored by the API application principal (HMAC path) and
    # observed by the ingress boundary. app_ingress never authors P.
    op.execute(
        "GRANT SELECT, INSERT ON TABLE public.b26_p2_provider_auth_consequence TO app_user"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_ingress;
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b26_p2_provider_auth_consequence ENABLE ROW LEVEL SECURITY"
    )
    op.execute(
        "ALTER TABLE ONLY public.b26_p2_provider_auth_consequence FORCE ROW LEVEL SECURITY"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_policies
                 WHERE schemaname = 'public'
                   AND tablename = 'b26_p2_provider_auth_consequence'
                   AND policyname = 'tenant_isolation_policy_b26_p2_provider_auth_consequence'
            ) THEN
                CREATE POLICY tenant_isolation_policy_b26_p2_provider_auth_consequence
                    ON public.b26_p2_provider_auth_consequence
                    USING (tenant_id = current_setting('app.current_tenant_id')::UUID)
                    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::UUID);
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XII2. Consequence recorder (P). Only the API application
    # principal (and migration admins) may record that provider
    # authentication succeeded. The ingress principal cannot record P,
    # so it cannot manufacture its own prerequisite.
    # ------------------------------------------------------------------
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
            _prev_guc text;
        BEGIN
            IF session_user NOT IN ('app_user', 'migration_owner', 'postgres') THEN
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
                   i.verified_commerce_ingress_state
              INTO _tenant, _idem, _state
              FROM public.webhook_ingress_identities AS i
             WHERE i.id = p_ingress;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_auth_cons_ingress_missing'
                    USING ERRCODE = '42501';
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
                ON CONFLICT (webhook_ingress_identity_id) DO UPDATE SET
                    provider = EXCLUDED.provider,
                    provider_event_reference = EXCLUDED.provider_event_reference,
                    body_sha256 = EXCLUDED.body_sha256,
                    signature_envelope_sha256 = EXCLUDED.signature_envelope_sha256,
                    auth_method = EXCLUDED.auth_method,
                    auth_version = EXCLUDED.auth_version,
                    verified_at = now();
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
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) FROM PUBLIC"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text) TO app_user"
    )

    # ------------------------------------------------------------------
    # XII3. Bound witness (M downstream of P). The single-argument form
    # is now fail-closed: possession of the ingress credential alone
    # proves nothing. The four-argument form derives the witness
    # deterministically from the independently recorded consequence,
    # binding tenant/provider/event/ingress/body/method. No random
    # token can stand in for authentication.
    # ------------------------------------------------------------------
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
        BEGIN
            RAISE EXCEPTION 'b26_p2_witness_no_auth_consequence'
                USING ERRCODE = '42501';
            RETURN NULL;
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
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid) TO app_ingress;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_record_ingress_auth_witness(
            p_ingress uuid,
            p_provider text,
            p_event_ref text,
            p_body_sha256 text
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
            _existing text;
            _witness text;
            _prev_guc text;
        BEGIN
            IF session_user NOT IN ('app_ingress', 'migration_owner', 'postgres') THEN
                RAISE EXCEPTION 'b26_p2_witness_caller_refused'
                    USING ERRCODE = '42501';
            END IF;
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.provider
              INTO _tenant, _idem, _state, _row_provider
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
            IF public.b26_p2_ascii_strip(COALESCE(_row_provider, '')) = '' THEN
                RAISE EXCEPTION 'b26_p2_witness_blank_shape_refused'
                    USING ERRCODE = '42501';
            END IF;
            -- The predecessor event must exist independently of this
            -- call: a consequence row authored by the API application
            -- principal in the HMAC-verified path, binding the same
            -- tenant/provider/event/body.
            SELECT c.provider, c.provider_event_reference, c.body_sha256,
                   c.signature_envelope_sha256, c.auth_method, c.auth_version
              INTO _c_provider, _c_event, _c_body, _c_sig, _c_method, _c_version
              FROM public.b26_p2_provider_auth_consequence AS c
             WHERE c.webhook_ingress_identity_id = p_ingress
               AND c.tenant_id = _tenant;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'b26_p2_witness_no_auth_consequence'
                    USING ERRCODE = '42501';
            END IF;
            IF _c_provider IS DISTINCT FROM p_provider THEN
                RAISE EXCEPTION 'b26_p2_witness_binding_conflict'
                    USING ERRCODE = '42501';
            END IF;
            IF _c_event IS DISTINCT FROM p_event_ref THEN
                RAISE EXCEPTION 'b26_p2_witness_binding_conflict'
                    USING ERRCODE = '42501';
            END IF;
            IF lower(_c_body) IS DISTINCT FROM lower(p_body_sha256) THEN
                RAISE EXCEPTION 'b26_p2_witness_binding_conflict'
                    USING ERRCODE = '42501';
            END IF;
            IF _c_provider IS DISTINCT FROM _row_provider THEN
                RAISE EXCEPTION 'b26_p2_witness_binding_conflict'
                    USING ERRCODE = '42501';
            END IF;
            SELECT w.witness_hash INTO _existing
              FROM public.b26_p2_ingress_auth_witness AS w
             WHERE w.webhook_ingress_identity_id = p_ingress;
            IF FOUND THEN
                RETURN _existing;
            END IF;
            _prov := _tenant::text || '|' || p_ingress::text || '|'
                || _c_provider || '|' || _c_event || '|'
                || lower(_c_body) || '|' || lower(_c_sig) || '|'
                || _c_method || '|' || COALESCE(_c_version, 'v1');
            _witness := encode(digest(_prov, 'sha256'), 'hex');
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
        "REVOKE ALL ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_record_ingress_auth_witness(uuid, text, text, text) TO app_ingress;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XII4. Strict attestation (no role-existence branching). Runtime
    # promotion requires the ingress principal AND a consequence-bound
    # witness. governed_attestation at runtime is migration/admin
    # custody only: the shipping ingress path uses
    # signed_provider_reingestion with a recorded consequence.
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
            SELECT i.tenant_id, i.idempotency_key,
                   i.verified_commerce_ingress_state, i.b26_p2_provenance_status
              INTO _tenant, _idem, _state, _prov_status
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
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT EXECUTE ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text) TO app_ingress;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
                REVOKE ALL ON FUNCTION public.b26_p2_attest_provenance_evidence(uuid, text, text)
                    FROM app_user;
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XII5. Strict authorship/provenance triggers (no branching).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_ingress_verified_authorship()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                    AND session_user NOT IN (
                        'app_ingress', 'migration_owner', 'postgres'
                    ) THEN
                    RAISE EXCEPTION 'b26_p2_verified_authorship_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.verified_commerce_ingress_state IS DISTINCT FROM
               OLD.verified_commerce_ingress_state THEN
                IF NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM
                   'authenticity_verified'
                    AND session_user NOT IN (
                        'app_ingress', 'migration_owner', 'postgres'
                    ) THEN
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
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF NEW.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    NEW.b26_p2_provenance_status := 'pending_not_applicable';
                    RETURN NEW;
                END IF;
                IF session_user IN ('app_ingress', 'migration_owner', 'postgres') THEN
                    NEW.b26_p2_provenance_status := 'authenticated_known';
                ELSE
                    NEW.b26_p2_provenance_status := 'unknown_legacy';
                END IF;
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.verified_commerce_ingress_state IS DISTINCT FROM 'authenticity_verified'
                   AND NEW.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified' THEN
                    IF session_user IN ('app_ingress', 'migration_owner', 'postgres') THEN
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
    # XII6. Ingress grants for the consequence relation + strict
    # re-grant of the XII topology (unconditional: the role exists by
    # the XII0 gate, so no existence branch remains).
    # ------------------------------------------------------------------
    # Grant issuance follows role existence (deployment mechanics);
    # the LAW (function bodies, triggers, RLS) is unconditional above
    # and below. A lane without the role therefore migrates with
    # strict law, zero ingress grants, a dead authentication plane,
    # and a refusing application startup -- never predecessor service.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ingress') THEN
                GRANT USAGE ON SCHEMA public TO app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_provenance_evidence FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_conduction_receipts FROM app_ingress;
                REVOKE ALL ON TABLE public.b23_match_task_dispatches FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_execution_outbox FROM app_ingress;
                REVOKE ALL ON TABLE public.b23_match_verdicts FROM app_ingress;
                REVOKE ALL ON TABLE public.b26_p2_scope_policy_authority FROM app_ingress;
                GRANT SELECT, INSERT, UPDATE ON TABLE public.webhook_ingress_identities TO app_ingress;
                GRANT SELECT ON TABLE public.tenants TO app_ingress;
                GRANT SELECT ON TABLE public.attribution_events TO app_ingress;
                GRANT SELECT ON TABLE public.b23_match_task_dispatches TO app_ingress;
                GRANT SELECT ON TABLE public.b26_p2_provenance_evidence TO app_ingress;
                GRANT SELECT ON TABLE public.b26_p2_ingress_auth_witness TO app_ingress;
                GRANT SELECT ON TABLE public.b26_p2_provider_auth_consequence TO app_ingress;
            ELSE
                RAISE NOTICE 'b26_p2_xii_no_ingress_role:strict_law_dead_auth_plane';
            END IF;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XII7. Topology adjudication + deterministic late provisioning
    # (contract B: late provisioning installs the exact governed
    # grants/topology; there is no third regime).
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
        "REVOKE ALL ON FUNCTION public.b26_p2_xii_topology_check() FROM PUBLIC"
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
                        'GRANT EXECUTE ON FUNCTION public.b26_p2_xii_topology_check() TO %I',
                        _r
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )
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
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xii_provision_ingress_topology() FROM PUBLIC"
    )

    # ------------------------------------------------------------------
    # XII8. Oracle extension: a witness without an independently
    # recorded consequence is a survivor (self-certified token).
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xii_invariant_oracle()
        RETURNS TABLE (violation_kind text, task_ref text, detail text)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            RETURN QUERY
            SELECT 'xii_witness_without_consequence'::text,
                   ('ingress:' || i.id::text)::text,
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
              JOIN public.b26_p2_ingress_auth_witness AS w
                ON w.webhook_ingress_identity_id = i.id
              WHERE i.verified_commerce_ingress_state = 'authenticity_verified'
                AND i.b26_p2_provenance_status = 'authenticated_known'
                AND NOT EXISTS (
                     SELECT 1 FROM public.b26_p2_provider_auth_consequence AS c
                      WHERE c.webhook_ingress_identity_id = i.id
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
        "REVOKE ALL ON FUNCTION public.b26_p2_xii_invariant_oracle() FROM PUBLIC"
    )


def downgrade() -> None:
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xii_invariant_oracle()"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xii_provision_ingress_topology()"
    )
    op.execute("DROP FUNCTION IF EXISTS public.b26_p2_xii_topology_check()")
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_ingress_auth_witness(uuid, text, text, text)"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_record_provider_auth_consequence(uuid, text, text, text, text, text, text)"
    )
    op.execute(
        "DROP TABLE IF EXISTS public.b26_p2_provider_auth_consequence"  # CI:DESTRUCTIVE_OK - reversible rollback removing the XII-only consequence relation; consequences are re-derivable from re-verified provider events, never primary history.
    )
    # Restore the XI single-argument witness + XI attester/trigger
    # branching by re-applying the XI revision's definitions is
    # intentionally NOT done here: a downgrade from XII leaves the
    # strict single-regime functions in place (fail-closed), and a
    # re-upgrade converges back to full XII. Predecessor (XI/X-era)
    # branching is never reintroduced by this path.
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
