-- B0.7-P4 Dashboard: breaker and shutoff state visibility.
SELECT
  'breaker' AS state_type,
  tenant_id::text AS tenant_id,
  user_id::text AS user_id,
  breaker_key AS state_key,
  state AS state_value,
  failure_count,
  opened_at,
  updated_at
FROM llm_breaker_state
WHERE tenant_id = :'tenant_id'
UNION ALL
SELECT
  'hourly_shutoff' AS state_type,
  tenant_id::text AS tenant_id,
  user_id::text AS user_id,
  to_char(hour_start, 'YYYY-MM-DD"T"HH24:00:00"Z"') AS state_key,
  CASE WHEN is_shutoff THEN 'true' ELSE 'false' END AS state_value,
  total_calls AS failure_count,
  disabled_until AS opened_at,
  updated_at
FROM llm_hourly_shutoff_state
WHERE tenant_id = :'tenant_id'
ORDER BY state_type, updated_at DESC;
