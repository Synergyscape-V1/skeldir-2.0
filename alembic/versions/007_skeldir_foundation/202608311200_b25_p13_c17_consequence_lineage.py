"""B2.5-P13 C17: consequence-coupled, reconstructable issuance lineage.

Revision ID: 202608311200
Revises: 202608301200

New authoritative completion is a projection of an exact signer-custodied
attempt artifact.  The issuer principal can begin/reconcile/finalize attempts,
but cannot create the ``signature_known`` fact that makes completion legal.
Pre-C17 ``issued`` assertions are retained without elevation as
``issued_pre_xvii`` because their cryptographic correspondence was not
consequence-coupled.
"""

from __future__ import annotations

from alembic import op


revision = "202608311200"
down_revision = "202608301200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            DROP CONSTRAINT ck_trust_access_log_unknown_state_shape,
            DROP CONSTRAINT ck_trust_access_log_attempt_state_shape,
            DROP CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto,
            DROP CONSTRAINT ck_trust_access_log_legacy_issued_evidence,
            DROP CONSTRAINT ck_trust_access_log_issued_requires_crypto,
            DROP CONSTRAINT ck_trust_access_log_issuance_state_event,
            DROP CONSTRAINT ck_trust_access_log_issuance_state;

        ALTER TABLE public.trust_access_log
            ADD COLUMN known_signature_at timestamptz,
            ADD COLUMN issued_attempt_id uuid,
            ADD COLUMN issued_envelope jsonb;

        DROP TRIGGER trg_trust_access_log_issuance_authority_guard
            ON public.trust_access_log;
        ALTER TABLE public.trust_access_log NO FORCE ROW LEVEL SECURITY;
        UPDATE public.trust_access_log
        SET issuance_state = 'issued_pre_xvii', updated_at = now()
        WHERE issuance_state = 'issued';
        ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY;

        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state CHECK (
                issuance_state IN (
                    'authorized', 'signing', 'signature_known', 'issued',
                    'issued_pre_xvii', 'issued_legacy', 'failed',
                    'signature_outcome_unknown', 'not_applicable'
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_issuance_state_event CHECK (
                (event_type = 'issuance' AND issuance_state <> 'not_applicable')
                OR (event_type <> 'issuance' AND issuance_state = 'not_applicable')
            ),
            ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (
                issuance_state <> 'issued' OR (
                    issued_at IS NOT NULL
                    AND issuance_attempted_at IS NOT NULL
                    AND known_signature_at IS NOT NULL
                    AND issued_attempt_id IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NOT NULL
                    AND octet_length(issued_signature) = 64
                    AND envelope_hash IS NOT NULL
                    AND issued_envelope IS NOT NULL
                    AND jsonb_typeof(issued_envelope) = 'object'
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_pre_xvii_evidence CHECK (
                issuance_state <> 'issued_pre_xvii' OR (
                    issued_at IS NOT NULL
                    AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NOT NULL
                    AND octet_length(issued_signature) = 64
                    AND envelope_hash IS NOT NULL
                    AND known_signature_at IS NULL
                    AND issued_attempt_id IS NULL
                    AND issued_envelope IS NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_legacy_issued_evidence CHECK (
                issuance_state <> 'issued_legacy' OR (
                    issued_at IS NOT NULL
                    AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NULL
                    AND envelope_hash IS NOT NULL
                    AND known_signature_at IS NULL
                    AND issued_attempt_id IS NULL
                    AND issued_envelope IS NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto CHECK (
                issuance_state IN ('issued', 'issued_pre_xvii', 'issued_legacy')
                OR (
                    issued_at IS NULL AND issued_signing_key_id IS NULL
                    AND issued_signature_hash IS NULL AND issued_signature IS NULL
                    AND issued_envelope IS NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_attempt_state_shape CHECK (
                (issuance_state IN (
                    'signing', 'signature_known', 'issued', 'issued_pre_xvii',
                    'issued_legacy', 'signature_outcome_unknown'
                ) AND issuance_attempted_at IS NOT NULL)
                OR (issuance_state IN ('authorized', 'failed', 'not_applicable')
                    AND issuance_attempted_at IS NULL)
            ),
            ADD CONSTRAINT ck_trust_access_log_unknown_state_shape CHECK (
                (issuance_state = 'signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NOT NULL)
                OR (issuance_state <> 'signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NULL)
            ),
            ADD CONSTRAINT ck_trust_access_log_known_state_shape CHECK (
                (issuance_state IN ('signature_known', 'issued')
                    AND known_signature_at IS NOT NULL
                    AND issued_attempt_id IS NOT NULL)
                OR (issuance_state NOT IN ('signature_known', 'issued')
                    AND known_signature_at IS NULL
                    AND issued_attempt_id IS NULL)
            )
        """
    )

    op.execute(
        """
        CREATE TABLE public.trust_issuance_attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            audit_ref text NOT NULL,
            attempt_number integer NOT NULL CHECK (attempt_number > 0),
            attempt_state text NOT NULL CHECK (
                attempt_state IN (
                    'signing', 'signature_outcome_unknown',
                    'signature_known', 'issued'
                )
            ),
            started_at timestamptz NOT NULL DEFAULT now(),
            outcome_unknown_at timestamptz,
            signature_known_at timestamptz,
            issued_at timestamptz,
            signing_key_id text,
            signature_hash text,
            signature bytea,
            signed_envelope_hash text,
            signed_envelope jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT fk_trust_issuance_attempt_audit
                FOREIGN KEY (tenant_id, audit_ref)
                REFERENCES public.trust_access_log(tenant_id, audit_ref)
                ON DELETE RESTRICT,
            CONSTRAINT uq_trust_issuance_attempt_number
                UNIQUE (tenant_id, audit_ref, attempt_number),
            CONSTRAINT uq_trust_issuance_attempt_identity
                UNIQUE (tenant_id, audit_ref, id),
            CONSTRAINT ck_trust_issuance_attempt_evidence CHECK (
                (attempt_state IN ('signature_known', 'issued')
                    AND signature_known_at IS NOT NULL
                    AND signing_key_id IS NOT NULL
                    AND signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND octet_length(signature) = 64
                    AND signed_envelope_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND jsonb_typeof(signed_envelope) = 'object')
                OR (attempt_state IN ('signing', 'signature_outcome_unknown')
                    AND signature_known_at IS NULL
                    AND signing_key_id IS NULL AND signature_hash IS NULL
                    AND signature IS NULL AND signed_envelope_hash IS NULL
                    AND signed_envelope IS NULL)
            ),
            CONSTRAINT ck_trust_issuance_attempt_unknown CHECK (
                (attempt_state = 'signature_outcome_unknown'
                    AND outcome_unknown_at IS NOT NULL)
                OR (attempt_state <> 'signature_outcome_unknown'
                    AND outcome_unknown_at IS NULL)
            ),
            CONSTRAINT ck_trust_issuance_attempt_issued CHECK (
                (attempt_state = 'issued' AND issued_at IS NOT NULL)
                OR (attempt_state <> 'issued' AND issued_at IS NULL)
            )
        );
        CREATE INDEX ix_trust_issuance_attempts_tenant_audit
            ON public.trust_issuance_attempts
            (tenant_id, audit_ref, attempt_number DESC);
        CREATE INDEX ix_trust_issuance_attempts_recovery
            ON public.trust_issuance_attempts
            (tenant_id, attempt_state, updated_at, id);
        ALTER TABLE public.trust_issuance_attempts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.trust_issuance_attempts FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_policy_trust_issuance_attempts
            ON public.trust_issuance_attempts
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid)
        """
    )

    op.execute(
        """
        CREATE TABLE public.trust_export_artifact_attempts (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
            request_binding_hash text NOT NULL
                CHECK (request_binding_hash ~ '^sha256:[0-9a-f]{64}$'),
            page_start integer NOT NULL CHECK (page_start >= 0),
            attempt_number integer NOT NULL CHECK (attempt_number > 0),
            attempt_state text NOT NULL CHECK (
                attempt_state IN ('signing','signature_outcome_unknown','issued')
            ),
            started_at timestamptz NOT NULL DEFAULT now(),
            outcome_unknown_at timestamptz,
            issued_at timestamptz,
            artifact_hash text,
            signing_key_id text,
            signature_hash text,
            signature bytea,
            signed_artifact jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_trust_export_artifact_attempt
                UNIQUE (tenant_id, request_binding_hash, page_start, attempt_number),
            CONSTRAINT ck_trust_export_artifact_attempt_evidence CHECK (
                (attempt_state = 'issued'
                    AND issued_at IS NOT NULL
                    AND artifact_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND signing_key_id IS NOT NULL
                    AND signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND octet_length(signature) = 64
                    AND jsonb_typeof(signed_artifact) = 'object')
                OR (attempt_state IN ('signing','signature_outcome_unknown')
                    AND issued_at IS NULL AND artifact_hash IS NULL
                    AND signing_key_id IS NULL AND signature_hash IS NULL
                    AND signature IS NULL AND signed_artifact IS NULL)
            ),
            CONSTRAINT ck_trust_export_artifact_attempt_unknown CHECK (
                (attempt_state = 'signature_outcome_unknown'
                    AND outcome_unknown_at IS NOT NULL)
                OR (attempt_state <> 'signature_outcome_unknown'
                    AND outcome_unknown_at IS NULL)
            )
        );
        CREATE INDEX ix_trust_export_artifact_attempts_lookup
            ON public.trust_export_artifact_attempts
            (tenant_id, request_binding_hash, page_start, attempt_number DESC);
        ALTER TABLE public.trust_export_artifact_attempts ENABLE ROW LEVEL SECURITY;
        ALTER TABLE public.trust_export_artifact_attempts FORCE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation_policy_trust_export_artifact_attempts
            ON public.trust_export_artifact_attempts
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);

        CREATE OR REPLACE FUNCTION public.trust_export_artifact_attempt_guard()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE table_owner text;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_export_artifact_attempts'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner)
                   OR NEW.attempt_state <> 'signing' THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:insert:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.request_binding_hash IS DISTINCT FROM OLD.request_binding_hash
               OR NEW.page_start IS DISTINCT FROM OLD.page_start
               OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number THEN
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:identity'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state <> 'signing' THEN
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:terminal:%',
                    OLD.attempt_state USING ERRCODE = '42501';
            END IF;
            IF NEW.attempt_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF NEW.attempt_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_export_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_export_attempt_authority_violation:transition:%->%',
                    OLD.attempt_state, NEW.attempt_state USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        REVOKE ALL ON FUNCTION public.trust_export_artifact_attempt_guard()
            FROM PUBLIC;
        CREATE TRIGGER trg_trust_export_artifact_attempt_guard
            BEFORE INSERT OR UPDATE ON public.trust_export_artifact_attempts
            FOR EACH ROW EXECUTE FUNCTION public.trust_export_artifact_attempt_guard()
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_issuance_attempt_guard()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE table_owner text;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_issuance_attempts'::regclass;
            IF TG_OP = 'INSERT' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner)
                   OR NEW.attempt_state <> 'signing' THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:insert:%',
                        session_user USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;
            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
               OR NEW.audit_ref IS DISTINCT FROM OLD.audit_ref
               OR NEW.id IS DISTINCT FROM OLD.id
               OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
               OR NEW.started_at IS DISTINCT FROM OLD.started_at THEN
                RAISE EXCEPTION 'trust_attempt_authority_violation:identity'
                    USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state IN ('signature_outcome_unknown', 'issued') THEN
                RAISE EXCEPTION 'trust_attempt_authority_violation:terminal:%',
                    OLD.attempt_state USING ERRCODE = '42501';
            END IF;
            IF OLD.attempt_state = 'signing'
               AND NEW.attempt_state = 'signature_known' THEN
                IF session_user NOT IN ('app_trust_signer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:signer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.attempt_state = 'signing'
                  AND NEW.attempt_state = 'signature_outcome_unknown' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSIF OLD.attempt_state = 'signature_known'
                  AND NEW.attempt_state = 'issued' THEN
                IF session_user NOT IN ('app_trust_issuer', table_owner) THEN
                    RAISE EXCEPTION 'trust_attempt_authority_violation:issuer:%',
                        session_user USING ERRCODE = '42501';
                END IF;
            ELSE
                RAISE EXCEPTION 'trust_attempt_authority_violation:transition:%->%',
                    OLD.attempt_state, NEW.attempt_state USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        REVOKE ALL ON FUNCTION public.trust_issuance_attempt_guard() FROM PUBLIC;
        CREATE TRIGGER trg_trust_issuance_attempt_guard
            BEFORE INSERT OR UPDATE ON public.trust_issuance_attempts
            FOR EACH ROW EXECUTE FUNCTION public.trust_issuance_attempt_guard()
        """
    )

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
        CREATE TRIGGER trg_trust_access_log_issuance_authority_guard
            BEFORE INSERT OR UPDATE ON public.trust_access_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_access_log_issuance_authority_guard();
        """
    )

    op.execute(
        """
        DO $GRANTS$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_trust_issuer') THEN
                GRANT SELECT, INSERT, UPDATE ON public.trust_issuance_attempts
                    TO app_trust_issuer;
                GRANT SELECT, INSERT, UPDATE
                    ON public.trust_export_artifact_attempts TO app_trust_issuer;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_trust_signer') THEN
                GRANT USAGE ON SCHEMA public TO app_trust_signer;
                GRANT SELECT, UPDATE ON public.trust_access_log TO app_trust_signer;
                GRANT SELECT, UPDATE ON public.trust_issuance_attempts
                    TO app_trust_signer;
                GRANT SELECT, UPDATE ON public.trust_export_artifact_attempts
                    TO app_trust_signer;
            END IF;
        END
        $GRANTS$
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $DROP_EXPORT_TRIGGER$
        BEGIN
            IF to_regclass('public.trust_export_artifact_attempts') IS NOT NULL THEN
                DROP TRIGGER IF EXISTS trg_trust_export_artifact_attempt_guard
                    ON public.trust_export_artifact_attempts;
            END IF;
        END
        $DROP_EXPORT_TRIGGER$;
        DROP FUNCTION IF EXISTS public.trust_export_artifact_attempt_guard();
        DROP TABLE IF EXISTS public.trust_export_artifact_attempts; -- # CI:DESTRUCTIVE_OK
        DROP TRIGGER IF EXISTS trg_trust_issuance_attempt_guard
            ON public.trust_issuance_attempts;
        DROP FUNCTION IF EXISTS public.trust_issuance_attempt_guard();
        DROP TRIGGER IF EXISTS trg_trust_access_log_issuance_authority_guard
            ON public.trust_access_log;
        DROP FUNCTION IF EXISTS public.trust_access_log_issuance_authority_guard();

        ALTER TABLE public.trust_access_log
            DROP CONSTRAINT ck_trust_access_log_known_state_shape,
            DROP CONSTRAINT ck_trust_access_log_unknown_state_shape,
            DROP CONSTRAINT ck_trust_access_log_attempt_state_shape,
            DROP CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto,
            DROP CONSTRAINT ck_trust_access_log_legacy_issued_evidence,
            DROP CONSTRAINT ck_trust_access_log_pre_xvii_evidence,
            DROP CONSTRAINT ck_trust_access_log_issued_requires_crypto,
            DROP CONSTRAINT ck_trust_access_log_issuance_state_event,
            DROP CONSTRAINT ck_trust_access_log_issuance_state;
        """
    )
    op.execute(
        """

        ALTER TABLE public.trust_access_log NO FORCE ROW LEVEL SECURITY;
        UPDATE public.trust_access_log SET
            issuance_state = CASE
                WHEN issuance_state IN ('issued', 'issued_pre_xvii') THEN 'issued'
                WHEN issuance_state = 'signature_known' THEN 'signature_outcome_unknown'
                ELSE issuance_state END,
            issuance_outcome_unknown_at = CASE
                WHEN issuance_state = 'signature_known' THEN now()
                ELSE issuance_outcome_unknown_at END,
            known_signature_at = NULL,
            issued_attempt_id = NULL,
            issued_envelope = NULL;
        ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY;
        """
    )
    op.execute(
        """

        DROP TABLE public.trust_issuance_attempts; -- # CI:DESTRUCTIVE_OK

        ALTER TABLE public.trust_access_log
            DROP COLUMN issued_envelope, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN issued_attempt_id, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN known_signature_at; -- # CI:DESTRUCTIVE_OK
        """
    )
    op.execute(
        """

        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state CHECK (
                issuance_state IN ('authorized','signing','issued','issued_legacy',
                    'failed','signature_outcome_unknown','not_applicable')),
            ADD CONSTRAINT ck_trust_access_log_issuance_state_event CHECK (
                (event_type='issuance' AND issuance_state<>'not_applicable')
                OR (event_type<>'issuance' AND issuance_state='not_applicable')),
            ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (
                issuance_state<>'issued' OR (
                    issued_at IS NOT NULL AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NOT NULL
                    AND octet_length(issued_signature)=64
                    AND envelope_hash IS NOT NULL)),
            ADD CONSTRAINT ck_trust_access_log_legacy_issued_evidence CHECK (
                issuance_state<>'issued_legacy' OR (
                    issued_at IS NOT NULL AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NULL AND envelope_hash IS NOT NULL)),
            ADD CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto CHECK (
                issuance_state IN ('issued','issued_legacy') OR (
                    issued_at IS NULL AND issued_signing_key_id IS NULL
                    AND issued_signature_hash IS NULL AND issued_signature IS NULL)),
            ADD CONSTRAINT ck_trust_access_log_attempt_state_shape CHECK (
                (issuance_state IN ('signing','issued','issued_legacy',
                    'signature_outcome_unknown') AND issuance_attempted_at IS NOT NULL)
                OR (issuance_state IN ('authorized','failed','not_applicable')
                    AND issuance_attempted_at IS NULL)),
            ADD CONSTRAINT ck_trust_access_log_unknown_state_shape CHECK (
                (issuance_state='signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NOT NULL)
                OR (issuance_state<>'signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NULL))
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_access_log_issuance_authority_guard()
        RETURNS trigger LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            table_owner text;
            has_authority boolean;
            consequence_changed boolean;
        BEGIN
            SELECT r.rolname INTO table_owner
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_roles r ON r.oid = c.relowner
            WHERE c.oid = 'public.trust_access_log'::regclass;
            has_authority := session_user IN ('app_trust_issuer', table_owner);
            IF TG_OP = 'INSERT' THEN
                IF (NEW.event_type = 'issuance' AND NEW.issuance_state <> 'authorized')
                   OR (NEW.event_type <> 'issuance'
                       AND NEW.issuance_state <> 'not_applicable') THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:insert_state:%',
                        NEW.issuance_state USING ERRCODE = '42501';
                END IF;
                IF NEW.issued_at IS NOT NULL
                   OR NEW.issuance_attempted_at IS NOT NULL
                   OR NEW.issuance_outcome_unknown_at IS NOT NULL
                   OR NEW.issued_signing_key_id IS NOT NULL
                   OR NEW.issued_signature_hash IS NOT NULL
                   OR NEW.issued_signature IS NOT NULL
                   OR COALESCE(NEW.issuance_attempt_count, 0) <> 0
                   OR COALESCE(NEW.issuance_unknown_outcome_count, 0) <> 0 THEN
                    RAISE EXCEPTION 'trust_issuance_authority_violation:insert_evidence'
                        USING ERRCODE = '42501';
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
                OR NEW.issued_signing_key_id IS DISTINCT FROM OLD.issued_signing_key_id
                OR NEW.issued_signature_hash IS DISTINCT FROM OLD.issued_signature_hash
                OR NEW.issued_signature IS DISTINCT FROM OLD.issued_signature
                OR NEW.issuance_attempt_count IS DISTINCT FROM OLD.issuance_attempt_count
                OR NEW.issuance_unknown_outcome_count IS DISTINCT FROM OLD.issuance_unknown_outcome_count;
            IF NOT consequence_changed THEN RETURN NEW; END IF;
            IF NOT has_authority THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:principal:%',
                    session_user USING ERRCODE = '42501';
            END IF;
            IF OLD.issuance_state IN ('issued','issued_legacy','not_applicable') THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:terminal:%',
                    OLD.issuance_state USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state <> OLD.issuance_state AND NOT (
                (OLD.issuance_state='authorized'
                    AND NEW.issuance_state IN ('signing','failed'))
                OR (OLD.issuance_state IN ('failed','signature_outcome_unknown')
                    AND NEW.issuance_state='signing')
                OR (OLD.issuance_state='signing'
                    AND NEW.issuance_state IN ('issued','signature_outcome_unknown'))
            ) THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:transition:%->%',
                    OLD.issuance_state, NEW.issuance_state USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_attempt_count < OLD.issuance_attempt_count
               OR NEW.issuance_unknown_outcome_count < OLD.issuance_unknown_outcome_count THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:lineage_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state='signing' AND OLD.issuance_state<>'signing'
               AND NEW.issuance_attempt_count<>OLD.issuance_attempt_count+1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:attempt_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state='signature_outcome_unknown'
               AND OLD.issuance_state<>'signature_outcome_unknown'
               AND NEW.issuance_unknown_outcome_count
                    <> OLD.issuance_unknown_outcome_count+1 THEN
                RAISE EXCEPTION 'trust_issuance_authority_violation:unknown_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            RETURN NEW;
        END;
        $BODY$;
        REVOKE ALL ON FUNCTION public.trust_access_log_issuance_authority_guard()
            FROM PUBLIC;
        CREATE TRIGGER trg_trust_access_log_issuance_authority_guard
            BEFORE INSERT OR UPDATE ON public.trust_access_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_access_log_issuance_authority_guard()
        """
    )
