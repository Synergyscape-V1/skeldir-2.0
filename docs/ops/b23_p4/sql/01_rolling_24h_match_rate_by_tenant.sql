-- B2.3-P4 canonical SQL telemetry: rolling 24-hour match rate by tenant.
-- Parameters: :tenant_id UUID.
-- Numerator: confirmed/provisional/adjusted verdicts updated in the last 24 hours.
-- Denominator: all terminal or matched verdict decisions updated in the last 24 hours.
WITH recent_decisions AS MATERIALIZED (
    SELECT
        tenant_id,
        status
    FROM public.b23_match_verdicts
    WHERE tenant_id = :tenant_id
      AND last_transition_at >= now() - interval '24 hours'
      AND status IN ('matched_provisional', 'matched_confirmed', 'adjusted', 'unmatched')
    ORDER BY last_transition_at DESC
)
SELECT
    tenant_id,
    count(*) FILTER (
        WHERE status IN ('matched_provisional', 'matched_confirmed', 'adjusted')
    ) AS matched_count,
    count(*) FILTER (
        WHERE status IN ('matched_provisional', 'matched_confirmed', 'adjusted', 'unmatched')
    ) AS decision_count,
    CASE
        WHEN count(*) FILTER (
            WHERE status IN ('matched_provisional', 'matched_confirmed', 'adjusted', 'unmatched')
        ) = 0 THEN 0::numeric
        ELSE round(
            (
                count(*) FILTER (
                    WHERE status IN ('matched_provisional', 'matched_confirmed', 'adjusted')
                )::numeric
                / count(*) FILTER (
                    WHERE status IN ('matched_provisional', 'matched_confirmed', 'adjusted', 'unmatched')
                )::numeric
            ),
            4
        )
    END AS match_rate
FROM recent_decisions
GROUP BY tenant_id;
