"""B2.5-P13 C7 source-change causality and planner-obligation conservation.

Revision ID: 202608221200
Revises: 202608202300
Create Date: 2026-08-22 12:00:00.000000

Three conservation laws become physical here.

1. Source-change causality.  Every B2.4 source relation carries statement-level
   triggers rendered from ``app.bayesian.source_invalidation_contract``.  A
   committed mutation that moves a row into or out of the canonical snapshot
   member set, or changes one of its projected columns, appends the dirty event
   in the same transaction as the mutation.  Invalidation is no longer a call
   site a future writer can forget; there is no code path between the write and
   the trigger.

2. Planner-obligation conservation.  A wakeup stops being a notification that a
   planner ran and becomes a durable obligation to revisit the tenant until no
   dirty state requires a later planner opportunity.  Acknowledgement is derived
   from residual authority read atomically at completion time, never from the
   absence of a Python exception, so a pre-debounce or candidate-limit-truncated
   pass retains or defers the obligation instead of destroying it.

3. Complete confidence dependency authority.  ``created_at`` orders
   ``has_newer_fit`` and backstops ``has_later_dirty_evidence``; ``id`` and
   ``tenant_id`` select the row.  All three decide signed confidence, so all
   three join the governed terminal set.  Artifact lifecycle and dirty-event
   status gain enforced transition contracts so non-fit decision inputs cannot
   silently rewrite epistemic history either.

The planner wakeup lease is also lifted clear of the worker hard time limit.  At
equal values a second planner could reclaim a tenant at the same instant the
first was force-killed; the lease now dominates the longest legitimate ownership
duration plus a shutdown/broker margin.
"""

from __future__ import annotations

from alembic import op


revision = "202608221200"
down_revision = "202608202300"
branch_labels = None
depends_on = None


# Governed terminal fit authority.  Every column that can change which fit is
# selected, whether it is the newest, how fresh its evidence is, or which
# provenance/reason the envelope carries.  Derived bidirectionally from
# app/confidence_projection/read_model.py by the C7 closure gate: a new
# decision-affecting reference that is absent here turns required CI red.
TRUST_FIT_DEPENDENCY_COLUMNS = (
    "id",
    "tenant_id",
    "model_type",
    "model_version",
    "source_window_start",
    "source_window_end",
    "source_snapshot_hash",
    "status",
    "data_completeness_status",
    "fallback_applied",
    "fallback_reason",
    "created_at",
    "completed_at",
    "updated_at",
    "diagnostic_status",
    "diagnostic_failure_reason",
    "credible_interval_status",
    "confidence_bucket",
    "confidence_bucket_reason",
    "confidence_policy_version",
    "confidence_semantics_version",
    "confidence_deterministic_revenue_minor",
    "confidence_deterministic_row_count",
    "confidence_match_verdict_count",
    "confidence_currency_count",
    "confidence_classified_at",
    "confidence_evidence_snapshot_hash",
    "source_read_started_at",
    "source_read_completed_at",
    "artifact_ref",
    "artifact_hash",
)

TERMINAL_FIT_STATUSES = (
    "succeeded",
    "failed",
    "timeout",
    "worker_lost",
    "fallback_only",
    "cancelled",
)

# A wakeup lease must dominate the longest legitimate planner ownership.  The
# worker hard time limit is 300s; an equal lease let a reclaimer and a
# force-killed owner overlap at the same instant.  The margin covers warm
# shutdown, broker acknowledgement, and worst-case database latency.  Recovery
# latency after a true crash is bounded by this value plus one beat interval,
# which delays work without losing it.
PLANNER_WAKEUP_LEASE_SECONDS = 600
PLANNER_WAKEUP_LEASE_MARGIN_SECONDS = 300

# Mirrors app.bayesian.fit_planner debounce authority.  The C7 gate asserts the
# defaults still equal QUIET_PERIOD_SECONDS / MAX_WAIT_SECONDS.
PLANNER_QUIET_PERIOD_SECONDS = 120
PLANNER_MAX_WAIT_SECONDS = 900

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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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
        'mmm',
        'b24-p3-orchestration-v1',
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


def _changed(columns: tuple[str, ...]) -> str:
    return "\n               OR ".join(
        f"NEW.{column} IS DISTINCT FROM OLD.{column}" for column in columns
    )


def _terminal_status_sql() -> str:
    return ", ".join(f"'{status}'" for status in TERMINAL_FIT_STATUSES)


def _worker_scoped(statement: str) -> None:
    """Apply a worker-dependent statement only where the role was provisioned."""

    escaped = statement.replace("'", "''")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                EXECUTE '{escaped}';
            END IF;
        END
        $$;
        """
    )


def _own_as_worker(signature: str) -> None:
    """Transfer one SECURITY DEFINER function to the worker authority."""

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


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Contract-derived source-change invalidation.
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # 2. Planner-obligation conservation.
    # ------------------------------------------------------------------
    op.execute(
        """
        ALTER TABLE public.b24_fit_planner_wakeups
            ADD COLUMN IF NOT EXISTS next_eligible_at timestamptz;
        COMMENT ON COLUMN public.b24_fit_planner_wakeups.next_eligible_at IS
            'NULL means immediately runnable. A timestamp means the tenant has '
            'residual dirty work whose debounce quiet period has not matured; '
            'the obligation is retained, not destroyed.';
        """
    )

    # Residual authority: exactly the debounce eligibility arithmetic the
    # production planner applies, evaluated against the tenant's remaining
    # unplanned dirty state.  Candidates this pass leased are excluded by their
    # live lease, so "processed" and "not yet processed" are distinguishable.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_fit_planner_residual_obligation(
            p_tenant_id uuid,
            p_quiet_period_seconds integer,
            p_max_wait_seconds integer
        )
        RETURNS TABLE(eligible_group_count integer, next_eligible_at timestamptz)
        LANGUAGE plpgsql
        STABLE
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            RETURN QUERY
            WITH candidate_groups AS (
                SELECT
                    max(dirty.observed_at) AS last_observed_at,
                    min(dirty.observed_at) AS first_observed_at
                FROM public.b24_dirty_events dirty
                WHERE dirty.tenant_id = p_tenant_id
                  AND (
                      dirty.status IN ('pending', 'authority_retry_ready')
                      OR (
                          dirty.status = 'leased'
                          AND dirty.lease_expires_at IS NOT NULL
                          AND dirty.lease_expires_at <= now()
                      )
                  )
                GROUP BY
                    dirty.model_type,
                    dirty.model_version,
                    dirty.source_window_start,
                    dirty.source_window_end,
                    dirty.source_snapshot_hash
            ),
            due_times AS (
                SELECT LEAST(
                    last_observed_at
                        + make_interval(secs => p_quiet_period_seconds),
                    first_observed_at
                        + make_interval(secs => GREATEST(
                            p_quiet_period_seconds, p_max_wait_seconds))
                ) AS due_at
                FROM candidate_groups
            )
            SELECT
                count(*) FILTER (WHERE due_at <= now())::integer,
                min(due_at) FILTER (WHERE due_at > now())
            FROM due_times;
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_fit_planner_residual_obligation(
            uuid, integer, integer
        ) FROM PUBLIC, app_user, app_rw, app_ro;
        """
    )
    _own_as_worker(
        "b24_fit_planner_residual_obligation(uuid, integer, integer)"
    )
    _worker_scoped(
        "GRANT EXECUTE ON FUNCTION "
        "public.b24_fit_planner_residual_obligation(uuid, integer, integer) "
        "TO app_worker"
    )

    # The selector honours a deferred obligation instead of hot-spinning a
    # tenant whose only work is still inside its quiet period.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_due_fit_planner_tenants(
            p_lease_owner text,
            p_limit integer DEFAULT 25
        )
        RETURNS TABLE(tenant_id uuid, wakeup_revision bigint)
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            IF p_lease_owner IS NULL OR btrim(p_lease_owner) = '' THEN
                RAISE EXCEPTION 'b24_fit_planner_lease_owner_required';
            END IF;
            RETURN QUERY
            WITH due AS (
                SELECT wakeup.tenant_id
                FROM public.b24_fit_planner_wakeups wakeup
                WHERE (
                        wakeup.next_eligible_at IS NULL
                        OR wakeup.next_eligible_at <= now()
                      )
                  AND (
                        wakeup.status = 'pending'
                        OR (
                            wakeup.status = 'leased'
                            AND wakeup.lease_expires_at <= now()
                        )
                      )
                ORDER BY wakeup.observed_at, wakeup.tenant_id
                LIMIT LEAST(GREATEST(p_limit, 1), 100)
                FOR UPDATE SKIP LOCKED
            )
            UPDATE public.b24_fit_planner_wakeups wakeup
            SET status = 'leased',
                lease_owner = p_lease_owner,
                lease_expires_at = now()
                    + make_interval(secs => {PLANNER_WAKEUP_LEASE_SECONDS}),
                updated_at = now()
            FROM due
            WHERE wakeup.tenant_id = due.tenant_id
            RETURNING wakeup.tenant_id, wakeup.wakeup_revision;
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_due_fit_planner_tenants(text, integer)
            FROM PUBLIC, app_user, app_rw, app_ro;
        """
    )
    _own_as_worker("b24_due_fit_planner_tenants(text, integer)")
    _worker_scoped(
        "GRANT EXECUTE ON FUNCTION "
        "public.b24_due_fit_planner_tenants(text, integer) TO app_worker"
    )

    # Acknowledgement derived from residual authority. The return value is the
    # machine-visible disposition of the obligation state machine rather than a
    # boolean that conflated "acknowledged" with "nothing left to do".
    op.execute(
        """
        DROP FUNCTION IF EXISTS public.b24_complete_fit_planner_wakeup(
            uuid, text, bigint, boolean
        );
        CREATE FUNCTION public.b24_complete_fit_planner_wakeup(
            p_tenant_id uuid,
            p_lease_owner text,
            p_wakeup_revision bigint,
            p_succeeded boolean,
            p_quiet_period_seconds integer,
            p_max_wait_seconds integer
        )
        RETURNS text
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        DECLARE
            residual_eligible integer;
            residual_next timestamptz;
            fenced boolean;
        BEGIN
            IF session_user <> 'app_worker' THEN
                RAISE EXCEPTION 'b24_worker_database_identity_required';
            END IF;
            -- Residual authority is tenant truth read under FORCE RLS. The
            -- caller must already have bound the tenant, so the obligation can
            -- never be judged against another tenant's dirty state.
            IF current_setting('app.current_tenant_id', true)
               IS DISTINCT FROM p_tenant_id::text THEN
                RAISE EXCEPTION 'b24_fit_planner_tenant_context_required';
            END IF;

            IF NOT p_succeeded THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, next_eligible_at = NULL,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner;
                IF FOUND THEN
                    RETURN 'released';
                END IF;
                RETURN 'stale_revision';
            END IF;

            SELECT eligible_group_count, next_eligible_at
            INTO residual_eligible, residual_next
            FROM public.b24_fit_planner_residual_obligation(
                p_tenant_id, p_quiet_period_seconds, p_max_wait_seconds
            );

            IF COALESCE(residual_eligible, 0) > 0 THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL, next_eligible_at = NULL,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'retained_eligible';
                END IF;
            ELSIF residual_next IS NOT NULL THEN
                UPDATE public.b24_fit_planner_wakeups
                SET status = 'pending', lease_owner = NULL,
                    lease_expires_at = NULL,
                    next_eligible_at = residual_next,
                    updated_at = now()
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'deferred';
                END IF;
            ELSE
                DELETE FROM public.b24_fit_planner_wakeups
                WHERE tenant_id = p_tenant_id
                  AND status = 'leased'
                  AND lease_owner = p_lease_owner
                  AND wakeup_revision = p_wakeup_revision;
                fenced := FOUND;
                IF fenced THEN
                    RETURN 'deleted';
                END IF;
            END IF;

            -- Revision fence missed: newer evidence arrived while this pass ran.
            -- Release any lease this owner still holds so the newer revision is
            -- immediately runnable, and never delete it.
            UPDATE public.b24_fit_planner_wakeups
            SET status = 'pending', lease_owner = NULL,
                lease_expires_at = NULL, next_eligible_at = NULL,
                updated_at = now()
            WHERE tenant_id = p_tenant_id
              AND status = 'leased'
              AND lease_owner = p_lease_owner;
            RETURN 'stale_revision';
        END
        $$;
        REVOKE ALL ON FUNCTION public.b24_complete_fit_planner_wakeup(
            uuid, text, bigint, boolean, integer, integer
        ) FROM PUBLIC, app_user, app_rw, app_ro;
        """
    )
    _own_as_worker(
        "b24_complete_fit_planner_wakeup("
        "uuid, text, bigint, boolean, integer, integer)"
    )
    _worker_scoped(
        "GRANT EXECUTE ON FUNCTION "
        "public.b24_complete_fit_planner_wakeup("
        "uuid, text, bigint, boolean, integer, integer) TO app_worker"
    )

    # New evidence must clear a deferral as well as invalidate a lease, or a
    # deferred tenant could sit behind a stale quiet-period estimate. The
    # predicate deliberately matches nothing in the steady pending state, which
    # preserves the PR #661 hot-row correction under bulk ingestion.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION
            public.b24_signal_fit_planner_wakeup_coalesced()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $$
        BEGIN
            IF NEW.status IN ('pending', 'authority_retry_ready')
               AND (
                    TG_OP = 'INSERT'
                    OR OLD.status IS DISTINCT FROM NEW.status
               ) THEN
                INSERT INTO public.b24_fit_planner_wakeups (
                    tenant_id, observed_at
                ) VALUES (NEW.tenant_id, NEW.observed_at)
                ON CONFLICT (tenant_id) DO NOTHING;

                IF NOT FOUND THEN
                    UPDATE public.b24_fit_planner_wakeups
                    SET wakeup_revision = CASE
                            WHEN status = 'leased' THEN wakeup_revision + 1
                            ELSE wakeup_revision
                        END,
                        status = 'pending',
                        lease_owner = NULL,
                        lease_expires_at = NULL,
                        next_eligible_at = NULL,
                        observed_at = LEAST(observed_at, NEW.observed_at),
                        updated_at = now()
                    WHERE tenant_id = NEW.tenant_id
                      AND (status = 'leased' OR next_eligible_at IS NOT NULL);
                END IF;
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )
    _own_as_worker("b24_signal_fit_planner_wakeup_coalesced()")

    # ------------------------------------------------------------------
    # 3. Complete confidence dependency authority.
    # ------------------------------------------------------------------
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION public.b24_enforce_terminal_fit_truth()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF public.b24_fit_status_is_terminal(OLD.status)
               AND ({_changed(TRUST_FIT_DEPENDENCY_COLUMNS)}) THEN
                RAISE EXCEPTION 'b24_terminal_fit_truth_immutable';
            END IF;
            RETURN NEW;
        END
        $$;
        """
    )

    # ------------------------------------------------------------------
    # 4. Non-fit decision authority lifecycle.
    # ------------------------------------------------------------------
    # Artifact lifecycle governs whether the Trust read can still resolve
    # evidence. Pruning is a legitimate, explainable degradation; resurrecting a
    # pruned or rejected artifact would silently rewrite epistemic history.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_artifact_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.lifecycle_status IS NOT DISTINCT FROM NEW.lifecycle_status THEN
                RETURN NEW;
            END IF;
            IF OLD.lifecycle_status IN ('pruned', 'rejected')
               AND NEW.lifecycle_status NOT IN ('pruned', 'rejected') THEN
                RAISE EXCEPTION 'b24_artifact_lifecycle_resurrection_forbidden';
            END IF;
            RETURN NEW;
        END
        $$;
        DROP TRIGGER IF EXISTS trg_b24_enforce_artifact_lifecycle
            ON public.bayesian_artifacts;
        CREATE TRIGGER trg_b24_enforce_artifact_lifecycle
        BEFORE UPDATE OF lifecycle_status ON public.bayesian_artifacts
        FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_artifact_lifecycle();
        """
    )

    # Dirty-event observed_at is a freshness input to the Trust projection and
    # its status decides whether a planning obligation still exists. Neither may
    # move backwards out of a terminal disposition.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.b24_enforce_dirty_event_lifecycle()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.observed_at IS DISTINCT FROM OLD.observed_at THEN
                RAISE EXCEPTION 'b24_dirty_event_observed_at_immutable';
            END IF;
            IF OLD.status IN (
                    'coalesced', 'claimed', 'suppressed', 'fallback_only',
                    'superseded', 'dispatched', 'authority_retry_superseded',
                    'authority_timeout', 'authority_build_failed', 'pruned'
               )
               AND NEW.status IS DISTINCT FROM OLD.status THEN
                RAISE EXCEPTION 'b24_dirty_event_terminal_status_immutable';
            END IF;
            RETURN NEW;
        END
        $$;
        DROP TRIGGER IF EXISTS trg_b24_enforce_dirty_event_lifecycle
            ON public.b24_dirty_events;
        CREATE TRIGGER trg_b24_enforce_dirty_event_lifecycle
        BEFORE UPDATE ON public.b24_dirty_events
        FOR EACH ROW EXECUTE FUNCTION public.b24_enforce_dirty_event_lifecycle();
        """
    )

    # ------------------------------------------------------------------
    # 5. Worker authority is not reachable from any runtime principal.
    # ------------------------------------------------------------------
    # C6 rejected MEMBER inheritance from app_user/app_ro/app_rw into
    # app_worker. MEMBER already covers SET ROLE, but the check is restated
    # against USAGE as well so implicit privilege inheritance and explicit role
    # assumption are both named invariants rather than one incidentally
    # covering the other. migration_owner is deliberately absent: PostgreSQL
    # requires membership in a role to transfer object ownership to it, and the
    # planner SECURITY DEFINER functions must be owned by app_worker. That
    # membership is a governed exception bounded by credential custody -- the
    # migration DSN is never issued to an API or worker process, which the C7
    # topology gate asserts against every in-scope executable topology.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regrole('app_worker') IS NOT NULL THEN
                IF pg_has_role('app_user', 'app_worker', 'USAGE')
                   OR pg_has_role('app_ro', 'app_worker', 'USAGE')
                   OR pg_has_role('app_rw', 'app_worker', 'USAGE')
                   OR pg_has_role('app_user', 'app_worker', 'MEMBER')
                   OR pg_has_role('app_ro', 'app_worker', 'MEMBER')
                   OR pg_has_role('app_rw', 'app_worker', 'MEMBER') THEN
                    RAISE EXCEPTION 'b25_p13_c7_runtime_must_not_reach_worker';
                END IF;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(SOURCE_INVALIDATION_DROP_DDL)
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_b24_enforce_dirty_event_lifecycle
            ON public.b24_dirty_events;
        DROP FUNCTION IF EXISTS public.b24_enforce_dirty_event_lifecycle();
        DROP TRIGGER IF EXISTS trg_b24_enforce_artifact_lifecycle
            ON public.bayesian_artifacts;
        DROP FUNCTION IF EXISTS public.b24_enforce_artifact_lifecycle();
        DROP FUNCTION IF EXISTS public.b24_complete_fit_planner_wakeup(
            uuid, text, bigint, boolean, integer, integer
        );
        DROP FUNCTION IF EXISTS public.b24_fit_planner_residual_obligation(
            uuid, integer, integer
        );
        ALTER TABLE public.b24_fit_planner_wakeups
            DROP COLUMN IF EXISTS next_eligible_at;
        """
    )
