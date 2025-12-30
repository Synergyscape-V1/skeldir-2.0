R6_SHA=2b0236c802b0017a50c93903c330e23d49078013
R6_TIMESTAMP_UTC=2025-12-30T17:19:40.948452+00:00
| task_name | task_kind | queue | routing_key | max_retries | retry_backoff | retry_jitter | default_retry_delay | autoretry_for | retry_policy_source | time_limit | soft_time_limit | acks_late | acks_source | reject_on_worker_lost | reject_source | acks_on_failure_or_timeout |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| celery.chord_unlock | system | housekeeping | housekeeping.task | 5 | True | True | 2 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.group | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.map | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.backend_cleanup | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.chain | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.starmap | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.accumulate | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.chord | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |
| celery.chunks | system | housekeeping | housekeeping.task | 3 | MISSING | MISSING | 180 | [] | task | 360 | 300 | True | task | True | task | True |