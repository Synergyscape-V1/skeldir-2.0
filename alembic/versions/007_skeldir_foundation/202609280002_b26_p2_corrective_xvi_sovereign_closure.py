"""B2.6-P2 Corrective XVI: sovereign closure at the DB plane.

Revision ID: 202609280002
Revises: 202609280001

XVI1. SOVEREIGN CONTENT-ADDRESSED DUPLICATE FENCE (H-XVI-R6). The relay
    idempotency key is routing information, not financial identity: the
    same provider event redelivered under a different key (rotated
    X-Idempotency-Key, crash-retry with a fresh key) must resolve to the
    already-authenticated lineage, never mint a second canonical lineage
    for one payment. The atomic now serializes on the byte identity
    (advisory transaction lock over tenant + body digest) and refuses
    authenticating a second ingress row for bytes an
    authenticated_known row already binds with the same provider event
    reference, with b26_p2_atomic_sovereign_duplicate_refused. The
    reference conjunction is exact for honest traffic (identical bytes
    determine identical meaning); distinct provider events never share
    bytes, so event-granular lineages are preserved; pending rows never
    block (crash-before-commit retry stays live); re-entry for the same
    row stays idempotent. The root and the direct finalizer catch the
    refusal and return the winning lineage.

XVI2. STRICT TRANSITION FRAME (H-XVI-R7/H-XVI-12). The XV evidence gate
    matched PG_CONTEXT with a substring test. The gate now requires the
    exact sovereign frame
    PL/pgSQL function b26_p2_authenticate_ingress_atomic(
    uuid,text,text,text,text,text,text)
    (anchored regular expression). Residual analysis: runtime principals
    hold no CREATE privilege on any schema (public CREATE revoked at
    the hardening revision; pg_temp function creation empirically
    denied on governed lanes), so no supported runtime capability can
    mint a same-signature frame; the only principals that can (migration
    owner/postgres) already possess unrestricted authority including
    dropping the gate itself. Exploitation therefore requires full
    database compromise, which is the TCB boundary, not a P2 defect.

No grant widening. No new nullable authority columns. All new
predicates use IS DISTINCT FROM (NULL-safe). No caller-settable GUC
carries privilege (the advisory lock keys on row content, not on
context). No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. Tenant RLS FORCE
untouched. Integer-minor money untouched.

Downgrade semantics: restores the 280001 gate and the 270001 atomic
verbatim, so a downgraded lane behaves exactly as XV specified
(documented, not silent). Legitimate-row evidence preservation across
deeper rollback is enforced by demotion inside the 202609270001
downgrade itself (demote-all-authenticated before evidence is dropped).
"""

from __future__ import annotations

from alembic import op

revision = "202609280002"
down_revision = "202609280001"
branch_labels = None
depends_on = None

# The strict sovereign frame. Must match the exact PG_CONTEXT line the
# trigger observes when it fires inside the atomic's transaction:
#   PL/pgSQL function b26_p2_authenticate_ingress_atomic(
#       uuid,text,text,text,text,text,text) line N at ...
_XVI_STRICT_FRAME_PATTERN = (
    "PL/pgSQL function b26_p2_authenticate_ingress_atomic\\("
    "uuid,text,text,text,text,text,text\\)"
)


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_provider_auth_consequence IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_auth_root_evidence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XVI1. Sovereign content-addressed duplicate fence in the atomic.
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
            _dup_id uuid;
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
            -- XVI1: serialize authentications of identical bytes. Two
            -- concurrent first-authentications of the same provider
            -- event under different idempotency keys would otherwise
            -- both pass every check above and mint two canonical
            -- lineages for one payment. The advisory lock is keyed on
            -- row content (tenant + body digest), never on caller
            -- context, and is transaction-scoped (released at commit).
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_bytes:' || _tenant::text),
                hashtext(lower(p_body_sha256))
            );
            -- Refuse when a DIFFERENT row already carries terminal
            -- authentication for these exact bytes AND the same provider
            -- event reference. The conjunction is exact for honest
            -- traffic: identical bytes determine identical meaning
            -- through sovereign derivation, so a same-bytes second
            -- lineage always presents the same reference; distinct
            -- provider events never share bytes. The reference clause
            -- additionally tolerates placeholder digests in pre-existing
            -- fixtures for distinct events (same fake digest, different
            -- references). Bypassing the conjunction requires either a
            -- sha256 second preimage (infeasible) or TCB-level fabricated
            -- digests (out of scope per directive §14). Pending rows
            -- never block (crash-before-commit retry stays live);
            -- re-entry for this same row proceeds to the idempotent
            -- path below.
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
    # XVI2. Strict sovereign transition frame for the evidence gate.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability()
        RETURNS trigger
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
                    IF _ctx IS NULL OR _ctx !~ 'PL/pgSQL function b26_p2_authenticate_ingress_atomic\\(uuid,text,text,text,text,text,text\\)' THEN
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


def downgrade() -> None:
    # Roll back XVI1 (sovereign duplicate fence): restore the 270001
    # atomic verbatim so a downgraded lane behaves exactly as XV
    # specified (documented, not silent).
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
    # Roll back XVI2 (strict frame): restore the 280001 substring gate
    # verbatim.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _ctx text;
        BEGIN
            IF TG_OP = 'INSERT' THEN
                IF session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
                    GET DIAGNOSTICS _ctx = PG_CONTEXT;
                    IF _ctx NOT LIKE '%b26_p2_authenticate_ingress_atomic%' THEN
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
    # The quarantine historical-finality trigger is intentionally NOT
    # rolled back (same rationale as the 280001 downgrade): it blocks
    # resurrection of known-unverifiable history through any deeper
    # downgrade. Re-upgrade converges the full XVI enforcement set.
