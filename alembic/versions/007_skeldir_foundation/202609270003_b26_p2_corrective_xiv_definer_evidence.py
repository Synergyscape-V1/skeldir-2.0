"""B2.6-P2 Corrective XIV: owner-agnostic DEFINER evidence gate.

Revision ID: 202609270003
Revises: 202609270002

Corrects the 202609270001 evidence immutability gate, which permitted
INSERT only when current_user is migration_owner/postgres. Lanes whose
migrations run under a lane-owner role (e.g. R3's r3 owner) create the
atomic transition owned by that role, so DEFINER-mediated evidence
writes carried current_user=r3 and were wrongly refused even though
they traversed the single authoritative commit interface.

The corrected law is owner-agnostic and physically precise: an INSERT
is permitted only when it executes under DEFINER privilege escalation
(current_user IS DISTINCT FROM session_user), i.e. through a SECURITY
DEFINER routine such as the atomic transition. Direct writes as any
runtime principal (current_user = session_user, in particular the
trust-root role itself) are refused; the table GRANTs independently
deny them. UPDATE/DELETE law is unchanged.

No P3/P4/P5/P8 state. B2.4/B2.13/LLM zero. B2.5-P14 conserved.
"""

from __future__ import annotations

from alembic import op

revision = "202609270003"
down_revision = "202609270002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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


def downgrade() -> None:
    # Fail-closed: keep the corrected gate on downgrade; re-upgrade converges.
    pass
