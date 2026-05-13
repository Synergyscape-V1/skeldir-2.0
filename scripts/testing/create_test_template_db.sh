#!/usr/bin/env bash
set -euo pipefail

ADMIN_DATABASE_URL="${ADMIN_DATABASE_URL:-postgresql://postgres:postgres@127.0.0.1:5432/postgres}"
TEMPLATE_DB="${TEMPLATE_DB:-skeldir_test_template}"
TEMPLATE_OWNER="${TEMPLATE_OWNER:-postgres}"
ARTIFACT_DIR="${M2_ARTIFACT_DIR:-artifacts/m2}"

mkdir -p "${ARTIFACT_DIR}"
start_epoch="$(date +%s)"

psql "${ADMIN_DATABASE_URL}" -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid)
  FROM pg_stat_activity
 WHERE datname = '${TEMPLATE_DB}'
   AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${TEMPLATE_DB};
CREATE DATABASE ${TEMPLATE_DB} OWNER ${TEMPLATE_OWNER};
SQL

template_url="${ADMIN_DATABASE_URL%/*}/${TEMPLATE_DB}"
MIGRATION_DATABASE_URL="${template_url}" DATABASE_URL="${template_url}" alembic upgrade head

psql "${ADMIN_DATABASE_URL}" -v ON_ERROR_STOP=1 <<SQL
UPDATE pg_database SET datistemplate = true, datallowconn = false WHERE datname = '${TEMPLATE_DB}';
SQL

duration="$(( $(date +%s) - start_epoch ))"
cat > "${ARTIFACT_DIR}/template_db_measurement.json" <<JSON
{"strategy":"postgres_template_database","template_db":"${TEMPLATE_DB}","duration_seconds":${duration}}
JSON
echo "M2 template DB ${TEMPLATE_DB} created in ${duration}s"
