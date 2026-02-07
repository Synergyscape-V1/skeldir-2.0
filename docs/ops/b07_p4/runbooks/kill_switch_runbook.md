# Kill-Switch Runbook (B0.7-P4)

## Trigger Conditions
- Upstream provider instability, runaway cost, or untrusted output event.

## Action
1. Set `LLM_PROVIDER_KILL_SWITCH=true` on worker runtime.
2. Restart worker process/container.
3. Dispatch a canary explanation request.
4. Verify result is `status=blocked` and `blocked_reason=provider_kill_switch`.
5. Verify `llm_api_calls.provider_attempted=false` for that request.
6. Verify audit evidence exists (`llm_api_calls` row persisted, non-pending status).

## Recovery
1. Set `LLM_PROVIDER_KILL_SWITCH=false`.
2. Restart worker.
3. Run one explanation canary (`status=accepted`) and verify provider path behavior.
4. Re-run SQL dashboards and attach outputs to incident timeline.
