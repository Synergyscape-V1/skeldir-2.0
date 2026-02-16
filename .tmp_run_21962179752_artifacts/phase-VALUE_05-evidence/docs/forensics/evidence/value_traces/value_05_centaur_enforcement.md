# Value Trace 05-WIN: Centaur Friction

## Test Scenario

1. Create job at t=0 -> PENDING with 45s hold
2. Poll at t=30s -> still PENDING (15s remaining)
3. Poll at t=46s -> READY_FOR_REVIEW (hold passed)
4. Check before approve -> NOT COMPLETED
5. Approve -> COMPLETED

## State Transitions

| Time | Action | Status | Assertion |
|------|--------|--------|----------|
| t=0s | create_job | PENDING | PENDING with 45s hold |
| t=30s | get_job | PENDING | Still PENDING (min_hold not reached) |
| t=46s | get_job | READY_FOR_REVIEW | READY_FOR_REVIEW (min_hold passed) |
| t=46s | check_not_completed | READY_FOR_REVIEW | NOT COMPLETED (approval gate enforced) |
| t=46s (after approve) | approve_job | COMPLETED | COMPLETED (after explicit approval) |

## SQL Proof Query

```sql

    SELECT
        id,
        status,
        created_at,
        min_hold_until,
        ready_for_review_at,
        approved_at,
        completed_at
    FROM investigation_jobs
    WHERE id = 'a2dadbc1-5576-44da-9420-9b0b751d16f7';

    -- Result:
    -- status: COMPLETED
    -- approved_at: NOT NULL (explicit approval required)
    -- completed_at: NOT NULL (only after approval)
    
```

## Invariants Proven

- [x] Minimum hold enforced (cannot skip 45s wait)
- [x] Approval gate enforced (cannot auto-complete)
- [x] State machine integrity (PENDING -> READY -> COMPLETED)
- [x] Cannot return 'final' immediately
