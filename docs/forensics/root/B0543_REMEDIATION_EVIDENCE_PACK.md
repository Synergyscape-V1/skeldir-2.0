# B0543 Remediation Evidence Pack

## Candidate + CI Binding

- Candidate SHA (C_atomic): acbdb4335c92371c33de183175b9efd10b5e35c9
- CI_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20682769852
- CI_JOB_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20682769852/job/59379192919
- B0543_WORKFLOW_RUN_URL: https://github.com/Muk223/skeldir-2.0/actions/runs/20682771958

## Atomic Candidate Diff (git show --name-only acbdb43)

```
commit acbdb4335c92371c33de183175b9efd10b5e35c9
Author: SKELDIR Development Team <dev@skeldir.com>
Date:   Sat Jan 3 14:47:43 2026 -0600

    B0543: Celery task layer + failure surfacing (DLQ+metrics+corr)

.github/workflows/b0543-matview-task-layer.yml
backend/app/celery_app.py
backend/app/observability/metrics.py
backend/app/tasks/matviews.py
backend/tests/test_b051_celery_foundation.py
backend/tests/test_b052_queue_topology_and_dlq.py
backend/tests/test_b0543_matview_task_layer.py
docs/backend/B0543_TASK_LAYER_SUMMARY.md
```

## Local Repro (Self-Contained)

```
$env:DATABASE_URL="postgresql+asyncpg://app_user:app_user@localhost:5432/skeldir_validation"; $env:TEST_ASYNC_DSN=$env:DATABASE_URL; python -m pytest backend/tests/test_b0543_matview_task_layer.py -q
```

Result:

```
4 passed in 0.40s
```
