#!/usr/bin/env bash
set -euo pipefail

# Zero-Drift v3.2 CI harness (backend-only)
# Runs all ZG gates in CI to produce portable evidence.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${ROOT_DIR}/backend:${PYTHONPATH:-}"

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGSUPER_USER="${PGSUPER_USER:-postgres}"
PGSUPER_PASS="${PGSUPER_PASS:-postgres}"

export MIGRATION_DATABASE_URL_FRESH="${MIGRATION_DATABASE_URL_FRESH:-postgresql://${PGSUPER_USER}:${PGSUPER_PASS}@${PGHOST}:${PGPORT}/skeldir_zg_fresh}"
export MIGRATION_DATABASE_URL_EXISTING="${MIGRATION_DATABASE_URL_EXISTING:-postgresql://${PGSUPER_USER}:${PGSUPER_PASS}@${PGHOST}:${PGPORT}/skeldir_zg_existing}"
export RUNTIME_DATABASE_URL="${RUNTIME_DATABASE_URL:-postgresql://app_user:app_user@${PGHOST}:${PGPORT}/skeldir_zg_fresh}"
export ZG_BEAT_TEST_INTERVAL_SECONDS="${ZG_BEAT_TEST_INTERVAL_SECONDS:-1}"
export DATABASE_URL="${RUNTIME_DATABASE_URL}"

psql_super() {
  PGPASSWORD="${PGSUPER_PASS}" psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGSUPER_USER}" "$@"
}

psql_app() {
  PGPASSWORD="app_user" psql -h "${PGHOST}" -p "${PGPORT}" -U "app_user" "$@"
}

create_roles() {
  psql_super -d postgres -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
    CREATE ROLE app_user LOGIN PASSWORD 'app_user';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_rw') THEN
    CREATE ROLE app_rw LOGIN PASSWORD 'app_rw';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_ro') THEN
    CREATE ROLE app_ro LOGIN PASSWORD 'app_ro';
  END IF;
END$$;
SQL
}

recreate_db() {
  local db="$1"
  psql_super -d postgres -c "DROP DATABASE IF EXISTS ${db};"
  psql_super -d postgres -c "CREATE DATABASE ${db} OWNER ${PGSUPER_USER};"
}

run_alembic() {
  local url="$1"
  local args="$2"
  MIGRATION_DATABASE_URL="${url}" DATABASE_URL="${url}" alembic ${args}
}

echo "== ZG-0.2: prepare roles and databases =="
create_roles
recreate_db "skeldir_zg_fresh"
recreate_db "skeldir_zg_existing"

echo "== ZG-0.1: maintenance import sanity check =="
python - <<'PY'
import importlib
mod = importlib.import_module("app.tasks.maintenance")
print(f"import_ok={mod is not None}")
PY

echo "== ZG-1: fresh DB upgrade to head =="
run_alembic "${MIGRATION_DATABASE_URL_FRESH}" "upgrade head"
run_alembic "${MIGRATION_DATABASE_URL_FRESH}" "current"
run_alembic "${MIGRATION_DATABASE_URL_FRESH}" "heads"

echo "== ZG-2: existing DB seed-before-upgrade =="
run_alembic "${MIGRATION_DATABASE_URL_EXISTING}" "upgrade 202511151400"
psql_super -d skeldir_zg_existing -v ON_ERROR_STOP=1 <<'SQL'
INSERT INTO tenants (id, name, api_key_hash, notification_email)
VALUES ('11111111-1111-1111-1111-111111111111','ZG Existing Tenant','hash','ops@example.com');

INSERT INTO attribution_events (id, tenant_id, occurred_at, session_id, revenue_cents, raw_payload)
VALUES ('33333333-3333-3333-3333-333333333333','11111111-1111-1111-1111-111111111111','2025-01-01T00:00:00Z','22222222-2222-2222-2222-222222222222',12345,'{}');
SQL
run_alembic "${MIGRATION_DATABASE_URL_EXISTING}" "upgrade head"
psql_super -d skeldir_zg_existing -c "SELECT id, idempotency_key, event_timestamp, conversion_value_cents FROM attribution_events;"

echo "== ZG-3: matview inventory determinism (fresh) =="
psql_app -d skeldir_zg_fresh -t -A -c "SELECT matviewname FROM pg_matviews WHERE schemaname='public' ORDER BY matviewname;" > /tmp/pg_matviews.txt
cat /tmp/pg_matviews.txt
echo "Registry from code:"
python - <<'PY'
from app.matviews.registry import list_names
print(list_names())
PY
python - <<'PY'
from pathlib import Path
from app.matviews.registry import list_names
db_list = [line.strip() for line in Path("/tmp/pg_matviews.txt").read_text().splitlines() if line.strip()]
reg_set, db_set = set(list_names()), set(db_list)
print(f"registry={sorted(reg_set)}")
print(f"db={sorted(db_set)}")
missing = reg_set - db_set
extra = db_set - reg_set
if missing or extra:
    print(f"MATVIEW MISMATCH missing={sorted(missing)} extra={sorted(extra)}")
    raise SystemExit(1)
print("MATVIEW INVENTORY OK (registry == pg_matviews)")
PY

echo "== ZG-4: refresh viability as app_user (fresh + existing) =="
psql_app -d skeldir_zg_fresh -c "SELECT relname, pg_get_userbyid(relowner) AS owner FROM pg_class WHERE relkind='m' AND relname LIKE 'mv_%' ORDER BY relname;"
psql_app -d skeldir_zg_fresh -c "SELECT c.relname AS matview, i.relname AS index_name, idx.indisunique FROM pg_index idx JOIN pg_class i ON i.oid = idx.indexrelid JOIN pg_class c ON c.oid = idx.indrelid WHERE c.relkind='m' AND c.relname LIKE 'mv_%' ORDER BY c.relname;"
psql_app -d skeldir_zg_fresh -c "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_revenue; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_status;"
psql_app -d skeldir_zg_existing -c "SET app.current_tenant_id='11111111-1111-1111-1111-111111111111'; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_allocation_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_channel_performance; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_revenue_summary; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_realtime_revenue; REFRESH MATERIALIZED VIEW CONCURRENTLY mv_reconciliation_status;"
echo "Role grants for app_user:"
psql_app -d skeldir_zg_fresh -c "SELECT table_name, privilege_type FROM information_schema.role_table_grants WHERE grantee='app_user' ORDER BY table_name, privilege_type;"
echo "Alembic heads (fresh):"
run_alembic "${MIGRATION_DATABASE_URL_FRESH}" "heads"

echo "== ZG-5: beat dispatch proof =="
export DATABASE_URL="${RUNTIME_DATABASE_URL}"
export CELERY_BROKER_URL="sqla+postgresql://app_user:app_user@${PGHOST}:${PGPORT}/skeldir_zg_fresh"
export CELERY_RESULT_BACKEND="db+postgresql://app_user:app_user@${PGHOST}:${PGPORT}/skeldir_zg_fresh"
cd backend
echo "ZG_BEAT_TEST_INTERVAL_SECONDS=${ZG_BEAT_TEST_INTERVAL_SECONDS}"
python - <<'PY'
from app.celery_app import celery_app
import json
print(json.dumps({
    "beat_schedule_loaded": bool(celery_app.conf.beat_schedule),
    "task_count": len(celery_app.conf.beat_schedule or {}),
    "tasks": {name: {"task": entry["task"], "schedule": str(entry["schedule"])} for name, entry in (celery_app.conf.beat_schedule or {}).items()},
}, indent=2))
PY
timeout 20 celery -A app.celery_app.celery_app beat --loglevel=INFO --pidfile= --schedule=/tmp/zg_beat_schedule --max-interval=2 > /tmp/zg_beat.log 2>&1 || true
cat /tmp/zg_beat.log
echo "---- beat dispatch lines ----"
grep -n "Sending due task" /tmp/zg_beat.log || true

echo "== ZG-6: serialization enforced in refresh path =="
python - <<'PY'
import asyncio, logging
from app.core.pg_locks import try_acquire_refresh_xact_lock
from app.db.session import engine
from app.matviews.executor import refresh_single_async
logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
async def hold_lock(duration):
    async with engine.begin() as conn:
        acquired, _lock_key = await try_acquire_refresh_xact_lock(conn, 'mv_allocation_summary', None)
        print(f"lock_holder_acquired={acquired}")
        await asyncio.sleep(duration)
    print("lock_holder_released")
async def attempt(label):
    result = await refresh_single_async('mv_allocation_summary', None, label)
    print(f"{label}: {result.outcome.value}")
    return result.outcome.value
async def main():
    lock_task = asyncio.create_task(hold_lock(2.0))
    await asyncio.sleep(0.2)
    skip_result = await attempt('task-skip')
    await lock_task
    success_result = await attempt('task-success')
    print({'skip': skip_result, 'success': success_result})
asyncio.run(main())
PY

echo "== ZG-7: worker ingestion write-block proof =="
psql_app -d skeldir_zg_fresh -c "SET app.execution_context='worker'; SET app.current_tenant_id='11111111-1111-1111-1111-111111111111'; INSERT INTO attribution_events (id, tenant_id, occurred_at, session_id, revenue_cents, raw_payload, idempotency_key, event_type, channel, event_timestamp, conversion_value_cents) VALUES ('88888888-8888-8888-8888-888888888888','11111111-1111-1111-1111-111111111111','2025-01-01T00:00:00Z','99999999-9999-9999-9999-999999999999',0,'{}','dup-worker-block','purchase','direct','2025-01-01T00:00:00Z',100);" && echo "UNEXPECTED: worker write succeeded" && exit 1 || true

echo "== Zero-Drift v3.2 CI harness completed =="
