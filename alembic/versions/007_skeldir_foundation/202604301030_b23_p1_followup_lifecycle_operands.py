"""B2.3-P1 follow-up corrective closure for lifecycle authority and operand semantics.

Revision ID: 202604301030
Revises: 202604291200
Create Date: 2026-04-30 10:30:00
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "202604301030"
down_revision: Union[str, None] = "202604291200"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LIFECYCLE_JOB_NAME = "b23_p1_apply_lifecycle_daily"
_LIFECYCLE_SCHEDULE = "30 3 * * *"
_LIFECYCLE_FUNCTION = "fn_b23_p1_apply_lifecycle"


def _grant_execute_if_role_exists(role: str, function_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.{function_name}(integer) TO {role}';
            END IF;
        END
        $$;
        """
    )


def _revoke_execute_if_role_exists(role: str, function_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') THEN
                EXECUTE 'REVOKE EXECUTE ON FUNCTION public.{function_name}(integer) FROM {role}';
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS canonical_expected_gross_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS canonical_captured_gross_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS canonical_net_verified_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS discrepancy_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS discrepancy_ratio_bps integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ADD COLUMN IF NOT EXISTS discrepancy_band varchar(32)
        """
    )

    op.execute(
        """
        UPDATE public.b23_match_verdicts
        SET
            canonical_expected_gross_amount_minor = COALESCE(canonical_expected_gross_amount_minor, attributed_amount_minor),
            canonical_captured_gross_amount_minor = COALESCE(canonical_captured_gross_amount_minor, verified_amount_minor),
            canonical_net_verified_amount_minor = COALESCE(canonical_net_verified_amount_minor, verified_amount_minor)
        """
    )
    op.execute(
        """
        UPDATE public.b23_match_verdicts
        SET
            discrepancy_amount_minor = canonical_expected_gross_amount_minor - canonical_net_verified_amount_minor,
            discrepancy_ratio_bps = CASE
                WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                ELSE ((canonical_expected_gross_amount_minor - canonical_net_verified_amount_minor) * 10000)
                    / canonical_expected_gross_amount_minor
            END
        """
    )
    op.execute(
        """
        UPDATE public.b23_match_verdicts
        SET discrepancy_band = CASE
            WHEN abs(discrepancy_ratio_bps) = 0 THEN 'exact'
            WHEN abs(discrepancy_ratio_bps) <= 100 THEN 'within_tolerance'
            WHEN abs(discrepancy_ratio_bps) <= 500 THEN 'over_tolerance'
            ELSE 'severe_gap'
        END
        """
    )

    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN canonical_expected_gross_amount_minor SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN canonical_captured_gross_amount_minor SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN canonical_net_verified_amount_minor SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN discrepancy_amount_minor SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN discrepancy_ratio_bps SET NOT NULL
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_match_verdicts
            ALTER COLUMN discrepancy_band SET NOT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_expected_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_expected_amount_non_negative
                    CHECK (canonical_expected_gross_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_captured_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_captured_amount_non_negative
                    CHECK (canonical_captured_gross_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_net_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_net_amount_non_negative
                    CHECK (canonical_net_verified_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_discrepancy_band'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_band
                    CHECK (
                        discrepancy_band IN (
                            'exact',
                            'within_tolerance',
                            'over_tolerance',
                            'severe_gap'
                        )
                    );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_discrepancy_ratio_range'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_range
                    CHECK (discrepancy_ratio_bps BETWEEN -1000000 AND 1000000);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_discrepancy_amount_consistency'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_amount_consistency
                    CHECK (
                        discrepancy_amount_minor
                        = (canonical_expected_gross_amount_minor - canonical_net_verified_amount_minor)
                    );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_discrepancy_ratio_consistency'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_discrepancy_ratio_consistency
                    CHECK (
                        discrepancy_ratio_bps = CASE
                            WHEN canonical_expected_gross_amount_minor = 0 THEN 0
                            ELSE ((discrepancy_amount_minor * 10000) / canonical_expected_gross_amount_minor)
                        END
                    );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_expected_matches_legacy'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_expected_matches_legacy
                    CHECK (canonical_expected_gross_amount_minor = attributed_amount_minor);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_match_verdicts_captured_matches_legacy'
            ) THEN
                ALTER TABLE public.b23_match_verdicts
                    ADD CONSTRAINT ck_b23_match_verdicts_captured_matches_legacy
                    CHECK (canonical_captured_gross_amount_minor = verified_amount_minor);
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_match_verdicts_tenant_discrepancy_band
            ON public.b23_match_verdicts (tenant_id, discrepancy_band, last_transition_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_match_verdicts_tenant_discrepancy_ratio_bps
            ON public.b23_match_verdicts (tenant_id, discrepancy_ratio_bps, last_transition_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.canonical_expected_gross_amount_minor IS
            'Canonical attribution-side expected gross amount in integer minor units.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.canonical_captured_gross_amount_minor IS
            'Canonical B2.2-ingress verified captured gross amount in integer minor units.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.canonical_net_verified_amount_minor IS
            'Canonical verified net amount after adjustment events in integer minor units.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.discrepancy_amount_minor IS
            'Canonical discrepancy amount in minor units (expected gross minus net verified).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.discrepancy_ratio_bps IS
            'Canonical discrepancy ratio in basis points.'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_match_verdicts.discrepancy_band IS
            'Canonical discrepancy class for indexed operational filtering.'
        """
    )

    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS captured_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS refund_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS chargeback_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS reversal_amount_minor integer
        """
    )
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ADD COLUMN IF NOT EXISTS net_effect_sign smallint
        """
    )

    op.execute(
        """
        UPDATE public.b23_revenue_events
        SET
            captured_amount_minor = CASE WHEN event_type = 'payment_capture' THEN amount_minor ELSE NULL END,
            refund_amount_minor = CASE WHEN event_type IN ('partial_refund', 'full_refund') THEN amount_minor ELSE NULL END,
            chargeback_amount_minor = CASE WHEN event_type IN ('chargeback_opened', 'chargeback_won', 'chargeback_lost') THEN amount_minor ELSE NULL END,
            reversal_amount_minor = CASE WHEN event_type = 'reversal' THEN amount_minor ELSE NULL END,
            net_effect_sign = CASE
                WHEN event_type = 'payment_capture' THEN 1
                WHEN event_type IN ('partial_refund', 'full_refund') THEN -1
                WHEN event_type = 'chargeback_opened' THEN 0
                WHEN event_type = 'chargeback_lost' THEN -1
                WHEN event_type IN ('chargeback_won', 'reversal') THEN 1
                ELSE 0
            END
        """
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - replacing generic amount authority with event-specific operands
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS amount_minor"
    )  # CI:DESTRUCTIVE_OK - replacing generic amount authority with event-specific operands
    op.execute(
        """
        ALTER TABLE public.b23_revenue_events
            ALTER COLUMN net_effect_sign SET NOT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_captured_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_captured_amount_non_negative
                    CHECK (captured_amount_minor IS NULL OR captured_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_refund_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_refund_amount_non_negative
                    CHECK (refund_amount_minor IS NULL OR refund_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_chargeback_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_chargeback_amount_non_negative
                    CHECK (chargeback_amount_minor IS NULL OR chargeback_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_reversal_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_reversal_amount_non_negative
                    CHECK (reversal_amount_minor IS NULL OR reversal_amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_net_effect_sign'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_net_effect_sign
                    CHECK (net_effect_sign IN (-1, 0, 1));
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_net_effect_sign_by_event_type'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_net_effect_sign_by_event_type
                    CHECK (
                        (event_type = 'payment_capture' AND net_effect_sign = 1)
                        OR (event_type IN ('partial_refund', 'full_refund') AND net_effect_sign = -1)
                        OR (event_type = 'chargeback_opened' AND net_effect_sign = 0)
                        OR (event_type = 'chargeback_lost' AND net_effect_sign = -1)
                        OR (event_type IN ('chargeback_won', 'reversal') AND net_effect_sign = 1)
                    );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_split_operand_exactly_one_non_null'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_split_operand_exactly_one_non_null
                    CHECK (
                        (
                            CASE WHEN captured_amount_minor IS NULL THEN 0 ELSE 1 END
                            + CASE WHEN refund_amount_minor IS NULL THEN 0 ELSE 1 END
                            + CASE WHEN chargeback_amount_minor IS NULL THEN 0 ELSE 1 END
                            + CASE WHEN reversal_amount_minor IS NULL THEN 0 ELSE 1 END
                        ) = 1
                    );
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_operand_columns_by_event_type'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_operand_columns_by_event_type
                    CHECK (
                        (
                            event_type = 'payment_capture'
                            AND captured_amount_minor IS NOT NULL
                            AND refund_amount_minor IS NULL
                            AND chargeback_amount_minor IS NULL
                            AND reversal_amount_minor IS NULL
                        )
                        OR (
                            event_type IN ('partial_refund', 'full_refund')
                            AND captured_amount_minor IS NULL
                            AND refund_amount_minor IS NOT NULL
                            AND chargeback_amount_minor IS NULL
                            AND reversal_amount_minor IS NULL
                        )
                        OR (
                            event_type IN ('chargeback_opened', 'chargeback_won', 'chargeback_lost')
                            AND captured_amount_minor IS NULL
                            AND refund_amount_minor IS NULL
                            AND chargeback_amount_minor IS NOT NULL
                            AND reversal_amount_minor IS NULL
                        )
                        OR (
                            event_type = 'reversal'
                            AND captured_amount_minor IS NULL
                            AND refund_amount_minor IS NULL
                            AND chargeback_amount_minor IS NULL
                            AND reversal_amount_minor IS NOT NULL
                        )
                    );
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b23_revenue_events_tenant_event_effect_sign
            ON public.b23_revenue_events (tenant_id, event_type, net_effect_sign, event_occurred_at DESC)
        """
    )

    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.captured_amount_minor IS
            'Absolute captured amount operand for payment_capture events (minor units).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.refund_amount_minor IS
            'Absolute refund amount operand for partial_refund/full_refund events (minor units).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.chargeback_amount_minor IS
            'Absolute chargeback amount operand for chargeback_* events (minor units).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.reversal_amount_minor IS
            'Absolute reversal/restoration amount operand for reversal events (minor units).'
        """
    )
    op.execute(
        """
        COMMENT ON COLUMN public.b23_revenue_events.net_effect_sign IS
            'Deterministic net effect sign on verified net revenue: +1 credit, -1 debit, 0 pending/no net effect.'
        """
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.{_LIFECYCLE_FUNCTION}(max_delete integer DEFAULT 5000)
        RETURNS TABLE(table_name text, deleted_rows integer)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public
        AS $$
        DECLARE
            effective_limit integer := GREATEST(1, COALESCE(max_delete, 5000));
            removed integer := 0;
        BEGIN
            WITH doomed AS (
                SELECT id
                FROM public.b23_webhook_ingestion_logs
                WHERE received_at < (now() - interval '365 days')
                ORDER BY received_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_webhook_ingestion_logs target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_webhook_ingestion_logs';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_exception_records
                WHERE raised_at < (now() - interval '1825 days')
                ORDER BY raised_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_exception_records target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_exception_records';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_match_verdicts
                WHERE created_at < (now() - interval '1825 days')
                ORDER BY created_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_match_verdicts target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_match_verdicts';
            deleted_rows := removed;
            RETURN NEXT;

            WITH doomed AS (
                SELECT id
                FROM public.b23_revenue_events
                WHERE event_occurred_at < (now() - interval '2555 days')
                ORDER BY event_occurred_at
                LIMIT effective_limit
            )
            DELETE FROM public.b23_revenue_events target
            USING doomed
            WHERE target.id = doomed.id;
            GET DIAGNOSTICS removed = ROW_COUNT;
            table_name := 'b23_revenue_events';
            deleted_rows := removed;
            RETURN NEXT;

            RETURN;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        COMMENT ON FUNCTION public.{_LIFECYCLE_FUNCTION}(integer) IS
            'B2.3-P1 database-native lifecycle retention enforcement for verdicts, exceptions, revenue events, and ingestion logs.'
        """
    )

    op.execute(
        """
        DO $$
        DECLARE
            enforce_pg_cron boolean := lower(coalesce(current_setting('skeldir.require_pg_cron', true), 'off'))
                IN ('1', 'true', 'on', 'yes');
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_available_extensions
                WHERE name = 'pg_cron'
            ) THEN
                BEGIN
                    EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_cron';
                EXCEPTION
                    WHEN raise_exception THEN
                        IF POSITION('can only create extension in database postgres' IN SQLERRM) > 0 THEN
                            IF enforce_pg_cron THEN
                                RAISE EXCEPTION 'missing_extension:pg_cron';
                            ELSE
                                RAISE NOTICE 'pg_cron control database differs from current database; deferring lifecycle job registration to governed deploy workflow';
                            END IF;
                        ELSE
                            RAISE;
                        END IF;
                END;
            ELSE
                IF enforce_pg_cron THEN
                    RAISE EXCEPTION 'missing_extension:pg_cron';
                ELSE
                    RAISE NOTICE 'pg_cron unavailable in this environment; skipping scheduled lifecycle registration';
                END IF;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        f"""
        DO $$
        DECLARE
            existing_job_id bigint;
            scheduled_job_id bigint;
            enforce_pg_cron boolean := lower(coalesce(current_setting('skeldir.require_pg_cron', true), 'off'))
                IN ('1', 'true', 'on', 'yes');
        BEGIN
            IF to_regnamespace('cron') IS NULL THEN
                IF enforce_pg_cron THEN
                    RAISE EXCEPTION 'missing_schema:cron';
                ELSE
                    RAISE NOTICE 'cron schema unavailable; skipping scheduled lifecycle registration';
                    RETURN;
                END IF;
            END IF;

            SELECT jobid
            INTO existing_job_id
            FROM cron.job
            WHERE jobname = '{_LIFECYCLE_JOB_NAME}'
            LIMIT 1;

            IF existing_job_id IS NOT NULL THEN
                PERFORM cron.unschedule(existing_job_id);
            END IF;

            SELECT cron.schedule(
                '{_LIFECYCLE_JOB_NAME}',
                '{_LIFECYCLE_SCHEDULE}',
                $cron$SELECT public.{_LIFECYCLE_FUNCTION}(5000);$cron$
            ) INTO scheduled_job_id;

            IF scheduled_job_id IS NULL THEN
                RAISE EXCEPTION 'failed_to_schedule_job:{_LIFECYCLE_JOB_NAME}';
            END IF;
        END
        $$;
        """
    )

    _grant_execute_if_role_exists("app_user", _LIFECYCLE_FUNCTION)
    _grant_execute_if_role_exists("app_rw", _LIFECYCLE_FUNCTION)
    _grant_execute_if_role_exists("app_ro", _LIFECYCLE_FUNCTION)


def downgrade() -> None:
    _revoke_execute_if_role_exists("app_ro", _LIFECYCLE_FUNCTION)
    _revoke_execute_if_role_exists("app_rw", _LIFECYCLE_FUNCTION)
    _revoke_execute_if_role_exists("app_user", _LIFECYCLE_FUNCTION)

    op.execute(
        f"""
        DO $$
        DECLARE
            existing_job_id bigint;
        BEGIN
            IF to_regnamespace('cron') IS NULL THEN
                RETURN;
            END IF;

            SELECT jobid
            INTO existing_job_id
            FROM cron.job
            WHERE jobname = '{_LIFECYCLE_JOB_NAME}'
            LIMIT 1;

            IF existing_job_id IS NOT NULL THEN
                PERFORM cron.unschedule(existing_job_id);
            END IF;
        END
        $$;
        """
    )

    op.execute(f"DROP FUNCTION IF EXISTS public.{_LIFECYCLE_FUNCTION}(integer)")

    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_revenue_events_tenant_event_effect_sign"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_operand_columns_by_event_type"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_split_operand_exactly_one_non_null"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_net_effect_sign_by_event_type"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_net_effect_sign"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_reversal_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_chargeback_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_refund_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP CONSTRAINT IF EXISTS ck_b23_revenue_events_captured_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events ADD COLUMN IF NOT EXISTS amount_minor integer"
    )
    op.execute(
        """
        UPDATE public.b23_revenue_events
        SET amount_minor = COALESCE(
            captured_amount_minor,
            refund_amount_minor,
            chargeback_amount_minor,
            reversal_amount_minor
        )
        """
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events ALTER COLUMN amount_minor SET NOT NULL"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_b23_revenue_events_amount_non_negative'
            ) THEN
                ALTER TABLE public.b23_revenue_events
                    ADD CONSTRAINT ck_b23_revenue_events_amount_non_negative
                    CHECK (amount_minor >= 0);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS net_effect_sign"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS reversal_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS chargeback_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS refund_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_revenue_events DROP COLUMN IF EXISTS captured_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup

    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_discrepancy_ratio_bps"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "DROP INDEX IF EXISTS public.idx_b23_match_verdicts_tenant_discrepancy_band"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_captured_matches_legacy"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_expected_matches_legacy"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_ratio_consistency"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_amount_consistency"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_ratio_range"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_discrepancy_band"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_net_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_captured_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP CONSTRAINT IF EXISTS ck_b23_match_verdicts_expected_amount_non_negative"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS discrepancy_band"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS discrepancy_ratio_bps"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS discrepancy_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS canonical_net_verified_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS canonical_captured_gross_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
    op.execute(
        "ALTER TABLE public.b23_match_verdicts DROP COLUMN IF EXISTS canonical_expected_gross_amount_minor"
    )  # CI:DESTRUCTIVE_OK - reversible corrective P1 follow-up cleanup
