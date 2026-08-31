"""B2.5-P13 C17-B: make the issuance guard body order-independent.

Revision ID: 202608312100
Revises: 202608311200

``DECLARE attempt public.trust_issuance_attempts%ROWTYPE`` forces PL/pgSQL to
resolve that table when the function is *created*, not when it runs. ``pg_dump``
emits functions before tables, so the canonical schema artifact could no longer
be applied to an empty database: R2's bootstrap failed with
``relation "public.trust_issuance_attempts" does not exist`` while compiling
this function.

``record`` defers the structure to the ``SELECT ... INTO`` that assigns it, so
the guard keeps identical behaviour -- including the unassigned-to-NULL
semantics the NOT FOUND branches rely on -- while the artifact becomes
order-independent. Nothing about who may write which transition changes here.
"""

from __future__ import annotations

from alembic import op


revision = "202608312100"
down_revision = "202608311200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_access_log_issuance_authority_guard()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            table_owner text;
            consequence_changed boolean;
            attempt record;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_access_log'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF (NEW.event_type = 'issuance' AND NEW.issuance_state <> 'authorized')
                   OR (NEW.event_type <> 'issuance'
                       AND NEW.issuance_state <> 'not_applicable') THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:insert_state:%',
                        NEW.issuance_state USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:tenant_rebind'
                    USING ERRCODE = '42501';
            END IF;
            consequence_changed :=
                NEW.issuance_state IS DISTINCT FROM OLD.issuance_state
                OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                OR NEW.issuance_attempted_at IS DISTINCT FROM OLD.issuance_attempted_at
                OR NEW.issuance_outcome_unknown_at IS DISTINCT FROM OLD.issuance_outcome_unknown_at
                OR NEW.known_signature_at IS DISTINCT FROM OLD.known_signature_at
                OR NEW.issued_attempt_id IS DISTINCT FROM OLD.issued_attempt_id
                OR NEW.issued_signing_key_id IS DISTINCT FROM OLD.issued_signing_key_id
                OR NEW.issued_signature_hash IS DISTINCT FROM OLD.issued_signature_hash
                OR NEW.issued_signature IS DISTINCT FROM OLD.issued_signature
                OR NEW.issued_envelope IS DISTINCT FROM OLD.issued_envelope
                OR NEW.issuance_attempt_count IS DISTINCT FROM OLD.issuance_attempt_count
                OR NEW.issuance_unknown_outcome_count IS DISTINCT FROM OLD.issuance_unknown_outcome_count;
            IF NOT consequence_changed THEN RETURN NEW; END IF;
            IF OLD.issuance_state IN (
                'issued', 'issued_pre_xvii', 'issued_legacy', 'not_applicable'
            ) THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:terminal:%',
                    OLD.issuance_state USING ERRCODE = '42501';
            END IF;
            IF OLD.issuance_state = 'signing'
               AND NEW.issuance_state = 'signature_known' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = NEW.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND OR NEW.known_signature_at IS DISTINCT FROM attempt.signature_known_at THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:known_attempt'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signature_known'
                  AND NEW.issuance_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = OLD.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND
                   OR NEW.issued_attempt_id IS DISTINCT FROM attempt.id
                   OR NEW.issued_signing_key_id IS DISTINCT FROM attempt.signing_key_id
                   OR NEW.issued_signature_hash IS DISTINCT FROM attempt.signature_hash
                   OR NEW.issued_signature IS DISTINCT FROM attempt.signature
                   OR NEW.issued_envelope IS DISTINCT FROM attempt.signed_envelope THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:evidence_correspondence'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signing'
                  AND NEW.issuance_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'authorized'
                  AND NEW.issuance_state IN ('signing', 'failed')
                  OR OLD.issuance_state IN ('failed', 'signature_outcome_unknown')
                     AND NEW.issuance_state = 'signing' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_issuance_authority_violation:transition:%->%',
                    OLD.issuance_state, NEW.issuance_state USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_attempt_count < OLD.issuance_attempt_count
               OR NEW.issuance_unknown_outcome_count < OLD.issuance_unknown_outcome_count THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:lineage_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signing' AND OLD.issuance_state <> 'signing'
               AND NEW.issuance_attempt_count <> OLD.issuance_attempt_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:attempt_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signature_outcome_unknown'
               AND OLD.issuance_state <> 'signature_outcome_unknown'
               AND NEW.issuance_unknown_outcome_count <> OLD.issuance_unknown_outcome_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:unknown_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
    """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_access_log_issuance_authority_guard()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            table_owner text;
            consequence_changed boolean;
            attempt public.trust_issuance_attempts%ROWTYPE;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_access_log'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF (NEW.event_type = 'issuance' AND NEW.issuance_state <> 'authorized')
                   OR (NEW.event_type <> 'issuance'
                       AND NEW.issuance_state <> 'not_applicable') THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:insert_state:%',
                        NEW.issuance_state USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:tenant_rebind'
                    USING ERRCODE = '42501';
            END IF;
            consequence_changed :=
                NEW.issuance_state IS DISTINCT FROM OLD.issuance_state
                OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                OR NEW.issuance_attempted_at IS DISTINCT FROM OLD.issuance_attempted_at
                OR NEW.issuance_outcome_unknown_at IS DISTINCT FROM OLD.issuance_outcome_unknown_at
                OR NEW.known_signature_at IS DISTINCT FROM OLD.known_signature_at
                OR NEW.issued_attempt_id IS DISTINCT FROM OLD.issued_attempt_id
                OR NEW.issued_signing_key_id IS DISTINCT FROM OLD.issued_signing_key_id
                OR NEW.issued_signature_hash IS DISTINCT FROM OLD.issued_signature_hash
                OR NEW.issued_signature IS DISTINCT FROM OLD.issued_signature
                OR NEW.issued_envelope IS DISTINCT FROM OLD.issued_envelope
                OR NEW.issuance_attempt_count IS DISTINCT FROM OLD.issuance_attempt_count
                OR NEW.issuance_unknown_outcome_count IS DISTINCT FROM OLD.issuance_unknown_outcome_count;
            IF NOT consequence_changed THEN RETURN NEW; END IF;
            IF OLD.issuance_state IN (
                'issued', 'issued_pre_xvii', 'issued_legacy', 'not_applicable'
            ) THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:terminal:%',
                    OLD.issuance_state USING ERRCODE = '42501';
            END IF;
            IF OLD.issuance_state = 'signing'
               AND NEW.issuance_state = 'signature_known' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = NEW.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND OR NEW.known_signature_at IS DISTINCT FROM attempt.signature_known_at THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:known_attempt'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signature_known'
                  AND NEW.issuance_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                SELECT * INTO attempt FROM public.trust_issuance_attempts
                WHERE tenant_id = NEW.tenant_id AND audit_ref = NEW.audit_ref
                  AND id = OLD.issued_attempt_id
                  AND attempt_state = 'signature_known';
                IF NOT FOUND
                   OR NEW.issued_attempt_id IS DISTINCT FROM attempt.id
                   OR NEW.issued_signing_key_id IS DISTINCT FROM attempt.signing_key_id
                   OR NEW.issued_signature_hash IS DISTINCT FROM attempt.signature_hash
                   OR NEW.issued_signature IS DISTINCT FROM attempt.signature
                   OR NEW.issued_envelope IS DISTINCT FROM attempt.signed_envelope THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:evidence_correspondence'
                        USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'signing'
                  AND NEW.issuance_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.issuance_state = 'authorized'
                  AND NEW.issuance_state IN ('signing', 'failed')
                  OR OLD.issuance_state IN ('failed', 'signature_outcome_unknown')
                     AND NEW.issuance_state = 'signing' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_issuance_authority_violation:transition:%->%',
                    OLD.issuance_state, NEW.issuance_state USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_attempt_count < OLD.issuance_attempt_count
               OR NEW.issuance_unknown_outcome_count < OLD.issuance_unknown_outcome_count THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:lineage_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signing' AND OLD.issuance_state <> 'signing'
               AND NEW.issuance_attempt_count <> OLD.issuance_attempt_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:attempt_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signature_outcome_unknown'
               AND OLD.issuance_state <> 'signature_outcome_unknown'
               AND NEW.issuance_unknown_outcome_count <> OLD.issuance_unknown_outcome_count + 1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:unknown_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
    """
    )
