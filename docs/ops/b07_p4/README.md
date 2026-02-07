# B0.7-P4 Operational Closure Pack

This folder is the executable operational readiness bundle for B0.7-P4.

## Contents
- `sql/01_monthly_spend.sql`: per-user/month spend ledger view.
- `sql/02_cache_hit_rate.sql`: cache hit ratio per endpoint.
- `sql/03_breaker_shutoff_state.sql`: breaker and hourly shutoff visibility.
- `sql/04_provider_cost_latency_distribution.sql`: provider/model cost+latency distribution.
- `runbooks/first_traffic_checklist.md`: preflight and first-traffic validations.
- `runbooks/kill_switch_runbook.md`: emergency provider kill-switch procedure.
- `runbooks/incident_response_runbook.md`: common P4 incidents and triage.

## CI Execution Contract
CI runs:
- `backend/tests/integration/test_b07_p4_operational_readiness_e2e.py`
- `scripts/ci/run_b07_p4_operational_queries.sh`

The runtime test writes `runtime_db_probe.json` and the SQL runner uses it to parameterize tenant/user scoped dashboards.
