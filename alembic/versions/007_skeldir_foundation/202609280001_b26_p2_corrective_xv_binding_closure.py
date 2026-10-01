"""B2.6-P2 Corrective XV: cryptographic meaning binding closure at the DB plane.

Revision ID: 202609280001
Revises: 202609270003

Closes the XIV survivor classes at their physical roots (Directive XV,
H-XV-R3/R4/R5/R6/R11):

XV1. TRANSITION-SPECIFIC EVIDENCE CAPABILITY (H-XV-R4). The XIV
    owner-agnostic gate admitted INSERT from ANY SECURITY DEFINER context
    (context-class authority). The gate now requires the call stack to
    contain the single sovereign transition
    (b26_p2_authenticate_ingress_atomic) -- verified via PG_CONTEXT --
    or direct migration-admin authorship. An administrator-authored deputy
    DEFINER routine no longer mints evidence: its stack names the deputy,
    not the atomic, and the INSERT is refused with
    b26_p2_auth_root_evidence_transition_refused. Runtime GRANTs deny
    direct writes first; this trigger is the backstop.

XV2. AUTHENTICATED MEANING IMMUTABILITY (H-XV-R5). The XIV temporal
    hardening covered conducted verdicts but left the authenticated (yet
    not-yet-conducted) ingress interval writable: verified_amount_minor
    7600 -> 9999 succeeded while the row remained authenticated_known.
    Once a row carries authenticity_verified state or authenticated_known
    provenance, every commerce-meaning column (tenant, provider, event and
    commerce references, normalized kind/value, amount, currency, scale,
    timestamp, idempotency identity) is immutable by database law. (The
    Skeldir event_id link is intentionally unfenced to preserve genuine
    duplicate re-ingestion.) A meaning-changing update fails closed with
    b26_p2_authenticated_meaning_immutable_refused. Precursor promotion
    (pending -> verified) is unaffected: the OLD row is not yet
    authenticated. The atomic's own provenance promotion (pending ->
    known, commerce columns untouched) is unaffected.

XV3. DOWNGRADE MONOTONICITY (H-XV-R11). Once the system has established
    that a historical lineage is unverifiable, no supported schema
    rollback may silently transform that fact into trusted authority. A
    BEFORE DELETE trigger on the execution quarantine refuses removal of
    historically_unverifiable_xiv dispositions
    (b26_p2_quarantine_historical_delete_refused) -- for ANY principal,
    including migration admins. The XIV downgrade path (which deletes
    those rows and drops the evidence table, resurrecting forged
    lineages as authenticated_known / P3-eligible) now fails closed with
    its transaction rolled back and state preserved. Probe dispositions
    (xiv_probe_quarantine, test artifacts) remain cleanable. No
    legitimate deletion path for known-unverifiable history exists by
    design; retirement, if ever required, is a deliberate reviewed
    migration, not a silent rollback side effect.

XV4. PROVISIONER CONVERGENCE. The XIV provisioner is re-declared with the
    XV trigger set so fresh and upgraded lanes converge on identical
    enforcement. No grant widening: the runtime privilege set is unchanged
    (ordinary principals gain nothing; the atomic remains the sole writer).

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved. Tenant RLS
FORCE untouched. Integer-minor money untouched. All B2.6 authority checks
use IS DISTINCT FROM (NULL-safe); no new nullable authority columns.

Downgrade semantics: XV2 (meaning immutability) is rolled back because
it reads a column predecessor schemas lack; the XIV evidence gate is
restored verbatim so a downgraded lane behaves exactly as XIV
specified. The quarantine finality guard persists across downgrade by
design (it references only the long-stable `reason` column).
"""

from __future__ import annotations

from alembic import op

revision = "202609280001"
down_revision = "202609270003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "LOCK TABLE public.webhook_ingress_identities IN SHARE ROW EXCLUSIVE MODE"
    )
    op.execute(
        "LOCK TABLE public.b26_p2_auth_root_evidence IN SHARE ROW EXCLUSIVE MODE"
    )

    # ------------------------------------------------------------------
    # XV1. Transition-specific evidence capability.
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
                    -- PG_CONTEXT contains the atomic's frame. Any other
                    -- SECURITY DEFINER routine (an administrator-authored
                    -- deputy, a future helper, a confused deputy) carries
                    -- its own frame instead and is refused here.
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

    # ------------------------------------------------------------------
    # XV2. Authenticated meaning immutability.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_authenticated_meaning_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                -- Only authenticated rows are fenced. Pending precursors
                -- (promotion pending -> verified) and non-authenticated
                -- states pass through to the sibling guards.
                IF OLD.verified_commerce_ingress_state IS NOT DISTINCT FROM 'authenticity_verified'
                   OR OLD.b26_p2_provenance_status IS NOT DISTINCT FROM 'authenticated_known' THEN
                    IF OLD.tenant_id IS DISTINCT FROM NEW.tenant_id
                       OR OLD.provider IS DISTINCT FROM NEW.provider
                       OR OLD.provider_native_event_reference IS DISTINCT FROM NEW.provider_native_event_reference
                       OR OLD.provider_native_commerce_reference IS DISTINCT FROM NEW.provider_native_commerce_reference
                       OR OLD.normalized_commerce_reference_kind IS DISTINCT FROM NEW.normalized_commerce_reference_kind
                       OR OLD.normalized_commerce_reference_value IS DISTINCT FROM NEW.normalized_commerce_reference_value
                       OR OLD.verified_amount_minor IS DISTINCT FROM NEW.verified_amount_minor
                       OR OLD.verified_amount_currency IS DISTINCT FROM NEW.verified_amount_currency
                       OR OLD.verified_amount_scale IS DISTINCT FROM NEW.verified_amount_scale
                       OR OLD.event_timestamp IS DISTINCT FROM NEW.event_timestamp
                       OR OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key THEN
                        -- NOTE: the Skeldir event_id link is intentionally
                        -- not fenced: genuine duplicate re-ingestion rebinds
                        -- it while financial meaning stays fixed.
                        RAISE EXCEPTION 'b26_p2_authenticated_meaning_immutable_refused'
                            USING ERRCODE = '42501';
                    END IF;
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_authenticated_meaning_immutability ON public.webhook_ingress_identities"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_authenticated_meaning_immutability
        BEFORE UPDATE ON public.webhook_ingress_identities
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_authenticated_meaning_immutability()
        """
    )

    # ------------------------------------------------------------------
    # XV3. Historical monotonicity: known-unverifiable quarantine rows
    # cannot be deleted by any principal through any path -- including
    # the XIV downgrade, which deletes them and drops the evidence
    # table. Probe dispositions (xiv_probe_quarantine test artifacts)
    # remain cleanable so validators keep their hygiene.
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_quarantine_historical_finality()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF OLD.reason IS NOT DISTINCT FROM 'historically_unverifiable_xiv' THEN
                    RAISE EXCEPTION 'b26_p2_quarantine_historical_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF OLD.reason IS NOT DISTINCT FROM 'historically_unverifiable_xiv'
                   AND NEW.reason IS DISTINCT FROM 'historically_unverifiable_xiv' THEN
                    RAISE EXCEPTION 'b26_p2_quarantine_historical_delete_refused'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            RETURN NEW;
        END $$;
        """
    )
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_quarantine_historical_finality ON public.b26_p2_execution_quarantine"
    )
    op.execute(
        """
        CREATE TRIGGER trg_b26_p2_quarantine_historical_finality
        BEFORE DELETE OR UPDATE ON public.b26_p2_execution_quarantine
        FOR EACH ROW EXECUTE FUNCTION public.b26_p2_enforce_quarantine_historical_finality()
        """
    )

    # ------------------------------------------------------------------
    # XV4. Provisioner convergence (re-declare with XV enforcement).
    # ------------------------------------------------------------------
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


def downgrade() -> None:
    # Roll back XV2 (authenticated-meaning immutability): its trigger
    # reads b26_p2_provenance_status, a column predecessor schemas
    # (below XI) do not have. Leaving it in place would break every
    # ingress UPDATE on a downgraded lane (failed downgrade lanes are
    # not fail-closed, they are broken). A downgraded lane gets exactly
    # predecessor guarantees -- documented, not silent.
    op.execute(
        "DROP TRIGGER IF EXISTS trg_b26_p2_authenticated_meaning_immutability"
        " ON public.webhook_ingress_identities"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS"
        " public.b26_p2_enforce_authenticated_meaning_immutability()"
    )
    # Restore the XIV owner-agnostic evidence gate verbatim (270003 law),
    # so the downgraded lane behaves exactly as XIV specified.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b26_p2_enforce_auth_root_evidence_immutability()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path TO 'pg_catalog', 'public'
        AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                -- Owner-agnostic gate with two lawful paths: (1) through
                -- a SECURITY DEFINER routine (the atomic transition),
                -- where current_user (the routine owner, whatever lane
                -- role created it) differs from session_user (the
                -- trust-root caller); (2) direct maintenance by a
                -- migration admin (seeders/provisioners running as
                -- migration_owner/postgres). Direct writes as any other
                -- principal, including the trust-root role itself, have
                -- identical current/session users and are refused
                -- (table GRANTs deny runtime roles first; this is the
                -- backstop).
                IF current_user IS NOT DISTINCT FROM session_user
                   AND session_user IS DISTINCT FROM 'migration_owner'
                   AND session_user IS DISTINCT FROM 'postgres' THEN
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
    # The quarantine historical-finality trigger is intentionally NOT
    # rolled back: it references only the long-stable `reason` column
    # and blocks resurrection of known-unverifiable history through any
    # deeper downgrade (including the XIV downgrade path). Re-upgrade
    # converges the full XV enforcement set.
