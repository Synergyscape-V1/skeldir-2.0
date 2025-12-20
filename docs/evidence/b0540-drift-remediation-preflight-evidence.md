## Zero-Drift Closure v3.2 — Backend-Only Proof Pack (Single SHA)

Session metadata
- Timestamp: 2025-12-20T13:12:00-06:00 (local)
- Branch: b0540-zero-drift-v3-proofpack
- Commit under test: 4e1fd20d2cfc99b8daa3123d5bf660c515dbe2a6 (pre-final-clean commit; no frontend changes)
- Policy: P1-A enforced via `scripts/run_alembic.ps1` (MIGRATION_DATABASE_URL uses postgres superuser); runtime uses app_user
- DB targets: fresh `skeldir_zg_fresh`, existing `skeldir_zg_existing`

### ZG-1 (PASS) — Fresh DB migration determinism
- DB: skeldir_zg_fresh (created fresh)
- Role: postgres (MIGRATION_DATABASE_URL)
- Commands / outputs:
```
psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS skeldir_zg_fresh"
DROP DATABASE
psql -U postgres -h localhost -c "CREATE DATABASE skeldir_zg_fresh OWNER postgres"
CREATE DATABASE

$env:MIGRATION_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/skeldir_zg_fresh'
./scripts/run_alembic.ps1 upgrade head
INFO  [alembic.runtime.migration] Running upgrade  -> baseline, Schema Foundation Baseline—Pre-B0.3
...
INFO  [alembic.runtime.migration] Running upgrade 6c5d5f5534ef -> 202512191900, Set matview ownership to app_user for refresh permissions.

./scripts/run_alembic.ps1 current
202512191900 (head)
```

### ZG-2 (PASS) — Existing DB migration determinism (seed-before-upgrade)
- DB: skeldir_zg_existing
- Role: postgres (MIGRATION_DATABASE_URL)
- Commands / outputs:
```
psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS skeldir_zg_existing"
psql -U postgres -h localhost -c "CREATE DATABASE skeldir_zg_existing OWNER postgres"

$env:MIGRATION_DATABASE_URL='postgresql://postgres:postgres@localhost:5432/skeldir_zg_existing'
./scripts/run_alembic.ps1 upgrade 202511151400    # pre-idempotency revision
INFO ... Running upgrade baseline -> 202511151400 ...

# Seed at REV_SEED (202511151400)
psql -U postgres -d skeldir_zg_existing -c "INSERT INTO tenants (id, name, api_key_hash, notification_email) VALUES ('11111111-1111-1111-1111-111111111111','ZG Existing Tenant','hash','ops@example.com'); INSERT INTO attribution_events (id, tenant_id, occurred_at, session_id, revenue_cents, raw_payload) VALUES ('33333333-3333-3333-3333-333333333333','11111111-1111-1111-1111-111111111111','2025-01-01T00:00:00Z','22222222-2222-2222-2222-222222222222',12345,'{}');"
INSERT 0 1
INSERT 0 1

# Upgrade to head under P1-A
./scripts/run_alembic.ps1 upgrade head
INFO  [alembic.runtime.migration] Running upgrade 202511151400 -> 202511151410 ...
...
INFO  [alembic.runtime.migration] Running upgrade 6c5d5f5534ef -> 202512191900, Set matview ownership to app_user for refresh permissions.

# Validation: backfill applied (no NULLs)
psql -U postgres -d skeldir_zg_existing -c "SELECT id, idempotency_key, event_timestamp, conversion_value_cents FROM attribution_events;"
id                                      | idempotency_key                                                       | event_timestamp         | conversion_value_cents
33333333-3333-3333-3333-333333333333    | 11111111-1111-1111-1111-111111111111:id:33333333-3333-3333-3333-333333333333 | 2024-12-31 18:00:00-06 | 12345
```

### ZG-3 (PASS) — Matview inventory determinism (fresh DB)
- DB: skeldir_zg_fresh (app_user)
- Commands / outputs:
```
psql -U app_user -d skeldir_zg_fresh -c "SELECT matviewname FROM pg_matviews ORDER BY matviewname;"
mv_allocation_summary
mv_channel_performance
mv_daily_revenue_summary

cd backend; python - <<'PY'
from app.core.matview_registry import MATERIALIZED_VIEWS
print(MATERIALIZED_VIEWS)
PY
['mv_allocation_summary', 'mv_channel_performance', 'mv_daily_revenue_summary']
```

### ZG-4 (PASS) — Refresh viability as app_user (fresh + existing) with ownership proof
- DBs: skeldir_zg_fresh, skeldir_zg_existing
- Commands / outputs (app_user):
```
# Ownership on fresh
psql -U app_user -d skeldir_zg_fresh -c "SELECT relname, pg_get_userbyid(relowner) AS owner FROM pg_class WHERE relkind='m' AND relname LIKE 'mv_%' ORDER BY relname;"
mv_allocation_summary    | app_user
mv_channel_performance   | app_user
mv_daily_revenue_summary | app_user

# Unique indexes
psql -U app_user -d skeldir_zg_fresh -c "SELECT c.relname AS matview, i.relname AS index_name, idx.indisunique FROM pg_index idx JOIN pg_class i ON i.oid = idx.indexrelid JOIN pg_class c ON c.oid = idx.indrelid WHERE c.relkind='m' AND c.relname LIKE 'mv_%' ORDER BY c.relname;"
mv_allocation_summary    | idx_mv_allocation_summary_key       | t
mv_channel_performance   | idx_mv_channel_performance_unique   | t
mv_daily_revenue_summary | idx_mv_daily_revenue_summary_unique | t

# Refresh on fresh DB
psql -U app_user -d skeldir_zg_fresh -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary;"
REFRESH MATERIALIZED VIEW
REFRESH MATERIALIZED VIEW
REFRESH MATERIALIZED VIEW

# Refresh on existing DB (with tenant GUC set)
psql -U app_user -d skeldir_zg_existing -c "SET app.current_tenant_id='11111111-1111-1111-1111-111111111111'; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary;"
SET
REFRESH MATERIALIZED VIEW
REFRESH MATERIALIZED VIEW
REFRESH MATERIALIZED VIEW
```

### ZG-5 (PASS) — Beat is real (schedule load + dispatch)
- Schedule introspection (app_user, skeldir_zg_fresh):
```
cd backend; $env:DATABASE_URL=postgresql://app_user:app_user@localhost:5432/skeldir_zg_fresh
python - <<'PY'
from app.celery_app import celery_app
import json
print(json.dumps({
    'beat_schedule_loaded': bool(celery_app.conf.beat_schedule),
    'task_count': len(celery_app.conf.beat_schedule or {}),
    'tasks': {
        name: {'task': entry['task'], 'schedule': str(entry['schedule'])}
        for name, entry in (celery_app.conf.beat_schedule or {}).items()
    }
}, indent=2))
PY
{
  "beat_schedule_loaded": true,
  "task_count": 3,
  "tasks": {
    "refresh-matviews-every-5-min": {"task": "app.tasks.maintenance.refresh_all_matviews_global_legacy", "schedule": "300.0"},
    "pii-audit-scanner": {"task": "app.tasks.maintenance.scan_for_pii_contamination", "schedule": "<crontab: 0 4 * * * (m/h/dM/MY/d)>"},
    "enforce-data-retention": {"task": "app.tasks.maintenance.enforce_data_retention", "schedule": "<crontab: 0 3 * * * (m/h/dM/MY/d)>"}
  }
}
```
- Beat dispatch proof (app_user, skeldir_zg_fresh):
```
# Started beat via Start-Process (Windows) with log redirect
# Log: tmp/beat.err
[2025-12-20 12:51:21,493: INFO/MainProcess] beat: Starting...
[2025-12-20 12:51:21,656: INFO/MainProcess] Scheduler: Sending due task pii-audit-scanner (app.tasks.maintenance.scan_for_pii_contamination)
[2025-12-20 12:51:21,748: INFO/MainProcess] Scheduler: Sending due task enforce-data-retention (app.tasks.maintenance.enforce_data_retention)
[2025-12-20 12:51:21,752: INFO/MainProcess] Scheduler: Sending due task refresh-matviews-every-5-min (app.tasks.maintenance.refresh_all_matviews_global_legacy)
```

### ZG-6 (PASS) — Serialization enforced in refresh path
- DB: skeldir_zg_fresh (app_user)
- Command / output (holds advisory lock, then executes real refresh path twice):
```
cd backend; $env:DATABASE_URL=postgresql://app_user:app_user@localhost:5432/skeldir_zg_fresh
python - <<'PY'
import asyncio, logging
from app.celery_app import celery_app
from app.tasks import maintenance as m
from app.core.pg_locks import try_acquire_refresh_lock, release_refresh_lock
from app.db.session import engine
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
async def hold_lock(duration):
    async with engine.begin() as conn:
        acquired = await try_acquire_refresh_lock(conn, 'mv_allocation_summary', None)
        print(f"lock_holder_acquired={acquired}")
        await asyncio.sleep(duration)
        await release_refresh_lock(conn, 'mv_allocation_summary', None)
        print("lock_holder_released")
async def attempt(label):
    result = await m._refresh_view('mv_allocation_summary', label, None)
    print(f"{label}: {result}")
    return result
async def main():
    lock_task = asyncio.create_task(hold_lock(2.0))
    await asyncio.sleep(0.2)
    skip_result = await attempt('task-skip')
    await lock_task
    success_result = await attempt('task-success')
    print({'skip': skip_result, 'success': success_result})
asyncio.run(main())
PY
INFO refresh_lock_acquired
INFO refresh_lock_already_held
INFO matview_refresh_skipped_already_running
INFO refresh_lock_released
INFO refresh_lock_acquired
INFO matview_refreshed
INFO refresh_lock_released
lock_holder_acquired=True
task-skip: skipped_already_running
lock_holder_released
task-success: success
{'skip': 'skipped_already_running', 'success': 'success'}
```

### ZG-7 (PASS) — Worker ingestion write-block regression proof
- DB: skeldir_zg_fresh
- Role: postgres (to show trigger blocks even superuser when worker context set)
- Command / output:
```
psql -h localhost -U postgres -d skeldir_zg_fresh -c "SET app.execution_context='worker'; SET app.current_tenant_id='11111111-1111-1111-1111-111111111111'; INSERT INTO attribution_events (id, tenant_id, occurred_at, session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel, event_timestamp, conversion_value_cents) VALUES ('88888888-8888-8888-8888-888888888888','11111111-1111-1111-1111-111111111111','2025-01-01T00:00:00Z','99999999-9999-9999-9999-999999999999',0,'{}','dup-worker-block','purchase','direct','2025-01-01T00:00:00Z',100);"
SET
ERROR:  ingestion tables are read-only in worker context (table=attribution_events)
CONTEXT:  PL/pgSQL function fn_block_worker_ingestion_mutation() line 4 at RAISESET
```

### Gate Ledger (v3.2)
| Gate | Status | Evidence |
| --- | --- | --- |
| ZG-0.2 | PENDING (final clean-tree capture required) | git status / diff outputs to be captured after final commit (backend-only scope, no frontend) |
| ZG-1 | PASS | Fresh DB `skeldir_zg_fresh` -> head `202512191900` under P1-A |
| ZG-2 | PASS | Existing DB `skeldir_zg_existing` seeded at 202511151400 -> head with backfill validated |
| ZG-3 | PASS | Matview inventory = registry (3 views) |
| ZG-4 | PASS | app_user refresh succeeds on fresh + existing; ownership + unique indexes proven |
| ZG-5 | PASS | Beat schedule loaded; beat log shows due-task dispatch for refresh + daily jobs |
| ZG-6 | PASS | Real refresh path uses advisory lock; concurrent run skips while lock held |
| ZG-7 | PASS | Worker-context ingestion mutation blocked by trigger |
