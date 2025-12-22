# B0.5.3.6 E2E Evidence (Pending CI Run)

## CI Run + Commit
- CI link: _add GH Actions run URL after execution_
- Commit: _add commit SHA validated by CI_

## Pytest Execution (celery-foundation job)
- Expected command: `pytest tests/test_b0536_attribution_e2e.py -v`
- Summary lines: _paste pytest pass summary from CI logs_

## Allocation Verification Excerpt
- Query:
  ```sql
  SELECT event_id, channel, allocation_ratio, allocated_revenue_cents, model_version
  FROM attribution_allocations
  WHERE tenant_id = '00000000-0000-0000-0000-000000000001'
  ORDER BY event_id, channel;
  ```
- Expected rows:
  - event_a (10k): direct/email/google_search → 3333 cents each (ratio 0.333333)
  - event_b (15k): direct/email/google_search → 5000 cents each (ratio 0.333333)

## DLQ Correlation Assertion
- Failure run uses `correlation_id` supplied by `schedule_recompute_window`.
- Verification query:
  ```sql
  SELECT task_name, exception_class, correlation_id, task_kwargs
  FROM worker_failed_jobs
  WHERE task_name = 'app.tasks.attribution.recompute_window'
  ORDER BY failed_at DESC
  LIMIT 1;
  ```
- Expected: `exception_class = 'ValueError'` and `correlation_id` matches scheduler-provided UUID; `task_kwargs.correlation_id` mirrors the same value.

