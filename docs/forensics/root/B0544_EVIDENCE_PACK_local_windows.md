# B0544_EVIDENCE_PACK_local_windows.md

## CI Binding
- candidate_sha: 4c3f1d5e31e1c6e025216f6ff7fa0bbd3a0e6eb0
- ci_run_url: https://github.com/Muk223/skeldir-2.0/actions/runs/20700005995
- ci_job_url: https://github.com/Muk223/skeldir-2.0/actions/runs/20700005995/job/59420921942
- r7_run_url: https://github.com/Muk223/skeldir-2.0/actions/runs/20700007606

## EG-1 Truth Anchor

Command:
```
git rev-parse HEAD
```
Output:
```
4c3f1d5e31e1c6e025216f6ff7fa0bbd3a0e6eb0
```

Command:
```
git status --porcelain
```
Output:
```
?? B0544_main_beat.err
?? B0544_main_beat.out
?? B0544_main_beat2.err
?? B0544_main_beat2.out
?? B0544_main_worker.err
?? B0544_main_worker.out
?? B0544_main_worker2.err
?? B0544_main_worker2.out
?? B0544_worker_runtime_main.err
?? B0544_worker_runtime_main.out
?? celerybeat-schedule.bak
?? celerybeat-schedule.dat
?? celerybeat-schedule.dir
```

## EG-2 Registration Determinism (worker startup log)

Worker startup log excerpt (B0544_main_worker2.err):
```
{"level": "INFO", "logger": "app.celery_app", "message": "celery_worker_registered_tasks"}
```

## EG-3 Runtime Stability (no event-loop mismatch)

Command:
```
Select-String -Path B0544_main_worker2.err -Pattern "Future attached to a different loop|Event loop is closed"
```
Output:
```
(no matches)
```

## EG-4 Beat Dispatch + Worker Consumption (2-tick proof)

Beat log excerpt (B0544_main_beat2.err):
```
[2026-01-04 17:18:06,360: INFO/MainProcess] beat: Starting...
[2026-01-04 17:18:06,474: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
[2026-01-04 17:18:08,457: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
[2026-01-04 17:18:10,458: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
```

Worker log excerpt (B0544_main_worker2.err):
```
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[319eaf04-2039-4edc-a5d2-c011f9fd0024] received"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_pulse_task_start", "task_id": "319eaf04-2039-4edc-a5d2-c011f9fd0024", "correlation_id_request": "ea31c240-b2ab-416f-9718-e0b6909568da"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_pulse_task_dispatched", "task_id": "319eaf04-2039-4edc-a5d2-c011f9fd0024", "correlation_id_request": "ea31c240-b2ab-416f-9718-e0b6909568da"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.pulse_matviews_global[319eaf04-2039-4edc-a5d2-c011f9fd0024] succeeded in 0.21799999999348074s: {'status': 'ok', 'tenant_count': 1, 'correlation_id': 'ea31c240-b2ab-416f-9718-e0b6909568da'}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.refresh_all_for_tenant[f720df73-783d-45c6-8c88-0a3db32003b9] received"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_refresh_task_completed", "task_id": "f720df73-783d-45c6-8c88-0a3db32003b9", "correlation_id_request": "ea31c240-b2ab-416f-9718-e0b6909568da", "tenant_id": "75060f4b-d0e2-42e7-b6de-3c3adb8fd971"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.refresh_all_for_tenant[f720df73-783d-45c6-8c88-0a3db32003b9] succeeded in 0.28200000000651926s: {'status': 'ok', 'results': [{'view_name': 'mv_allocation_summary', 'tenant_id': '75060f4b-d0e2-42e7-b6de-3c3adb8fd971', 'correlation_id': 'ea31c240-b2ab-416f-9718-e0b6909568da', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T23:18:07.030829+00:00', 'duration_ms': 45, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_channel_performance', 'tenant_id': '75060f4b-d0e2-42e7-b6de-3c3adb8fd971', 'correlation_id': 'ea31c240-b2ab-416f-9718-e0b6909568da', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T23:18:07.076827+00:00', 'duration_ms': 42, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_daily_revenue_summary', 'tenant_id': '75060f4b-d0e2-42e7-b6de-3c3adb8fd971', 'correlation_id': 'ea31c240-b2ab-416f-9718-e0b6909568da', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T23:18:07.118827+00:00', 'duration_ms': 40, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_realtime_revenue', 'tenant_id': '75060f4b-d0...', ...}]}
```

Command used to capture EG-4:
```
$env:PYTHONPATH="backend"; $env:TEST_ASYNC_DSN="postgresql+asyncpg://postgres@localhost:5432/skeldir_validation";
$env:DATABASE_URL="postgresql+asyncpg://postgres@localhost:5432/skeldir_validation";
$env:CELERY_RESULT_BACKEND="db+postgresql://postgres@localhost:5432/skeldir_validation";
$env:CELERY_BROKER_URL="sqla+postgresql://postgres@localhost:5432/skeldir_validation";
$env:CELERY_METRICS_ADDR="127.0.0.1"; $env:CELERY_METRICS_PORT="9557";
$env:ZG_BEAT_TEST_INTERVAL_SECONDS="2";
celery -A app.celery_app.celery_app worker -l info -Q maintenance -P solo -c 1 --without-gossip --without-mingle --without-heartbeat
celery -A app.celery_app.celery_app beat -l info
```

## EG-5 Governance Schedule Preservation

Command:
```
celery -A app.celery_app.celery_app report
```
Output:
```
beat_schedule: 
    'enforce-data-retention': {   'options': {'expires': 3600},
                                  'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>,
                                  'task': 'app.tasks.maintenance.enforce_data_retention'},
    'pii-audit-scanner': {   'options': {'expires': 3600},
                             'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>,
                             'task': 'app.tasks.maintenance.scan_for_pii_contamination'},
    'refresh-matviews-every-5-min': {   'kwargs': {'schedule_class': 'minute'},
                                        'options': {'expires': 600},
                                        'schedule': 300.0,
                                        'task': 'app.tasks.matviews.pulse_matviews_global'}}
```
