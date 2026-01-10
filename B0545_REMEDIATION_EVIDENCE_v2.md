# B0545_REMEDIATION_EVIDENCE_v2

## PR + Chain-of-Custody
PR URL: https://github.com/Muk223/skeldir-2.0/pull/13
Head branch: b0545-convergence-v2
Candidate SHA (Commit C): b44ec5f81d8187a844d2d09153056a55064a16ef
Main merge commit SHA: 1e35e08bca6be14eb424ca12c77b423503c654d0
CI head SHA (b0545-convergence run): 1e35e08bca6be14eb424ca12c77b423503c654d0
CI Run URL (b0545-convergence): https://github.com/Muk223/skeldir-2.0/actions/runs/20883741633
CI Run URL (full CI): https://github.com/Muk223/skeldir-2.0/actions/runs/20883783616

All main checks green: YES

## Artifact
Artifact name: b0545-kinetic-evidence-1e35e08bca6be14eb424ca12c77b423503c654d0
Artifact size: 21291 bytes
Artifact inventory:
- beat.log (755 bytes)
- beat.pid (5 bytes)
- beat_due_task.txt (146 bytes)
- beat_pulse_task.txt (146 bytes)
- celery_config.json (294 bytes)
- evidence_manifest.txt (1613 bytes)
- force_failure_call.txt (37 bytes)
- inspect_active_queues.txt (47 bytes)
- inspect_ping.txt (57 bytes)
- inspect_registered.txt (47 bytes)
- inspect_stats.txt (47 bytes)
- kombu_message_after.txt (32 bytes)
- kombu_message_before.txt (32 bytes)
- metadata.txt (280 bytes)
- worker.log (15786 bytes)
- worker.pid (5 bytes)
- worker_failed_jobs_after.txt (32 bytes)
- worker_failed_jobs_before.txt (32 bytes)
- worker_failed_jobs_row.txt (410 bytes)
- worker_pulse_dispatched.txt (214 bytes)
- worker_pulse_received.txt (491 bytes)
- worker_pulse_start.txt (209 bytes)
- worker_received.txt (480 bytes)
- worker_registered_tasks.txt (94 bytes)

## Kinetic Evidence
Beat dispatch excerpt (beat_due_task.txt):
```
2:[2026-01-10 20:12:25,388: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
```

Worker receipt excerpt (worker_pulse_received.txt):
```
57:{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[0c88134f-b33c-4010-9e55-50b4f28e331a] received"}
```

Inspect ping output (inspect_ping.txt):
```
->  b0545@runnervmi13qx: OK
        pong

1 node online.
```

DB probes (DLQ side effect):
worker_failed_jobs_before.txt:
```
 count 
-------
     0
(1 row)
```

worker_failed_jobs_after.txt:
```
 count 
-------
     1
(1 row)
```

worker_failed_jobs_row.txt:
```
             task_name             |            correlation_id            |    error_type    |             error_message             
-----------------------------------+--------------------------------------+------------------+---------------------------------------
 app.tasks.matviews.refresh_single | 8469f29f-23be-4b9f-bf00-4648a9647f8c | validation_error | View 'mv_nonexistent' not in registry
(1 row)
```
