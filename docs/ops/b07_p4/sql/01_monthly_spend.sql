-- B0.7-P4 Dashboard: per-user monthly spend from Postgres ledger truth.
SELECT
  tenant_id::text AS tenant_id,
  user_id::text AS user_id,
  month,
  total_cost_cents,
  total_calls
FROM llm_monthly_costs
WHERE tenant_id = :'tenant_id'
ORDER BY month DESC, user_id;
