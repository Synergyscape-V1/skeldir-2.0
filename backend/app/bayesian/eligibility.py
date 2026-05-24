"""B2.4-P2 aggregate eligibility preflight.

Eligibility is intentionally aggregate-only. It must run before any row-level
source cursor is opened so sparse tenant behavior is not materialized or hashed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.bayesian.input_contract import (
    ELIGIBILITY_POLICY_VERSION,
    LIFECYCLE_INCLUSION_RULES,
    SPARSE_PRIVACY_THRESHOLDS,
    SparsePrivacyThresholds,
)
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY


class EligibilityDecision(StrEnum):
    ELIGIBLE = "eligible"
    FALLBACK_ONLY = "fallback_only"


class EligibilityStatus(StrEnum):
    ELIGIBLE = "eligible"
    SOURCE_WINDOW_EMPTY = "source_window_empty"
    INSUFFICIENT_DATA = "insufficient_data"
    INSUFFICIENT_PRIVACY_COHORT = "insufficient_privacy_cohort"


class DataCompletenessStatus(StrEnum):
    COMPLETE = "complete"
    INSUFFICIENT = "insufficient"


class FallbackReason(StrEnum):
    SOURCE_WINDOW_EMPTY = "source_window_empty"
    INSUFFICIENT_DATA = "insufficient_data"
    INSUFFICIENT_PRIVACY_COHORT = "insufficient_privacy_cohort"


@dataclass(frozen=True)
class CurrencyGroupPreflight:
    currency_code: str
    observation_count: int
    amount_minor: int


@dataclass(frozen=True)
class EligibilityPreflightResult:
    tenant_id: UUID
    model_type: str
    model_version: str
    source_window_start: datetime
    source_window_end: datetime
    decision: EligibilityDecision
    eligibility_status: EligibilityStatus
    data_completeness_status: DataCompletenessStatus
    fallback_reason: FallbackReason | None
    included_row_counts_by_source: dict[str, int]
    excluded_row_counts_by_reason: dict[str, int]
    currency_groups: tuple[CurrencyGroupPreflight, ...]
    eligible_channel_count: int
    provider_count: int
    campaign_or_feature_count: int
    eligible_conversion_or_revenue_event_count: int
    eligible_amount_minor_by_currency: dict[str, int]
    confirmed_match_verdict_count: int
    source_window_empty: bool
    insufficient_privacy_cohort: bool
    min_event_at: datetime | None
    max_event_at: datetime | None
    source_window_density_days: int
    last_eligibility_check_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    eligibility_policy_version: str = ELIGIBILITY_POLICY_VERSION

    @property
    def is_eligible(self) -> bool:
        return self.decision == EligibilityDecision.ELIGIBLE


_PROCESSED_EVENT_STATUSES = LIFECYCLE_INCLUSION_RULES[
    "attribution_events.processing_status"
]
_CONVERSION_EVENT_TYPES = LIFECYCLE_INCLUSION_RULES["attribution_events.event_type"]
_MATCH_VERDICT_STATUSES = LIFECYCLE_INCLUSION_RULES["b23_match_verdicts.status"]
_REVENUE_EVENT_TYPES = LIFECYCLE_INCLUSION_RULES["b23_revenue_events.event_type"]
_CHANNEL_CAP_PLUS_ONE = B24_RESOURCE_POLICY.max_channels + 1
_PROVIDER_CAP_PLUS_ONE = B24_RESOURCE_POLICY.max_providers + 1
_CAMPAIGN_FEATURE_CAP_PLUS_ONE = B24_RESOURCE_POLICY.max_campaigns_or_feature_keys + 1


_PREFLIGHT_SQL = (
    text(
        """
        WITH RECURSIVE eligible_attribution_events AS (
            SELECT id, channel, nullif(campaign_id, '') AS campaign_id,
                   upper(coalesce(currency, 'USD')) AS currency_code,
                   revenue_cents, occurred_at
            FROM public.attribution_events
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :window_start
              AND occurred_at < :window_end
              AND processing_status IN :processed_event_statuses
              AND event_type IN :conversion_event_types
        ),
        excluded_attribution_events AS (
            SELECT processing_status, count(*)::bigint AS count
            FROM public.attribution_events
            WHERE tenant_id = :tenant_id
              AND occurred_at >= :window_start
              AND occurred_at < :window_end
              AND (
                    processing_status NOT IN :processed_event_statuses
                    OR event_type NOT IN :conversion_event_types
              )
            GROUP BY processing_status
        ),
        eligible_allocations AS (
            SELECT id, channel_code, allocated_revenue_cents, created_at
            FROM public.attribution_allocations
            WHERE tenant_id = :tenant_id
              AND created_at >= :window_start
              AND created_at < :window_end
              AND verified = true
        ),
        eligible_match_verdicts AS (
            SELECT id, nullif(provider, '') AS provider, upper(currency_code) AS currency_code,
                   canonical_net_verified_amount_minor, last_transition_at
            FROM public.b23_match_verdicts
            WHERE tenant_id = :tenant_id
              AND last_transition_at >= :window_start
              AND last_transition_at < :window_end
              AND status IN :match_verdict_statuses
        ),
        excluded_match_verdicts AS (
            SELECT status, count(*)::bigint AS count
            FROM public.b23_match_verdicts
            WHERE tenant_id = :tenant_id
              AND last_transition_at >= :window_start
              AND last_transition_at < :window_end
              AND status NOT IN :match_verdict_statuses
            GROUP BY status
        ),
        eligible_revenue_events AS (
            SELECT id, nullif(provider, '') AS provider, upper(currency_code) AS currency_code,
                   coalesce(captured_amount_minor, 0)
                   + coalesce(refund_amount_minor, 0)
                   + coalesce(chargeback_amount_minor, 0)
                   + coalesce(reversal_amount_minor, 0) AS amount_minor,
                   event_occurred_at
            FROM public.b23_revenue_events
            WHERE tenant_id = :tenant_id
              AND event_occurred_at >= :window_start
              AND event_occurred_at < :window_end
              AND event_type IN :revenue_event_types
        ),
        excluded_revenue_events AS (
            SELECT event_type, count(*)::bigint AS count
            FROM public.b23_revenue_events
            WHERE tenant_id = :tenant_id
              AND event_occurred_at >= :window_start
              AND event_occurred_at < :window_end
              AND event_type NOT IN :revenue_event_types
            GROUP BY event_type
        ),
        currency_groups AS (
            SELECT currency_code, count(*)::bigint AS observation_count,
                   coalesce(sum(amount_minor), 0)::bigint AS amount_minor
            FROM eligible_revenue_events
            GROUP BY currency_code
        ),
        channel_keys(channel_key, ordinal) AS (
            (
                SELECT channel AS channel_key, 1 AS ordinal
                FROM public.attribution_events
                WHERE tenant_id = :tenant_id
                  AND occurred_at >= :window_start
                  AND occurred_at < :window_end
                  AND processing_status IN :processed_event_statuses
                  AND event_type IN :conversion_event_types
                  AND channel IS NOT NULL
                  AND channel <> ''
                ORDER BY channel, occurred_at, id
                LIMIT 1
            )
            UNION ALL
            SELECT next_key.channel_key, channel_keys.ordinal + 1
            FROM channel_keys
            CROSS JOIN LATERAL (
                SELECT candidate.channel AS channel_key
                FROM public.attribution_events AS candidate
                WHERE candidate.tenant_id = :tenant_id
                  AND candidate.occurred_at >= :window_start
                  AND candidate.occurred_at < :window_end
                  AND candidate.processing_status IN :processed_event_statuses
                  AND candidate.event_type IN :conversion_event_types
                  AND candidate.channel IS NOT NULL
                  AND candidate.channel <> ''
                  AND candidate.channel > channel_keys.channel_key
                ORDER BY candidate.channel, candidate.occurred_at, candidate.id
                LIMIT 1
            ) AS next_key
            WHERE channel_keys.ordinal < :channel_cap_plus_one
        ),
        campaign_feature_keys(feature_key, ordinal) AS (
            (
                SELECT campaign_id AS feature_key, 1 AS ordinal
                FROM public.attribution_events
                WHERE tenant_id = :tenant_id
                  AND occurred_at >= :window_start
                  AND occurred_at < :window_end
                  AND processing_status IN :processed_event_statuses
                  AND event_type IN :conversion_event_types
                  AND campaign_id IS NOT NULL
                  AND campaign_id <> ''
                ORDER BY campaign_id, occurred_at, id
                LIMIT 1
            )
            UNION ALL
            SELECT next_key.feature_key, campaign_feature_keys.ordinal + 1
            FROM campaign_feature_keys
            CROSS JOIN LATERAL (
                SELECT candidate.campaign_id AS feature_key
                FROM public.attribution_events AS candidate
                WHERE candidate.tenant_id = :tenant_id
                  AND candidate.occurred_at >= :window_start
                  AND candidate.occurred_at < :window_end
                  AND candidate.processing_status IN :processed_event_statuses
                  AND candidate.event_type IN :conversion_event_types
                  AND candidate.campaign_id IS NOT NULL
                  AND candidate.campaign_id <> ''
                  AND candidate.campaign_id > campaign_feature_keys.feature_key
                ORDER BY candidate.campaign_id, candidate.occurred_at, candidate.id
                LIMIT 1
            ) AS next_key
            WHERE campaign_feature_keys.ordinal < :campaign_feature_cap_plus_one
        ),
        provider_keys(provider_key, ordinal) AS (
            (
                SELECT chosen_provider.provider_key, 1 AS ordinal
                FROM (
                    SELECT
                        (
                            SELECT provider
                            FROM public.b23_match_verdicts
                            WHERE tenant_id = :tenant_id
                              AND last_transition_at >= :window_start
                              AND last_transition_at < :window_end
                              AND status IN :match_verdict_statuses
                              AND provider IS NOT NULL
                              AND provider <> ''
                            ORDER BY provider, last_transition_at, id
                            LIMIT 1
                        ) AS match_provider_key,
                        (
                            SELECT provider
                            FROM public.b23_revenue_events
                            WHERE tenant_id = :tenant_id
                              AND event_occurred_at >= :window_start
                              AND event_occurred_at < :window_end
                              AND event_type IN :revenue_event_types
                              AND provider IS NOT NULL
                              AND provider <> ''
                            ORDER BY provider, event_occurred_at, id
                            LIMIT 1
                        ) AS revenue_provider_key
                ) AS first_provider_candidates
                CROSS JOIN LATERAL (
                    SELECT
                        CASE
                            WHEN first_provider_candidates.match_provider_key IS NULL
                                THEN first_provider_candidates.revenue_provider_key
                            WHEN first_provider_candidates.revenue_provider_key IS NULL
                                THEN first_provider_candidates.match_provider_key
                            WHEN first_provider_candidates.match_provider_key
                                <= first_provider_candidates.revenue_provider_key
                                THEN first_provider_candidates.match_provider_key
                            ELSE first_provider_candidates.revenue_provider_key
                        END AS provider_key
                ) AS chosen_provider
                WHERE chosen_provider.provider_key IS NOT NULL
            )
            UNION ALL
            SELECT next_provider.provider_key, provider_keys.ordinal + 1
            FROM provider_keys
            CROSS JOIN LATERAL (
                SELECT chosen_provider.provider_key
                FROM (
                    SELECT
                        (
                            SELECT candidate.provider
                            FROM public.b23_match_verdicts AS candidate
                            WHERE candidate.tenant_id = :tenant_id
                              AND candidate.last_transition_at >= :window_start
                              AND candidate.last_transition_at < :window_end
                              AND candidate.status IN :match_verdict_statuses
                              AND candidate.provider IS NOT NULL
                              AND candidate.provider <> ''
                              AND candidate.provider > provider_keys.provider_key
                            ORDER BY candidate.provider, candidate.last_transition_at, candidate.id
                            LIMIT 1
                        ) AS match_provider_key,
                        (
                            SELECT candidate.provider
                            FROM public.b23_revenue_events AS candidate
                            WHERE candidate.tenant_id = :tenant_id
                              AND candidate.event_occurred_at >= :window_start
                              AND candidate.event_occurred_at < :window_end
                              AND candidate.event_type IN :revenue_event_types
                              AND candidate.provider IS NOT NULL
                              AND candidate.provider <> ''
                              AND candidate.provider > provider_keys.provider_key
                            ORDER BY candidate.provider, candidate.event_occurred_at, candidate.id
                            LIMIT 1
                        ) AS revenue_provider_key
                ) AS next_provider_candidates
                CROSS JOIN LATERAL (
                    SELECT
                        CASE
                            WHEN next_provider_candidates.match_provider_key IS NULL
                                THEN next_provider_candidates.revenue_provider_key
                            WHEN next_provider_candidates.revenue_provider_key IS NULL
                                THEN next_provider_candidates.match_provider_key
                            WHEN next_provider_candidates.match_provider_key
                                <= next_provider_candidates.revenue_provider_key
                                THEN next_provider_candidates.match_provider_key
                            ELSE next_provider_candidates.revenue_provider_key
                        END AS provider_key
                ) AS chosen_provider
                WHERE chosen_provider.provider_key IS NOT NULL
            ) AS next_provider
            WHERE provider_keys.ordinal < :provider_cap_plus_one
        ),
        all_event_times AS (
            SELECT occurred_at AS event_at FROM eligible_attribution_events
            UNION ALL
            SELECT created_at AS event_at FROM eligible_allocations
            UNION ALL
            SELECT last_transition_at AS event_at FROM eligible_match_verdicts
            UNION ALL
            SELECT event_occurred_at AS event_at FROM eligible_revenue_events
        )
        SELECT
            (SELECT count(*)::bigint FROM eligible_attribution_events) AS attribution_event_count,
            (SELECT count(*)::bigint FROM eligible_allocations) AS allocation_count,
            (SELECT count(*)::bigint FROM eligible_match_verdicts) AS match_verdict_count,
            (SELECT count(*)::bigint FROM eligible_revenue_events) AS revenue_event_count,
            (SELECT count(*)::bigint FROM channel_keys) AS eligible_channel_count,
            (SELECT count(*)::bigint FROM provider_keys) AS provider_count,
            (SELECT count(*)::bigint FROM campaign_feature_keys) AS campaign_or_feature_count,
            (SELECT count(*)::bigint FROM eligible_attribution_events) AS distinct_source_event_count,
            (SELECT coalesce(sum(revenue_cents), 0)::bigint FROM eligible_attribution_events) AS attribution_amount_minor,
            (SELECT coalesce(sum(canonical_net_verified_amount_minor), 0)::bigint FROM eligible_match_verdicts) AS match_amount_minor,
            (SELECT min(event_at) FROM all_event_times) AS min_event_at,
            (SELECT max(event_at) FROM all_event_times) AS max_event_at,
            (SELECT coalesce(jsonb_object_agg(currency_code, amount_minor), '{}'::jsonb) FROM currency_groups)
                AS eligible_amount_minor_by_currency,
            (SELECT coalesce(jsonb_agg(jsonb_build_object(
                'currency_code', currency_code,
                'observation_count', observation_count,
                'amount_minor', amount_minor
            ) ORDER BY currency_code), '[]'::jsonb) FROM currency_groups) AS currency_groups,
            (SELECT coalesce(jsonb_object_agg('attribution_events:' || processing_status, count), '{}'::jsonb)
                FROM excluded_attribution_events) AS excluded_attribution_counts,
            (SELECT coalesce(jsonb_object_agg('b23_match_verdicts:' || status, count), '{}'::jsonb)
                FROM excluded_match_verdicts) AS excluded_match_counts,
            (SELECT coalesce(jsonb_object_agg('b23_revenue_events:' || event_type, count), '{}'::jsonb)
                FROM excluded_revenue_events) AS excluded_revenue_counts
        """
    )
    .bindparams(bindparam("processed_event_statuses", expanding=True))
    .bindparams(bindparam("conversion_event_types", expanding=True))
    .bindparams(bindparam("match_verdict_statuses", expanding=True))
    .bindparams(bindparam("revenue_event_types", expanding=True))
)


def _as_int(value: object) -> int:
    return int(value or 0)


def _source_window_density_days(
    min_event_at: datetime | None, max_event_at: datetime | None
) -> int:
    if min_event_at is None or max_event_at is None:
        return 0
    return max(1, (max_event_at.date() - min_event_at.date()).days + 1)


def _currency_groups(raw_groups: object) -> tuple[CurrencyGroupPreflight, ...]:
    groups = raw_groups or []
    return tuple(
        CurrencyGroupPreflight(
            currency_code=str(row["currency_code"]).upper(),
            observation_count=_as_int(row["observation_count"]),
            amount_minor=_as_int(row["amount_minor"]),
        )
        for row in groups
    )


def _excluded_counts(*raw_maps: object) -> dict[str, int]:
    merged: dict[str, int] = {}
    for raw in raw_maps:
        for key, value in dict(raw or {}).items():
            merged[str(key)] = _as_int(value)
    return merged


def classify_preflight(
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
    row: dict,
    thresholds: SparsePrivacyThresholds = SPARSE_PRIVACY_THRESHOLDS,
) -> EligibilityPreflightResult:
    """Classify aggregate counts without inspecting row-level source payloads."""

    attribution_event_count = _as_int(row["attribution_event_count"])
    allocation_count = _as_int(row["allocation_count"])
    match_verdict_count = _as_int(row["match_verdict_count"])
    revenue_event_count = _as_int(row["revenue_event_count"])
    source_row_count = (
        attribution_event_count
        + allocation_count
        + match_verdict_count
        + revenue_event_count
    )
    eligible_channel_count = _as_int(row["eligible_channel_count"])
    provider_count = _as_int(row["provider_count"])
    campaign_or_feature_count = _as_int(row["campaign_or_feature_count"])
    distinct_source_event_count = _as_int(row["distinct_source_event_count"])
    conversion_or_revenue_count = attribution_event_count + revenue_event_count
    min_event_at = row["min_event_at"]
    max_event_at = row["max_event_at"]
    density_days = _source_window_density_days(min_event_at, max_event_at)
    groups = _currency_groups(row["currency_groups"])
    amount_by_currency = {
        str(key).upper(): _as_int(value)
        for key, value in dict(row["eligible_amount_minor_by_currency"] or {}).items()
    }
    included_counts = {
        "attribution_events": attribution_event_count,
        "attribution_allocations": allocation_count,
        "b23_match_verdicts": match_verdict_count,
        "b23_revenue_events": revenue_event_count,
    }
    excluded_counts = _excluded_counts(
        row["excluded_attribution_counts"],
        row["excluded_match_counts"],
        row["excluded_revenue_counts"],
    )

    reason: FallbackReason | None = None
    status = EligibilityStatus.ELIGIBLE
    insufficient_privacy = False
    if source_row_count == 0:
        status = EligibilityStatus.SOURCE_WINDOW_EMPTY
        reason = FallbackReason.SOURCE_WINDOW_EMPTY
    elif (
        source_row_count < thresholds.minimum_eligible_source_events
        or distinct_source_event_count < thresholds.minimum_distinct_source_events
        or conversion_or_revenue_count < thresholds.minimum_conversion_or_revenue_events
        or match_verdict_count < thresholds.minimum_confirmed_match_verdicts
    ):
        status = EligibilityStatus.INSUFFICIENT_DATA
        reason = FallbackReason.INSUFFICIENT_DATA
    elif (
        eligible_channel_count < thresholds.minimum_distinct_channels
        or density_days < thresholds.minimum_source_window_density_days
        or any(
            group.observation_count < thresholds.minimum_observations_per_currency
            for group in groups
        )
    ):
        status = EligibilityStatus.INSUFFICIENT_PRIVACY_COHORT
        reason = FallbackReason.INSUFFICIENT_PRIVACY_COHORT
        insufficient_privacy = True

    decision = (
        EligibilityDecision.ELIGIBLE
        if reason is None
        else EligibilityDecision.FALLBACK_ONLY
    )
    return EligibilityPreflightResult(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        decision=decision,
        eligibility_status=status,
        data_completeness_status=(
            DataCompletenessStatus.COMPLETE
            if reason is None
            else DataCompletenessStatus.INSUFFICIENT
        ),
        fallback_reason=reason,
        included_row_counts_by_source=included_counts,
        excluded_row_counts_by_reason=excluded_counts,
        currency_groups=groups,
        eligible_channel_count=eligible_channel_count,
        provider_count=provider_count,
        campaign_or_feature_count=campaign_or_feature_count,
        eligible_conversion_or_revenue_event_count=conversion_or_revenue_count,
        eligible_amount_minor_by_currency=amount_by_currency,
        confirmed_match_verdict_count=match_verdict_count,
        source_window_empty=status == EligibilityStatus.SOURCE_WINDOW_EMPTY,
        insufficient_privacy_cohort=insufficient_privacy,
        min_event_at=min_event_at,
        max_event_at=max_event_at,
        source_window_density_days=density_days,
    )


async def run_eligibility_preflight(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    model_type: str,
    model_version: str,
    source_window_start: datetime,
    source_window_end: datetime,
) -> EligibilityPreflightResult:
    """Run indexed aggregate eligibility preflight before source streaming."""

    result = await session.execute(
        _PREFLIGHT_SQL,
        {
            "tenant_id": str(tenant_id),
            "window_start": source_window_start,
            "window_end": source_window_end,
            "processed_event_statuses": tuple(_PROCESSED_EVENT_STATUSES),
            "conversion_event_types": tuple(_CONVERSION_EVENT_TYPES),
            "match_verdict_statuses": tuple(_MATCH_VERDICT_STATUSES),
            "revenue_event_types": tuple(_REVENUE_EVENT_TYPES),
            "channel_cap_plus_one": _CHANNEL_CAP_PLUS_ONE,
            "provider_cap_plus_one": _PROVIDER_CAP_PLUS_ONE,
            "campaign_feature_cap_plus_one": _CAMPAIGN_FEATURE_CAP_PLUS_ONE,
        },
    )
    row = dict(result.mappings().one())
    return classify_preflight(
        tenant_id=tenant_id,
        model_type=model_type,
        model_version=model_version,
        source_window_start=source_window_start,
        source_window_end=source_window_end,
        row=row,
    )
