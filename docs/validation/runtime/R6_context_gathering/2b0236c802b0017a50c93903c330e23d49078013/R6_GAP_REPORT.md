R6_SHA=2b0236c802b0017a50c93903c330e23d49078013
R6_TIMESTAMP_UTC=2025-12-30T17:19:40.948452+00:00
# R6 Governance Gap Report

- R6_SHA: 2b0236c802b0017a50c93903c330e23d49078013
- R6_TIMESTAMP_UTC: 2025-12-30T17:19:40.948452+00:00

## Required Control Set

- task_time_limit: 360 (evidence: R6_CELERY_INSPECT_CONF.json)
- task_soft_time_limit: 300 (evidence: R6_CELERY_INSPECT_CONF.json)
- task_acks_late: True (evidence: R6_CELERY_INSPECT_CONF.json)
- task_reject_on_worker_lost: True (evidence: R6_CELERY_INSPECT_CONF.json)
- task_acks_on_failure_or_timeout: True (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_prefetch_multiplier: 1 (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_max_tasks_per_child: 1 (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_max_memory_per_child: 200000 (evidence: R6_CELERY_INSPECT_CONF.json)

## Gaps

- tasks_missing_retry_caps: 0
- tasks_missing_timeouts: 0
- active_queues_observed: housekeeping, maintenance, llm, attribution
