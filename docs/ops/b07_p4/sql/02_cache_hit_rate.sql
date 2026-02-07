-- B0.7-P4 Dashboard: cache hit rate by endpoint.
SELECT
  endpoint,
  COUNT(*) AS total_calls,
  SUM(CASE WHEN was_cached THEN 1 ELSE 0 END) AS cache_hits,
  ROUND(100.0 * SUM(CASE WHEN was_cached THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS cache_hit_rate_pct
FROM llm_api_calls
WHERE tenant_id = :'tenant_id'
  AND user_id = :'user_id'
GROUP BY endpoint
ORDER BY endpoint;
