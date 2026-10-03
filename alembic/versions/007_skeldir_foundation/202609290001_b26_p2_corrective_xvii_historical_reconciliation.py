"""B2.6-P2 Corrective XVII: historical semantic reconciliation at the DB plane.

Revision ID: 202609290001
Revises: 202609280002

Conservation law closed here (past AND future state):

    PROVIDER EVIDENCE = GOVERNED PROVIDER SEMANTICS
    = CANONICAL EVENT IDENTITY = PERSISTED FINANCIAL MEANING
    = HISTORICALLY JUSTIFIED AUTHORITY = DOWNSTREAM P3 TRUTH

XVII1. SEMANTIC-REGIME IDENTITY + HISTORICAL DISPOSITION (H-XVII-R1/R2/R3).
    New non-nullable ``b26_p2_semantic_regime`` on ingress rows, defaulting
    to ``pre-xvii-unverifiable``. The atomic stamps
    ``xvii-sovereign-v1`` (the governed contract regime) on every new
    authentication. The upgrade deterministically demotes EVERY still-trusted
    row that cannot prove byte->meaning binding to ``pending_authentication``
    with explicit ``b26_p2_demotion_reason = 'xvii-pre-binding-unverifiable'``
    (single tenant-looped statement, provenance trigger disabled around it
    per the established XIV/XVI pattern, re-enabled in the same
    transaction). Rationale (H-XVII-R19): raw provider bytes are not
    retained by privacy law and the witness never bound the semantic tuple,
    so no historical row can prove its persisted meaning was derived from
    its authenticated bytes -- including rows carrying modern-shape
    evidence minted under the XIV handoff regime. Conservative demotion is
    the only defensible architecture; re-authentication happens naturally
    via provider redelivery (adopt-or-promote), which now produces a
    regime-stamped, tuple-bound lineage. Redelivery of a demoted row clears
    the reason in the same atomic transition.

XVII2. PROVIDER-EVENT + COMMERCE IDENTITY CONSERVATION (H-XVII-R4/R5/R6).
    The XVI fence refused same-bytes/same-reference re-mints only. The
    atomic now additionally refuses, with distinct tokens:
      same (tenant, provider, event reference), different body
        -> b26_p2_atomic_event_identity_conflict_refused
      same (tenant, provider, commerce kind, commerce value) across
      distinct events
        -> b26_p2_atomic_commerce_identity_conflict_refused
    Same-row re-entry stays idempotent; pending rows never block. Two new
    partial unique indexes make the law physical under every writer and
    every race (advisory locks serialize the friendly-token path; the
    index is the backstop). Governed contract law: one immutable provider
    event = one canonical lineage; one economic commerce identity = one
    canonical financial fact within the supported lifecycle.

XVII3. SEMANTIC-TUPLE BINDING (H-XVII-R12). The witness digest preimage
    now covers the derived semantic tuple (commerce kind/value, amount,
    currency, scale, canonical UTC instant) in addition to the
    cryptographic identity. Tuple change without witness change is
    impossible (meaning-immutability trigger); witness change without the
    atomic is impossible (no runtime grants); staleness from regime
    rotation is repaired deterministically inside the atomic on
    re-authentication. ``b26_p2_xvii_semantic_binding_oracle()`` recomputes
    every trusted row's witness and reports detachment, regime drift, and
    duplicate canonical groups.

XVII4. REGIME-GATED DISPATCH/P3/RESOLVER (H-XVII-R2/R18). Dispatch,
    P3 eligibility, and the sovereign admission resolver additionally
    require ``b26_p2_semantic_regime = 'xvii-sovereign-v1'``. Historical
    invalidation and dispatch exclusion are one transaction: demotion is a
    single statement under table lock, and every dispatch edge re-checks
    provenance + regime at use time, so no stale row can escape the sweep
    or dispatch after being determined invalid.

XVII5. DEMOTION-REASON PROVENANCE (H-XVII-R14). ``b26_p2_demotion_reason``
    distinguishes ``pending`` (never authenticated) from
    ``pending + reason`` (previously trusted, later demoted because its
    proof regime became invalid). Non-authoritative marker: it gates
    nothing, it explains.

No grant widening. No new nullable authority columns. All new predicates
use IS DISTINCT FROM (NULL-safe). No caller-settable GUC carries
privilege. No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. Tenant RLS FORCE
untouched. Integer-minor money untouched. New forward migration only:
no already-deployed revision is edited (H-XVII-R13).

Downgrade semantics: restores the 280002 atomic, the 270001 dispatch
trigger, the 240002 P3 function, and the VI resolver verbatim; drops the
new indexes and the oracle; keeps the regime/reason columns (defaulted,
ORM-safe) and keeps demoted rows pending (honest: rollback must not
resurrect unverifiable authority). Re-upgrade re-stamps via redelivery.
"""

from __future__ import annotations

from alembic import op

revision = "202609290001"
down_revision = "202609280002"
branch_labels = None
depends_on = None

# Governed semantic-regime identity. MUST equal the provider semantic
# contract's ``semantic_regime`` and the parser's
# SEMANTIC_CONTRACT_REGIME. The contract gate asserts all three agree.
_XVII_REGIME = "xvii-sovereign-v1"
_XVII_LEGACY_REGIME = "pre-xvii-unverifiable"
_XVII_DEMOTION_REASON = "xvii-pre-binding-unverifiable"


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
    op.execute(
        "LOCK TABLE public.b26_p2_ingress_auth_witness IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XVII1a. Regime + reason columns. NOT NULL with a legacy default so
    # every pre-XVII row is born classified as unverifiable: no
    # grandfathering by row shape.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " ADD COLUMN IF NOT EXISTS b26_p2_semantic_regime text NOT NULL"
        f" DEFAULT '{_XVII_LEGACY_REGIME}'"
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " ADD COLUMN IF NOT EXISTS b26_p2_demotion_reason text DEFAULT NULL"
    )

    # ------------------------------------------------------------------
    # XVII1b. Historical disposition: every still-trusted row whose
    # semantic authority cannot be justified becomes explicitly
    # non-authoritative with an explicit reason. Tenant-looped (RLS
    # FORCE respected); the provenance trigger exists precisely to stop
    # non-migration authors doing this, so it is disabled around the
    # single disposition statement and re-enabled in the same
    # transaction (established XIV/XVI pattern). The meaning-immutability
    # trigger is untouched: only provenance + reason change.
    # ------------------------------------------------------------------
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " DISABLE TRIGGER trg_b26_p2_ingress_provenance"
    )
    op.execute(
        """
        DO $$
        DECLARE _t uuid;
        BEGIN
            FOR _t IN SELECT id FROM public.tenants LOOP
                PERFORM set_config('app.current_tenant_id', _t::text, true);
                UPDATE public.webhook_ingress_identities AS i
                   SET b26_p2_provenance_status = 'pending_authentication',
                       b26_p2_demotion_reason = '%s'
                 WHERE i.tenant_id = _t
                   AND i.b26_p2_provenance_status
                       IS NOT DISTINCT FROM 'authenticated_known'
                   AND i.b26_p2_semantic_regime
                       IS DISTINCT FROM '%s';
            END LOOP;
            PERFORM set_config('app.current_tenant_id', '', true);
        END $$;
        """
        % (_XVII_DEMOTION_REASON, _XVII_REGIME)
    )
    op.execute(
        "ALTER TABLE public.webhook_ingress_identities"
        " ENABLE TRIGGER trg_b26_p2_ingress_provenance"
    )

    # ------------------------------------------------------------------
    # XVII2a. Physical identity conservation: partial unique indexes.
    # Built AFTER disposition, so no historical duplicate can block the
    # build and no two canonical truths for one sovereign identity can
    # survive. Only authenticated_known rows participate: pending
    # precursors, demoted history, and crash-retry rows never collide.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_b26_p2_xvii_event_identity
            ON public.webhook_ingress_identities
               (tenant_id, provider, provider_native_event_reference)
         WHERE b26_p2_provenance_status = 'authenticated_known'
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_b26_p2_xvii_commerce_identity
            ON public.webhook_ingress_identities
               (tenant_id, provider,
                normalized_commerce_reference_kind,
                normalized_commerce_reference_value)
         WHERE b26_p2_provenance_status = 'authenticated_known'
        """
    )

    # ------------------------------------------------------------------
    # XVII2b/XVII3. Atomic with identity conservation, tuple-bound
    # witness, and regime stamping. XVI fence + strict frame preserved
    # verbatim (same 7-argument signature: the evidence-gate regex still
    # matches). New conflict tokens are distinct from the duplicate
    # token so gates can tell redelivery (idempotent) from conflicting
    # provider truth (refused).
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
                   i.b26_p2_semantic_regime
              INTO _tenant, _idem, _state, _row_provider, _prov,
                   _t_kind, _t_value, _t_cref, _t_amount, _t_ccy, _t_scale,
                   _t_ts, _sem_regime
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
                -- now justified under current law.
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
    # XVII4a. Dispatch law: quarantined, unwitnessed, unprovenanced, or
    # regime-unverifiable state cannot dispatch anew. The regime clause
    # is what makes the semantic identity actually constrain trust.
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
            _witness text;
        BEGIN
            SELECT i.b26_p2_provenance_status, i.b26_p2_semantic_regime
              INTO _prov, _regime
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
    # XVII4b. P3 eligibility: historically + currently valid authority
    # only. The regime clause closes the XIV-survivor P3 path: an old
    # unbound row can no longer conduct merely by wearing modern-shape
    # evidence.
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

    # ------------------------------------------------------------------
    # XVII4c. Sovereign admission resolver: the admitted ingress must be
    # verified AND provenance-trusted AND regime-governed. A demoted or
    # pre-regime row can no longer found worker authority even when its
    # window is sovereign.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_resolve_dispatch_authority(
            p_task_id text
        )
        RETURNS TABLE (
            tenant_id uuid,
            webhook_ingress_identity_id uuid,
            window_start timestamp with time zone,
            window_end timestamp with time zone
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dir_ws timestamptz;
            _dir_we timestamptz;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _ingress_prov text;
            _ingress_regime text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RETURN;
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id,
                   dir.window_start, dir.window_end
              INTO _tenant, _ingress, _dir_ws, _dir_we
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end
                  INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_authority_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_ws IS DISTINCT FROM _dir_ws
                   OR _dispatch_we IS DISTINCT FROM _dir_we THEN
                    RAISE EXCEPTION 'b26_p2_directory_forked_authority_refused'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state,
                       i.b26_p2_provenance_status, i.b26_p2_semantic_regime
                  INTO _clock, _ingress_state, _ingress_prov, _ingress_regime
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_prov IS DISTINCT FROM 'authenticated_known' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_provenance_unknown'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_regime IS DISTINCT FROM 'xvii-sovereign-v1' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_regime_unverifiable'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                tenant_id := _tenant;
                webhook_ingress_identity_id := _ingress;
                window_start := _exp_ws;
                window_end := _exp_we;
                RETURN NEXT;
                RETURN;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )

    # ------------------------------------------------------------------
    # XVII6. Semantic-binding oracle: recomputes every trusted row's
    # tuple-bound witness and reports detachment, regime drift, and
    # duplicate canonical groups. Read-only; the contract/physics gates
    # execute it on every lane.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_xvii_semantic_binding_oracle()
        RETURNS TABLE (violation_kind text, task_ref text, detail text)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _canon text;
            _expected text;
        BEGIN
            -- Tuple-bound witness mismatch on trusted rows.
            FOR task_ref, detail, _canon, _expected IN
                SELECT ('ingress:' || i.id::text)::text,
                       ('ingress=' || i.id::text)::text,
                       to_char(i.event_timestamp AT TIME ZONE 'UTC',
                               'YYYY-MM-DD HH24:MI:SS.US'),
                       encode(digest(
                           i.tenant_id::text || '|' || i.id::text || '|'
                           || c.provider || '|' || c.provider_event_reference || '|'
                           || lower(c.body_sha256) || '|'
                           || lower(c.signature_envelope_sha256) || '|'
                           || c.auth_method || '|' || COALESCE(c.auth_version, 'v1') || '|'
                           || COALESCE(i.normalized_commerce_reference_kind, '') || '|'
                           || COALESCE(i.normalized_commerce_reference_value, '') || '|'
                           || COALESCE(i.verified_amount_minor::text, '') || '|'
                           || COALESCE(i.verified_amount_currency, '') || '|'
                           || COALESCE(i.verified_amount_scale::text, '') || '|'
                           || COALESCE(to_char(i.event_timestamp AT TIME ZONE 'UTC',
                                               'YYYY-MM-DD HH24:MI:SS.US'), ''),
                           'sha256'), 'hex')
                  FROM public.webhook_ingress_identities AS i
                  JOIN public.b26_p2_provider_auth_consequence AS c
                    ON c.webhook_ingress_identity_id = i.id
                   AND c.tenant_id = i.tenant_id
                 WHERE i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
            LOOP
                -- Compare inside the loop against the stored witness.
                PERFORM 1 FROM public.b26_p2_ingress_auth_witness AS w
                 WHERE w.webhook_ingress_identity_id = split_part(task_ref, ':', 2)::uuid
                   AND w.witness_hash IS NOT DISTINCT FROM _expected;
                IF NOT FOUND THEN
                    violation_kind := 'xvii_semantic_tuple_detached';
                    RETURN NEXT;
                END IF;
            END LOOP;
            -- Regime drift: trusted rows outside the governed regime.
            RETURN QUERY
            SELECT 'xvii_regime_unverifiable_trusted'::text,
                   ('ingress:' || i.id::text)::text,
                   ('ingress=' || i.id::text)::text
              FROM public.webhook_ingress_identities AS i
             WHERE i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
               AND i.b26_p2_semantic_regime IS DISTINCT FROM 'xvii-sovereign-v1';
            -- Duplicate canonical event lineages for one provider event.
            RETURN QUERY
            SELECT 'xvii_duplicate_canonical_event'::text,
                   ('tenant=' || i.tenant_id::text)::text,
                   ('event_ref=' || i.provider_native_event_reference)::text
              FROM public.webhook_ingress_identities AS i
             WHERE i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
             GROUP BY i.tenant_id, i.provider, i.provider_native_event_reference
            HAVING count(*) > 1;
            -- Duplicate canonical financial facts for one commerce identity.
            RETURN QUERY
            SELECT 'xvii_duplicate_canonical_commerce'::text,
                   ('tenant=' || i.tenant_id::text)::text,
                   ('commerce=' || i.normalized_commerce_reference_kind
                    || ':' || i.normalized_commerce_reference_value)::text
              FROM public.webhook_ingress_identities AS i
             WHERE i.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known'
             GROUP BY i.tenant_id, i.provider,
                      i.normalized_commerce_reference_kind,
                      i.normalized_commerce_reference_value
            HAVING count(*) > 1;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.b26_p2_xvii_semantic_binding_oracle() FROM PUBLIC"
    )


def downgrade() -> None:
    # Restore predecessor law verbatim (documented, not silent). Demoted
    # rows stay pending: rollback must not resurrect unverifiable
    # authority. Regime/reason columns stay (defaulted, ORM-safe).
    op.execute("DROP INDEX IF EXISTS public.uq_b26_p2_xvii_event_identity")
    op.execute("DROP INDEX IF EXISTS public.uq_b26_p2_xvii_commerce_identity")
    op.execute(
        "DROP FUNCTION IF EXISTS public.b26_p2_xvii_semantic_binding_oracle()"
    )
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
    # Roll back XVII4b: restore the 240002 P3 function verbatim.
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
            IF _tenant IS NULL
               OR NOT EXISTS (
                    SELECT 1 FROM public.tenants AS t WHERE t.id = _tenant
               ) THEN
                PERFORM set_config(
                    'app.current_tenant_id', COALESCE(_prev_guc, ''), true
                );
                RETURN FALSE;
            END IF;
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
    # Roll back XVII4c: restore the VI sovereign admission resolver
    # verbatim (provenance/regime clauses were XVII additions).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_resolve_dispatch_authority(
            p_task_id text
        )
        RETURNS TABLE (
            tenant_id uuid,
            webhook_ingress_identity_id uuid,
            window_start timestamp with time zone,
            window_end timestamp with time zone
        )
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        DECLARE
            _task text;
            _tenant uuid;
            _ingress uuid;
            _dir_ws timestamptz;
            _dir_we timestamptz;
            _dispatch_ws timestamptz;
            _dispatch_we timestamptz;
            _clock timestamptz;
            _ingress_state text;
            _exp_ws timestamptz;
            _exp_we timestamptz;
            _prev_guc text;
        BEGIN
            _task := btrim(COALESCE(p_task_id, ''));
            IF _task = '' THEN
                RETURN;
            END IF;
            SELECT dir.tenant_id, dir.webhook_ingress_identity_id,
                   dir.window_start, dir.window_end
              INTO _tenant, _ingress, _dir_ws, _dir_we
              FROM public.b26_p2_task_authority_directory AS dir
             WHERE dir.task_id = _task;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            BEGIN
                _prev_guc := current_setting('app.current_tenant_id', true);
            EXCEPTION WHEN OTHERS THEN
                _prev_guc := NULL;
            END;
            PERFORM set_config('app.current_tenant_id', _tenant::text, true);
            BEGIN
                SELECT d.window_start, d.window_end
                  INTO _dispatch_ws, _dispatch_we
                  FROM public.b23_match_task_dispatches AS d
                 WHERE d.task_id = _task;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_authority_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _dispatch_ws IS DISTINCT FROM _dir_ws
                   OR _dispatch_we IS DISTINCT FROM _dir_we THEN
                    RAISE EXCEPTION 'b26_p2_directory_forked_authority_refused'
                        USING ERRCODE = '42501';
                END IF;
                SELECT i.event_timestamp, i.verified_commerce_ingress_state
                  INTO _clock, _ingress_state
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.id = _ingress
                   AND i.tenant_id = _tenant;
                IF NOT FOUND THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_missing'
                        USING ERRCODE = '42501';
                END IF;
                IF _ingress_state IS DISTINCT FROM 'authenticity_verified' THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_sovereign_ingress_unverified'
                        USING ERRCODE = '42501';
                END IF;
                _exp_ws := public.b26_p2_canonical_day_start(_clock);
                _exp_we := public.b26_p2_canonical_day_end(_clock);
                IF _dispatch_ws IS DISTINCT FROM _exp_ws
                   OR _dispatch_we IS DISTINCT FROM _exp_we THEN
                    RAISE EXCEPTION 'b26_p2_dispatch_window_not_sovereign'
                        USING ERRCODE = '42501';
                END IF;
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                tenant_id := _tenant;
                webhook_ingress_identity_id := _ingress;
                window_start := _exp_ws;
                window_end := _exp_we;
                RETURN NEXT;
                RETURN;
            EXCEPTION WHEN OTHERS THEN
                PERFORM set_config('app.current_tenant_id',
                                   COALESCE(_prev_guc, ''), true);
                RAISE;
            END;
        END $$;
        """
    )
    # Roll back XVII2b/XVII3: restore the 280002 atomic verbatim so a
    # downgraded lane behaves exactly as XVI specified (documented, not
    # silent). Tuple binding, identity-conflict refusals, and regime
    # stamping are XVI-unknown; demoted rows stay pending via the
    # predecessor provenance trigger.
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
            PERFORM pg_advisory_xact_lock(
                hashtext('b26_p2_sovereign_bytes:' || _tenant::text),
                hashtext(lower(p_body_sha256))
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
