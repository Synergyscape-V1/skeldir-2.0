# B0544_REMEDIATION_EVIDENCE_PACK_local_windows_v2.md

## EG-1 Truth Anchor

Command:
```
git rev-parse HEAD
```
Output:
```
00f3c3f54a47bf684ef50b9b04f96f94338567ac
```

Command:
```
git status --porcelain
```
Output:
```
(clean)
```

## EG-2 Registration Determinism (report + inspect registered + worker startup log)

Command:
```
celery -A app.celery_app.celery_app report
```
Output:
```

software -> celery:5.6.0 (recovery) kombu:5.6.1 py:3.11.9
            billiard:4.2.4 sqlalchemy:2.0.44
platform -> system:Windows arch:64bit, WindowsPE
            kernel version:10 imp:CPython
loader   -> celery.loaders.app.AppLoader
settings -> transport:sqla results:db+postgresql://postgres:**@localhost:5432/skeldir

deprecated_settings: None
broker_url: 'sqla+postgresql://postgres:**@localhost:5432/skeldir'
result_backend: 'db+postgresql://postgres:********@localhost:5432/skeldir'
task_serializer: 'json'
result_serializer: 'json'
accept_content: ['json']
enable_utc: True
timezone: 'UTC'
task_track_started: True
broker_transport_options: 
 'max_overflow': 0, 'pool_recycle': 300, 'pool_size': 5}
database_engine_options: 
 'pool_recycle': 300, 'pool_size': 5}
worker_send_task_events: True
worker_hijack_root_logger: False
task_acks_late: True
task_reject_on_worker_lost: True
task_acks_on_failure_or_timeout: True
worker_prefetch_multiplier: 1
task_soft_time_limit: 300
task_time_limit: 360
worker_max_tasks_per_child: 100
worker_max_memory_per_child: 250000
task_annotations: 
    'celery.chord_unlock': {   'default_retry_delay': 2,
                               'max_retries': 5,
                               'retry_backoff': True,
                               'retry_jitter': True}}
include: ['app.tasks.housekeeping',
 'app.tasks.maintenance',
 'app.tasks.matviews',
 'app.tasks.llm',
 'app.tasks.attribution',
 'app.tasks.r4_failure_semantics',
 'app.tasks.r6_resource_governance']
task_queues: [<unbound Queue housekeeping -> <unbound Exchange ''(direct)> -> housekeeping.#>,
 <unbound Queue maintenance -> <unbound Exchange ''(direct)> -> maintenance.#>,
 <unbound Queue llm -> <unbound Exchange ''(direct)> -> llm.#>,
 <unbound Queue attribution -> <unbound Exchange ''(direct)> -> attribution.#>]
task_routes: 
    'app.tasks.attribution.*': {   'queue': 'attribution',
                                   'routing_key': '********'},
    'app.tasks.housekeeping.*': {   'queue': 'housekeeping',
                                    'routing_key': '********'},
    'app.tasks.llm.*': {'queue': 'llm', 'routing_key': '********'},
    'app.tasks.maintenance.*': {   'queue': 'maintenance',
                                   'routing_key': '********'},
    'app.tasks.matviews.*': {'queue': 'maintenance', 'routing_key': '********'},
    'app.tasks.r4_failure_semantics.*': {   'queue': 'housekeeping',
                                            'routing_key': '********'},
    'app.tasks.r6_resource_governance.*': {   'queue': 'housekeeping',
                                              'routing_key': '********'}}
task_default_queue: 'housekeeping'
task_default_exchange: 'tasks'
task_default_routing_key: '********'
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

Command:
```
celery -A app.celery_app.celery_app inspect registered --timeout=10
```
Output:
```
Error: No nodes replied within time constraint
```

Worker startup log excerpt:
```
{"level": "INFO", "logger": "app.celery_app", "message": "celery_worker_registered_tasks"}
```

## EG-3 Runtime Stability (no event-loop mismatch)

Command:
```
Select-String -Path B0544_worker10.err -Pattern "Future attached to a different loop|Event loop is closed"
```
Output:
```
(no matches)
```

## EG-4 Beat Dispatch + Worker Consumption (2-tick proof)

Beat log excerpt:
```
[2026-01-04 14:35:55,199: INFO/MainProcess] beat: Starting...
[2026-01-04 14:35:57,231: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
[2026-01-04 14:35:59,214: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
[2026-01-04 14:36:01,215: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
[2026-01-04 14:36:03,215: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.matviews.pulse_matviews_global)
```

Worker log excerpt:
```
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[f70ed66a-9bba-4416-a921-3b58f8391394] received"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.pulse_matviews_global[f70ed66a-9bba-4416-a921-3b58f8391394] succeeded in 0.21899999998277053s: {'status': 'ok', 'tenant_count': 1, 'correlation_id': 'ec75f105-8985-4491-b38b-2dd97d9e7c9a'}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.refresh_all_for_tenant[09be0061-70e3-49c5-8474-4e76520c4c5e] received"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_refresh_task_completed", "task_id": "09be0061-70e3-49c5-8474-4e76520c4c5e", "correlation_id_request": "ec75f105-8985-4491-b38b-2dd97d9e7c9a", "tenant_id": "2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.refresh_all_for_tenant[09be0061-70e3-49c5-8474-4e76520c4c5e] succeeded in 0.375s: {'status': 'ok', 'results': [{'view_name': 'mv_allocation_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'ec75f105-8985-4491-b38b-2dd97d9e7c9a', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:57.933453+00:00', 'duration_ms': 46, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_channel_performance', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'ec75f105-8985-4491-b38b-2dd97d9e7c9a', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:57.979967+00:00', 'duration_ms': 140, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_daily_revenue_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'ec75f105-8985-4491-b38b-2dd97d9e7c9a', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:58.121045+00:00', 'duration_ms': 42, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_realtime_revenue', 'tenant_id': '2fcd3c5c-0...', ...}]}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[f61090d6-e280-4fd8-a17b-3476d19982f0] received"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.pulse_matviews_global[f61090d6-e280-4fd8-a17b-3476d19982f0] succeeded in 0.10999999998603016s: {'status': 'ok', 'tenant_count': 1, 'correlation_id': '44079a7b-7724-4db5-a4c0-e23639151f55'}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.refresh_all_for_tenant[3a3019ec-0740-4dde-9882-679199cd34a0] received"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_refresh_task_completed", "task_id": "3a3019ec-0740-4dde-9882-679199cd34a0", "correlation_id_request": "44079a7b-7724-4db5-a4c0-e23639151f55", "tenant_id": "2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.refresh_all_for_tenant[3a3019ec-0740-4dde-9882-679199cd34a0] succeeded in 0.28100000001722947s: {'status': 'ok', 'results': [{'view_name': 'mv_allocation_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': '44079a7b-7724-4db5-a4c0-e23639151f55', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:59.438360+00:00', 'duration_ms': 42, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_channel_performance', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': '44079a7b-7724-4db5-a4c0-e23639151f55', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:59.480877+00:00', 'duration_ms': 40, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_daily_revenue_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': '44079a7b-7724-4db5-a4c0-e23639151f55', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:35:59.520880+00:00', 'duration_ms': 40, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_realtime_revenue', 'tenant_id': '2fcd3c5c-04...', ...}]}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[c7bb7a43-7f4b-449c-97b1-3e9f9484b20a] received"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.pulse_matviews_global[c7bb7a43-7f4b-449c-97b1-3e9f9484b20a] succeeded in 0.10899999999674037s: {'status': 'ok', 'tenant_count': 1, 'correlation_id': 'faa69d60-c041-4abd-a85f-87040b8b3a1e'}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.refresh_all_for_tenant[069ab26c-c8d0-409e-986d-de9350cbe7f8] received"}
{"level": "INFO", "logger": "app.tasks.matviews", "message": "matview_refresh_task_completed", "task_id": "069ab26c-c8d0-409e-986d-de9350cbe7f8", "correlation_id_request": "faa69d60-c041-4abd-a85f-87040b8b3a1e", "tenant_id": "2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.refresh_all_for_tenant[069ab26c-c8d0-409e-986d-de9350cbe7f8] succeeded in 0.3130000000237487s: {'status': 'ok', 'results': [{'view_name': 'mv_allocation_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'faa69d60-c041-4abd-a85f-87040b8b3a1e', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:36:01.873825+00:00', 'duration_ms': 51, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_channel_performance', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'faa69d60-c041-4abd-a85f-87040b8b3a1e', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:36:01.924829+00:00', 'duration_ms': 49, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_daily_revenue_summary', 'tenant_id': '2fcd3c5c-04d1-433b-a4ce-e037b1e8d4ca', 'correlation_id': 'faa69d60-c041-4abd-a85f-87040b8b3a1e', 'outcome': 'SUCCESS', 'started_at': '2026-01-04T20:36:01.973950+00:00', 'duration_ms': 46, 'error_type': None, 'error_message': None, 'lock_key_debug': {...}}, {'view_name': 'mv_realtime_revenue', 'tenant_id': '2fcd3c5c-04...', ...}]}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.pulse_matviews_global[f4c9b0a4-5c9e-4f20-b973-eaf296eca40f] received"}
{"level": "INFO", "logger": "celery.app.trace", "message": "Task app.tasks.matviews.pulse_matviews_global[f4c9b0a4-5c9e-4f20-b973-eaf296eca40f] succeeded in 0.21899999998277053s: {'status': 'ok', 'tenant_count': 1, 'correlation_id': '30232e89-5c91-45af-ba73-08f0eda2b3ca'}"}
{"level": "INFO", "logger": "celery.worker.strategy", "message": "Task app.tasks.matviews.refresh_all_for_tenant[3aa52204-9798-4229-98aa-9772b85d957a] received"}
```

## Worker Survival Regression Test (local)

Command:
```
$env:TEST_ASYNC_DSN="postgresql+asyncpg://postgres@localhost:5432/skeldir_validation";
$env:DATABASE_URL="postgresql+asyncpg://postgres@localhost:5432/skeldir_validation";
$env:CELERY_RESULT_BACKEND="db+postgresql://postgres@localhost:5432/skeldir_validation";
$env:CELERY_BROKER_URL="sqla+postgresql://postgres@localhost:5432/skeldir_validation";
pytest backend/tests/test_b0543_matview_task_layer.py -k worker_survives_matview_failure -vv
```

Output:
```
backend/tests/test_b0543_matview_task_layer.py::test_worker_survives_matview_failure
INFO     app.tasks.matviews:matviews.py:124 matview_refresh_task_start
ERROR    app.tasks.matviews:matviews.py:154 matview_refresh_view_failed
ERROR    app.tasks.matviews:matviews.py:178 matview_refresh_task_failed
ERROR    app.celery_app:celery_app.py:371 celery_task_failed
ERROR    celery.app.trace:trace.py:285 Task app.tasks.matviews.refresh_single[...] raised unexpected: MatviewTaskFailure('matview refresh failed: view=mv_allocation_summary outcome=FAILED')
INFO     app.tasks.matviews:matviews.py:124 matview_refresh_task_start
INFO     app.tasks.matviews:matviews.py:156 matview_refresh_view_completed
INFO     app.tasks.matviews:matviews.py:180 matview_refresh_task_completed
INFO     celery.app.trace:trace.py:128 Task app.tasks.matviews.refresh_single[...] succeeded in 0.0s: {'status': 'ok', 'result': {...}, 'strategy': 'SUCCESS'}
PASSED
```

## EG-5 Governance Schedule Preservation

Beat schedule excerpt (from report):
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
