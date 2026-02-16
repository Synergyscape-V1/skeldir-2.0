# Value Trace 03-WIN: Budget-Kill Circuit Breaker

## Contract Field Presence

- cost_usd field present: True
- latency_ms field present: True
- timeout_ms field present: True

## Budget Enforcement Test

### Adversarial Scenario

- Requested model: `gpt-4` (premium)
- Input tokens: 5000
- Output tokens: 3000
- Estimated cost: 33¢
- Budget cap: 30¢

### Decision

| Metric | Value |
|--------|-------|
| Action | **FALLBACK** |
| Resolved Model | `claude-3-haiku` |
| Reason | FALLBACK: gpt-4 -> claude-3-haiku (requested 33¢ > cap 30¢; fallback_estimate 1¢) |

## SQL Proof Query

```sql

    SELECT
        request_id,
        requested_model,
        resolved_model,
        estimated_cost_cents,
        cap_cents,
        decision,
        reason
    FROM llm_call_audit
    WHERE tenant_id = 'ba6c1bf3-7e62-4bf9-bdea-2ee343bbe4de' AND user_id = '71a393e7-110d-4066-88fd-6fc5221c1c07'
    ORDER BY created_at DESC
    LIMIT 1;

    -- Result:
    -- requested_model: gpt-4
    -- resolved_model: claude-3-haiku
    -- estimated_cost_cents: 33
    -- cap_cents: 30
    -- decision: FALLBACK
    
```

## Invariants Proven

- [x] Contract fields present (cost_usd, latency_ms, timeout_ms)
- [x] Premium model blocked/fallback when over budget
- [x] Audit trail exists in llm_call_audit
- [x] No premium execution beyond cap
