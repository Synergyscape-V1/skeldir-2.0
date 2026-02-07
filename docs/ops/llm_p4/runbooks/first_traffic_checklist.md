# First Traffic Checklist (B0.7-P4)

1. Confirm migrations are at `head` and `llm_api_calls`, `llm_breaker_state`, `llm_hourly_shutoff_state`, `llm_monthly_costs` exist.
2. Confirm worker is attached to queue `llm` and `task_always_eager` is false.
3. Dispatch one request for each task type: `route`, `explanation`, `investigation`, `budget_optimization`.
4. Verify one `llm_api_calls` row per request id/endpoint and `status != pending`.
5. Verify investigation and budget job materialization tables have one row each.
6. Verify RLS by querying same request_id under wrong tenant/user GUC and getting `0` rows.
7. Run all SQL dashboards in `docs/ops/llm_p4/sql` and store outputs with timestamp.
8. Verify cache hit rate dashboard shows at least one cache hit after replaying identical request with same watermark.
9. Verify breaker/shutoff dashboard shows state transitions after induced failures and shutoff seed.
10. Verify provider distribution dashboard includes success and blocked/failed statuses.
