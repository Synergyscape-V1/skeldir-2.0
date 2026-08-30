"""B2.5-P13 C16: conserve issuance truth in both physical directions.

Revision ID: 202608301200
Revises: 202608291200

The predecessor state machine distinguished authorization from completion, but
it did not durably cross the irreversible private-key boundary before signing.
Consequently a real signature could exist while the row still said
``authorized``. This revision adds a write-ahead ``signing`` state, an explicit
``signature_outcome_unknown`` state, retained raw signature evidence for new
``issued`` rows, and truthful legacy handling.

No historical row is given evidence that the database did not observe:

* valid historical ``issued`` rows become immutable ``issued_legacy`` rows;
* incomplete or structurally invalid historical issuance rows become
  ``signature_outcome_unknown``;
* no signature bytes are fabricated during the backfill.
"""

from __future__ import annotations

from alembic import op


revision = "202608301200"
down_revision = "202608291200"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD COLUMN issuance_attempted_at timestamptz,
            ADD COLUMN issuance_outcome_unknown_at timestamptz,
            ADD COLUMN issued_signature bytea,
            ADD COLUMN issuance_attempt_count integer NOT NULL DEFAULT 0,
            ADD COLUMN issuance_unknown_outcome_count integer NOT NULL DEFAULT 0
        """
    )
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            DROP CONSTRAINT ck_trust_access_log_unissued_has_no_crypto,
            DROP CONSTRAINT ck_trust_access_log_issued_requires_crypto,
            DROP CONSTRAINT ck_trust_access_log_issuance_state_event,
            DROP CONSTRAINT ck_trust_access_log_issuance_state
        """
    )  # CI:DESTRUCTIVE_OK - replaced below by stricter C16 constraints.

    # FORCE RLS applies to the non-superuser table owner. Lift it only for the
    # deterministic backfill and restore it before any constraint is exposed.
    op.execute("ALTER TABLE public.trust_access_log NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE public.trust_access_log
        SET issuance_state = CASE
                WHEN event_type <> 'issuance' THEN 'not_applicable'
                WHEN issuance_state = 'issued'
                     AND issued_at IS NOT NULL
                     AND issued_signing_key_id IS NOT NULL
                     AND issued_signature_hash IS NOT NULL
                     AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                     AND envelope_hash IS NOT NULL
                    THEN 'issued_legacy'
                ELSE 'signature_outcome_unknown'
            END,
            issuance_attempted_at = CASE
                WHEN event_type = 'issuance'
                    THEN COALESCE(issued_at, updated_at, created_at)
                ELSE NULL
            END,
            issuance_outcome_unknown_at = CASE
                WHEN event_type = 'issuance' AND NOT (
                    issuance_state = 'issued'
                    AND issued_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND envelope_hash IS NOT NULL
                ) THEN now()
                ELSE NULL
            END,
            issued_at = CASE
                WHEN event_type = 'issuance'
                     AND issuance_state = 'issued'
                     AND issued_at IS NOT NULL
                     AND issued_signing_key_id IS NOT NULL
                     AND issued_signature_hash IS NOT NULL
                     AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                     AND envelope_hash IS NOT NULL
                    THEN issued_at
                ELSE NULL
            END,
            issued_signing_key_id = CASE
                WHEN event_type = 'issuance'
                     AND issuance_state = 'issued'
                     AND issued_at IS NOT NULL
                     AND issued_signing_key_id IS NOT NULL
                     AND issued_signature_hash IS NOT NULL
                     AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                     AND envelope_hash IS NOT NULL
                    THEN issued_signing_key_id
                ELSE NULL
            END,
            issued_signature_hash = CASE
                WHEN event_type = 'issuance'
                     AND issuance_state = 'issued'
                     AND issued_at IS NOT NULL
                     AND issued_signing_key_id IS NOT NULL
                     AND issued_signature_hash IS NOT NULL
                     AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                     AND envelope_hash IS NOT NULL
                    THEN issued_signature_hash
                ELSE NULL
            END,
            issued_signature = NULL,
            updated_at = now()
        """
    )
    op.execute("ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY")

    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state CHECK (
                issuance_state IN (
                    'authorized',
                    'signing',
                    'issued',
                    'issued_legacy',
                    'failed',
                    'signature_outcome_unknown',
                    'not_applicable'
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_issuance_state_event CHECK (
                (event_type = 'issuance' AND issuance_state <> 'not_applicable')
                OR (event_type <> 'issuance' AND issuance_state = 'not_applicable')
            ),
            ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (
                issuance_state <> 'issued'
                OR (
                    issued_at IS NOT NULL
                    AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NOT NULL
                    AND octet_length(issued_signature) = 64
                    AND envelope_hash IS NOT NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_legacy_issued_evidence CHECK (
                issuance_state <> 'issued_legacy'
                OR (
                    issued_at IS NOT NULL
                    AND issuance_attempted_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND issued_signature IS NULL
                    AND envelope_hash IS NOT NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto CHECK (
                issuance_state IN ('issued', 'issued_legacy')
                OR (
                    issued_at IS NULL
                    AND issued_signing_key_id IS NULL
                    AND issued_signature_hash IS NULL
                    AND issued_signature IS NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_attempt_state_shape CHECK (
                (
                    issuance_state IN (
                        'signing', 'issued', 'issued_legacy',
                        'signature_outcome_unknown'
                    )
                    AND issuance_attempted_at IS NOT NULL
                )
                OR (
                    issuance_state IN ('authorized', 'failed', 'not_applicable')
                    AND issuance_attempted_at IS NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_unknown_state_shape CHECK (
                (
                    issuance_state = 'signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NOT NULL
                )
                OR (
                    issuance_state <> 'signature_outcome_unknown'
                    AND issuance_outcome_unknown_at IS NULL
                )
            )
        """
    )

    # A CHECK constraint proves shape, never consequence.  Audit 58 Finding 2
    # and the Corrective XVI role x state matrix both require that ordinary
    # runtime authority cannot turn structural plausibility into authoritative
    # issuance history.  Shape alone cannot deliver that: any principal able to
    # write the row can also write 64 fabricated bytes.  The transition
    # authority is therefore narrowed to a dedicated least-privilege login
    # principal, `app_trust_issuer`, checked against `session_user` -- which,
    # unlike `current_user`, no SET ROLE can forge -- plus the schema owner,
    # which is migration authority and out of runtime scope by definition.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.trust_access_log_issuance_authority_guard()
        RETURNS trigger
        LANGUAGE plpgsql
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
                -- A row may only be born in a state that asserts no physical
                -- signing consequence whatsoever.
                IF NEW.event_type = 'issuance' THEN
                    IF NEW.issuance_state <> 'authorized' THEN
                        RAISE EXCEPTION
                            'trust_issuance_authority_violation:insert_state:%',
                            NEW.issuance_state USING ERRCODE = '42501';
                    END IF;
                ELSIF NEW.issuance_state <> 'not_applicable' THEN
                    RAISE EXCEPTION
                        'trust_issuance_authority_violation:insert_state:%',
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
                    RAISE EXCEPTION
                        'trust_issuance_authority_violation:insert_evidence'
                        USING ERRCODE = '42501';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:tenant_rebind'
                    USING ERRCODE = '42501';
            END IF;

            consequence_changed :=
                NEW.issuance_state IS DISTINCT FROM OLD.issuance_state
                OR NEW.issued_at IS DISTINCT FROM OLD.issued_at
                OR NEW.issuance_attempted_at
                    IS DISTINCT FROM OLD.issuance_attempted_at
                OR NEW.issuance_outcome_unknown_at
                    IS DISTINCT FROM OLD.issuance_outcome_unknown_at
                OR NEW.issued_signing_key_id
                    IS DISTINCT FROM OLD.issued_signing_key_id
                OR NEW.issued_signature_hash
                    IS DISTINCT FROM OLD.issued_signature_hash
                OR NEW.issued_signature IS DISTINCT FROM OLD.issued_signature
                OR NEW.issuance_attempt_count
                    IS DISTINCT FROM OLD.issuance_attempt_count
                OR NEW.issuance_unknown_outcome_count
                    IS DISTINCT FROM OLD.issuance_unknown_outcome_count;

            IF NOT consequence_changed THEN
                RETURN NEW;
            END IF;

            IF NOT has_authority THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:principal:%',
                    session_user USING ERRCODE = '42501';
            END IF;

            -- Physical history, once durably established, is immutable.  A
            -- later event may never deny or restate a signing consequence the
            -- database already witnessed.
            IF OLD.issuance_state IN (
                'issued', 'issued_legacy', 'not_applicable'
            ) THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:terminal:%',
                    OLD.issuance_state USING ERRCODE = '42501';
            END IF;

            IF NEW.issuance_state <> OLD.issuance_state THEN
                IF NOT (
                    (OLD.issuance_state = 'authorized'
                        AND NEW.issuance_state IN ('signing', 'failed'))
                    OR (OLD.issuance_state IN (
                            'failed', 'signature_outcome_unknown'
                        )
                        AND NEW.issuance_state = 'signing')
                    OR (OLD.issuance_state = 'signing'
                        AND NEW.issuance_state IN (
                            'issued', 'signature_outcome_unknown'
                        ))
                ) THEN
                    RAISE EXCEPTION
                        'trust_issuance_authority_violation:transition:%->%',
                        OLD.issuance_state, NEW.issuance_state
                        USING ERRCODE = '42501';
                END IF;
            END IF;

            -- Lineage is monotonic.  A retry may not erase the fact that an
            -- earlier signing consequence may physically have occurred.
            IF NEW.issuance_attempt_count < OLD.issuance_attempt_count
               OR NEW.issuance_unknown_outcome_count
                    < OLD.issuance_unknown_outcome_count THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:lineage_regression'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signing'
               AND OLD.issuance_state <> 'signing'
               AND NEW.issuance_attempt_count
                    <> OLD.issuance_attempt_count + 1 THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:attempt_not_counted'
                    USING ERRCODE = '42501';
            END IF;
            IF NEW.issuance_state = 'signature_outcome_unknown'
               AND OLD.issuance_state <> 'signature_outcome_unknown'
               AND NEW.issuance_unknown_outcome_count
                    <> OLD.issuance_unknown_outcome_count + 1 THEN
                RAISE EXCEPTION
                    'trust_issuance_authority_violation:unknown_not_counted'
                    USING ERRCODE = '42501';
            END IF;

            RETURN NEW;
        END;
        $BODY$;
        REVOKE ALL ON FUNCTION public.trust_access_log_issuance_authority_guard()
            FROM PUBLIC;
        CREATE TRIGGER trg_trust_access_log_issuance_authority_guard
            BEFORE INSERT OR UPDATE
            ON public.trust_access_log
            FOR EACH ROW
            EXECUTE FUNCTION public.trust_access_log_issuance_authority_guard()
        """
    )

    # Least privilege: the issuance principal may read and transition the audit
    # ledger and nothing else.  A leaked issuer DSN cannot read tenant business
    # data, and a leaked `app_user` DSN cannot write issuance consequence.
    op.execute(
        """
        DO $GRANTS$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_catalog.pg_roles
                WHERE rolname = 'app_trust_issuer'
            ) THEN
                EXECUTE 'GRANT USAGE ON SCHEMA public TO app_trust_issuer';
                EXECUTE 'GRANT SELECT, UPDATE ON public.trust_access_log '
                    || 'TO app_trust_issuer';
            END IF;
        END
        $GRANTS$;
        """
    )

    # H-XVI-05 survey found one additional unguarded nullable operand whose
    # NULL result could falsely satisfy an advertised diagnostic invariant.
    # Degrade any impossible historical claim before validating the correction.
    op.execute(
        """
        UPDATE public.bayesian_model_fits
        SET credible_interval_status = 'invalid',
            diagnostic_status = 'failed',
            diagnostic_failure_reason = 'invalid_diagnostic_summary',
            confidence_bucket = 'unavailable',
            confidence_bucket_reason = 'persisted_classification_invalid',
            confidence_policy_version = 'b24-p10-confidence-policy-v1',
            confidence_semantics_version = 'b24-p10-confidence-semantics-v1',
            confidence_classified_at = COALESCE(confidence_classified_at, now()),
            updated_at = now()
        WHERE credible_interval_status = 'available'
          AND divergence_count IS NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagnostics,
            ADD CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagnostics
            CHECK (
                credible_interval_status <> 'available'
                OR (
                    diagnostic_status = 'passed'
                    AND fallback_applied = false
                    AND r_hat_max IS NOT NULL AND r_hat_max <= 1.01
                    AND ess_min IS NOT NULL AND ess_min >= 400
                    AND divergence_count IS NOT NULL AND divergence_count = 0
                    AND hdi_lower IS NOT NULL AND hdi_upper IS NOT NULL
                    AND interval_element_count IS NOT NULL
                    AND interval_element_count > 0
                    AND diagnostic_policy_version IS NOT NULL
                    AND diagnostic_target_filter_version IS NOT NULL
                    AND interval_policy_version IS NOT NULL
                )
            )
        """
    )  # CI:DESTRUCTIVE_OK - replaced atomically by NULL-safe equivalent.

    # The same catalog-wide survey found that the available-confidence guard
    # relied on three-valued CHECK semantics for its nullable classification
    # and evidence operands.  In particular, a low/medium/high bucket with an
    # entirely absent evidence tuple could evaluate to NULL and be accepted.
    # Make both the intentionally-unclassified arm and every required operand
    # explicit.  NOT VALID preserves the predecessor's historical-validation
    # posture while enforcing the corrected predicate on all new writes.
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT ck_bayesian_model_fits_available_confidence_complete,
            ADD CONSTRAINT ck_bayesian_model_fits_available_confidence_complete
            CHECK (
                confidence_bucket IS NULL
                OR confidence_bucket NOT IN ('low', 'medium', 'high')
                OR (
                    status = 'succeeded'
                    AND data_completeness_status = 'complete'
                    AND fallback_applied = false
                    AND diagnostic_status = 'passed'
                    AND credible_interval_status = 'available'
                    AND artifact_ref IS NOT NULL
                    AND artifact_hash IS NOT NULL
                    AND confidence_evidence_snapshot_hash IS NOT NULL
                    AND confidence_evidence_snapshot_hash = source_snapshot_hash
                    AND confidence_deterministic_revenue_minor IS NOT NULL
                    AND confidence_deterministic_row_count IS NOT NULL
                    AND confidence_match_verdict_count IS NOT NULL
                    AND confidence_currency_count IS NOT NULL
                    AND confidence_currency_count <= 1
                    AND confidence_classified_at IS NOT NULL
                    AND confidence_classified_at >= source_read_completed_at
                    AND source_read_started_at IS NOT NULL
                    AND source_read_completed_at IS NOT NULL
                    AND source_read_completed_at >= source_read_started_at
                    AND confidence_bucket_reason IS NOT NULL
                    AND (
                        (confidence_bucket = 'high'
                         AND confidence_bucket_reason = 'narrow_interval')
                        OR (confidence_bucket = 'medium'
                            AND confidence_bucket_reason = 'moderate_interval')
                        OR (confidence_bucket = 'low'
                            AND confidence_bucket_reason = 'wide_interval')
                    )
                )
            ) NOT VALID
        """
    )  # CI:DESTRUCTIVE_OK - replaced atomically by NULL-safe equivalent.

    # These two constraints intentionally allow NULL. Spell that policy rather
    # than relying on CHECK's three-valued-logic acceptance rule.
    op.execute(
        """
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256,
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256
            CHECK (
                claim_capability_digest IS NULL
                OR claim_capability_digest ~ '^[a-f0-9]{64}$'
            );
        ALTER TABLE public.explanation_cache
            DROP CONSTRAINT explanation_cache_cache_hit_count_check,
            ADD CONSTRAINT explanation_cache_cache_hit_count_check
            CHECK (cache_hit_count IS NULL OR cache_hit_count >= 0)
        """
    )  # CI:DESTRUCTIVE_OK - replaced by semantically explicit equivalents.


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT ck_bayesian_model_fits_available_confidence_complete,
            ADD CONSTRAINT ck_bayesian_model_fits_available_confidence_complete
            CHECK (
                confidence_bucket NOT IN ('low', 'medium', 'high')
                OR (
                    status = 'succeeded'
                    AND data_completeness_status = 'complete'
                    AND fallback_applied = false
                    AND diagnostic_status = 'passed'
                    AND credible_interval_status = 'available'
                    AND artifact_ref IS NOT NULL
                    AND artifact_hash IS NOT NULL
                    AND confidence_evidence_snapshot_hash = source_snapshot_hash
                    AND confidence_deterministic_revenue_minor IS NOT NULL
                    AND confidence_deterministic_row_count IS NOT NULL
                    AND confidence_match_verdict_count IS NOT NULL
                    AND confidence_currency_count IS NOT NULL
                    AND confidence_currency_count <= 1
                    AND confidence_classified_at IS NOT NULL
                    AND confidence_classified_at >= source_read_completed_at
                    AND source_read_started_at IS NOT NULL
                    AND source_read_completed_at IS NOT NULL
                    AND source_read_completed_at >= source_read_started_at
                    AND (
                        (confidence_bucket = 'high'
                         AND confidence_bucket_reason = 'narrow_interval')
                        OR (confidence_bucket = 'medium'
                            AND confidence_bucket_reason = 'moderate_interval')
                        OR (confidence_bucket = 'low'
                            AND confidence_bucket_reason = 'wide_interval')
                    )
                )
            ) NOT VALID
        """
    )  # CI:DESTRUCTIVE_OK - downgrade restores the predecessor definition.
    op.execute(
        """
        ALTER TABLE public.explanation_cache
            DROP CONSTRAINT explanation_cache_cache_hit_count_check,
            ADD CONSTRAINT explanation_cache_cache_hit_count_check
            CHECK (cache_hit_count >= 0);
        ALTER TABLE public.b24_fit_dispatch_outbox
            DROP CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256,
            ADD CONSTRAINT ck_b24_fit_dispatch_outbox_claim_capability_digest_sha256
            CHECK (claim_capability_digest ~ '^[a-f0-9]{64}$')
        """
    )  # CI:DESTRUCTIVE_OK - downgrade restores the predecessor definitions.
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagnostics,
            ADD CONSTRAINT ck_bayesian_model_fits_available_interval_requires_passed_diagnostics
            CHECK (
                credible_interval_status <> 'available'
                OR (
                    diagnostic_status = 'passed'
                    AND fallback_applied = false
                    AND r_hat_max IS NOT NULL AND r_hat_max <= 1.01
                    AND ess_min IS NOT NULL AND ess_min >= 400
                    AND divergence_count = 0
                    AND hdi_lower IS NOT NULL AND hdi_upper IS NOT NULL
                    AND interval_element_count IS NOT NULL
                    AND interval_element_count > 0
                    AND diagnostic_policy_version IS NOT NULL
                    AND diagnostic_target_filter_version IS NOT NULL
                    AND interval_policy_version IS NOT NULL
                )
            )
        """
    )  # CI:DESTRUCTIVE_OK - downgrade restores the predecessor definition.
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_trust_access_log_issuance_authority_guard
            ON public.trust_access_log;
        DROP FUNCTION IF EXISTS
            public.trust_access_log_issuance_authority_guard()
        """
    )  # CI:DESTRUCTIVE_OK - downgrade rollback of C16 trigger/function.
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            DROP CONSTRAINT ck_trust_access_log_unknown_state_shape,
            DROP CONSTRAINT ck_trust_access_log_attempt_state_shape,
            DROP CONSTRAINT ck_trust_access_log_nonissued_has_no_crypto,
            DROP CONSTRAINT ck_trust_access_log_legacy_issued_evidence,
            DROP CONSTRAINT ck_trust_access_log_issued_requires_crypto,
            DROP CONSTRAINT ck_trust_access_log_issuance_state_event,
            DROP CONSTRAINT ck_trust_access_log_issuance_state
        """
    )  # CI:DESTRUCTIVE_OK - release C16 shapes before predecessor-state backfill.
    op.execute("ALTER TABLE public.trust_access_log NO FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        UPDATE public.trust_access_log
        SET issuance_state = CASE
                WHEN event_type <> 'issuance' THEN 'not_applicable'
                WHEN issuance_state = 'issued_legacy' THEN 'issued'
                WHEN issuance_state = 'issued' THEN 'issued'
                ELSE 'failed'
            END,
            issued_at = CASE
                WHEN issuance_state IN ('issued', 'issued_legacy') THEN issued_at
                ELSE NULL
            END,
            issued_signing_key_id = CASE
                WHEN issuance_state IN ('issued', 'issued_legacy')
                    THEN issued_signing_key_id
                ELSE NULL
            END,
            issued_signature_hash = CASE
                WHEN issuance_state IN ('issued', 'issued_legacy')
                    THEN issued_signature_hash
                ELSE NULL
            END,
            updated_at = now()
        """
    )
    op.execute("ALTER TABLE public.trust_access_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            DROP COLUMN issuance_unknown_outcome_count, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN issuance_attempt_count, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN issued_signature, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN issuance_outcome_unknown_at, -- # CI:DESTRUCTIVE_OK
            DROP COLUMN issuance_attempted_at -- # CI:DESTRUCTIVE_OK
        """
    )  # CI:DESTRUCTIVE_OK - downgrade rollback of C16 columns/constraints.
    op.execute(
        """
        ALTER TABLE public.trust_access_log
            ADD CONSTRAINT ck_trust_access_log_issuance_state CHECK (
                issuance_state IN ('authorized', 'issued', 'failed', 'not_applicable')
            ),
            ADD CONSTRAINT ck_trust_access_log_issuance_state_event CHECK (
                (event_type = 'issuance' AND issuance_state <> 'not_applicable')
                OR (event_type <> 'issuance' AND issuance_state = 'not_applicable')
            ),
            ADD CONSTRAINT ck_trust_access_log_issued_requires_crypto CHECK (
                issuance_state <> 'issued'
                OR (
                    issued_at IS NOT NULL
                    AND issued_signing_key_id IS NOT NULL
                    AND issued_signature_hash ~ '^sha256:[0-9a-f]{64}$'
                    AND envelope_hash IS NOT NULL
                )
            ),
            ADD CONSTRAINT ck_trust_access_log_unissued_has_no_crypto CHECK (
                issuance_state = 'issued'
                OR (
                    issued_at IS NULL
                    AND issued_signing_key_id IS NULL
                    AND issued_signature_hash IS NULL
                )
            )
        """
    )
