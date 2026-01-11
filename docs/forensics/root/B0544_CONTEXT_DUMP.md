# B0544_CONTEXT_DUMP.md

## Repo SHA + Timestamp

- sha: 2c924f7ffcc16075c4e6a3fe1d5614ad2f43c1af
- timestamp_utc: 2026-01-03T22:10:38.5779288Z

## Truth Anchor Map

- celery app definition: backend/app/celery_app.py
- celery config: backend/app/core/config.py
- beat schedule definition: backend/app/tasks/beat_schedule.py
- matview tasks: backend/app/tasks/matviews.py
- maintenance tasks (legacy refresh): backend/app/tasks/maintenance.py

## Hypothesis Results (H1?H4)

### H-B0544-CG-1 ? There is no existing Beat schedule (schedule is absent), only hooks.

Status: FAIL

Reasoning: A beat schedule is defined in backend/app/tasks/beat_schedule.py (build_beat_schedule + BEAT_SCHEDULE) and is loaded in backend/app/celery_app.py via celery_app.conf.beat_schedule = BEAT_SCHEDULE. The grep output shows beat_schedule references in the codebase, including the loader in celery_app.py. This indicates a schedule exists, not just hooks.

### H-B0544-CG-2 ? Beat is not started anywhere (no runtime entrypoint), so scheduling cannot happen today.

Status: PARTIAL PASS

Reasoning: There is no beat entrypoint in Procfile/compose/Makefile; the only explicit beat invocation is in scripts/ci/zero_drift_v3_2.sh (CI harness). The runtime entrypoint evidence is therefore CI-only, not deployment. This supports the hypothesis for normal runtime, but refutes it for CI harness.

### H-B0544-CG-3 ? Single scheduler hook point exists (celery_app/config), no competing scheduler.

Status: PASS

Reasoning: The searches for cron/APScheduler/PeriodicTask/DatabaseScheduler/redbeat show only documentation and evidence artifacts, not active scheduler code. The only scheduler-like mechanism visible in code is Celery Beat via beat_schedule and celery_app.conf.beat_schedule. No competing scheduler entrypoints (cron/apscheduler) are found.

### H-B0544-CG-4 ? R6 governance fuses apply globally and Beat will not bypass them.

Status: PASS

Reasoning: Celery config defines global fuses in backend/app/core/config.py and applies them in backend/app/celery_app.py. The grep output shows task_time_limit, task_soft_time_limit, worker_max_tasks_per_child, worker_prefetch_multiplier, acks_late, and reject_on_worker_lost configured globally. Matview tasks do not override these, so Beat-triggered tasks would inherit the global constraints.

## Raw Command Outputs

### 1) Schedule definitions

Command:

```
rg -n "beat_schedule|CELERYBEAT_SCHEDULE|CELERY_BEAT|PeriodicTask|django-celery-beat|add_periodic_task|crontab\(" -S --glob "!**/.git/**" --glob "!**/node_modules/**" .
```

Output:

```
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\backend\app\tasks\beat_schedule.py:33:def build_beat_schedule() -> Dict[str, Dict[str, Any]]:
.\backend\app\tasks\beat_schedule.py:43:            "schedule": crontab(hour=4, minute=0),
.\backend\app\tasks\beat_schedule.py:48:            "schedule": crontab(hour=3, minute=0),
.\backend\app\tasks\beat_schedule.py:55:BEAT_SCHEDULE = build_beat_schedule()
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:774:        "schedule": crontab(hour=4, minute=0),  # Daily at 4:00 AM UTC
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:1085:        "schedule": crontab(hour=3, minute=0),  # Daily at 3:00 AM UTC
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\backend\app\celery_app.py:195:    from app.tasks.beat_schedule import BEAT_SCHEDULE
.\backend\app\celery_app.py:196:    celery_app.conf.beat_schedule = BEAT_SCHEDULE
.\backend\app\celery_app.py:205:            "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
.\backend\app\celery_app.py:206:            "scheduled_tasks": list(celery_app.conf.beat_schedule.keys()) if celery_app.conf.beat_schedule else [],
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:129:    'beat_schedule_loaded': bool(celery_app.conf.beat_schedule),
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:130:    'task_count': len(celery_app.conf.beat_schedule or {}),
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:133:        for name, entry in (celery_app.conf.beat_schedule or {}).items()
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:138:  "beat_schedule_loaded": true,
.\docs\evidence\b054-forensic-readiness-evidence.md:620:             "schedule": crontab(hour=4, minute=0),
.\docs\evidence\b054-forensic-readiness-evidence.md:625:             "schedule": crontab(hour=3, minute=0),
.\docs\evidence\b054-forensic-readiness-evidence.md:634:   - **No `beat_schedule` key in conf.update()**
.\docs\evidence\b054-forensic-readiness-evidence.md:635:   - **Missing:** `beat_schedule=BEAT_SCHEDULE` assignment
.\docs\evidence\b054-forensic-readiness-evidence.md:953:- **Required Fix:** Load beat_schedule into celery_app.conf AND start Beat process (or use alternative scheduler)
.\docs\evidence\b054-forensic-readiness-evidence.md:978:2. **G11 BLOCKER addressed:** Load beat_schedule and deploy Beat process OR use alternative scheduling
.\docs\evidence\b054-forensic-readiness-evidence.md:993:2. **Fix G11:** Add `celery_app.conf.beat_schedule = BEAT_SCHEDULE` in celery_app.py:154
.\scripts\ci\zero_drift_v3_2.sh:132:    "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
.\scripts\ci\zero_drift_v3_2.sh:133:    "task_count": len(celery_app.conf.beat_schedule or {}),
.\scripts\ci\zero_drift_v3_2.sh:134:    "tasks": {name: {"task": entry["task"], "schedule": str(entry["schedule"])} for name, entry in (celery_app.conf.beat_schedule or {}).items()},
.\scripts\ci\zero_drift_v3_2.sh:137:timeout 20 celery -A app.celery_app.celery_app beat --loglevel=INFO --pidfile= --schedule=/tmp/zg_beat_schedule --max-interval=2 > /tmp/zg_beat.log 2>&1 || true
```

### 2) Pulse semantics search

Command:

```
rg -n "matview|matviews|refresh_all_for_tenant|refresh_single|maintenance|beat|scheduler|periodic" -S backend
```

Output:

```
backend\B0.5.1_VALIDATION_STATUS_REPORT.md:122:| `scan_for_pii_contamination_task` | [app.tasks.maintenance](backend/app/tasks/maintenance.py#L83) | 83 |
backend\B0.5.1_VALIDATION_STATUS_REPORT.md:123:| `enforce_data_retention_task` | [app.tasks.maintenance](backend/app/tasks/maintenance.py#L137) | 137 |
backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1503:- Test environment: Periodic manual cleanup via direct SQL (bypass trigger using superuser)
backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1754:-- Periodic archival job (weekly cron)
backend\app\celery_app.py:165:            "app.tasks.maintenance",
backend\app\celery_app.py:166:            "app.tasks.matviews",
backend\app\celery_app.py:176:            Queue('maintenance', routing_key='maintenance.#'),
backend\app\celery_app.py:182:            'app.tasks.maintenance.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
backend\app\celery_app.py:183:            'app.tasks.matviews.*': {'queue': 'maintenance', 'routing_key': 'maintenance.task'},
backend\app\celery_app.py:194:    # B0.5.4.0: Load Beat schedule (closes G11 drift - beat not deployed)
backend\app\celery_app.py:195:    from app.tasks.beat_schedule import BEAT_SCHEDULE
backend\app\celery_app.py:196:    celery_app.conf.beat_schedule = BEAT_SCHEDULE
backend\app\celery_app.py:205:            "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
backend\app\celery_app.py:206:            "scheduled_tasks": list(celery_app.conf.beat_schedule.keys()) if celery_app.conf.beat_schedule else [],
backend\test_eg6_serialization.py:14:from app.tasks.maintenance import _qualified_matview_identifier
backend\test_eg6_serialization.py:37:            qualified = _qualified_matview_identifier(view_name, task_id=task_id)
backend\app\matviews\executor.py:23:from app.matviews import registry
backend\app\matviews\executor.py:62:def _qualified_matview_identifier(view_name: str) -> str:
backend\app\matviews\executor.py:72:def _topological_order(entries: Iterable[registry.MatviewRegistryEntry]) -> list[registry.MatviewRegistryEntry]:
backend\app\matviews\executor.py:74:    ordered: list[registry.MatviewRegistryEntry] = []
backend\app\matviews\executor.py:81:            raise ValueError(f"Matview registry dependency cycle: {cycle}")
backend\app\matviews\executor.py:91:async def refresh_single_async(
backend\app\matviews\executor.py:104:        qualified_view = _qualified_matview_identifier(view_name)
backend\app\matviews\executor.py:148:            "matview_refresh_executor_failed",
backend\app\matviews\executor.py:169:def refresh_single(
backend\app\matviews\executor.py:175:    Synchronous wrapper for refresh_single_async.
backend\app\matviews\executor.py:180:        return asyncio.run(refresh_single_async(view_name, tenant_id, correlation_id))
backend\app\matviews\executor.py:181:    raise RuntimeError("refresh_single cannot run inside an active event loop")
backend\app\matviews\executor.py:184:async def refresh_all_for_tenant_async(
backend\app\matviews\executor.py:191:        results.append(await refresh_single_async(entry.name, tenant_id, correlation_id))
backend\app\matviews\executor.py:195:def refresh_all_for_tenant(
backend\app\matviews\executor.py:200:    Synchronous wrapper to refresh all matviews for a tenant.
backend\app\matviews\executor.py:205:        return asyncio.run(refresh_all_for_tenant_async(tenant_id, correlation_id))
backend\app\matviews\executor.py:206:    raise RuntimeError("refresh_all_for_tenant cannot run inside an active event loop")
backend\app\matviews\__init__.py:4:The registry is the sole authoritative source of refreshable matviews.
backend\app\core\matview_registry.py:4:Authoritative registry now lives in app.matviews.registry.
backend\app\core\matview_registry.py:8:from app.matviews.registry import get_entry, list_names
backend\app\core\matview_registry.py:13:def get_all_matviews() -> List[str]:
backend\app\core\matview_registry.py:20:def validate_matview_name(view_name: str) -> bool:
backend\app\core\matview_registry.py:22:    Validate that a matview name is in the canonical registry.
backend\app\core\pg_locks.py:70:    Try to acquire an xact-scoped advisory lock for matview refresh.
backend\app\matviews\registry.py:21:class MatviewRegistryEntry:
backend\app\matviews\registry.py:32:_REGISTRY: dict[str, MatviewRegistryEntry] = {
backend\app\matviews\registry.py:33:    "mv_allocation_summary": MatviewRegistryEntry(
backend\app\matviews\registry.py:43:    "mv_channel_performance": MatviewRegistryEntry(
backend\app\matviews\registry.py:53:    "mv_daily_revenue_summary": MatviewRegistryEntry(
backend\app\matviews\registry.py:63:    "mv_realtime_revenue": MatviewRegistryEntry(
backend\app\matviews\registry.py:73:    "mv_reconciliation_status": MatviewRegistryEntry(
backend\app\matviews\registry.py:86:def get_entry(view_name: str) -> MatviewRegistryEntry:
backend\app\matviews\registry.py:96:def list_entries() -> list[MatviewRegistryEntry]:
backend\app\matviews\registry.py:110:def all_entries() -> Iterable[MatviewRegistryEntry]:
backend\app\core\__init__.py:9:- matviews/registry.py: Materialized view registry
backend\app\observability\metrics.py:55:matview_refresh_total = Counter(
backend\app\observability\metrics.py:56:    "matview_refresh_total",
backend\app\observability\metrics.py:61:matview_refresh_duration_seconds = Histogram(
backend\app\observability\metrics.py:62:    "matview_refresh_duration_seconds",
backend\app\observability\metrics.py:68:matview_refresh_failures_total = Counter(
backend\app\observability\metrics.py:69:    "matview_refresh_failures_total",
backend\app\tasks\beat_schedule.py:2:Celery Beat schedule definitions.
backend\app\tasks\beat_schedule.py:6:so beat dispatch evidence appears within short CI timeboxes.
backend\app\tasks\beat_schedule.py:17:    Return the refresh interval for matview refresh.
backend\app\tasks\beat_schedule.py:19:    CI can override via ZG_BEAT_TEST_INTERVAL_SECONDS to force fast dispatch
backend\app\tasks\beat_schedule.py:22:    override = os.getenv("ZG_BEAT_TEST_INTERVAL_SECONDS")
backend\app\tasks\beat_schedule.py:33:def build_beat_schedule() -> Dict[str, Dict[str, Any]]:
backend\app\tasks\beat_schedule.py:36:        "refresh-matviews-every-5-min": {
backend\app\tasks\beat_schedule.py:37:            "task": "app.tasks.maintenance.refresh_all_matviews_global_legacy",
backend\app\tasks\beat_schedule.py:42:            "task": "app.tasks.maintenance.scan_for_pii_contamination",
backend\app\tasks\beat_schedule.py:47:            "task": "app.tasks.maintenance.enforce_data_retention",
backend\app\tasks\beat_schedule.py:55:BEAT_SCHEDULE = build_beat_schedule()
backend\tests\integration\test_data_retention.py:78:        from app.tasks.maintenance import enforce_data_retention_task
backend\app\tasks\maintenance.py:2:Maintenance Background Tasks
backend\app\tasks\maintenance.py:4:Foundation-level maintenance tasks executed by Celery workers. These tasks are
backend\app\tasks\maintenance.py:20:from app.matviews.registry import get_entry, list_names
backend\app\tasks\maintenance.py:21:from app.matviews.executor import RefreshOutcome, refresh_single
backend\app\tasks\maintenance.py:31:def _validated_matview_identifier(
backend\app\tasks\maintenance.py:35:    Validate matview name against registry and return a safely quoted identifier.
backend\app\tasks\maintenance.py:44:            "matview_refresh_invalid_view_name",
backend\app\tasks\maintenance.py:56:def _qualified_matview_identifier(
backend\app\tasks\maintenance.py:60:    Return schema-qualified, safely quoted matview identifier.
backend\app\tasks\maintenance.py:62:    quoted_view = _validated_matview_identifier(view_name, task_id=task_id, tenant_id=tenant_id)
backend\app\tasks\maintenance.py:68:    name="app.tasks.maintenance.refresh_all_matviews_global_legacy",
backend\app\tasks\maintenance.py:69:    routing_key="maintenance.task",
backend\app\tasks\maintenance.py:73:def refresh_all_matviews_global_legacy(self) -> Dict[str, str]:
backend\app\tasks\maintenance.py:81:    Use `refresh_matview_for_tenant` for new integrations.
backend\app\tasks\maintenance.py:90:            result = refresh_single(view_name, None, correlation_id)
backend\app\tasks\maintenance.py:93:                raise RuntimeError(f"Matview refresh failed: {view_name}")
backend\app\tasks\maintenance.py:97:            "matview_refresh_failed",
backend\app\tasks\maintenance.py:108:    name="app.tasks.maintenance.refresh_matview_for_tenant",
backend\app\tasks\maintenance.py:109:    routing_key="maintenance.task",
backend\app\tasks\maintenance.py:114:def refresh_matview_for_tenant(self, tenant_id: UUID, view_name: str, correlation_id: Optional[str] = None) -> Dict[str, str]:
backend\app\tasks\maintenance.py:137:        _qualified_matview_identifier(view_name, task_id=self.request.id, tenant_id=tenant_id)
backend\app\tasks\maintenance.py:138:        result = refresh_single(view_name, tenant_id, correlation_id)
backend\app\tasks\maintenance.py:140:            "tenant_matview_refresh_completed",
backend\app\tasks\maintenance.py:150:            raise RuntimeError("Matview refresh failed")
backend\app\tasks\maintenance.py:159:            "tenant_matview_refresh_failed",
backend\app\tasks\maintenance.py:180:    name="app.tasks.maintenance.scan_for_pii_contamination",
backend\app\tasks\maintenance.py:243:    name="app.tasks.maintenance.enforce_data_retention",
backend\tests\test_b052_queue_topology_and_dlq.py:26:from app.tasks.maintenance import refresh_all_matviews_global_legacy
backend\tests\test_b052_queue_topology_and_dlq.py:27:from app.tasks import matviews  # noqa: F401
backend\tests\test_b052_queue_topology_and_dlq.py:40:        assert len(queues) >= 4, "At least 4 queues (housekeeping, maintenance, llm, attribution) must exist"
backend\tests\test_b052_queue_topology_and_dlq.py:44:        assert "maintenance" in queue_names
backend\tests\test_b052_queue_topology_and_dlq.py:55:        assert "app.tasks.maintenance.*" in routes
backend\tests\test_b052_queue_topology_and_dlq.py:56:        assert "app.tasks.matviews.*" in routes
backend\tests\test_b052_queue_topology_and_dlq.py:62:        assert routes["app.tasks.maintenance.*"]["queue"] == "maintenance"
backend\tests\test_b052_queue_topology_and_dlq.py:63:        assert routes["app.tasks.matviews.*"]["queue"] == "maintenance"
backend\tests\test_b052_queue_topology_and_dlq.py:74:            "app.tasks.maintenance.refresh_all_matviews_global_legacy",
backend\tests\test_b052_queue_topology_and_dlq.py:75:            "app.tasks.maintenance.refresh_matview_for_tenant",
backend\tests\test_b052_queue_topology_and_dlq.py:76:            "app.tasks.matviews.refresh_single",
backend\tests\test_b052_queue_topology_and_dlq.py:77:            "app.tasks.matviews.refresh_all_for_tenant",
backend\tests\test_b052_queue_topology_and_dlq.py:78:            "app.tasks.maintenance.scan_for_pii_contamination",
backend\tests\test_b052_queue_topology_and_dlq.py:79:            "app.tasks.maintenance.enforce_data_retention",
backend\tests\test_b052_queue_topology_and_dlq.py:94:        maintenance_route = celery_app.tasks["app.tasks.maintenance.refresh_all_matviews_global_legacy"].routing_key
backend\tests\test_b052_queue_topology_and_dlq.py:95:        matviews_route = celery_app.tasks["app.tasks.matviews.refresh_single"].routing_key
backend\tests\test_b052_queue_topology_and_dlq.py:105:        assert routes["app.tasks.maintenance.*"]["routing_key"] == "maintenance.task"
backend\tests\test_b052_queue_topology_and_dlq.py:106:        assert routes["app.tasks.matviews.*"]["routing_key"] == "maintenance.task"
backend\tests\test_b051_celery_foundation.py:36:from app.tasks.maintenance import scan_for_pii_contamination_task  # noqa: E402
backend\tests\test_b051_celery_foundation.py:37:from app.tasks import matviews  # noqa: E402,F401
backend\tests\test_b051_celery_foundation.py:191:        "housekeeping,maintenance,llm,attribution",
backend\tests\test_b051_celery_foundation.py:321:    assert "app.tasks.maintenance.refresh_all_matviews_global_legacy" in registered
backend\tests\test_b051_celery_foundation.py:322:    assert "app.tasks.maintenance.refresh_matview_for_tenant" in registered
backend\tests\test_b051_celery_foundation.py:323:    assert "app.tasks.matviews.refresh_single" in registered
backend\tests\test_b051_celery_foundation.py:324:    assert "app.tasks.matviews.refresh_all_for_tenant" in registered
backend\app\tasks\matviews.py:2:Matview task wrapper layer (B0.5.4.3).
backend\app\tasks\matviews.py:4:Delegates to the matview executor and emits logs/metrics/DLQ-triggering
backend\app\tasks\matviews.py:15:from app.matviews.executor import RefreshOutcome, RefreshResult, refresh_all_for_tenant, refresh_single
backend\app\tasks\matviews.py:33:class MatviewTaskFailure(RuntimeError):
backend\app\tasks\matviews.py:54:    metrics.matview_refresh_total.labels(
backend\app\tasks\matviews.py:59:    metrics.matview_refresh_duration_seconds.labels(
backend\app\tasks\matviews.py:64:        metrics.matview_refresh_failures_total.labels(
backend\app\tasks\matviews.py:80:        "matview_refresh_task_start",
backend\app\tasks\matviews.py:109:        logger.error("matview_refresh_task_failed", extra=payload)
backend\app\tasks\matviews.py:111:        logger.info("matview_refresh_task_completed", extra=payload)
backend\app\tasks\matviews.py:122:        raise task.retry(exc=RuntimeError("matview_refresh_retry"), countdown=retry_delay_s)
backend\app\tasks\matviews.py:124:        raise MatviewTaskFailure(
backend\app\tasks\matviews.py:125:            f"matview refresh failed: view={result.view_name} outcome={result.outcome.value}"
backend\app\tasks\matviews.py:136:    name="app.tasks.matviews.refresh_single",
backend\app\tasks\matviews.py:137:    routing_key="maintenance.task",
backend\app\tasks\matviews.py:142:def matview_refresh_single(
backend\app\tasks\matviews.py:160:    result = refresh_single(view_name, tenant_id, correlation_id)
backend\app\tasks\matviews.py:174:    name="app.tasks.matviews.refresh_all_for_tenant",
backend\app\tasks\matviews.py:175:    routing_key="maintenance.task",
backend\app\tasks\matviews.py:180:def matview_refresh_all_for_tenant(
backend\app\tasks\matviews.py:189:        "matview_refresh_all_task_start",
backend\app\tasks\matviews.py:197:    results = refresh_all_for_tenant(tenant_id, correlation_id)
backend\app\tasks\r6_resource_governance.py:125:    routing_key="maintenance.task",
backend\app\tasks\r6_resource_governance.py:232:    routing_key="maintenance.task",
backend\app\middleware\pii_stripping.py:10:- Layer 3 (Audit): Periodic scanning detects residual contamination
backend\tests\test_b0541_view_registry.py:7:from app.matviews import registry
backend\tests\test_b0541_view_registry.py:8:from app.tasks import maintenance
backend\tests\test_b0541_view_registry.py:78:    qualified = maintenance._qualified_matview_identifier(valid_name, task_id="t", tenant_id=None)
backend\tests\test_b0541_view_registry.py:85:            maintenance._validated_matview_identifier(name, task_id="t", tenant_id=None)
backend\validation\database\migration_inventory.txt:37:C:\Users\ayewhy\II SKELDIR II\alembic\versions\003_data_governance\202511171400_drop_deprecated_matviews.py            
backend\tests\test_b0543_matview_task_layer.py:20:from app.matviews import executor
backend\tests\test_b0543_matview_task_layer.py:22:from app.tasks import matviews as matview_tasks
backend\tests\test_b0543_matview_task_layer.py:44:        strategy = matview_tasks.strategy_for_refresh_result(result)
backend\tests\test_b0543_matview_task_layer.py:45:        assert isinstance(strategy, matview_tasks.TaskOutcomeStrategy)
backend\tests\test_b0543_matview_task_layer.py:56:    with pytest.raises(matview_tasks.UnmappedOutcomeError):
backend\tests\test_b0543_matview_task_layer.py:57:        matview_tasks.strategy_for_refresh_result(result)
backend\tests\test_b0543_matview_task_layer.py:60:def test_matview_metrics_emitted(monkeypatch):
backend\tests\test_b0543_matview_task_layer.py:68:        def fake_refresh_single(view_name, tenant_id_arg, correlation_id_arg):
backend\tests\test_b0543_matview_task_layer.py:71:        monkeypatch.setattr(matview_tasks, "refresh_single", fake_refresh_single)
backend\tests\test_b0543_matview_task_layer.py:73:        counter = metrics.matview_refresh_total.labels(
backend\tests\test_b0543_matview_task_layer.py:76:            strategy=matview_tasks.TaskOutcomeStrategy.SUCCESS.value,
backend\tests\test_b0543_matview_task_layer.py:80:        matview_tasks.matview_refresh_single.delay(
backend\tests\test_b0543_matview_task_layer.py:90:        assert b"matview_refresh_total" in metrics_payload
backend\tests\test_b0543_matview_task_layer.py:91:        assert b"matview_refresh_duration_seconds" in metrics_payload
backend\tests\test_b0543_matview_task_layer.py:97:async def test_matview_failure_persists_correlation_id(monkeypatch):
backend\tests\test_b0543_matview_task_layer.py:105:        def fake_refresh_single(view_name, tenant_id_arg, correlation_id_arg):
backend\tests\test_b0543_matview_task_layer.py:108:        monkeypatch.setattr(matview_tasks, "refresh_single", fake_refresh_single)
backend\tests\test_b0543_matview_task_layer.py:110:        with pytest.raises(matview_tasks.MatviewTaskFailure):
backend\tests\test_b0543_matview_task_layer.py:111:            matview_tasks.matview_refresh_single.delay(
backend\tests\test_b0543_matview_task_layer.py:123:                    WHERE task_name = 'app.tasks.matviews.refresh_single'
backend\tests\test_b0543_matview_task_layer.py:131:        assert row is not None, "Failed matview task should be captured in worker_failed_jobs"
backend\tests\test_b0543_matview_task_layer.py:143:                    WHERE task_name = 'app.tasks.matviews.refresh_single'
backend\tests\test_b0542_refresh_executor.py:11:from app.matviews import executor, registry
backend\tests\test_b0542_refresh_executor.py:39:    patched = registry.MatviewRegistryEntry(
backend\tests\test_b0542_refresh_executor.py:52:        executor.refresh_single_async(view_name, tenant_id, "corr-1"),
backend\tests\test_b0542_refresh_executor.py:53:        executor.refresh_single_async(view_name, tenant_id, "corr-1"),
backend\tests\test_b0542_refresh_executor.py:109:    async def fake_refresh_single_async(view_name: str, tenant_id_arg, correlation_id=None):
backend\tests\test_b0542_refresh_executor.py:127:    monkeypatch.setattr(executor, "refresh_single_async", fake_refresh_single_async)
backend\tests\test_b0542_refresh_executor.py:129:    results = await executor.refresh_all_for_tenant_async(tenant_id, "corr-2")
backend\tests\test_b0542_refresh_executor.py:139:            "has_refresh_single": hasattr(executor, "refresh_single"),
backend\tests\test_b0542_refresh_executor.py:140:            "has_refresh_all_for_tenant": hasattr(executor, "refresh_all_for_tenant"),
backend\tests\test_matview_refresh_validation.py:3:from app.tasks import maintenance as m
backend\tests\test_matview_refresh_validation.py:6:def test_validated_matview_identifier_rejects_non_registry():
backend\tests\test_matview_refresh_validation.py:8:        m._validated_matview_identifier("not_a_view", task_id="t", tenant_id=None)
backend\tests\test_matview_refresh_validation.py:11:def test_validated_matview_identifier_quotes_registry_member():
backend\tests\test_matview_refresh_validation.py:12:    ident = m._validated_matview_identifier("mv_allocation_summary", task_id="t", tenant_id=None)
backend\tests\test_matview_refresh_validation.py:25:def test_validated_matview_identifier_rejects_injection_candidates(bad_name: str):
backend\tests\test_matview_refresh_validation.py:27:        m._validated_matview_identifier(bad_name, task_id="t", tenant_id=None)
backend\tests\test_matview_refresh_validation.py:31:    qualified = m._qualified_matview_identifier("mv_allocation_summary", task_id="t", tenant_id=None)
backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
backend\tests\value_traces\test_value_04_registry_trace.py:2:Value Trace 04: Registry-to-Reality matview inventory check.
backend\tests\value_traces\test_value_04_registry_trace.py:4:Compares the view registry against pg_matviews and emits a diff artifact.
backend\tests\value_traces\test_value_04_registry_trace.py:15:from app.matviews.registry import list_names
backend\tests\value_traces\test_value_04_registry_trace.py:25:async def test_value_trace_registry_matches_pg_matviews():
backend\tests\value_traces\test_value_04_registry_trace.py:30:                SELECT matviewname
backend\tests\value_traces\test_value_04_registry_trace.py:31:                FROM pg_matviews
backend\tests\value_traces\test_value_04_registry_trace.py:32:                ORDER BY matviewname
backend\tests\value_traces\test_value_04_registry_trace.py:36:        matviews = sorted(result.scalars().all())
backend\tests\value_traces\test_value_04_registry_trace.py:39:    diff_missing = [m for m in registry_sorted if m not in matviews]
backend\tests\value_traces\test_value_04_registry_trace.py:40:    diff_extra = [m for m in matviews if m not in registry_sorted]
backend\tests\value_traces\test_value_04_registry_trace.py:44:        "pg_matviews": matviews,
backend\tests\value_traces\test_value_04_registry_trace.py:54:        fh.write("# Value Trace 04 ??? Registry vs pg_matviews\n\n")
backend\tests\value_traces\test_value_04_registry_trace.py:56:        fh.write(f"- pg_matviews: {matviews}\n")
backend\tests\value_traces\test_value_04_registry_trace.py:60:    assert not diff_missing and not diff_extra, "Registry and pg_matviews must match"
backend\validation\evidence\database\migration_inventory.txt:37:C:\Users\ayewhy\II SKELDIR II\alembic\versions\003_data_governance\202511171400_drop_deprecated_matviews.py            
backend\validation\evidence\database\current_schema_20251127_111736.sql:527:COMMENT ON FUNCTION public.fn_scan_pii_contamination() IS 'PII contamination scanning function (Layer 3 operations audit). Returns: Count of PII findings detected. Scope: Scans all three JSONB surfaces (attribution_events.raw_payload, dead_events.raw_payload, revenue_ledger.metadata). Behavior: Inserts findings into pii_audit_findings table for each detected PII key. Performance: Batch operation, intended for periodic scheduled execution (not per-transaction). Security: Does not log actual PII values, only record IDs and key names. Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".';
backend\validation\evidence\database\current_schema_20251127_111736.sql:1419:COMMENT ON TABLE public.pii_audit_findings IS 'PII audit findings repository (Layer 3 operations audit). Purpose: Store PII contamination detections from periodic scans. Data class: Non-PII (contains record IDs and key names only, not actual PII values). Ownership: Operations/Security team. Use: Detect Layer 1/Layer 2 failures, compliance auditing, incident response. Schedule: Daily (non-prod), Hourly/Daily (prod). Reference: ADR-003-PII-Defense-Strategy.md Section "Layer 3 (Operations)".';
```

### 3) Beat entrypoint search

Command:

```
rg -n "celery .*beat|celerybeat|--beat|beat -S|Scheduler" -S --glob "!**/.git/**" --glob "!**/node_modules/**" .
```

Output:

```
.\B0544_tmp\cmd1.txt:2:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:3:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:5:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:6:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:12:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:13:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:15:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:16:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:20:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:21:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:23:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:24:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\B0544_tmp\cmd1.txt:43:.\scripts\ci\zero_drift_v3_2.sh:137:timeout 20 celery -A app.celery_app.celery_app beat --loglevel=INFO --pidfile= --schedule=/tmp/zg_beat_schedule --max-interval=2 > /tmp/zg_beat.log 2>&1 || true
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\scripts\ci\zero_drift_v3_2.sh:137:timeout 20 celery -A app.celery_app.celery_app beat --loglevel=INFO --pidfile= --schedule=/tmp/zg_beat_schedule --max-interval=2 > /tmp/zg_beat.log 2>&1 || true
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\evidence\b0540_ci_truthlayer_evidence.md:33:- **Beat dispatch proof (ZG-5)**: `Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.maintenance.refresh_all_matviews_global_legacy)` repeats with 1s interval (`tmp/zero_drift_v3_2_run7.log` lines @ `2025-12-21T18:40:04Z`???`18:40:22Z`), demonstrating dispatch, not just startup.
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:48:      "beat_scheduler": "celery.beat:PersistentScheduler",
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:152:[2025-12-20 12:51:21,656: INFO/MainProcess] Scheduler: Sending due task pii-audit-scanner (app.tasks.maintenance.scan_for_pii_contamination)
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:153:[2025-12-20 12:51:21,748: INFO/MainProcess] Scheduler: Sending due task enforce-data-retention (app.tasks.maintenance.enforce_data_retention)
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:154:[2025-12-20 12:51:21,752: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.maintenance.refresh_all_matviews_global_legacy)
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:654:**Selected Mechanism**: Celery Beat (Application-Layer Scheduler)
.\docs\evidence\b054-forensic-readiness-evidence.md:47:# Standard command would be: celery -A app.celery_app.celery_app beat --loglevel=INFO
.\docs\evidence\b054-forensic-readiness-evidence.md:641:   - **No `celery beat` process**
.\docs\evidence\b054-forensic-readiness-evidence.md:658:- CI does NOT start `celery beat` process
.\docs\evidence\b054-forensic-readiness-evidence.md:818:- CI does NOT start `celery beat` process
.\docs\evidence\b054-forensic-readiness-evidence.md:994:3. **Deploy Beat:** Add `celery beat` startup command to CI and local docs
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:38:    "beat_scheduler": "celery.beat:PersistentScheduler",
```

### 4) Compose/Procfile/Makefile discovery

Command:

```
Get-ChildItem -Recurse -File -Include "docker-compose*.yml","compose*.yml","Makefile","Procfile" . | ForEach-Object { $_.FullName }
```

Output:

```
C:\Users\ayewhy\II SKELDIR II\frontend\node_modules\sort-by\Makefile
C:\Users\ayewhy\II SKELDIR II\node_modules\delayed-stream\Makefile
C:\Users\ayewhy\II SKELDIR II\node_modules\foreach\Makefile
C:\Users\ayewhy\II SKELDIR II\node_modules\json-pointer\Makefile
C:\Users\ayewhy\II SKELDIR II\node_modules\lunr\Makefile
C:\Users\ayewhy\II SKELDIR II\docker-compose.component-dev.yml
C:\Users\ayewhy\II SKELDIR II\docker-compose.mock.yml
C:\Users\ayewhy\II SKELDIR II\Makefile
C:\Users\ayewhy\II SKELDIR II\Procfile
```

### 5) Celery entrypoints in compose/Procfile/scripts

Command:

```
rg -n "celery" -S docker-compose*.yml compose*.yml Makefile Procfile scripts 2>$null
```

Output:

```
Procfile:8:#   - worker: Celery background worker
Procfile:20:worker: cd backend && celery -A app.tasks worker --loglevel=info
scripts\ci\zero_drift_v3_2.sh:124:export CELERY_BROKER_URL="sqla+postgresql://app_user:app_user@${PGHOST}:${PGPORT}/skeldir_zg_fresh"
scripts\ci\zero_drift_v3_2.sh:125:export CELERY_RESULT_BACKEND="db+postgresql://app_user:app_user@${PGHOST}:${PGPORT}/skeldir_zg_fresh"
scripts\ci\zero_drift_v3_2.sh:129:from app.celery_app import celery_app
scripts\ci\zero_drift_v3_2.sh:132:    "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
scripts\ci\zero_drift_v3_2.sh:133:    "task_count": len(celery_app.conf.beat_schedule or {}),
scripts\ci\zero_drift_v3_2.sh:134:    "tasks": {name: {"task": entry["task"], "schedule": str(entry["schedule"])} for name, entry in (celery_app.conf.beat_schedule or {}).items()},
scripts\ci\zero_drift_v3_2.sh:137:timeout 20 celery -A app.celery_app.celery_app beat --loglevel=INFO --pidfile= --schedule=/tmp/zg_beat_schedule --max-interval=2 > /tmp/zg_beat.log 2>&1 || true
scripts\r4\render_r4_summary.py:99:    gate_fix_0 = bool(env.get("candidate_sha") and env.get("tenants") and env.get("celery") and verdicts and evidence_pack)
scripts\r4\render_r4_summary.py:101:    celery_env = env.get("celery", {}) if isinstance(env.get("celery", {}), dict) else {}
scripts\r4\render_r4_summary.py:102:    broker_scheme = str(celery_env.get("broker_scheme") or "")
scripts\r4\render_r4_summary.py:103:    backend_scheme = str(celery_env.get("result_backend_scheme") or "")
scripts\r4\render_r4_summary.py:104:    broker_hash = str(celery_env.get("broker_dsn_sha256") or "")
scripts\r4\render_r4_summary.py:105:    backend_hash = str(celery_env.get("result_backend_dsn_sha256") or "")
scripts\r4\render_r4_summary.py:166:            f"- `acks_late` = `{env.get('celery', {}).get('acks_late')}`",
scripts\r4\render_r4_summary.py:167:            f"- `reject_on_worker_lost` = `{env.get('celery', {}).get('reject_on_worker_lost')}`",
scripts\r4\render_r4_summary.py:168:            f"- `acks_on_failure_or_timeout` = `{env.get('celery', {}).get('acks_on_failure_or_timeout')}`",
scripts\r4\render_r4_summary.py:169:            f"- `prefetch_multiplier` = `{env.get('celery', {}).get('prefetch_multiplier')}`",
scripts\r4\worker_failure_semantics.py:4:Authoritative proof harness: runs against a real Postgres + real Celery worker fabric
scripts\r4\worker_failure_semantics.py:29:from app.celery_app import celery_app  # noqa: E402
scripts\r4\worker_failure_semantics.py:41:def _kill_stray_celery_workers() -> int:
scripts\r4\worker_failure_semantics.py:43:    Best-effort cleanup: ensure no orphaned Celery worker processes remain between scenarios.
scripts\r4\worker_failure_semantics.py:64:        if "celery" not in args or "app.celery_app.celery_app" not in args or " worker" not in args:
scripts\r4\worker_failure_semantics.py:183:            "celery",
scripts\r4\worker_failure_semantics.py:185:            "app.celery_app.celery_app",
scripts\r4\worker_failure_semantics.py:308:    raise TimeoutError("Timed out waiting for Celery results")
scripts\r4\worker_failure_semantics.py:315:            r = celery_app.send_task("app.tasks.housekeeping.ping", kwargs={"fail": False})
scripts\r4\worker_failure_semantics.py:651:        celery_app.send_task(
scripts\r4\worker_failure_semantics.py:737:        celery_app.send_task(
scripts\r4\worker_failure_semantics.py:860:    r = celery_app.send_task(
scripts\r4\worker_failure_semantics.py:915:    runaway = celery_app.send_task(
scripts\r4\worker_failure_semantics.py:928:        celery_app.send_task(
scripts\r4\worker_failure_semantics.py:983:    r = celery_app.send_task(
scripts\r4\worker_failure_semantics.py:1047:    broker_dsn = str(getattr(celery_app.conf, "broker_url", "") or "")
scripts\r4\worker_failure_semantics.py:1048:    backend_dsn = str(getattr(celery_app.conf, "result_backend", "") or "")
scripts\r4\worker_failure_semantics.py:1089:    poison_worker = WorkerSupervisor(concurrency=concurrency, pool=poison_pool, log_prefix="celery_harness_worker_poison")
scripts\r4\worker_failure_semantics.py:1100:    broker_transport_options = getattr(celery_app.conf, "broker_transport_options", None)
scripts\r4\worker_failure_semantics.py:1102:        "visibility_timeout_s": int(_env("CELERY_BROKER_VISIBILITY_TIMEOUT_S", "0") or 0),
scripts\r4\worker_failure_semantics.py:1104:            _env("CELERY_BROKER_RECOVERY_SWEEP_INTERVAL_S", _env("CELERY_BROKER_POLLING_INTERVAL_S", "0.0")) or 0.0
scripts\r4\worker_failure_semantics.py:1106:        "task_name_filter": _env("CELERY_BROKER_RECOVERY_TASK_NAME_FILTER", ""),
scripts\r4\worker_failure_semantics.py:1113:        "celery": {
scripts\r4\worker_failure_semantics.py:1120:            "acks_late": bool(getattr(celery_app.conf, "task_acks_late", False)),
scripts\r4\worker_failure_semantics.py:1121:            "reject_on_worker_lost": bool(getattr(celery_app.conf, "task_reject_on_worker_lost", False)),
scripts\r4\worker_failure_semantics.py:1122:            "acks_on_failure_or_timeout": bool(getattr(celery_app.conf, "task_acks_on_failure_or_timeout", False)),
scripts\r4\worker_failure_semantics.py:1123:            "prefetch_multiplier": int(getattr(celery_app.conf, "worker_prefetch_multiplier", 0) or 0),
scripts\r4\worker_failure_semantics.py:1137:                "prefetch": config_dump["celery"]["prefetch_multiplier"],
scripts\r4\worker_failure_semantics.py:1138:                "acks_late": config_dump["celery"]["acks_late"],
scripts\r4\worker_failure_semantics.py:1139:                "reject_on_worker_lost": config_dump["celery"]["reject_on_worker_lost"],
scripts\r4\worker_failure_semantics.py:1140:                "acks_on_failure_or_timeout": config_dump["celery"]["acks_on_failure_or_timeout"],
scripts\r4\worker_failure_semantics.py:1190:                    _kill_stray_celery_workers()
scripts\r4\worker_failure_semantics.py:1198:                        concurrency=crash_concurrency, pool=crash_pool, log_prefix="celery_harness_worker_crash"
scripts\r4\worker_failure_semantics.py:1223:                    _kill_stray_celery_workers()
scripts\r4\worker_failure_semantics.py:1231:                        concurrency=concurrency, pool=main_pool, log_prefix="celery_harness_worker_main"
scripts\r4\worker_failure_semantics.py:1288:                _kill_stray_celery_workers()
scripts\r4\worker_failure_semantics.py:1291:                    _kill_stray_celery_workers()
scripts\r4\worker_failure_semantics.py:1294:                    _kill_stray_celery_workers()
scripts\r6\r6_context_gathering.py:24:from celery import __version__ as celery_version
scripts\r6\r6_context_gathering.py:25:from celery.result import AsyncResult
scripts\r6\r6_context_gathering.py:28:from app.celery_app import celery_app  # noqa: E402
scripts\r6\r6_context_gathering.py:94:def _celery_cli(base_args: list[str]) -> str:
scripts\r6\r6_context_gathering.py:95:    command = ["celery", "-A", "app.celery_app.celery_app"] + base_args
scripts\r6\r6_context_gathering.py:140:    conf = celery_app.conf
scripts\r6\r6_context_gathering.py:144:    for task_name, task in celery_app.tasks.items():
scripts\r6\r6_context_gathering.py:145:        if task_name.startswith("celery.") or task_name.startswith("kombu."):
scripts\r6\r6_context_gathering.py:274:        f"- task_time_limit: {conf.get('task_time_limit')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:275:        f"- task_soft_time_limit: {conf.get('task_soft_time_limit')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:276:        f"- task_acks_late: {conf.get('task_acks_late')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:277:        f"- task_reject_on_worker_lost: {conf.get('task_reject_on_worker_lost')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:278:        f"- task_acks_on_failure_or_timeout: {conf.get('task_acks_on_failure_or_timeout')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:279:        f"- worker_prefetch_multiplier: {conf.get('worker_prefetch_multiplier')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:280:        f"- worker_max_tasks_per_child: {conf.get('worker_max_tasks_per_child')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:281:        f"- worker_max_memory_per_child: {conf.get('worker_max_memory_per_child')} (evidence: R6_CELERY_INSPECT_CONF.json)",
scripts\r6\r6_context_gathering.py:300:            result = celery_app.send_task(
scripts\r6\r6_context_gathering.py:314:    result = celery_app.send_task(
scripts\r6\r6_context_gathering.py:352:    result = celery_app.send_task(
scripts\r6\r6_context_gathering.py:398:        celery_app.send_task(
scripts\r6\r6_context_gathering.py:406:        celery_app.send_task(
scripts\r6\r6_context_gathering.py:466:        result = celery_app.send_task(
scripts\r6\r6_context_gathering.py:535:        "celery": {"version": celery_version},
scripts\r6\r6_context_gathering.py:544:        output_dir / "R6_CELERY_REPORT.log",
scripts\r6\r6_context_gathering.py:545:        _celery_cli(["report"]),
scripts\r6\r6_context_gathering.py:550:        output_dir / "R6_CELERY_INSPECT_CONF.log",
scripts\r6\r6_context_gathering.py:551:        _celery_cli(["inspect", "conf"]),
scripts\r6\r6_context_gathering.py:556:        output_dir / "R6_CELERY_INSPECT_STATS.log",
scripts\r6\r6_context_gathering.py:557:        _celery_cli(["inspect", "stats"]),
scripts\r6\r6_context_gathering.py:563:        _celery_cli(["inspect", "active_queues"]),
scripts\r6\r6_context_gathering.py:569:        _celery_cli(["inspect", "registered"]),
scripts\r6\r6_context_gathering.py:577:    _write_json(output_dir / "R6_CELERY_INSPECT_CONF.json", snapshot, sha=sha, timestamp=timestamp)
scripts\r6\r6_context_gathering.py:579:    inspector = celery_app.control.inspect(timeout=5)
scripts\r6\r6_context_gathering.py:589:    _write_json(output_dir / "R6_CELERY_INSPECT_STATS.json", stats, sha=sha, timestamp=timestamp)
scripts\r6\r6_context_gathering.py:595:            "tasks": sorted(celery_app.tasks.keys()),
scripts\r6\r6_context_gathering.py:622:    conf = celery_app.conf
```

### 6) Competing scheduler search (cron/APScheduler/loop)

Command:

```
rg -n "cron|crontab|APScheduler|schedule\.every|while True|sleep\(|timer|Periodic|background job" -S --glob "!**/.git/**" --glob "!**/node_modules/**" backend scripts .
```

Output:

```
.\B0.5.2_Context_Inventory_Baseline.md:181:2. **Worker-level DLQ schema**: Postgres tables + routing convention for failed background jobs, ensuring deterministic failure capture and replay.
scripts\ci\zero_drift_v3_2.sh:153:        await asyncio.sleep(duration)
scripts\ci\zero_drift_v3_2.sh:161:    await asyncio.sleep(0.2)
scripts\r4\worker_failure_semantics.py:307:        time.sleep(0.25)
scripts\r4\worker_failure_semantics.py:318:            time.sleep(0.5)
scripts\r4\worker_failure_semantics.py:553:        await asyncio.sleep(0.2)
scripts\r4\worker_failure_semantics.py:604:        await asyncio.sleep(0.2)
scripts\r4\worker_failure_semantics.py:675:        await asyncio.sleep(0.5)
scripts\r4\worker_failure_semantics.py:922:    time.sleep(0.5)
scripts\r4\worker_failure_semantics.py:943:        await asyncio.sleep(0.5)
scripts\r6\r6_context_gathering.py:307:            time.sleep(1)
scripts\r3\ingestion_under_fire.py:108:            await asyncio.sleep(delay_s)
scripts\r3\ingestion_under_fire.py:208:        await asyncio.sleep(delay_s)
.\B0544_tmp\cmd2.txt:3:backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1503:- Test environment: Periodic manual cleanup via direct SQL (bypass trigger using superuser)
.\B0544_tmp\cmd2.txt:4:backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1754:-- Periodic archival job (weekly cron)
.\B0544_tmp\cmd2.txt:147:backend\app\middleware\pii_stripping.py:10:- Layer 3 (Audit): Periodic scanning detects residual contamination
.\B0544_tmp\cmd2.txt:192:backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
.\B0544_tmp\cmd1.txt:1:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:4:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:8:.\backend\app\tasks\beat_schedule.py:43:            "schedule": crontab(hour=4, minute=0),
.\B0544_tmp\cmd1.txt:9:.\backend\app\tasks\beat_schedule.py:48:            "schedule": crontab(hour=3, minute=0),
.\B0544_tmp\cmd1.txt:11:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:14:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:17:.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:774:        "schedule": crontab(hour=4, minute=0),  # Daily at 4:00 AM UTC
.\B0544_tmp\cmd1.txt:18:.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:1085:        "schedule": crontab(hour=3, minute=0),  # Daily at 3:00 AM UTC
.\B0544_tmp\cmd1.txt:19:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:22:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\B0544_tmp\cmd1.txt:33:.\docs\evidence\b054-forensic-readiness-evidence.md:620:             "schedule": crontab(hour=4, minute=0),
.\B0544_tmp\cmd1.txt:34:.\docs\evidence\b054-forensic-readiness-evidence.md:625:             "schedule": crontab(hour=3, minute=0),
.\DIRECTOR_BRIEFING_VALIDATION_RESULTS.md:241:????????? tasks/ (background jobs)
backend\B044_EXECUTION_SUMMARY.md:517:-- Weekly cron job
backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1503:- Test environment: Periodic manual cleanup via direct SQL (bypass trigger using superuser)
backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1754:-- Periodic archival job (weekly cron)
.\tests\contract\test_mock_integrity.py:231:                time.sleep(RETRY_DELAY * (attempt + 1))
backend\app\tasks\r6_resource_governance.py:144:        while True:
backend\app\tasks\r6_resource_governance.py:145:            time.sleep(0.2)
backend\app\tasks\r6_resource_governance.py:159:        while True:
backend\app\tasks\r6_resource_governance.py:160:            time.sleep(0.2)
backend\app\tasks\r6_resource_governance.py:211:    time.sleep(0.2)
backend\app\tasks\r6_resource_governance.py:249:    time.sleep(float(sleep_s))
backend\app\tasks\r4_failure_semantics.py:250:        time.sleep(3600)
backend\app\tasks\r4_failure_semantics.py:301:def runaway_sleep(self, *, tenant_id: str, correlation_id: str, sleep_s: int) -> dict[str, str]:
backend\app\tasks\r4_failure_semantics.py:318:        time.sleep(sleep_s)
backend\app\tasks\context.py:55:        time.sleep(0.01)
backend\app\tasks\beat_schedule.py:12:from celery.schedules import crontab
backend\app\tasks\beat_schedule.py:43:            "schedule": crontab(hour=4, minute=0),
backend\app\tasks\beat_schedule.py:48:            "schedule": crontab(hour=3, minute=0),
.\artifacts_vt_run3\phase-VALUE_04-evidence\backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
backend\app\middleware\pii_stripping.py:10:- Layer 3 (Audit): Periodic scanning detects residual contamination
.\scripts\r6\r6_context_gathering.py:307:            time.sleep(1)
.\scripts\r4\worker_failure_semantics.py:307:        time.sleep(0.25)
.\scripts\r4\worker_failure_semantics.py:318:            time.sleep(0.5)
.\scripts\r4\worker_failure_semantics.py:553:        await asyncio.sleep(0.2)
.\scripts\r4\worker_failure_semantics.py:604:        await asyncio.sleep(0.2)
.\scripts\r4\worker_failure_semantics.py:675:        await asyncio.sleep(0.5)
.\scripts\r4\worker_failure_semantics.py:922:    time.sleep(0.5)
.\scripts\r4\worker_failure_semantics.py:943:        await asyncio.sleep(0.5)
.\scripts\r3\ingestion_under_fire.py:108:            await asyncio.sleep(delay_s)
.\scripts\r3\ingestion_under_fire.py:208:        await asyncio.sleep(delay_s)
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:44:      "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:282:      "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:283:      "worker_timer_precision": 1.0
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:34:    "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:272:    "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:273:    "worker_timer_precision": 1.0
.\backend\scripts\repro_fixture_ping.py:67:            time.sleep(poll_interval)
.\monitoring\alerts\pii-alerts.yml:74:          action: "Check audit scan scheduler configuration, verify cron job or scheduled task"
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:44:      "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:282:      "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:283:      "worker_timer_precision": 1.0
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:34:    "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:272:    "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:273:    "worker_timer_precision": 1.0
.\docs\archive\FRONTEND_IMPLEMENTATION_SPECIFICATION.md:133:- Clears timers on unmount to avoid memory leaks.
backend\app\celery_app.py:305:        while True:
backend\app\celery_app.py:319:            time.sleep(sweep_interval_s)
.\backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
.\frontend\src\hooks\useTokenManager.tsx:29:  const refP = useRef<Promise<void> | null>(null), timer = useRef<number | null>(null);
.\frontend\src\hooks\useTokenManager.tsx:32:  const clearToken = () => { setT(null); setE(null); setErr(null); if (timer.current) clearTimeout(timer.current); };
.\frontend\src\hooks\useTokenManager.tsx:52:    if (d > 0) timer.current = window.setTimeout(refreshToken, d);
.\frontend\src\hooks\useTokenManager.tsx:54:    return () => { if (timer.current) clearTimeout(timer.current); };
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:44:      "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:46:      "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:289:      "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:290:      "worker_timer_precision": 1.0
.\frontend\src\hooks\useReconciliationAutoRefresh.ts:68:  // Countdown timer for "Next refresh in X seconds"
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:34:    "beat_cron_starting_deadline": null,
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:36:    "beat_schedule": "{'refresh-matviews-every-5-min': {'task': 'app.tasks.maintenance.refresh_all_matviews_global_legacy', 'schedule': 300.0, 'options': {'expires': 600}}, 'pii-audit-scanner': {'task': 'app.tasks.maintenance.scan_for_pii_contamination', 'schedule': <crontab: 0 4 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}, 'enforce-data-retention': {'task': 'app.tasks.maintenance.enforce_data_retention', 'schedule': <crontab: 0 3 * * * (m/h/dM/MY/d)>, 'options': {'expires': 3600}}}",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:279:    "worker_timer": null,
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:280:    "worker_timer_precision": 1.0
.\backend\B044_EXECUTION_SUMMARY.md:517:-- Weekly cron job
.\frontend\src\hooks\use-file-downloader.ts:61:      if (currentDownloadTokenRef.current === downloadToken) { const timer = fallbackTimersRef.current.get(downloadToken); if (timer) { clearTimeout(timer); fallbackTimersRef.current.delete(downloadToken); } setIsDownloading(false); }
.\frontend\src\hooks\use-file-downloader.ts:63:      if (currentDownloadTokenRef.current === downloadToken) { const timer = fallbackTimersRef.current.get(downloadToken); if (timer) { clearTimeout(timer); fallbackTimersRef.current.delete(downloadToken); } }
.\frontend\src\hooks\use-file-downloader.ts:88:  useEffect(() => () => { abortControllerRef.current?.abort(); blobUrlsRef.current.forEach(url => URL.revokeObjectURL(url)); revokeTimersRef.current.forEach(timer => clearTimeout(timer)); fallbackTimersRef.current.forEach(timer => clearTimeout(timer)); }, []);
.\docs\archive\completed-phases\b0.3\B0.3_FORENSIC_ANALYSIS_RESPONSE.md:775:- External scheduler (cron, Kubernetes jobs)
.\backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1503:- Test environment: Periodic manual cleanup via direct SQL (bypass trigger using superuser)
.\backend\B043_COMPLETE_TECHNICAL_SUMMARY.md:1754:-- Periodic archival job (weekly cron)
.\frontend\src\hooks\use-auto-dismiss.ts:16:  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
.\frontend\src\hooks\use-auto-dismiss.ts:35:    if (timerRef.current) clearTimeout(timerRef.current);
.\frontend\src\hooks\use-auto-dismiss.ts:48:    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration - pausedAtRef.current);
.\frontend\src\hooks\use-auto-dismiss.ts:55:    if (timerRef.current) clearTimeout(timerRef.current);
.\frontend\src\hooks\use-auto-dismiss.ts:60:    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration);
.\frontend\src\hooks\use-auto-dismiss.ts:65:    if (timerRef.current) clearTimeout(timerRef.current);
.\frontend\src\hooks\use-auto-dismiss.ts:73:    timerRef.current = setTimeout(() => !dismissedRef.current && (dismissedRef.current = true, onDismissRef.current()), duration);
.\frontend\src\hooks\use-auto-dismiss.ts:75:    return () => { if (timerRef.current) clearTimeout(timerRef.current); if (rafRef.current) cancelAnimationFrame(rafRef.current); };
.\docs\archive\completed-phases\b0.1\B0.1_PHASE_FORENSIC_EVALUATION_RESPONSE.md:761:- Periodic batch scanning
backend\test_eg6_serialization.py:36:            await asyncio.sleep(delay_sec)
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:660:- No external DB-level cron dependencies (e.g., `pg_cron`)
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:774:        "schedule": crontab(hour=4, minute=0),  # Daily at 4:00 AM UTC
.\docs\governance\PRIVACY_LIFECYCLE_IMPLEMENTATION.md:1085:        "schedule": crontab(hour=3, minute=0),  # Daily at 3:00 AM UTC
.\docs\governance\DATA_PRIVACY_LIFECYCLE.md:96:**Mechanism**: Periodic batch scanning of JSONB surfaces to detect residual PII contamination
.\backend\app\tasks\r6_resource_governance.py:144:        while True:
.\backend\app\tasks\r6_resource_governance.py:145:            time.sleep(0.2)
.\backend\app\tasks\r6_resource_governance.py:159:        while True:
.\backend\app\tasks\r6_resource_governance.py:160:            time.sleep(0.2)
.\backend\app\tasks\r6_resource_governance.py:211:    time.sleep(0.2)
.\backend\app\tasks\r6_resource_governance.py:249:    time.sleep(float(sleep_s))
.\backend\app\tasks\r4_failure_semantics.py:250:        time.sleep(3600)
.\backend\app\tasks\r4_failure_semantics.py:301:def runaway_sleep(self, *, tenant_id: str, correlation_id: str, sleep_s: int) -> dict[str, str]:
.\backend\app\tasks\r4_failure_semantics.py:318:        time.sleep(sleep_s)
.\backend\app\tasks\context.py:55:        time.sleep(0.01)
.\backend\app\tasks\beat_schedule.py:12:from celery.schedules import crontab
.\backend\app\tasks\beat_schedule.py:43:            "schedule": crontab(hour=4, minute=0),
.\backend\app\tasks\beat_schedule.py:48:            "schedule": crontab(hour=3, minute=0),
.\artifacts_vt_run3\phase-VALUE_03-evidence\backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
.\scripts\ci\zero_drift_v3_2.sh:153:        await asyncio.sleep(duration)
.\scripts\ci\zero_drift_v3_2.sh:161:    await asyncio.sleep(0.2)
backend\tests\test_b0542_refresh_executor.py:37:        await asyncio.sleep(0.25)
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:142:    "pii-audit-scanner": {"task": "app.tasks.maintenance.scan_for_pii_contamination", "schedule": "<crontab: 0 4 * * * (m/h/dM/MY/d)>"},
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:143:    "enforce-data-retention": {"task": "app.tasks.maintenance.enforce_data_retention", "schedule": "<crontab: 0 3 * * * (m/h/dM/MY/d)>"}
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:173:        await asyncio.sleep(duration)
.\docs\evidence\b0540-drift-remediation-preflight-evidence.md:182:    await asyncio.sleep(0.2)
.\docs\evidence\b054-forensic-readiness-evidence.md:620:             "schedule": crontab(hour=4, minute=0),
.\docs\evidence\b054-forensic-readiness-evidence.md:625:             "schedule": crontab(hour=3, minute=0),
.\docs\evidence\b054-forensic-readiness-evidence.md:665:- B0.5.4 implementation must decide: Enable Beat or use alternative scheduling (e.g., cron, CI scheduled workflow)
.\docs\evidence\b054-forensic-readiness-evidence.md:1003:8. **Decision:** Beat scheduling OR CI cron OR both?
backend\tests\test_b051_celery_foundation.py:152:            time.sleep(2)
backend\tests\test_b051_celery_foundation.py:251:        time.sleep(1)
.\backend\app\middleware\pii_stripping.py:10:- Layer 3 (Audit): Periodic scanning detects residual contamination
.\backend\app\celery_app.py:305:        while True:
.\backend\app\celery_app.py:319:            time.sleep(sweep_interval_s)
.\backend\test_eg6_serialization.py:36:            await asyncio.sleep(delay_sec)
backend\scripts\repro_fixture_ping.py:67:            time.sleep(poll_interval)
.\frontend\src\components\icons\SkelderIcons.tsx:220:      {/* Clock/timer visualization */}
.\frontend\package-lock.json:2884:    "node_modules/@types/d3-timer": {
.\frontend\package-lock.json:2886:      "resolved": "https://registry.npmjs.org/@types/d3-timer/-/d3-timer-3.0.2.tgz",
.\frontend\package-lock.json:3736:    "node_modules/d3-timer": {
.\frontend\package-lock.json:3738:      "resolved": "https://registry.npmjs.org/d3-timer/-/d3-timer-3.0.1.tgz",
.\frontend\package-lock.json:6081:        "@types/d3-timer": "^3.0.0",
.\frontend\package-lock.json:6088:        "d3-timer": "^3.0.1"
.\artifacts_vt_run3\phase-VALUE_01-evidence\backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
.\frontend\src\components\dashboard\VerificationToast.tsx:21:    const timer = setTimeout(() => {
.\frontend\src\components\dashboard\VerificationToast.tsx:35:      clearTimeout(timer);
.\frontend\src\components\dashboard\VerificationToast.tsx:60:    const timer = setTimeout(onDismiss, 4000);
.\frontend\src\components\dashboard\VerificationToast.tsx:61:    return () => clearTimeout(timer);
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:2884:    "node_modules/@types/d3-timer": {
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:2886:      "resolved": "https://registry.npmjs.org/@types/d3-timer/-/d3-timer-3.0.2.tgz",
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:3736:    "node_modules/d3-timer": {
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:3738:      "resolved": "https://registry.npmjs.org/d3-timer/-/d3-timer-3.0.1.tgz",
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:6081:        "@types/d3-timer": "^3.0.0",
.\artifacts\runtime_preflight\2025-12-24_7650d094\package-lock.json:6088:        "d3-timer": "^3.0.1"
.\artifacts_vt_run3\phase-VALUE_02-evidence\backend\validation\evidence\privacy\pii_middleware_implemented.txt:23:- Periodic batch scanning
.\backend\tests\test_b051_celery_foundation.py:152:            time.sleep(2)
.\backend\tests\test_b051_celery_foundation.py:251:        time.sleep(1)
.\backend\tests\test_b0542_refresh_executor.py:37:        await asyncio.sleep(0.25)
```

### 7) Database scheduler search

Command:

```
rg -n "django-celery-beat|PeriodicTask|DatabaseScheduler|redbeat|celerybeat-schedule" -S --glob "!**/.git/**" --glob "!**/node_modules/**" .
```

Output:

```
.\B0544_tmp\cmd3.txt:1:.\B0544_tmp\cmd1.txt:2:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:3:.\B0544_tmp\cmd1.txt:5:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:5:.\B0544_tmp\cmd1.txt:12:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:7:.\B0544_tmp\cmd1.txt:15:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:9:.\B0544_tmp\cmd1.txt:20:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:11:.\B0544_tmp\cmd1.txt:23:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:14:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:16:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:19:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:21:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:24:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd3.txt:35:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:2:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:5:.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:12:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:15:.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:20:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\B0544_tmp\cmd1.txt:23:.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\2b0236c802b0017a50c93903c330e23d49078013\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\c7abcf220dc96f0029baa701341b1e6def10cbb5\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CONCURRENCY_SNAPSHOT.json:47:      "beat_schedule_filename": "celerybeat-schedule",
.\docs\validation\runtime\R6_context_gathering\540b1eab47622080a2d4447e674af8d7b3c6b0b6\R6_CELERY_INSPECT_CONF.json:37:    "beat_schedule_filename": "celerybeat-schedule",
```

### 8) R6 fuse config search

Command:

```
rg -n "task_time_limit|task_soft_time_limit|max_tasks_per_child|prefetch|acks_late|reject_on_worker_lost|task_routes|task_default_queue" -S backend/app
```

Output:

```
backend/app\celery_app.py:147:        task_acks_late=settings.CELERY_TASK_ACKS_LATE,
backend/app\celery_app.py:148:        task_reject_on_worker_lost=settings.CELERY_TASK_REJECT_ON_WORKER_LOST,
backend/app\celery_app.py:150:        worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
backend/app\celery_app.py:151:        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT_S,
backend/app\celery_app.py:152:        task_time_limit=settings.CELERY_TASK_TIME_LIMIT_S,
backend/app\celery_app.py:153:        worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
backend/app\celery_app.py:180:        task_routes={
backend/app\celery_app.py:189:        task_default_queue='housekeeping',
backend/app\core\config.py:62:    CELERY_TASK_ACKS_LATE: bool = Field(
backend/app\core\config.py:66:    CELERY_TASK_REJECT_ON_WORKER_LOST: bool = Field(
backend/app\core\config.py:74:    CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(
backend/app\core\config.py:76:        description="Prefetch multiplier for worker (1 minimizes starvation and improves crash determinism).",
backend/app\core\config.py:78:    CELERY_TASK_SOFT_TIME_LIMIT_S: int = Field(
backend/app\core\config.py:82:    CELERY_TASK_TIME_LIMIT_S: int = Field(
backend/app\core\config.py:86:    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(
backend/app\core\config.py:177:    @field_validator("CELERY_WORKER_PREFETCH_MULTIPLIER")
backend/app\core\config.py:179:    def validate_celery_prefetch_multiplier(cls, value: int) -> int:
backend/app\core\config.py:181:            raise ValueError("CELERY_WORKER_PREFETCH_MULTIPLIER must be >= 1")
backend/app\core\config.py:184:    @field_validator("CELERY_TASK_SOFT_TIME_LIMIT_S", "CELERY_TASK_TIME_LIMIT_S")
backend/app\core\config.py:186:    def validate_celery_task_time_limits(cls, value: int, info) -> int:
backend/app\core\config.py:191:    @field_validator("CELERY_WORKER_MAX_TASKS_PER_CHILD", "CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB")
backend/app\tasks\r4_failure_semantics.py:111:    acks_late=False,
backend/app\tasks\r4_failure_semantics.py:166:    acks_late=True,
backend/app\tasks\r4_failure_semantics.py:255:@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.rls_cross_tenant_probe", acks_late=False)
backend/app\tasks\r4_failure_semantics.py:299:    acks_late=False,
backend/app\tasks\r4_failure_semantics.py:328:@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.sentinel_side_effect", acks_late=False)
backend/app\tasks\r4_failure_semantics.py:350:@celery_app.task(bind=True, name="app.tasks.r4_failure_semantics.privilege_probes", acks_late=False)
backend/app\tasks\r6_resource_governance.py:73:    acks_late=False,
backend/app\tasks\r6_resource_governance.py:89:            "task_time_limit": getattr(conf, "task_time_limit", None),
backend/app\tasks\r6_resource_governance.py:90:            "task_soft_time_limit": getattr(conf, "task_soft_time_limit", None),
backend/app\tasks\r6_resource_governance.py:91:            "task_acks_late": bool(getattr(conf, "task_acks_late", False)),
backend/app\tasks\r6_resource_governance.py:92:            "task_reject_on_worker_lost": bool(getattr(conf, "task_reject_on_worker_lost", False)),
backend/app\tasks\r6_resource_governance.py:96:            "worker_prefetch_multiplier": int(
backend/app\tasks\r6_resource_governance.py:97:                getattr(conf, "worker_prefetch_multiplier", 0) or 0
backend/app\tasks\r6_resource_governance.py:99:            "worker_max_tasks_per_child": getattr(conf, "worker_max_tasks_per_child", None),
backend/app\tasks\r6_resource_governance.py:106:        "task_default_queue": getattr(conf, "task_default_queue", None),
backend/app\tasks\r6_resource_governance.py:111:            "CELERYD_PREFETCH_MULTIPLIER": os.getenv("CELERYD_PREFETCH_MULTIPLIER"),
backend/app\tasks\r6_resource_governance.py:112:            "CELERYD_MAX_TASKS_PER_CHILD": os.getenv("CELERYD_MAX_TASKS_PER_CHILD"),
backend/app\tasks\r6_resource_governance.py:193:    name="app.tasks.r6_resource_governance.prefetch_short_task",
backend/app\tasks\r6_resource_governance.py:196:def prefetch_short_task(self, run_id: str, index: int) -> dict:
backend/app\tasks\r6_resource_governance.py:199:        f"r6_prefetch_short_start run_id={run_id} task_id={self.request.id} index={index}",
backend/app\tasks\r6_resource_governance.py:214:        f"r6_prefetch_short_end run_id={run_id} task_id={self.request.id} index={index}",
backend/app\tasks\r6_resource_governance.py:231:    name="app.tasks.r6_resource_governance.prefetch_long_task",
backend/app\tasks\r6_resource_governance.py:234:def prefetch_long_task(self, run_id: str, index: int, sleep_s: float = 2.0) -> dict:
backend/app\tasks\r6_resource_governance.py:237:        f"r6_prefetch_long_start run_id={run_id} task_id={self.request.id} index={index}",
backend/app\tasks\r6_resource_governance.py:252:        f"r6_prefetch_long_end run_id={run_id} task_id={self.request.id} index={index}",
```

## Split-brain risk check

No competing scheduler mechanism (cron/APScheduler/database scheduler) appears in code; only Celery Beat is present as the scheduling mechanism via backend/app/tasks/beat_schedule.py and celery_app.conf.beat_schedule. Beat entrypoints are found in the CI harness (scripts/ci/zero_drift_v3_2.sh) but not in Procfile/compose runtime. This suggests a split-brain risk is currently low in code, but runtime may be missing a beat process outside CI.

## Implementation readiness verdict

Context gathered ? safe to draft B0.5.4.4 implementation directive, with explicit note that beat is only invoked in CI and no runtime beat entrypoint is present in Procfile/compose.
