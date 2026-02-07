-- B0.7-P4 Dashboard: provider cost and latency distribution by provider/model/status.
SELECT
  provider,
  model,
  status,
  COUNT(*) AS call_count,
  SUM(cost_cents) AS total_cost_cents,
  MIN(latency_ms) AS min_latency_ms,
  ROUND(AVG(latency_ms)::numeric, 2) AS avg_latency_ms,
  MAX(latency_ms) AS max_latency_ms
FROM llm_api_calls
WHERE tenant_id = :'tenant_id'
GROUP BY provider, model, status
ORDER BY total_cost_cents DESC, provider, model, status;
