"""B2.5-P13 C19: derive allocation verification from B2.3 verdict truth.

Revision ID: 202609011200
Revises: 202608312100

An attribution worker may compute allocation shape, but it cannot establish
revenue verification.  This migration makes ``attribution_allocations.verified``
a database-derived projection of the matching B2.3 verdict.  The projection and
the verdict transition commit atomically, so B2.4 cannot observe a verified
allocation without a confirmed/adjusted revenue authority row.
"""

from __future__ import annotations

from alembic import op


revision = "202609011200"
down_revision = "202608312100"
branch_labels = None
depends_on = None


# The financial-window invalidation surface is the rendered authority contract:
# source_invalidation_contract.render_source_invalidation_ddl must reproduce
# this literal byte-for-byte, and the C7 closure gate enforces it.
SOURCE_INVALIDATION_DDL = """
CREATE OR REPLACE FUNCTION public.b24_mark_allocation_financial_window_dirty()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $BODY$
DECLARE
    source_row public.attribution_allocations%ROWTYPE;
    financial_window_start timestamptz;
BEGIN
    source_row := CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    IF TG_OP = 'UPDATE' AND
       (NEW.event_id,
       NEW.tenant_id,
       NEW.channel_code,
       NEW.allocated_revenue_cents,
       NEW.allocation_ratio,
       NEW.model_type,
       NEW.model_version,
       NEW.verified,
       NEW.verification_source,
       NEW.verification_timestamp)
       IS NOT DISTINCT FROM
       (OLD.event_id,
       OLD.tenant_id,
       OLD.channel_code,
       OLD.allocated_revenue_cents,
       OLD.allocation_ratio,
       OLD.model_type,
       OLD.model_version,
       OLD.verified,
       OLD.verification_source,
       OLD.verification_timestamp) THEN
        RETURN NULL;
    END IF;
    IF NOT COALESCE(
            CASE WHEN TG_OP = 'DELETE' THEN OLD.verified
                 WHEN TG_OP = 'INSERT' THEN NEW.verified
                 ELSE OLD.verified OR NEW.verified END,
            false
        ) THEN
            RETURN NULL;
        END IF;

    SELECT date_trunc('day', event.occurred_at)
      INTO financial_window_start
      FROM public.attribution_events AS event
     WHERE event.tenant_id = source_row.tenant_id
       AND event.id = source_row.event_id
       AND event.processing_status IN ('pending', 'processed')
       AND event.event_type IN ('conversion', 'purchase');
    IF financial_window_start IS NULL THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    ) VALUES (
        source_row.tenant_id,
        'bayesian_attribution_confidence', 'b24-p6-real-fit-v1',
        financial_window_start, financial_window_start + interval '1 day',
        'attribution_allocations_financial_event_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'c19|attribution_allocations|' || source_row.tenant_id::text || '|'
            || source_row.id::text || '|' || TG_OP || '|'
            || transaction_timestamp()::text || '|' || txid_current()::text,
            'UTF8')), 'hex'),
        left('attribution_allocations:' || source_row.id::text, 128),
        transaction_timestamp(), 'pending',
        transaction_timestamp(), transaction_timestamp()
    );
    RETURN NULL;
END;
$BODY$;

DROP TRIGGER IF EXISTS trg_b24_mark_allocation_financial_window_dirty ON public.attribution_allocations;
CREATE TRIGGER trg_b24_mark_allocation_financial_window_dirty
AFTER INSERT OR UPDATE OR DELETE ON public.attribution_allocations
FOR EACH ROW
EXECUTE FUNCTION public.b24_mark_allocation_financial_window_dirty();

CREATE OR REPLACE FUNCTION public.b24_mark_verdict_financial_window_dirty()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $BODY$
DECLARE
    source_row public.b23_match_verdicts%ROWTYPE;
    financial_window_start timestamptz;
BEGIN
    source_row := CASE WHEN TG_OP = 'DELETE' THEN OLD ELSE NEW END;
    IF TG_OP = 'UPDATE' AND
       (NEW.attribution_event_id,
       NEW.tenant_id,
       NEW.status,
       NEW.canonical_net_verified_amount_minor,
       NEW.currency_code,
       NEW.last_transition_at)
       IS NOT DISTINCT FROM
       (OLD.attribution_event_id,
       OLD.tenant_id,
       OLD.status,
       OLD.canonical_net_verified_amount_minor,
       OLD.currency_code,
       OLD.last_transition_at) THEN
        RETURN NULL;
    END IF;
    IF NOT (
            (TG_OP <> 'INSERT' AND OLD.status IN ('matched_confirmed', 'adjusted'))
            OR
            (TG_OP <> 'DELETE' AND NEW.status IN ('matched_confirmed', 'adjusted'))
        ) THEN
            RETURN NULL;
        END IF;

    SELECT date_trunc('day', event.occurred_at)
      INTO financial_window_start
      FROM public.attribution_events AS event
     WHERE event.tenant_id = source_row.tenant_id
       AND event.id = source_row.attribution_event_id
       AND event.processing_status IN ('pending', 'processed')
       AND event.event_type IN ('conversion', 'purchase');
    IF financial_window_start IS NULL THEN
        RETURN NULL;
    END IF;

    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    ) VALUES (
        source_row.tenant_id,
        'bayesian_attribution_confidence', 'b24-p6-real-fit-v1',
        financial_window_start, financial_window_start + interval '1 day',
        'b23_match_verdicts_financial_event_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'c19|b23_match_verdicts|' || source_row.tenant_id::text || '|'
            || source_row.id::text || '|' || TG_OP || '|'
            || transaction_timestamp()::text || '|' || txid_current()::text,
            'UTF8')), 'hex'),
        left('b23_match_verdicts:' || source_row.id::text, 128),
        transaction_timestamp(), 'pending',
        transaction_timestamp(), transaction_timestamp()
    );
    RETURN NULL;
END;
$BODY$;

DROP TRIGGER IF EXISTS trg_b24_mark_verdict_financial_window_dirty ON public.b23_match_verdicts;
CREATE TRIGGER trg_b24_mark_verdict_financial_window_dirty
AFTER INSERT OR UPDATE OR DELETE ON public.b23_match_verdicts
FOR EACH ROW
EXECUTE FUNCTION public.b24_mark_verdict_financial_window_dirty();
"""


# The XIX lifecycle contract widened attribution-event membership to
# ('pending', 'processed') x ('conversion', 'purchase'), so the frozen C8
# write-clock functions no longer describe governed truth. This migration
# refreshes them to the same rendered authority; C8 remains history.
WRITE_CLOCK_INVALIDATION_DDL = """
CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_events_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.occurred_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.processing_status IN ('pending', 'processed') AND row_set.event_type IN ('conversion', 'purchase'), false) AND row_set.occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_events_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.occurred_at, new_row.event_timestamp, new_row.event_type, new_row.channel, new_row.campaign_id, new_row.revenue_cents, new_row.conversion_value_cents, new_row.currency, new_row.processing_status)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.occurred_at, old_row.event_timestamp, old_row.event_type, old_row.channel, old_row.campaign_id, old_row.revenue_cents, old_row.conversion_value_cents, old_row.currency, old_row.processing_status)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('pending', 'processed') AND new_row.event_type IN ('conversion', 'purchase'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('pending', 'processed') AND old_row.event_type IN ('conversion', 'purchase'), false) AND old_row.occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.occurred_at, new_row.event_timestamp, new_row.event_type, new_row.channel, new_row.campaign_id, new_row.revenue_cents, new_row.conversion_value_cents, new_row.currency, new_row.processing_status)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.occurred_at, old_row.event_timestamp, old_row.event_type, old_row.channel, old_row.campaign_id, old_row.revenue_cents, old_row.conversion_value_cents, old_row.currency, old_row.processing_status)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_events_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'attribution_events_snapshot_changed',
        'attribution_events',
        encode(sha256(convert_to(
            'attribution_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.occurred_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.processing_status IN ('pending', 'processed') AND row_set.event_type IN ('conversion', 'purchase'), false) AND row_set.occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_insert ON public.attribution_events;
CREATE TRIGGER trg_b24_invalidate_attribution_events_insert
AFTER INSERT ON public.attribution_events
REFERENCING NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_insert();

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_update ON public.attribution_events;
CREATE TRIGGER trg_b24_invalidate_attribution_events_update
AFTER UPDATE ON public.attribution_events
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_update();

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_delete ON public.attribution_events;
CREATE TRIGGER trg_b24_invalidate_attribution_events_delete
AFTER DELETE ON public.attribution_events
REFERENCING OLD TABLE AS old_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_events_delete();

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_revenue_events_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.event_occurred_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND row_set.event_occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_revenue_events_update()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.event_occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) OR (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.match_verdict_id, new_row.provider, new_row.canonical_commerce_reference, new_row.event_type, new_row.currency_code, new_row.event_occurred_at, new_row.captured_amount_minor, new_row.refund_amount_minor, new_row.chargeback_amount_minor, new_row.reversal_amount_minor, new_row.net_effect_sign, new_row.is_gross_capture_correction)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.match_verdict_id, old_row.provider, old_row.canonical_commerce_reference, old_row.event_type, old_row.currency_code, old_row.event_occurred_at, old_row.captured_amount_minor, old_row.refund_amount_minor, old_row.chargeback_amount_minor, old_row.reversal_amount_minor, old_row.net_effect_sign, old_row.is_gross_capture_correction)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.event_occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) OR (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND new_row.event_occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND old_row.event_occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.match_verdict_id, new_row.provider, new_row.canonical_commerce_reference, new_row.event_type, new_row.currency_code, new_row.event_occurred_at, new_row.captured_amount_minor, new_row.refund_amount_minor, new_row.chargeback_amount_minor, new_row.reversal_amount_minor, new_row.net_effect_sign, new_row.is_gross_capture_correction)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.match_verdict_id, old_row.provider, old_row.canonical_commerce_reference, old_row.event_type, old_row.currency_code, old_row.event_occurred_at, old_row.captured_amount_minor, old_row.refund_amount_minor, old_row.chargeback_amount_minor, old_row.reversal_amount_minor, old_row.net_effect_sign, old_row.is_gross_capture_correction)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_revenue_events_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $b24_invalidation$
BEGIN
    INSERT INTO public.b24_dirty_events (
        tenant_id, model_type, model_version,
        source_window_start, source_window_end,
        dirty_reason, source_family, event_hash, source_event_id,
        observed_at, status, created_at, updated_at
    )
    SELECT
        affected.tenant_id,
        'bayesian_attribution_confidence',
        'b24-p6-real-fit-v1',
        affected.window_start,
        affected.window_start + interval '1 day',
        'b23_revenue_events_snapshot_changed',
        'b23_revenue_events',
        encode(sha256(convert_to(
            'b23_revenue_events|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_revenue_events:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.event_occurred_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.event_type IN ('payment_capture', 'partial_refund', 'full_refund', 'chargeback_lost', 'chargeback_won', 'reversal'), false) AND row_set.event_occurred_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_insert ON public.b23_revenue_events;
CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_insert
AFTER INSERT ON public.b23_revenue_events
REFERENCING NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_insert();

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_update ON public.b23_revenue_events;
CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_update
AFTER UPDATE ON public.b23_revenue_events
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_update();

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_delete ON public.b23_revenue_events;
CREATE TRIGGER trg_b24_invalidate_b23_revenue_events_delete
AFTER DELETE ON public.b23_revenue_events
REFERENCING OLD TABLE AS old_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_revenue_events_delete();
"""


def upgrade() -> None:
    op.execute(SOURCE_INVALIDATION_DDL)
    op.execute(WRITE_CLOCK_INVALIDATION_DDL)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_bind_session_authority_from_event()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            authority_now timestamptz;
        BEGIN
            authority_now := COALESCE(
                NEW.event_timestamp,
                NEW.occurred_at,
                transaction_timestamp()
            );
            IF NEW.session_id IS NULL THEN
                NEW.session_id := gen_random_uuid();
            END IF;

            INSERT INTO public.session_authority
            (
                tenant_id, session_id, issued_at, expires_at, last_seen_at,
                invalidated_at, invalidation_reason, issued_by, created_at, updated_at
            )
            VALUES
            (
                NEW.tenant_id, NEW.session_id, authority_now,
                authority_now + interval '24 hours', authority_now,
                NULL, NULL, 'attribution_event_insert',
                transaction_timestamp(), transaction_timestamp()
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = GREATEST(
                    public.session_authority.last_seen_at,
                    EXCLUDED.last_seen_at
                ),
                updated_at = transaction_timestamp();

            IF EXISTS (
                SELECT 1
                  FROM public.session_authority AS authority
                 WHERE authority.tenant_id = NEW.tenant_id
                   AND authority.session_id = NEW.session_id
                   AND (
                       authority.invalidated_at IS NOT NULL
                       OR authority.issued_at > authority_now
                       OR authority.expires_at <= authority_now
                   )
            ) THEN
                RAISE EXCEPTION
                    'session authority violation: stale or invalidated session_id on attribution_events insert';
            END IF;

            RETURN NEW;
        END;
        $BODY$;

        CREATE OR REPLACE FUNCTION public.b23_project_allocation_verification()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        DECLARE
            authority record;
        BEGIN
            SELECT verdict.*
              INTO authority
              FROM public.b23_match_verdicts AS verdict
             WHERE verdict.tenant_id = NEW.tenant_id
               AND verdict.attribution_event_id = NEW.event_id
               AND verdict.status IN ('matched_confirmed', 'adjusted')
             ORDER BY
                 CASE verdict.status WHEN 'adjusted' THEN 0 ELSE 1 END,
                 verdict.last_transition_at DESC,
                 verdict.id DESC
             LIMIT 1;

            IF FOUND THEN
                NEW.verified := true;
                NEW.verification_source := 'b23_match_verdict';
                NEW.verification_timestamp := authority.last_transition_at;
            ELSE
                NEW.verified := false;
                NEW.verification_source := NULL;
                NEW.verification_timestamp := NULL;
            END IF;
            RETURN NEW;
        END;
        $BODY$;

        CREATE OR REPLACE FUNCTION public.b23_refresh_allocation_verification()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = pg_catalog, public
        AS $BODY$
        BEGIN
            IF NEW.attribution_event_id IS NULL THEN
                RETURN NEW;
            END IF;

            UPDATE public.attribution_allocations AS allocation
               SET verified = NEW.status IN ('matched_confirmed', 'adjusted'),
                   verification_source = CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN 'b23_match_verdict'
                       ELSE NULL
                   END,
                   verification_timestamp = CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN NEW.last_transition_at
                       ELSE NULL
                   END,
                   updated_at = transaction_timestamp()
             WHERE allocation.tenant_id = NEW.tenant_id
               AND allocation.event_id = NEW.attribution_event_id
               AND (
                   allocation.verified IS DISTINCT FROM
                       (NEW.status IN ('matched_confirmed', 'adjusted'))
                   OR allocation.verification_source IS DISTINCT FROM CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN 'b23_match_verdict'
                       ELSE NULL
                   END
                   OR allocation.verification_timestamp IS DISTINCT FROM CASE
                       WHEN NEW.status IN ('matched_confirmed', 'adjusted')
                           THEN NEW.last_transition_at
                       ELSE NULL
                   END
               );
            RETURN NEW;
        END;
        $BODY$;


        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_insert
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_update
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_delete
            ON public.attribution_allocations;

        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_insert
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_update
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_delete
            ON public.b23_match_verdicts;

        DROP TRIGGER IF EXISTS trg_b23_project_allocation_verification
            ON public.attribution_allocations;
        CREATE TRIGGER trg_b23_project_allocation_verification
        BEFORE INSERT OR UPDATE OF tenant_id, event_id, verified,
            verification_source, verification_timestamp
        ON public.attribution_allocations
        FOR EACH ROW
        EXECUTE FUNCTION public.b23_project_allocation_verification();

        DROP TRIGGER IF EXISTS trg_b23_refresh_allocation_verification_insert
            ON public.b23_match_verdicts;
        CREATE TRIGGER trg_b23_refresh_allocation_verification_insert
        AFTER INSERT ON public.b23_match_verdicts
        FOR EACH ROW
        EXECUTE FUNCTION public.b23_refresh_allocation_verification();

        DROP TRIGGER IF EXISTS trg_b23_refresh_allocation_verification_update
            ON public.b23_match_verdicts;
        CREATE TRIGGER trg_b23_refresh_allocation_verification_update
        AFTER UPDATE OF status, attribution_event_id, last_transition_at
        ON public.b23_match_verdicts
        FOR EACH ROW
        WHEN (
            OLD.status IS DISTINCT FROM NEW.status
            OR OLD.attribution_event_id IS DISTINCT FROM NEW.attribution_event_id
            OR OLD.last_transition_at IS DISTINCT FROM NEW.last_transition_at
        )
        EXECUTE FUNCTION public.b23_refresh_allocation_verification();

        WITH authorities AS (
            SELECT DISTINCT ON (
                       verdict.tenant_id,
                       verdict.attribution_event_id
                   )
                   verdict.tenant_id,
                   verdict.attribution_event_id,
                   verdict.last_transition_at
              FROM public.b23_match_verdicts AS verdict
             WHERE verdict.attribution_event_id IS NOT NULL
               AND verdict.status IN ('matched_confirmed', 'adjusted')
             ORDER BY
                   verdict.tenant_id,
                   verdict.attribution_event_id,
                   CASE verdict.status WHEN 'adjusted' THEN 0 ELSE 1 END,
                   verdict.last_transition_at DESC,
                   verdict.id DESC
        )
        UPDATE public.attribution_allocations AS allocation
           SET verified = true,
               verification_source = 'b23_match_verdict',
               verification_timestamp = authority.last_transition_at,
               updated_at = transaction_timestamp()
          FROM authorities AS authority
         WHERE allocation.tenant_id = authority.tenant_id
           AND allocation.event_id = authority.attribution_event_id;

        UPDATE public.attribution_allocations AS allocation
           SET verified = false,
               verification_source = NULL,
               verification_timestamp = NULL,
               updated_at = transaction_timestamp()
         WHERE allocation.verified = true
           AND NOT EXISTS (
               SELECT 1
                 FROM public.b23_match_verdicts AS verdict
                WHERE verdict.tenant_id = allocation.tenant_id
                  AND verdict.attribution_event_id = allocation.event_id
                  AND verdict.status IN ('matched_confirmed', 'adjusted')
           );

        COMMENT ON FUNCTION public.b23_project_allocation_verification() IS
            'C19: allocation verification is projected only from confirmed/adjusted B2.3 verdict authority.';
        COMMENT ON FUNCTION public.b23_refresh_allocation_verification() IS
            'C19: verdict transitions and allocation verification converge in one PostgreSQL transaction.';
        COMMENT ON FUNCTION public.b24_mark_allocation_financial_window_dirty() IS
            'C19: allocation changes invalidate the governed window of the underlying financial event.';
        COMMENT ON FUNCTION public.b24_mark_verdict_financial_window_dirty() IS
            'C19: verdict changes invalidate the governed window of the underlying financial event.';
        COMMENT ON FUNCTION public.fn_bind_session_authority_from_event() IS
            'C19: session authority is adjudicated in the event-time domain, including bounded legitimate backfill.';

        -- The deployment provisioner creates the LOGIN roles; migration-only
        -- replay jobs have no CREATEROLE capability and may not have them.
        -- Following the C6 pattern, optional-role grants are conditional so a
        -- legacy replay skips absent identities instead of failing.
        DO $$
        BEGIN
            IF to_regrole('app_celery_transport') IS NOT NULL THEN
                EXECUTE 'GRANT USAGE ON SCHEMA public TO app_celery_transport';
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON
                    public.kombu_queue,
                    public.kombu_message,
                    public.celery_taskmeta,
                    public.celery_tasksetmeta
                TO app_celery_transport';
                EXECUTE 'GRANT USAGE, SELECT ON
                    public.queue_id_sequence,
                    public.message_id_sequence,
                    public.task_id_sequence,
                    public.taskset_id_sequence,
                    public.kombu_queue_id_seq,
                    public.kombu_message_id_seq,
                    public.celery_taskmeta_id_seq,
                    public.celery_tasksetmeta_id_seq
                TO app_celery_transport';
            END IF;
        END
        $$;

        -- The dispatch publisher is a real Celery worker; its failure hook
        -- must be able to persist its own dead letters like app_worker can.
        -- FORCE RLS previously admitted only app_user, so worker substrate
        -- roles held grants they could never exercise; extend the same
        -- tenant-isolation expression to them rather than weakening it.
        -- The policy role list is composed from the roles that exist so the
        -- same migration replays on provisioner and migration-only topologies.
        DO $$
        DECLARE
            dlq_roles text;
        BEGIN
            IF to_regrole('app_dispatch_publisher') IS NOT NULL THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE ON public.worker_failed_jobs'
                    || ' TO app_dispatch_publisher';
            END IF;
            SELECT string_agg(quote_ident(role_name), ', ')
              INTO dlq_roles
              FROM unnest(
                  ARRAY['app_user', 'app_worker', 'app_dispatch_publisher']
              ) AS role_name
             WHERE to_regrole(role_name) IS NOT NULL;
            EXECUTE 'DROP POLICY IF EXISTS tenant_isolation_policy'
                || ' ON public.worker_failed_jobs';
            EXECUTE format(
                'CREATE POLICY tenant_isolation_policy'
                || ' ON public.worker_failed_jobs TO %s USING ('
                || 'tenant_id IS NULL OR tenant_id::text'
                || ' = current_setting(''app.current_tenant_id'', true))',
                dlq_roles
            );
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.fn_bind_session_authority_from_event()
        RETURNS trigger AS $BODY$
        DECLARE
            authority_now timestamptz;
        BEGIN
            authority_now := now();
            IF NEW.session_id IS NULL THEN
                NEW.session_id := gen_random_uuid();
            END IF;

            INSERT INTO public.session_authority
            (
                tenant_id, session_id, issued_at, expires_at, last_seen_at,
                invalidated_at, invalidation_reason, issued_by, created_at, updated_at
            )
            VALUES
            (
                NEW.tenant_id, NEW.session_id, authority_now,
                authority_now + interval '24 hours', authority_now,
                NULL, NULL, 'attribution_event_insert', authority_now, authority_now
            )
            ON CONFLICT (tenant_id, session_id)
            DO UPDATE SET
                last_seen_at = GREATEST(
                    public.session_authority.last_seen_at,
                    EXCLUDED.last_seen_at
                ),
                updated_at = EXCLUDED.updated_at;

            IF EXISTS (
                SELECT 1
                  FROM public.session_authority AS authority
                 WHERE authority.tenant_id = NEW.tenant_id
                   AND authority.session_id = NEW.session_id
                   AND (
                       authority.invalidated_at IS NOT NULL
                       OR authority.expires_at <= authority_now
                   )
            ) THEN
                RAISE EXCEPTION
                    'session authority violation: stale or invalidated session_id on attribution_events insert';
            END IF;

            RETURN NEW;
        END;
        $BODY$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS trg_b23_refresh_allocation_verification_update
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b23_refresh_allocation_verification_insert
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b23_project_allocation_verification
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_mark_allocation_financial_window_dirty
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_mark_verdict_financial_window_dirty
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_insert
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_update
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_delete
            ON public.attribution_allocations;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_insert
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_update
            ON public.b23_match_verdicts;
        DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_delete
            ON public.b23_match_verdicts;
        CREATE TRIGGER trg_b24_invalidate_attribution_allocations_insert
        AFTER INSERT ON public.attribution_allocations
        REFERENCING NEW TABLE AS new_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_insert();
        CREATE TRIGGER trg_b24_invalidate_attribution_allocations_update
        AFTER UPDATE ON public.attribution_allocations
        REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_update();
        CREATE TRIGGER trg_b24_invalidate_attribution_allocations_delete
        AFTER DELETE ON public.attribution_allocations
        REFERENCING OLD TABLE AS old_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_delete();
        CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_insert
        AFTER INSERT ON public.b23_match_verdicts
        REFERENCING NEW TABLE AS new_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_insert();
        CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_update
        AFTER UPDATE ON public.b23_match_verdicts
        REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_update();
        CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_delete
        AFTER DELETE ON public.b23_match_verdicts
        REFERENCING OLD TABLE AS old_rows
        FOR EACH STATEMENT
        EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_delete();
        DROP FUNCTION IF EXISTS public.b23_refresh_allocation_verification();
        DROP FUNCTION IF EXISTS public.b23_project_allocation_verification();
        DROP FUNCTION IF EXISTS public.b24_mark_allocation_financial_window_dirty();
        DROP FUNCTION IF EXISTS public.b24_mark_verdict_financial_window_dirty();
        DO $$
        BEGIN
            EXECUTE 'DROP POLICY IF EXISTS tenant_isolation_policy'
                || ' ON public.worker_failed_jobs';
            IF to_regrole('app_user') IS NOT NULL THEN
                EXECUTE 'CREATE POLICY tenant_isolation_policy'
                    || ' ON public.worker_failed_jobs TO app_user USING ('
                    || 'tenant_id IS NULL OR tenant_id::text'
                    || ' = current_setting(''app.current_tenant_id'', true))';
            END IF;
            IF to_regrole('app_dispatch_publisher') IS NOT NULL THEN
                EXECUTE 'REVOKE SELECT, INSERT, UPDATE ON public.worker_failed_jobs'
                    || ' FROM app_dispatch_publisher';
            END IF;
            IF to_regrole('app_celery_transport') IS NOT NULL THEN
                EXECUTE 'REVOKE ALL ON
                    public.queue_id_sequence,
                    public.message_id_sequence,
                    public.task_id_sequence,
                    public.taskset_id_sequence,
                    public.kombu_queue_id_seq,
                    public.kombu_message_id_seq,
                    public.celery_taskmeta_id_seq,
                    public.celery_tasksetmeta_id_seq
                FROM app_celery_transport';
                EXECUTE 'REVOKE ALL ON
                    public.kombu_queue,
                    public.kombu_message,
                    public.celery_taskmeta,
                    public.celery_tasksetmeta
                FROM app_celery_transport';
                EXECUTE 'REVOKE USAGE ON SCHEMA public FROM app_celery_transport';
            END IF;
        END
        $$;
        """
    )
