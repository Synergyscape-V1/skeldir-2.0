"""B2.5-P13 C8 identity-space unification and window-causality closure.

Revision ID: 202608231200
Revises: 202608221200
Create Date: 2026-08-23 12:00:00.000000

C7 made source invalidation physical. C8 makes it *reach the thing it protects*.

Two seams were severing the causal graph. The invalidation triggers emitted the
B2.4-P3 orchestration-era identity ``('mmm', 'b24-p3-orchestration-v1')`` while
the Trust confidence read model projects only
``'bayesian_attribution_confidence'`` and joined dirty evidence on exact model
equality -- so no committed source change could make a signed claim stale. And
the triggers emitted one-day windows while two of three production dirty
producers forward arbitrary caller windows, with freshness joined on exact
window equality -- so a change inside a wider fit could not stale it either.

Both are corrected structurally rather than by relabelling:

* ``model_identity`` is now the single registry declaring which identity
  production may emit and which Trust may project. This revision records that
  registry in the database as a CHECK, so an unregistered family cannot be
  stored at all -- a default parameter is not an architecture guarantee.

* Staleness becomes bounded window OVERLAP. A dirty event records the SCOPE of a
  change, which is all a writer can know; the affected-fit relation is evaluated
  at read time, correlated to one requested fit, so no unbounded write-time
  fan-out is introduced. ``b24_source_windows_overlap`` is the one definition of
  that relation, used by the read model and by the proofs.

Historical rows carrying the retired identity remain legal and readable. They
are not rewritten: reclassifying already-signed epistemic history would be the
precise failure this phase exists to prevent.
"""

from __future__ import annotations

from alembic import op


revision = "202608231200"
down_revision = "202608221200"
branch_labels = None
depends_on = None


# Mirrors app.bayesian.model_identity.MODEL_IDENTITY_REGISTRY. The C8 gate
# asserts these agree, so a family added in Python without being admitted here
# (or vice versa) turns required CI red.
REGISTERED_MODEL_TYPES = ('bayesian_attribution_confidence', 'mmm')
ACTIVE_MODEL_TYPE = "bayesian_attribution_confidence"
ACTIVE_MODEL_VERSION = "b24-p6-real-fit-v1"

SOURCE_INVALIDATION_DDL = """
CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_allocations_insert()
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
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.created_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.verified = true, false) AND row_set.created_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_allocations_update()
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
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.created_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) OR (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL))
              AND (
                (COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.event_id, new_row.created_at, new_row.channel_code, new_row.allocated_revenue_cents, new_row.allocation_ratio, new_row.model_type, new_row.model_version, new_row.verified, new_row.verification_source, new_row.verification_timestamp)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.event_id, old_row.created_at, old_row.channel_code, old_row.allocated_revenue_cents, old_row.allocation_ratio, old_row.model_type, old_row.model_version, old_row.verified, old_row.verification_source, old_row.verification_timestamp)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.created_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) OR (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL))
              AND (
                (COALESCE(new_row.verified = true, false) AND new_row.created_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.verified = true, false) AND old_row.created_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.event_id, new_row.created_at, new_row.channel_code, new_row.allocated_revenue_cents, new_row.allocation_ratio, new_row.model_type, new_row.model_version, new_row.verified, new_row.verification_source, new_row.verification_timestamp)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.event_id, old_row.created_at, old_row.channel_code, old_row.allocated_revenue_cents, old_row.allocation_ratio, old_row.model_type, old_row.model_version, old_row.verified, old_row.verification_source, old_row.verification_timestamp)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_attribution_allocations_delete()
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
        'attribution_allocations_snapshot_changed',
        'attribution_allocations',
        encode(sha256(convert_to(
            'attribution_allocations|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('attribution_allocations:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.created_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.verified = true, false) AND row_set.created_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_insert ON public.attribution_allocations;
CREATE TRIGGER trg_b24_invalidate_attribution_allocations_insert
AFTER INSERT ON public.attribution_allocations
REFERENCING NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_insert();

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_update ON public.attribution_allocations;
CREATE TRIGGER trg_b24_invalidate_attribution_allocations_update
AFTER UPDATE ON public.attribution_allocations
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_update();

DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_delete ON public.attribution_allocations;
CREATE TRIGGER trg_b24_invalidate_attribution_allocations_delete
AFTER DELETE ON public.attribution_allocations
REFERENCING OLD TABLE AS old_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_attribution_allocations_delete();

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
        WHERE COALESCE(row_set.processing_status IN ('processed') AND row_set.event_type IN ('conversion'), false) AND row_set.occurred_at IS NOT NULL
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
            WHERE ((COALESCE(new_row.processing_status IN ('processed') AND new_row.event_type IN ('conversion'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('processed') AND old_row.event_type IN ('conversion'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('processed') AND new_row.event_type IN ('conversion'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('processed') AND old_row.event_type IN ('conversion'), false) AND old_row.occurred_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.occurred_at, new_row.event_timestamp, new_row.event_type, new_row.channel, new_row.campaign_id, new_row.revenue_cents, new_row.conversion_value_cents, new_row.currency, new_row.processing_status)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.occurred_at, old_row.event_timestamp, old_row.event_type, old_row.channel, old_row.campaign_id, old_row.revenue_cents, old_row.conversion_value_cents, old_row.currency, old_row.processing_status)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.occurred_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.processing_status IN ('processed') AND new_row.event_type IN ('conversion'), false) AND new_row.occurred_at IS NOT NULL) OR (COALESCE(old_row.processing_status IN ('processed') AND old_row.event_type IN ('conversion'), false) AND old_row.occurred_at IS NOT NULL))
              AND (
                (COALESCE(new_row.processing_status IN ('processed') AND new_row.event_type IN ('conversion'), false) AND new_row.occurred_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.processing_status IN ('processed') AND old_row.event_type IN ('conversion'), false) AND old_row.occurred_at IS NOT NULL)
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
        WHERE COALESCE(row_set.processing_status IN ('processed') AND row_set.event_type IN ('conversion'), false) AND row_set.occurred_at IS NOT NULL
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

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_match_verdicts_insert()
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
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.last_transition_at) AS window_start
        FROM new_rows row_set
        WHERE COALESCE(row_set.status IN ('matched_confirmed', 'adjusted'), false) AND row_set.last_transition_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_match_verdicts_update()
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
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT tenant_id, window_start FROM (
            SELECT new_row.tenant_id AS tenant_id,
                   date_trunc('day', new_row.last_transition_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) OR (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL))
              AND (
                (COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.attribution_event_id, new_row.provider, new_row.canonical_commerce_reference, new_row.status, new_row.match_quality, new_row.attributed_amount_minor, new_row.verified_amount_minor, new_row.currency_code, new_row.confirmed_at, new_row.adjusted_at, new_row.last_transition_at, new_row.canonical_expected_gross_amount_minor, new_row.canonical_captured_gross_amount_minor, new_row.canonical_net_verified_amount_minor, new_row.discrepancy_amount_minor, new_row.discrepancy_ratio_bps, new_row.discrepancy_band)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.attribution_event_id, old_row.provider, old_row.canonical_commerce_reference, old_row.status, old_row.match_quality, old_row.attributed_amount_minor, old_row.verified_amount_minor, old_row.currency_code, old_row.confirmed_at, old_row.adjusted_at, old_row.last_transition_at, old_row.canonical_expected_gross_amount_minor, old_row.canonical_captured_gross_amount_minor, old_row.canonical_net_verified_amount_minor, old_row.discrepancy_amount_minor, old_row.discrepancy_ratio_bps, old_row.discrepancy_band)
              )
            UNION
            SELECT old_row.tenant_id AS tenant_id,
                   date_trunc('day', old_row.last_transition_at) AS window_start
            FROM new_rows new_row
            JOIN old_rows old_row ON old_row.id = new_row.id
            WHERE ((COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) OR (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL))
              AND (
                (COALESCE(new_row.status IN ('matched_confirmed', 'adjusted'), false) AND new_row.last_transition_at IS NOT NULL) IS DISTINCT FROM (COALESCE(old_row.status IN ('matched_confirmed', 'adjusted'), false) AND old_row.last_transition_at IS NOT NULL)
                OR (new_row.id, new_row.tenant_id, new_row.attribution_event_id, new_row.provider, new_row.canonical_commerce_reference, new_row.status, new_row.match_quality, new_row.attributed_amount_minor, new_row.verified_amount_minor, new_row.currency_code, new_row.confirmed_at, new_row.adjusted_at, new_row.last_transition_at, new_row.canonical_expected_gross_amount_minor, new_row.canonical_captured_gross_amount_minor, new_row.canonical_net_verified_amount_minor, new_row.discrepancy_amount_minor, new_row.discrepancy_ratio_bps, new_row.discrepancy_band)
                   IS DISTINCT FROM (old_row.id, old_row.tenant_id, old_row.attribution_event_id, old_row.provider, old_row.canonical_commerce_reference, old_row.status, old_row.match_quality, old_row.attributed_amount_minor, old_row.verified_amount_minor, old_row.currency_code, old_row.confirmed_at, old_row.adjusted_at, old_row.last_transition_at, old_row.canonical_expected_gross_amount_minor, old_row.canonical_captured_gross_amount_minor, old_row.canonical_net_verified_amount_minor, old_row.discrepancy_amount_minor, old_row.discrepancy_ratio_bps, old_row.discrepancy_band)
              )
        ) both_buckets
        WHERE window_start IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

CREATE OR REPLACE FUNCTION public.b24_invalidate_b23_match_verdicts_delete()
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
        'b23_match_verdicts_snapshot_changed',
        'b23_match_verdicts',
        encode(sha256(convert_to(
            'b23_match_verdicts|' || affected.tenant_id::text || '|'
            || affected.window_start::text, 'UTF8')), 'hex'),
        left('b23_match_verdicts:' || affected.window_start::text, 128),
        now(),
        'pending',
        now(),
        now()
    FROM (
        SELECT DISTINCT
            row_set.tenant_id AS tenant_id,
            date_trunc('day', row_set.last_transition_at) AS window_start
        FROM old_rows row_set
        WHERE COALESCE(row_set.status IN ('matched_confirmed', 'adjusted'), false) AND row_set.last_transition_at IS NOT NULL
    ) affected;
    RETURN NULL;
END
$b24_invalidation$;

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_insert ON public.b23_match_verdicts;
CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_insert
AFTER INSERT ON public.b23_match_verdicts
REFERENCING NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_insert();

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_update ON public.b23_match_verdicts;
CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_update
AFTER UPDATE ON public.b23_match_verdicts
REFERENCING OLD TABLE AS old_rows NEW TABLE AS new_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_update();

DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_delete ON public.b23_match_verdicts;
CREATE TRIGGER trg_b24_invalidate_b23_match_verdicts_delete
AFTER DELETE ON public.b23_match_verdicts
REFERENCING OLD TABLE AS old_rows
FOR EACH STATEMENT EXECUTE FUNCTION public.b24_invalidate_b23_match_verdicts_delete();

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

SOURCE_INVALIDATION_DROP_DDL = """
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_insert ON public.attribution_allocations;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_allocations_insert();
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_update ON public.attribution_allocations;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_allocations_update();
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_allocations_delete ON public.attribution_allocations;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_allocations_delete();
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_insert ON public.attribution_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_events_insert();
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_update ON public.attribution_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_events_update();
DROP TRIGGER IF EXISTS trg_b24_invalidate_attribution_events_delete ON public.attribution_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_attribution_events_delete();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_insert ON public.b23_match_verdicts;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_match_verdicts_insert();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_update ON public.b23_match_verdicts;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_match_verdicts_update();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_match_verdicts_delete ON public.b23_match_verdicts;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_match_verdicts_delete();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_insert ON public.b23_revenue_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_revenue_events_insert();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_update ON public.b23_revenue_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_revenue_events_update();
DROP TRIGGER IF EXISTS trg_b24_invalidate_b23_revenue_events_delete ON public.b23_revenue_events;
DROP FUNCTION IF EXISTS public.b24_invalidate_b23_revenue_events_delete();
"""


def _registered_model_sql() -> str:
    return ", ".join(f"'{model_type}'" for model_type in REGISTERED_MODEL_TYPES)


def _own_as_worker(signature: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE 'GRANT CREATE ON SCHEMA public TO app_worker';
                EXECUTE 'ALTER FUNCTION public.{signature} OWNER TO app_worker';
                EXECUTE 'REVOKE CREATE ON SCHEMA public FROM app_worker';
            END IF;
        END
        $$;
        """
    )


def _allow_replace(signature: str) -> None:
    """Restore EXECUTE to the migrating principal just long enough to replace.

    C7 revoked EXECUTE on these functions from app_user, and PostgreSQL requires
    EXECUTE on an existing function to CREATE OR REPLACE it. In a topology whose
    migration principal is one of the revoked roles the replace is otherwise
    denied even though that principal owns the function.
    """

    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regprocedure('public.{signature}') IS NOT NULL THEN
                EXECUTE 'GRANT EXECUTE ON FUNCTION public.{signature} TO '
                        || quote_ident(current_user);
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Window dependency: one definition of "this change affects this fit".
    # ------------------------------------------------------------------
    # Half-open interval overlap, matching the source query's own
    # [window_start, window_end) range semantics exactly.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_source_windows_overlap(
            p_change_start timestamptz,
            p_change_end timestamptz,
            p_fit_start timestamptz,
            p_fit_end timestamptz
        )
        RETURNS boolean
        LANGUAGE sql
        IMMUTABLE
        PARALLEL SAFE
        AS $$
            SELECT p_change_start < p_fit_end AND p_fit_start < p_change_end
        $$;
        COMMENT ON FUNCTION public.b24_source_windows_overlap(
            timestamptz, timestamptz, timestamptz, timestamptz
        ) IS
            'B2.5-P13 C8 affected-fit relation. A source change scope stales a '
            'fit when the two half-open windows overlap. Equality was the C7 '
            'behaviour and could not stale a fit wider than one day.';
        GRANT EXECUTE ON FUNCTION public.b24_source_windows_overlap(
            timestamptz, timestamptz, timestamptz, timestamptz
        ) TO PUBLIC;
        """
    )

    # Supports the correlated overlap EXISTS the read model evaluates per fit.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_b24_dirty_events_staleness_overlap
            ON public.b24_dirty_events (
                tenant_id, model_type, source_window_start,
                source_window_end, observed_at
            );
        """
    )

    # ------------------------------------------------------------------
    # 2. Model identity is registered authority, not a default parameter.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        ALTER TABLE public.b24_dirty_events
            ADD CONSTRAINT ck_b24_dirty_events_registered_model_type
            CHECK (model_type IN ({_registered_model_sql()}));
        ALTER TABLE public.bayesian_model_fits
            ADD CONSTRAINT ck_bayesian_model_fits_registered_model_type
            CHECK (model_type IN ({_registered_model_sql()}));
        """
    )

    # ------------------------------------------------------------------
    # 3. Re-render invalidation at the canonical identity.
    # ------------------------------------------------------------------
    for relation in (
        "attribution_allocations",
        "attribution_events",
        "b23_match_verdicts",
        "b23_revenue_events",
    ):
        for operation in ("insert", "update", "delete"):
            _allow_replace(f"b24_invalidate_{relation}_{operation}()")

    op.execute(SOURCE_INVALIDATION_DDL)

    for relation in (
        "attribution_allocations",
        "attribution_events",
        "b23_match_verdicts",
        "b23_revenue_events",
    ):
        for operation in ("insert", "update", "delete"):
            signature = f"b24_invalidate_{relation}_{operation}()"
            op.execute(
                f"REVOKE ALL ON FUNCTION public.{signature} "
                "FROM PUBLIC, app_user, app_rw, app_ro"
            )
            _own_as_worker(signature)


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE public.bayesian_model_fits
            DROP CONSTRAINT IF EXISTS ck_bayesian_model_fits_registered_model_type;
        ALTER TABLE public.b24_dirty_events
            DROP CONSTRAINT IF EXISTS ck_b24_dirty_events_registered_model_type;
        DROP INDEX IF EXISTS public.idx_b24_dirty_events_staleness_overlap;
        DROP FUNCTION IF EXISTS public.b24_source_windows_overlap(
            timestamptz, timestamptz, timestamptz, timestamptz
        );
        """
    )
