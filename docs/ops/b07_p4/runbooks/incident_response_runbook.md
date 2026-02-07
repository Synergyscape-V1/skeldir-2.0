# Incident Response Runbook (B0.7-P4)

## Incident: Worker consumes nothing
1. Confirm broker/result DSNs point to Postgres and worker is on `llm` queue.
2. Check worker logs for task registration and `ready` marker.
3. Dispatch canary and verify `llm_api_calls` row appears with non-pending status.

## Incident: Cache appears ineffective
1. Replay identical prompt with `cache_enabled=true` and stable `cache_watermark`.
2. Verify second call has `was_cached=true`, `provider_attempted=false`.
3. Query `llm_semantic_cache` by tenant/user/endpoint/cache_key.

## Incident: Breaker not opening
1. Drive repeated provider failures (`raise_error=true`).
2. Verify `llm_breaker_state.failure_count` increments and state moves to `open`.
3. Verify subsequent request blocks with `block_reason=breaker_open`.

## Incident: RLS suspicion
1. Query with correct `app.current_tenant_id` and `app.current_user_id` GUC.
2. Re-query same request with wrong tenant and wrong user GUC.
3. Expect `0` rows in both wrong-identity checks.
