R6_SHA=c7abcf220dc96f0029baa701341b1e6def10cbb5
R6_TIMESTAMP_UTC=2025-12-30T16:31:21.381749+00:00
# R6 Governance Gap Report

- R6_SHA: c7abcf220dc96f0029baa701341b1e6def10cbb5
- R6_TIMESTAMP_UTC: 2025-12-30T16:31:21.381749+00:00

## Required Control Set

- task_time_limit: None (evidence: R6_CELERY_INSPECT_CONF.json)
- task_soft_time_limit: None (evidence: R6_CELERY_INSPECT_CONF.json)
- task_acks_late: True (evidence: R6_CELERY_INSPECT_CONF.json)
- task_reject_on_worker_lost: True (evidence: R6_CELERY_INSPECT_CONF.json)
- task_acks_on_failure_or_timeout: True (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_prefetch_multiplier: 1 (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_max_tasks_per_child: None (evidence: R6_CELERY_INSPECT_CONF.json)
- worker_max_memory_per_child: None (evidence: R6_CELERY_INSPECT_CONF.json)

## Gaps

- tasks_missing_retry_caps: 1
- tasks_missing_timeouts: 9
- active_queues_observed: housekeeping, maintenance, llm, attribution
- retry_cap_missing_tasks: celery.chord_unlock
- timeout_missing_tasks: celery.chain, celery.starmap, celery.accumulate, celery.chord, celery.chunks, celery.chord_unlock, celery.group, celery.map, celery.backend_cleanup
