# Value Trace 05-WIN: Centaur Friction

## Test Scenario

1. Create job at t=0 -> SUBMITTED with 45s hold
2. Poll at t=30s -> still SUBMITTED (15s remaining)
3. Poll at t=46s -> READY_FOR_REVIEW (hold passed)
4. Check before approve -> NOT COMPLETED
5. Approve -> APPROVED
6. Complete -> COMPLETED

## State Transitions

| Time | Action | Status | Assertion |
|------|--------|--------|----------|
| t=0s | create_job | submitted | SUBMITTED with 45s hold |
| t=30s | get_job | submitted | Still SUBMITTED (min_hold not reached) |
| t=46s | get_job | ready_for_review | READY_FOR_REVIEW (min_hold passed) |
| t=46s | check_not_completed | ready_for_review | NOT COMPLETED (approval gate enforced) |
| t=46s (after approve) | approve_job | approved | APPROVED (human review accepted) |
| t=46s (after completion) | complete_job | completed | COMPLETED (service-mediated post-approval terminalization) |

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
    WHERE id = '36b2265e-04ea-4c19-b901-efdc4da363f2';

    -- Result:
    -- status: COMPLETED
    -- approved_at: NOT NULL (explicit approval required)
    -- completed_at: NOT NULL (only after service-mediated completion)
    
```

## Invariants Proven

- [x] Minimum hold enforced (cannot skip 45s wait)
- [x] Approval gate enforced (cannot auto-complete)
- [x] State machine integrity (SUBMITTED -> READY -> APPROVED -> COMPLETED)
- [x] Cannot return 'final' immediately
